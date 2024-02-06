# P.S.~Mandrik, IHEP, https://github.com/pmandrik

import os
import sys
import json
import flask
import logging
import requests
import dqmsquare_cfg
from flask import Flask, render_template, redirect
from dotenv import load_dotenv
from db import DQM2MirrorDB
from decorators import check_login, check_auth
from custom_logger import set_log_handler, custom_formatter

load_dotenv()  # Load environmental variables from .env file, if present

log = logging.getLogger(__name__)

log.info("start_server() call ... ")


def create_app(cfg):
    app = Flask(
        __name__, static_url_path=os.path.join("/", cfg["SERVER_URL_PREFIX"], "static")
    )
    set_log_handler(
        logger=log,
        path=cfg["SERVER_LOG_PATH"],
        interval=cfg["LOGGER_ROTATION_TIME"],
        nlogs=cfg["LOGGER_MAX_N_LOG_FILES"],
        enable_debug=cfg["SERVER_DEBUG"],
    )

    log.info(f"Configured logger for server, level={log.level}")
    cr_usernames = {}
    # Read in CR credentials from env var
    try:
        username, password = os.environ.get("DQM_CR_USERNAMES").split(":")
        cr_usernames = {username: password}
    except Exception as e:
        log.error(
            f"No Control Room credentials configured! Please set the DQM_CR_USERNAMES env var: {repr}"
        )
        raise e

    # Path to the Cinder mount, for permanent storage
    SERVER_DATA_PATH = cfg["SERVER_DATA_PATH"]

    # global variables and auth cookies
    CMSWEB_FRONTEND_PROXY_URL = cfg["CMSWEB_FRONTEND_PROXY_URL"]
    CERT_PATH = [cfg["SERVER_GRID_CERT_PATH"], cfg["SERVER_GRID_KEY_PATH"]]

    cookies = {
        str(cfg["FFF_SECRET_NAME"]): os.environ.get(
            "DQM_FFF_SECRET", "changeme"
        ).strip()
    }

    db_playback = DQM2MirrorDB(log, cfg["DB_PLAYBACK_URI"], server=True)
    db_production = DQM2MirrorDB(log, cfg["DB_PRODUCTION_URI"], server=True)
    databases = {
        "playback": db_playback,
        "production": db_production,
    }

    log.info(
        "\n\n\n =============================================================================== "
    )
    log.info(
        "\n\n\n dqmsquare_server ============================================================== "
    )

    ### DQM^2 Mirror ###
    @app.route(os.path.join("/", cfg["SERVER_URL_PREFIX"] + "/"))
    def greet():
        return render_template(
            "runs.html",
            PREFIX=os.path.join("/", cfg["SERVER_URL_PREFIX"] + "/"),
            FRONTEND_API_QUERY_INTERVAL=cfg["FRONTEND_API_QUERY_INTERVAL"],
            VERSION=cfg["VERSION"],
            TIMEZONE=cfg["TIMEZONE"],
        )

    @app.route(os.path.join("/", cfg["SERVER_URL_PREFIX"], "static/<path:filename>"))
    def get_static(filename):
        """
        Endpoint that returns files from the static directory.
        """
        return flask.send_from_directory("static", filename)

    @app.route(
        os.path.join(
            "/", cfg["SERVER_URL_PREFIX"], SERVER_DATA_PATH, "tmp/<path:filename>"
        )
    )
    def get_tmp(filename):
        """
        Route that fetches file from the tmp directory.
        """
        # TODO: remove if, make paths easier to handle
        return flask.send_from_directory(
            (
                os.path.join("/", SERVER_DATA_PATH, "tmp")
                if cfg["ENV"] != "development"
                else "tmp"
            ),
            filename,
        )

    @app.route(
        os.path.join(
            "/", cfg["SERVER_URL_PREFIX"], SERVER_DATA_PATH, "log/<path:filename>"
        )
    )
    def get_log(filename):
        """
        Route to directly access grabber and server log files.
        """
        # TODO: remove if, make paths easier to handle
        content = flask.send_from_directory(
            (
                os.path.join("/", SERVER_DATA_PATH, "log")
                if cfg["ENV"] != "development"
                else "log"
            ),
            filename,
        )
        return content

    @app.route(
        os.path.join(
            "/",
            cfg["SERVER_URL_PREFIX"],
            "api",
        )
    )
    def dqm2_api():
        """
        Get data from DQM^2 Mirror's Databases.
        """
        log.info(flask.request.base_url)
        what = flask.request.args.get("what")

        if what == "get_run":
            run = flask.request.args.get("run", default=0)
            db_name = flask.request.args.get("db", default="")
            db_ = databases.get(db_name, db_playback)
            run_data = db_.get_mirror_data(run)
            runs_around = db_.get_runs_around(run)
            return json.dumps([runs_around, run_data])
        if what == "get_graph":
            run = flask.request.args.get("run", default=0)
            db_name = flask.request.args.get("db", default="")
            db_ = databases.get(db_name, db_playback)
            graph_data = db_.get_graphs_data(run)
            return json.dumps(graph_data)
        if what == "get_runs":
            run_from = flask.request.args.get("from", default=0)
            run_to = flask.request.args.get("to", default=0)
            bad_only = flask.request.args.get("bad_only", default=0)
            with_ls_only = flask.request.args.get("ls", default=0)
            db_name = flask.request.args.get("db", default="")
            db_ = databases.get(db_name, db_playback)
            answer = db_.get_timeline_data(
                min(run_from, run_to),
                max(run_from, run_to),
                int(bad_only),
                int(with_ls_only),
            )
            return json.dumps(answer)
        if what == "get_clients":
            run_from = flask.request.args.get("from", default=0)
            run_to = flask.request.args.get("to", default=0)
            db_name = flask.request.args.get("db", default="")
            db_ = databases.get(db_name, db_playback)
            answer = db_.get_clients(run_from, run_to)
            return json.dumps(answer)
        if what == "get_info":
            db_name = flask.request.args.get("db", default="")
            db_ = databases.get(db_name, db_playback)
            answer = db_.get_info()
            return json.dumps(answer)
        if what == "get_logs":
            client_id = flask.request.args.get("id", default=0)
            db_name = flask.request.args.get("db", default="")
            db_ = databases.get(db_name, db_playback)
            answer = db_.get_logs(client_id)
            a1 = "".join(eval(answer[0]))
            a2 = "".join(eval(answer[1]))
            return "<plaintext>" + a1 + "\n ... \n\n" + a2

    ### TIMELINE ###
    @app.route(os.path.join("/", cfg["SERVER_URL_PREFIX"], "timeline/"))
    def get_timeline():
        return render_template(
            "timeline.html",
            PREFIX=os.path.join("/", cfg["SERVER_URL_PREFIX"] + "/"),
            FRONTEND_API_QUERY_INTERVAL=cfg["FRONTEND_API_QUERY_INTERVAL"],
            VERSION=cfg["VERSION"],
        )

    ### CR ###
    @app.route(
        os.path.join("/", cfg["SERVER_URL_PREFIX"], "cr", "login/"), methods=["GET"]
    )
    def login():
        log.info("In login view")
        return render_template(
            "login.html",
            PREFIX=os.path.join(
                "/",
                cfg["SERVER_URL_PREFIX"] + "/",
            ),
            VERSION=cfg["VERSION"],
        )

    @app.route(
        os.path.join("/", cfg["SERVER_URL_PREFIX"], "cr", "login/"), methods=["POST"]
    )
    def do_login():
        username = flask.request.form.get("username")
        password = flask.request.form.get("password")
        login_successful = check_login(
            username=username, password=password, cr_usernames=cr_usernames
        )
        log.info(f"login successful: {login_successful}")
        if login_successful:
            resp = redirect(flask.url_for("get_cr"))
            resp.set_cookie(
                "dqmsquare-mirror-cr-account",
                username,
                path="/",
                max_age=24 * 60 * 60,
                httponly=True,
            )
            return resp
        else:
            return "<p>Login failed.</p>"

    @app.route(os.path.join("/", cfg["SERVER_URL_PREFIX"], "cr/logout/"))
    def do_logout():
        log.info("logout")
        resp = flask.make_response(redirect(flask.url_for("greet")))

        resp.set_cookie(
            "dqmsquare-mirror-cr-account", "random", path="/", httponly=True
        )
        return resp

    @app.route(os.path.join("/", cfg["SERVER_URL_PREFIX"], "cr/"))
    @check_auth(cr_usernames=cr_usernames)
    def get_cr():
        return render_template(
            "cr.html",
            PREFIX=os.path.join(
                "/",
                cfg["SERVER_URL_PREFIX"] + "/",
            ),
            VERSION=cfg["VERSION"],
        )

    # DQM & FFF & HLTD
    @app.route(os.path.join("/", cfg["SERVER_URL_PREFIX"], "cr", "exe"))
    @check_auth(redirect=False, cr_usernames=cr_usernames)
    def cr_exe():
        log.info(flask.request.base_url)
        what = flask.request.args.get("what")

        ### get data from DQM^2 Mirror
        if what == "get_simulator_run_keys":
            try:
                answer = str(cfg["SERVER_SIMULATOR_RUN_KEYS"].split(","))
                return answer
            except Exception as e:
                log.warning(e)
                return repr(e), 400

        # using exe API
        # initial request
        url = (
            os.path.join(CMSWEB_FRONTEND_PROXY_URL, "cr/exe?")
            + flask.request.query_string.decode()
        )
        answer = None
        try:
            r = requests.get(url, cert=CERT_PATH, verify=False, cookies=cookies)
            dqm2_answer = r.content
        except Exception as e:
            log.warning("cr_exe() initial request : " + repr(e))
            return repr(e), 400

        if what in ["get_production_runs"]:
            return ",".join(
                [
                    str(i)
                    + str(i)
                    + str(i)
                    + str(i)
                    + str(i)
                    + str(i)
                    + "_"
                    + str(i)
                    + str(i)
                    + str(i)
                    for i in range(10)
                ]
            )
        if what in ["copy_production_runs"]:
            return "Ok"

        if what in [
            "get_dqm_machines",
            "get_simulator_config",
            "get_hltd_versions",
            "get_fff_versions",
            "restart_hltd",
            "restart_fff",
            "get_simulator_runs",
            "start_playback_run",
            "get_dqm_clients",
            "change_dqm_client",
            "get_cmssw_info",
        ]:
            # change format to be printable
            answer = dqm2_answer
            try:
                format = flask.request.args.get("format", default=None)
                if (what in ["get_hltd_versions", "get_fff_versions"]) and format:
                    answer = ""
                    data = json.loads(dqm2_answer)
                    for key, lst in sorted(data.items()):
                        answer += "<strong>" + key + "</strong>\n"
                        for host, version in sorted(lst.items()):
                            answer += host + " " + version

                if what == "get_dqm_machines" and format:
                    answer = ""
                    data = json.loads(dqm2_answer)
                    for key, lst in sorted(data.items()):
                        answer += "<strong>" + key + "</strong> " + str(lst) + "\n"

                if what == "get_simulator_config":
                    answer = json.loads(dqm2_answer)

            except Exception as e:
                log.warning("cr_exe() change format to be printable : " + repr(e))
                return repr(e), 400

            return answer

        ### get logs data in new window tabs from DQM^2
        if what in ["get_fff_logs", "get_hltd_logs"]:
            data = ["No data from fff available ..."]

            try:
                data = json.loads(dqm2_answer)
            except Exception as e:
                log.warning(
                    "cr_exe() : can't json.loads from DQM^2 data " + dqm2_answer
                )
                log.warning(repr(e))
                return repr(e), 400

            file_urls = []
            for item in data:
                if not len(item):
                    continue
                try:
                    # Dirty machete code for now. The problem is that the SERVER_DATA_PATH is also used for a
                    # file path and a URL. This means that for os.path.join to work, the path must NOT have a
                    # leading "/" (see: https://docs.python.org/3/library/os.path.html#os.path.join).
                    # This means that we do not know explicitly if the path is relative or absolute.
                    # For development, we store the tmp file locally, so we consider the path relative.
                    # For non-development, the SERVER_DATA_PATH is considered an absolute path.
                    fname = dqmsquare_cfg.dump_tmp_file(
                        data=item,
                        path=(
                            os.path.join(SERVER_DATA_PATH, "tmp")
                            if cfg["ENV"] == "development"
                            else os.path.join("/", SERVER_DATA_PATH, "tmp")
                        ),
                        prefix=what,
                        postfix=".txt",
                    )
                except Exception as e:
                    log.warning(
                        "cr_exe() : error in dqmsquare_cfg.dump_tmp_file for file:"
                    )
                    log.warning(repr(e))
                    continue
                file_urls += [
                    os.path.join(
                        "/", cfg["SERVER_URL_PREFIX"], SERVER_DATA_PATH, "tmp", fname
                    )
                ]
            log.debug(f"tmp Filenames: {file_urls}")
            return str(file_urls)

        # default answer
        log.warning(f"cr_exe() : No actions defined for request: '{repr(what)}'")
        return "No actions defined for that request"

    return app


if __name__ == "__main__":
    # Local development entrypoint
    cfg = dqmsquare_cfg.load_cfg()
    app = create_app(cfg=cfg)
    app.run(
        host=str(cfg["SERVER_HOST"]),
        port=int(cfg["SERVER_PORT"]),
        debug=bool(cfg["SERVER_DEBUG"]),
    )
