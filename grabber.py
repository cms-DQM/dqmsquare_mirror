# P.S.~Mandrik, IHEP, https://github.com/pmandrik
import os
import sys
import json
import time, sys
import requests
import urllib3
import logging
import traceback
import dqmsquare_cfg
from custom_logger import custom_formatter, set_log_handler
from db import DQM2MirrorDB


urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

log = logging.getLogger(__name__)

if __name__ == "__main__":
    cfg = dqmsquare_cfg.load_cfg()

    run_modes = ["playback", "production"]
    playback = cfg["FFF_PLAYBACK_MACHINES"]
    production = cfg["FFF_PRODUCTION_MACHINES"]

    if len(sys.argv) > 1 and sys.argv[1] == "playback":
        set_log_handler(
            log,
            cfg["ROBBER_LOG_PATH_PLAYBACK"],
            cfg["LOGGER_ROTATION_TIME"],
            cfg["LOGGER_MAX_N_LOG_FILES"],
            cfg["GRABBER_DEBUG"],
        )
        run_modes = ["playback"]
    elif len(sys.argv) > 1 and sys.argv[1] == "production":
        set_log_handler(
            log,
            cfg["ROBBER_LOG_PATH_PRODUCTION"],
            cfg["LOGGER_ROTATION_TIME"],
            cfg["LOGGER_MAX_N_LOG_FILES"],
            cfg["GRABBER_DEBUG"],
        )
        run_modes = ["production"]
    else:
        set_log_handler(
            log,
            cfg["GRABBER_LOG_PATH"],
            cfg["LOGGER_ROTATION_TIME"],
            cfg["LOGGER_MAX_N_LOG_FILES"],
            cfg["GRABBER_DEBUG"],
        )

    if cfg["ENV"] == "development":
        formatter = custom_formatter
        handler2 = logging.StreamHandler(sys.stdout)
        handler2.setFormatter(formatter)
        level = logging.DEBUG if cfg["GRABBER_DEBUG"] else logging.INFO
        handler2.setLevel(level=level)
        log.addHandler(handler2)
        log.info(f"Configured logger for grabber, level={level}")

    ### global variables and auth cookies
    cmsweb_proxy_url = cfg["CMSWEB_FRONTEND_PROXY_URL"]
    cert_path = [cfg["SERVER_GRID_CERT_PATH"], cfg["SERVER_GRID_KEY_PATH"]]
    fff_secret = "changeme"

    env_secret = os.environ.get("DQM_FFF_SECRET")
    if env_secret:
        fff_secret = env_secret
        log.debug("Found secret in environmental variables")
    else:
        log.warning("No secret found in environmental variables")

    # Trailing whitespace in secret leads to crashes, strip it
    cookies = {str(cfg["FFF_SECRET_NAME"]): fff_secret.strip()}

    ### DQM^2-MIRROR DB CONNECTION
    db_playback, db_production = None, None
    if "playback" in run_modes:
        db_playback = DQM2MirrorDB(log, cfg["DB_PLAYBACK_URI"])
    if "production" in run_modes:
        db_production = DQM2MirrorDB(log, cfg["DB_PRODUCTION_URI"])

    def get_documents_from_fff(dqm_machine, dqm_port=cfg["FFF_PORT"], runs_ids=[]):
        """
        FFF API around SQL DB is websocket based, we need to define event in message and send it.
        API is simple - we can get only 1000 headers with clients ids and documents per client ids
        headers == clients basic info
        documents == clients logs and other information
        """
        url = f'{cfg["CMSWEB_FRONTEND_PROXY_URL"]}/redirect?path={dqm_machine}&port={dqm_port}'
        if dqm_machine == cfg["SERVER_FFF_MACHINE"]:
            url = cfg["CMSWEB_FRONTEND_PROXY_URL"] + "/sync_proxy"

        jsn = {"event": "request_documents", "ids": runs_ids}
        data = json.dumps({"messages": [json.dumps(jsn)]})
        log.debug(f"POSTing to '{url}' with data: {jsn}")
        r = requests.post(
            url,
            data=data,
            cert=cert_path,
            verify=False,
            headers={},
            cookies=cookies,
            timeout=30,
        )
        log.debug(f"Got {len(r.content)} byte response.")

        return r.content

    def get_headers_from_fff(dqm_machine, dqm_port=cfg["FFF_PORT"], revision=0):
        url = f'{cfg["CMSWEB_FRONTEND_PROXY_URL"]}/redirect?path={dqm_machine}&port={dqm_port}'
        if dqm_machine == cfg["SERVER_FFF_MACHINE"]:
            url = cfg["CMSWEB_FRONTEND_PROXY_URL"] + "/sync_proxy"

        jsn = {"event": "sync_request", "known_rev": str(revision)}
        data = json.dumps({"messages": [json.dumps(jsn)]})
        log.debug(f"POSTing to '{url}' with data: {jsn}")
        r = requests.post(
            url,
            data=data,
            cert=cert_path,
            verify=False,
            headers={},
            cookies=cookies,
            timeout=30,
        )
        log.debug(f"Got response of length {len(r.content)}.")

        return r.content

    bad_rvs = []

    def update_db(db_, host, rev=0):
        """
        TODO: Cleanup; this is definitely NOT just updating the DB
        """
        global bad_rvs
        log.info(f"Update host {host} {str(rev)}")
        if not rev:
            rev = 0

        headers_answer = get_headers_from_fff(host, revision=rev)
        try:
            headers_answer = json.loads(json.loads(headers_answer)["messages"][0])
            headers = headers_answer["headers"]
            rev = headers_answer["rev"]
        except Exception as error_log:
            log.warning(headers_answer)
            log.warning(repr(error_log))
            log.warning(traceback.format_exc())
            return

        if not len(headers):
            return
        for header in headers:
            id = header["_id"]
            log.info("Process header " + str(id))

            if host[0] == "b":
                if "analyze_files" not in id:
                    log.debug("Skip, no 'analyze_files' key")
                    continue
                document_answer = get_documents_from_fff(host, runs_ids=[id])
                document = json.loads(json.loads(document_answer)["messages"][0])[
                    "documents"
                ][0]
                log.debug("Fill graph info into DB ... ")
                answer = db_.fill_graph(header, document)
                if answer:
                    bad_rvs += [answer]
            else:
                document_answer = get_documents_from_fff(host, runs_ids=[id])
                document = json.loads(json.loads(document_answer)["messages"][0])[
                    "documents"
                ][0]
                log.debug("Fill doc info into DB ... ")
                answer = db_.fill(header, document)
                if answer:
                    bad_rvs += [answer]

    log.info("Starting loop for modes " + str(run_modes))

    while True:
        try:
            ### get content from active sites
            if "playback" in run_modes:
                for host in playback:
                    log.debug(f"Getting latest rev for {host} from DB.")
                    rev = db_playback.get_rev(host)
                    log.debug(f"Latest rev = {rev}.")
                    update_db(db_playback, host, rev)
            if "production" in run_modes:
                for host in production:
                    log.debug(f"Getting latest rev for {host} from DB.")
                    rev = db_production.get_rev(host)
                    log.debug(f"Latest rev = {rev}.")
                    update_db(db_production, host, rev)
        except KeyboardInterrupt:
            break
        except Exception as error:
            log.warning(f"Crashed in loop with error: {repr(error)}")
            log.warning(f"Traceback: {traceback.format_exc()}")
            continue

        if cfg["ENV"] != "development":
            log.debug("z-Z-z until next iteration")
            time.sleep(int(cfg["SLEEP_TIME"]))

        if len(bad_rvs):
            log.info(f"BAD REVISIONS: {bad_rvs}")
