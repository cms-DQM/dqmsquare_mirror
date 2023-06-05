# P.S.~Mandrik, IHEP, https://github.com/pmandrik

import dqmsquare_cfg
import requests
import flask
from flask import Flask
import logging
import json
from db import DQM2MirrorDB

log = logging.getLogger(__name__)

log.info("start_server() call ... ")
app = Flask(__name__)


def create_app(cfg):
    dqmsquare_cfg.set_log_handler(
        log,
        cfg["SERVER_LOG_PATH"],
        cfg["LOGGER_ROTATION_TIME"],
        cfg["LOGGER_MAX_N_LOG_FILES"],
        True,
    )
    SERVER_DATA_PATH = cfg["SERVER_DATA_PATH"]
    SERVER_LINK_PREFIX = cfg["SERVER_LINK_PREFIX"]

    log.info(
        "\n\n\n =============================================================================== "
    )
    log.info(
        "\n\n\n dqmsquare_server ============================================================== "
    )

    def make_dqm_mirrow_page(cfg):
        ifile = open("static/dqm_mirror_template.html", "r")
        content = ifile.read()
        ifile.close()

        # if cfg["SERVER_LOCAL"] :
        content = content.replace(
            "%PATH_TO_PRODUCTION_PAGE%", cfg["SERVER_PATH_TO_PRODUCTION_PAGE"]
        )
        content = content.replace(
            "%PATH_TO_PLAYBACK_PAGE%", cfg["SERVER_PATH_TO_PLAYBACK_PAGE"]
        )
        # else :
        #  content = content.replace( "%PATH_TO_PRODUCTION_PAGE%",  "/dqm/dqm-square/" + cfg["SERVER_PATH_TO_PRODUCTION_PAGE"] )
        #  content = content.replace( "%PATH_TO_PLAYBACK_PAGE%",    "/dqm/dqm-square/" + cfg["SERVER_PATH_TO_PLAYBACK_PAGE"] )

        content = content.replace("%RELOAD_TIME%", str(cfg["SERVER_RELOAD_TIME"]))

        ofile = open("static/dqm_mirror.html", "w")
        ofile.write(content)
        ofile.close()

    ### DQM^2 Mirror ###
    @app.route("/")
    @app.route("/dqm/dqm-square-k8")
    @app.route("/dqm/dqm-square-k8/")
    def greet(name="Stranger"):
        return flask.send_file("./static/dqm_runs.html")

    if cfg["SERVER_K8"]:
        ### K8
        @app.route("/dqm/dqm-square-k8/static/<path:name>")
        def get_static(name):
            return flask.send_from_directory("static", name)

        @app.route("/dqm/dqm-square-k8" + SERVER_DATA_PATH + "tmp/<path:name>")
        @app.route("/dqm/dqm-square-k8" + SERVER_DATA_PATH + "tmp/tmp/<path:name>")
        def get_tmp(name):
            return flask.send_from_directory(SERVER_DATA_PATH + "tmp/", name)

        @app.route("/dqm/dqm-square-k8" + SERVER_DATA_PATH + "log/<path:name>")
        @app.route("/dqm/dqm-square-k8" + SERVER_DATA_PATH + "tmp/log/<path:name>")
        def get_log(name):
            content = flask.send_from_directory(SERVER_DATA_PATH + "log/", name)
            return content

    else:

        @app.route("/static/<path:name>")
        @app.route("/dqm/dqm-square-k8/static/<path:name>")
        def get_static(name):
            return flask.send_from_directory("static", name)

        @app.route("/tmp/<path:name>")
        @app.route("/tmp/tmp/<path:name>")
        def get_tmp(name):
            content = flask.send_from_directory("./tmp/", name)
            return content

        @app.route("/log/<path:name>")
        @app.route("/tmp/log/<path:name>")
        def get_log(name):
            content = flask.send_from_directory("./log/", name)
            return content

    if True:
        ### global variables and auth cookies
        cr_path = cfg["SERVER_FFF_CR_PATH"]
        cert_path = [cfg["SERVER_GRID_CERT_PATH"], cfg["SERVER_GRID_KEY_PATH"]]
        selenium_secret = "changeme"
        env_secret = dqmsquare_cfg.get_env_secret(log, "DQM_PASSWORD")
        if env_secret:
            selenium_secret = env_secret
        cookies = {str(cfg["FFF_SECRET_NAME"]): selenium_secret}

        ### DQM^2-MIRROR DB API
        db = DQM2MirrorDB(log, cfg["GRABBER_DB_PLAYBACK_PATH"], server=True)
        db_production = DQM2MirrorDB(
            log, cfg["GRABBER_DB_PRODUCTION_PATH"], server=True
        )
        dbs = {"playback": db, "production": db_production, "": db_production}

        @app.route("/api")
        @app.route("/dqm/dqm-square-k8/api")
        def dqm2_api():
            log.info(flask.request.base_url)
            what = flask.request.args.get("what")

            ### get data from DQM^2 Mirror
            if what == "get_run":
                run = flask.request.args.get("run", default=0)
                db_name = flask.request.args.get("db", default="")
                db_ = dbs.get(db_name, db)
                run_data = db_.get_mirror_data(run)
                runs_around = db_.get_runs_arounds(run)
                return json.dumps([runs_around, run_data])
            if what == "get_graph":
                run = flask.request.args.get("run", default=0)
                db_name = flask.request.args.get("db", default="")
                db_ = dbs.get(db_name, db)
                graph_data = db_.get_graphs_data(run)
                return json.dumps(graph_data)
            if what == "get_runs":
                run_from = flask.request.args.get("from", default=0)
                run_to = flask.request.args.get("to", default=0)
                bad_only = flask.request.args.get("bad_only", default=0)
                with_ls_only = flask.request.args.get("ls", default=0)
                db_name = flask.request.args.get("db", default="")
                db_ = dbs.get(db_name, db)
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
                db_ = dbs.get(db_name, db)
                answer = db_.get_clients(run_from, run_to)
                return json.dumps(answer)
            if what == "get_info":
                db_name = flask.request.args.get("db", default="")
                db_ = dbs.get(db_name, db)
                answer = db_.get_info()
                return json.dumps(answer)
            if what == "get_logs":
                client_id = flask.request.args.get("id", default=0)
                db_name = flask.request.args.get("db", default="")
                db_ = dbs.get(db_name, db)
                answer = db_.get_logs(client_id)
                a1 = "".join(eval(answer[0]))
                a2 = "".join(eval(answer[1]))
                # print( a1 + a2 )
                return "<plaintext>" + a1 + "\n ... \n\n" + a2

        ### HBEAT ###
        # @app.route('/heartbeat')
        # @app.route('/heartbeat/')
        # @app.route('/dqm/dqm-square-k8/heartbeat')
        # @app.route('/dqm/dqm-square-k8/heartbeat/')
        # def get_hbeat(name='Stranger'):
        #  return static_file("dqm_heartbeat.html", root='./static/')

        ### TIMELINE ###
        @app.route("/timeline")
        @app.route("/timeline/")
        @app.route("/dqm/dqm-square-k8/timeline")
        @app.route("/dqm/dqm-square-k8/timeline/")
        def get_timeline(name="Stranger"):
            return flask.send_file("./static/dqm_timeline.html")

        ### CR ###
        cr_usernames = dqmsquare_cfg.get_cr_usernames(log, "DQM_CR_USERNAMES")
        env_cookie_secret = dqmsquare_cfg.get_env_secret(log, "DQM_CR_SECRET")
        cookie_secret = env_cookie_secret if env_cookie_secret else "secret"

        def check_login(username, password, cookie=False):
            if username not in cr_usernames:
                return False
            if cookie:
                return True
            if password != cr_usernames[username]:
                return False
            return True

        @app.route("/cr/login", methods=["POST"])
        @app.route("/dqm/dqm-square-k8/cr/login", methods=["POST"])
        def do_login():
            username = flask.request.form.get("username")
            password = flask.request.form.get("password")
            log.info("login result " + str(check_login(username, password)))
            if check_login(username, password):
                resp = flask.make_response(flask.redirect("/dqm/dqm-square-k8/cr"))
                if cfg["SERVER_K8"]:
                    resp = flask.make_response(
                        flask.redirect("https://cmsweb.cern.ch/dqm/dqm-square-k8/cr")
                    )
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

        @app.route("/cr/logout")
        @app.route(
            "/dqm/dqm-square-k8/cr/logout"
        )  # https://cmsweb.cern.ch/dqm/dqm-square-k8/
        def do_logout():
            log.info("logout")
            resp = flask.make_response(flask.redirect("/"))
            if cfg["SERVER_K8"]:
                resp = flask.make_response(
                    flask.redirect("https://cmsweb.cern.ch/dqm/dqm-square-k8/")
                )
            resp.set_cookie(
                "dqmsquare-mirror-cr-account", "random", path="/", httponly=True
            )
            return resp

        def check_auth(redirect=True):
            def check_auth_(fn):
                def check_auth__(*args, **kwargs):
                    username = flask.request.cookies.get("dqmsquare-mirror-cr-account")
                    if not check_login(username, None, True):
                        if redirect:
                            if cfg["SERVER_K8"]:
                                return flask.redirect(
                                    "https://cmsweb.cern.ch/dqm/dqm-square-k8/cr/login"
                                )
                            else:
                                return flask.redirect("/dqm/dqm-square-k8/cr/login")
                        else:
                            return "Please login ..."
                    else:
                        return fn(*args, **kwargs)

                check_auth__.__name__ = fn.__name__
                return check_auth__

            return check_auth_

        @app.route("/cr")
        @app.route("/cr/")
        @app.route("/dqm/dqm-square-k8/cr")
        @app.route("/dqm/dqm-square-k8/cr/")
        @check_auth()
        def get_cr(name="Stranger"):
            return flask.send_file("./static/dqm_cr.html")

        @app.route("/cr/login", methods=["GET"])
        @app.route("/dqm/dqm-square-k8/cr/login", methods=["GET"])
        def login():
            return """
            <style>
	          .title {
                padding-left: 16px;
                padding-top: 7px;
                padding-right: 16px;
                padding-bottom: 6px;
                text-decoration: none;
                font-size: 18px;
                background-color: #2471a3;
                color:  #d4e6f1 ;
                font-weight: bold;
              }
            </style>
            <div class="title">
              DQM <sup>2</sup> &#x25A0; Welcom!
            </div> <br>
            <form action="/dqm/dqm-square-k8/cr/login" method="post">
                Username: <input name="username" type="text" />
                Password: <input name="password" type="password" />
                <input value="Login" type="submit" />
            </form>
        """

        # DQM & FFF & HLTD
        @app.route("/cr/exe")
        @app.route(
            "/dqm/dqm-square-k8/cr/exe"
        )  # http://0.0.0.0:8887/dqm/dqm-square-k8/cr/exe?what=get_dqm_machines&
        @check_auth(False)
        def cr_exe():
            log.info(flask.request.base_url)
            what = flask.request.args.get("what")

            ### get data from DQM^2 Mirror
            if what == "get_simulator_run_keys":
                try:
                    answer = str(cfg["SERVER_SIMULATOR_RUN_KEYS"].split(","))
                    return answer
                except Exception as error_log:
                    log.warning(error_log)
                    return repr(error_log), 400

            # using exe API
            # initial request
            url = cr_path + "/cr/exe?" + flask.request.query_string.decode()
            answer = None
            try:
                r = requests.get(url, cert=cert_path, verify=False, cookies=cookies)
                dqm2_answer = r.content
            except Exception as error_log:
                log.warning("cr_exe() initial request : " + repr(error_log))
                return repr(error_log), 400

            log.warning(what)
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

                except Exception as error_log:
                    log.warning(
                        "cr_exe() change format to be printable : " + repr(error_log)
                    )
                    return repr(error_log), 400

                return answer

            ### get logs data in new window tabs from DQM^2
            if what in ["get_fff_logs", "get_hltd_logs"]:
                data = ["No data from fff available ..."]

                try:
                    data = json.loads(dqm2_answer)
                except Exception as error_log:
                    log.warning(
                        "cr_exe() : can't json.loads from DQM^2 data " + dqm2_answer
                    )
                    log.warning(repr(error_log))
                    return repr(error_log), 400

                fnames = []
                for item in data:
                    if not len(item):
                        continue
                    try:
                        fname = dqmsquare_cfg.dump_tmp_file(
                            item, SERVER_DATA_PATH + "tmp/", what, ".txt"
                        )
                    except Exception as error_log:
                        log.warning(
                            "cr_exe() : error in dqmsquare_cfg.dump_tmp_file for file:"
                        )
                        log.warning(repr(error_log))
                        continue
                    fnames += [SERVER_LINK_PREFIX + SERVER_DATA_PATH + "tmp/" + fname]
                return str(fnames)

            # default answer
            log.warning(
                "cr_exe() : No actions defined for that request : " + repr(what)
            )
            return "No actions defined for that request"

    log.info("make_dqm_mirrow_page() call ... ")
    make_dqm_mirrow_page(cfg)
    return app


if __name__ == "__main__":
    cfg = dqmsquare_cfg.load_cfg("dqmsquare_mirror.cfg")
    create_app = create_app(cfg)
    create_app.run(
        host=str(cfg["SERVER_HOST"]),
        port=int(cfg["SERVER_PORT"]),
        debug=bool(cfg["SERVER_DEBUG"]),
    )
else:
    cfg = dqmsquare_cfg.load_cfg("dqmsquare_mirror.cfg")
    gunicorn_app = create_app(cfg)
