# P.S.~Mandrik, IHEP, https://github.com/pmandrik

import os
import json
import flask
import logging
import requests
import dqmsquare_cfg
from flask import Flask, render_template, redirect
from dotenv import load_dotenv
from db import DQM2MirrorDB
from decorators import check_login, check_auth
from custom_logger import set_log_handler
from datetime import datetime, date

load_dotenv()  # Load environmental variables from .env file, if present

log = logging.getLogger(__name__)

log.info("start_server() call ... ")
VALID_DATABASE_OPTIONS = ["playback", "production"]


def json_serializer(obj):
    """
    JSON serializer for objects not serializable by default json code
    https://stackoverflow.com/a/22238613/6562491
    """

    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    raise TypeError("Type %s not serializable" % type(obj))


def create_app(cfg: dict):
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
        username, password = os.environ.get("DQM_CR_USERNAMES", "").split(":")
        cr_usernames = {username: password}
    except Exception as e:
        log.error(
            "No Control Room credentials configured! Please set the DQM_CR_USERNAMES env var",
            exc_info=True,
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

    db_playback = DQM2MirrorDB(
        log=log,
        host=cfg.get("DB_PLAYBACK_HOST"),
        port=cfg.get("DB_PLAYBACK_PORT"),
        username=cfg.get("DB_PLAYBACK_USERNAME"),
        password=cfg.get("DB_PLAYBACK_PASSWORD"),
        db_name=cfg.get("DB_PLAYBACK_NAME"),
        server=True,
    )
    db_production = DQM2MirrorDB(
        log=log,
        host=cfg.get("DB_PRODUCTION_HOST"),
        port=cfg.get("DB_PRODUCTION_PORT"),
        username=cfg.get("DB_PRODUCTION_USERNAME"),
        password=cfg.get("DB_PRODUCTION_PASSWORD"),
        db_name=cfg.get("DB_PRODUCTION_NAME"),
        server=True,
    )
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
            "index.html",
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
            "/",
            cfg["SERVER_URL_PREFIX"],
            SERVER_DATA_PATH,
            "comparison_reports/<path:id>",
        )
    )
    def get_comparison_report(id: str):
        """
        Route that fetches file from the tmp directory.
        """
        return flask.send_from_directory(
            (cfg["CMSSW_COMPARISON_REPORTS_STORE_PATH"].joinpath(id)),
            "dqm-histo-comparison-summary.html",
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
            "/", cfg["SERVER_URL_PREFIX"], "api", "get_cmssw_comparison_reports"
        )
    )
    def get_cmssw_comparison_reports():
        id = flask.request.args.get("id", type=str, default="")
        type = flask.request.args.get("type", type=str)
        page = flask.request.args.get("page", type=int, default=1)
        items_per_page = flask.request.args.get("items_per_page", type=int, default=10)
        base_cmssw_version = flask.request.args.get(
            "base_cmssw_version", type=str, default=""
        )
        base_prs = flask.request.args.get("base_prs", type=list, default=[])
        log.debug(base_prs)
        comp_cmssw_version = flask.request.args.get(
            "comp_cmssw_version", type=str, default=""
        )
        if not type:
            return json.dumps(
                db_playback.get_cmssw_comparison_reports(
                    items_per_page=items_per_page,
                    page=page,
                    id=id,
                    base_cmssw_version=base_cmssw_version,
                    comp_cmssw_version=comp_cmssw_version,
                ),
                default=json_serializer,
            )
        elif type == "html":
            return flask.redirect(flask.url_for("get_comparison_report", id=id))

    @app.route(os.path.join("/", cfg["SERVER_URL_PREFIX"], "api", "get_graph"))
    def get_graph():
        try:
            run = int(flask.request.args.get("run", type=int))
        except (ValueError, TypeError):
            return "run must be an integer", 400
        db_name = flask.request.args.get("db", type=str)
        if db_name not in VALID_DATABASE_OPTIONS:
            return f"db must be one of {VALID_DATABASE_OPTIONS}", 400
        db_ = databases.get(db_name, db_playback)
        graph_data = db_.get_graphs(run)
        return json.dumps(graph_data)

    @app.route(os.path.join("/", cfg["SERVER_URL_PREFIX"], "api", "get_run"))
    def get_run():
        try:
            run = int(flask.request.args.get("run", type=int))
        except (ValueError, TypeError):
            return "run must be an integer", 400
        db_name = flask.request.args.get("db", type=str)
        if db_name not in VALID_DATABASE_OPTIONS:
            return f"db must be one of {VALID_DATABASE_OPTIONS}", 400
        db_ = databases.get(db_name, db_playback)
        run_data = db_.get_mirror_data(run)
        runs_around = db_.get_runs_around(run)
        return json.dumps([runs_around, run_data])

    @app.route(os.path.join("/", cfg["SERVER_URL_PREFIX"], "api", "get_runs"))
    def get_runs():
        try:
            run_from = int(flask.request.args.get("from", type=int))
            run_to = int(flask.request.args.get("to", type=int))
            bad_only = bool(flask.request.args.get("bad_only", type=int))
            with_ls_only = bool(flask.request.args.get("ls", type=int))
        except (ValueError, TypeError):
            return ("to, from, bad_only and ls must be integers", 400)
        db_name = flask.request.args.get("db", default="", type=str)
        if db_name not in VALID_DATABASE_OPTIONS:
            return f"db must be one of {VALID_DATABASE_OPTIONS}", 400
        db_ = databases.get(db_name, db_playback)
        answer = db_.get_timeline_data(
            min(run_from, run_to),
            max(run_from, run_to),
            bad_only,
            with_ls_only,
        )
        return json.dumps(answer)

    @app.route(os.path.join("/", cfg["SERVER_URL_PREFIX"], "api", "get_info"))
    def get_cliget_infoents():
        db_name = flask.request.args.get("db", type=str)
        if db_name not in VALID_DATABASE_OPTIONS:
            return f"db must be one of {VALID_DATABASE_OPTIONS}", 400
        db_ = databases.get(db_name, db_playback)
        answer = db_.get_info()
        return json.dumps(answer)

    @app.route(os.path.join("/", cfg["SERVER_URL_PREFIX"], "api", "get_logs"))
    def get_logs():
        client_id = flask.request.args.get("id", type=str)
        db_name = flask.request.args.get("db", type=str)
        if db_name not in VALID_DATABASE_OPTIONS:
            return f"db must be one of {VALID_DATABASE_OPTIONS}", 400
        db_ = databases.get(db_name, db_playback)
        answer = db_.get_logs(client_id)
        a1 = a2 = ""
        if answer[0]:
            a1 = "".join(eval(answer[0]))
        if answer[1]:
            a2 = "".join(eval(answer[1]))
        return "<pre>" + a1 + "\n ... \n\n" + a2 + "</pre>"

    @app.route(os.path.join("/", cfg["SERVER_URL_PREFIX"], "api", "get_cluster_status"))
    def get_cluster_status():
        cluster = flask.request.args.get("cluster", default="playback", type=str)
        if cluster not in VALID_DATABASE_OPTIONS:
            return f"cluster must be one of {VALID_DATABASE_OPTIONS}", 400
        db_ = databases.get(cluster, db_playback)
        answer = db_.get_cluster_status()
        return json.dumps(answer)

    @app.route(os.path.join("/", cfg["SERVER_URL_PREFIX"], "api", "get_clients"))
    def get_clients():
        try:
            run_from = int(flask.request.args.get("from", type=int))
            run_to = int(flask.request.args.get("to", type=int))
        except (ValueError, TypeError):
            return ("to, from must be integers", 400)
        db_name = flask.request.args.get("db", type=str)
        if db_name not in VALID_DATABASE_OPTIONS:
            return f"db must be one of {VALID_DATABASE_OPTIONS}", 400
        db_ = databases.get(db_name, db_playback)
        answer = db_.get_clients(run_from, run_to)
        return json.dumps(answer)

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
            dqm2_answer = r.content.decode("utf-8")
        except Exception as e:
            log.warning(f"cr_exe@{what} initial request: {repr(e)}")
            return f"Error querying fff_dqmtools: {repr(e)}", 400

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

                elif what == "get_dqm_machines" and format:
                    answer = ""
                    data = json.loads(dqm2_answer)
                    for key, lst in sorted(data.items()):
                        answer += "<strong>" + key + "</strong> " + str(lst) + "\n"

                elif what == "get_simulator_config":
                    answer = json.loads(dqm2_answer)

            except Exception as e:
                log.warning(
                    f"cr_exe@{what}: Error when reading answer: {repr(e)}. Answer was: {answer}"
                )
                return f"Error parsing fff_dqmtools answer: {repr(e)}", 400

            return answer

        ### get logs data in new window tabs from DQM^2
        if what in ["get_fff_logs", "get_hltd_logs"]:
            data = ["No data from fff available ..."]

            try:
                data = json.loads(dqm2_answer)
            except Exception as e:
                log.warning(f"cr_exe@{what}: json.loads failed on data {dqm2_answer}")
                log.warning(repr(e))
                return f"Error parsing fff_dqmtools answer: {repr(e)}", 400

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
                        f"cr_exe@{what}: error in dqmsquare_cfg.dump_tmp_file for file: {repr(e)}"
                    )
                    continue
                file_urls += [
                    os.path.join(
                        "/", cfg["SERVER_URL_PREFIX"], SERVER_DATA_PATH, "tmp", fname
                    )
                ]
            log.debug(f"tmp Filenames: {file_urls}")
            return str(file_urls)

        # default answer
        log.warning(f"cr_exe@{what} : No actions defined for request.")
        return f"No actions defined for request '{what}'", 400

    @app.route(os.path.join("/", cfg["SERVER_URL_PREFIX"], "release_comparisons/"))
    def release_comparisons():
        return render_template(
            "release_comparisons.html",
            PREFIX=os.path.join("/", cfg["SERVER_URL_PREFIX"] + "/"),
            FRONTEND_API_QUERY_INTERVAL=cfg["FRONTEND_API_QUERY_INTERVAL"],
            VERSION=cfg["VERSION"],
            TIMEZONE=cfg["TIMEZONE"],
        )

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
