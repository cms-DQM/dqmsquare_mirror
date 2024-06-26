# P.S.~Mandrik, IHEP, https://github.com/pmandrik
import os
import sys
import json
import time, sys
import requests
import urllib3
from urllib.parse import urljoin, urlencode
import logging
import traceback
import dqmsquare_cfg
from custom_logger import custom_formatter, set_log_handler
from db import DQM2MirrorDB
import threading

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)
cfg = dqmsquare_cfg.load_cfg()


def get_documents_from_fff(host: str, port: int = cfg["FFF_PORT"], runs_ids: list = []):
    """
    Given a host and the port where fff_dqmtools is listenting to, request documents for runs
    supplied by runs_ids (which have been extracted from the headers previously).

    The request is made indirectly to the SERVER_FFF_MACHINE, through the CMSWEB_FRONTEND_PROXY_URL.

    documents == logs from clients running on host and other information
    """
    if host == cfg["SERVER_FFF_MACHINE"]:
        url = cfg["CMSWEB_FRONTEND_PROXY_URL"] + "/sync_proxy"
    else:
        url = f'{cfg["CMSWEB_FRONTEND_PROXY_URL"]}/redirect?path={host}&port={port}'

    jsn = {"event": "request_documents", "ids": runs_ids}
    data = json.dumps({"messages": [json.dumps(jsn)]})
    logger.debug(f"POSTing to '{url}' with data: {data}")
    r = requests.post(
        url,
        data=data,
        cert=cert_path,
        verify=False,
        headers={},
        cookies=cookies,
        timeout=30,
    )
    logger.debug(f"Got {len(r.content)} byte response.")
    return r.content


def get_headers_from_fff(host: str, port: int = cfg["FFF_PORT"], revision: int = 0):
    """
    Given a host and the port where fff_dqmtools is listening to, connect to the proxy
    (i.e. indirectly the SERVER_FFF_MACHINE) and request headers, starting from the
    revision supplied.

    The request is made indirectly to the SERVER_FFF_MACHINE, through the CMSWEB_FRONTEND_PROXY_URL.

    Up to 1000 headers are returned.

    headers == clients basic info
    """
    # If the host is the SERVER_FFF_MACHINE itself, hit the sync_proxy endpoint
    if host == cfg["SERVER_FFF_MACHINE"]:
        url = cfg["CMSWEB_FRONTEND_PROXY_URL"] + "/sync_proxy"
    else:
        url = f'{cfg["CMSWEB_FRONTEND_PROXY_URL"]}/redirect?path={host}&port={port}'

    jsn = {"event": "sync_request", "known_rev": str(revision)}
    data = json.dumps({"messages": [json.dumps(jsn)]})
    logger.debug(f"POSTing to '{url}' with data: {jsn}")
    r = requests.post(
        url,
        data=data,
        cert=cert_path,
        verify=False,
        headers={},
        cookies=cookies,
        timeout=30,
    )
    logger.debug(f"Got response of length {len(r.content)}.")

    return r.content


# # Global list storing number of errors returned from fill/fill_graph(??)
# # Those functions do not return a revision number, but a 0 if no error and 1
# # otherwise, meaning that bad_rvs stores an array of ones.
# bad_rvs = []


def get_latest_info_from_host(host: str, rev: int, db: DQM2MirrorDB) -> None:
    """
    Given a host and a revision, it gets the latest headers from the host specified,
    and for each one it gets the appropriate "documents", storing them in the
    database.
    """
    # global bad_rvs
    logger.info(f"Updating host {host}, starting from revision {str(rev)}")
    if not rev:
        rev = 0

    headers_answer = get_headers_from_fff(host, revision=rev)
    try:
        headers_answer = json.loads(json.loads(headers_answer)["messages"][0])
        headers = headers_answer["headers"]
        rev = headers_answer["rev"]
        logger.debug(
            f"Got {headers_answer['total_sent']} headers, from {rev[0]} to {rev[1]}."
        )
    except Exception as e:
        logger.warning(f"Error when getting headers: {repr(e)}")
        logger.warning(f"Got response: {headers_answer}")
        logger.warning(traceback.format_exc())
        return

    if not len(headers):
        return
    for i, header in enumerate(headers):
        id = header["_id"]
        logger.info(f"Processing header {str(id)} ({i+1}/{len(headers)})")

        is_bu = host.startswith("bu") or host.startswith("dqmrubu")
        if is_bu and "analyze_files" not in id:
            logger.debug("Skip, no 'analyze_files' key")
            continue
        document_answer = get_documents_from_fff(host, runs_ids=[id])
        document = json.loads(json.loads(document_answer)["messages"][0])["documents"][
            0
        ]
        logger.debug("Filling info into DB ... ")

        # BU sends us file delivery graph info, FUs sends us logs and event processing rates.
        answer = (
            db.fill_graph(header, document) if is_bu else db.fill_run(header, document)
        )
        # TODO: Decide what kind of errors should be returned from the db fill functions.
        # if answer:
        #     bad_rvs += [answer]


def get_cluster_status(db: DQM2MirrorDB, cluster: str = "playback"):
    """
    Function that queries the gateway playback machine periodically to get the status of the
    production or playback cluster machines.
    """
    logger.debug(f"Requesting {cluster} cluster status.")
    url = urljoin(
        cfg["CMSWEB_FRONTEND_PROXY_URL"] + "/",
        "cr/exe?" + urlencode({"cluster": cluster, "what": "get_cluster_status"}),
    )
    response = requests.get(
        url,
        cookies={str(cfg["FFF_SECRET_NAME"]): os.environ.get("DQM_FFF_SECRET").strip()},
        verify=False,
        cert=([cfg["SERVER_GRID_CERT_PATH"], cfg["SERVER_GRID_KEY_PATH"]]),
    )
    if response.status_code != 200:
        logger.error(
            f"fff_dqmtools ({url}) returned {response.status_code}. Response: "
            f"{response.text}"
        )
        raise Exception(
            f"Failed to fetch {cluster} status. Got ({response.status_code}) {response.text}"
        )
    logger.debug(f"Got {cluster} cluster status.")

    try:
        response = response.json()
    except Exception as e:
        logger.error(f"Exception {e} when parsing: {response.text}")
        raise Exception(f"Failed to parse {cluster} status. Got {response.text}")
    db.fill_cluster_status(response)


def get_latest_info_from_hosts(hosts: list[str], db: DQM2MirrorDB) -> None:
    """
    Function that gets updated information on each of the hosts specified
    in hostnames, storing the new information into db.
    """
    for host in hosts:
        logger.debug(f"Getting latest rev for {host} from DB.")
        rev = db.get_latest_revision(host)
        get_latest_info_from_host(host=host, rev=rev, db=db)


if __name__ == "__main__":
    run_modes: list[str] = ["playback", "production"]
    playback_machines: list[str] = cfg["FFF_PLAYBACK_MACHINES"]
    production_machines: list[str] = cfg["FFF_PRODUCTION_MACHINES"]

    if len(sys.argv) > 1 and sys.argv[1] == "playback":
        set_log_handler(
            logger,
            cfg["GRABBER_LOG_PATH_PLAYBACK"],
            cfg["LOGGER_ROTATION_TIME"],
            cfg["LOGGER_MAX_N_LOG_FILES"],
            cfg["GRABBER_DEBUG"],
        )
        run_modes = ["playback"]
    elif len(sys.argv) > 1 and sys.argv[1] == "production":
        set_log_handler(
            logger,
            cfg["GRABBER_LOG_PATH_PRODUCTION"],
            cfg["LOGGER_ROTATION_TIME"],
            cfg["LOGGER_MAX_N_LOG_FILES"],
            cfg["GRABBER_DEBUG"],
        )
        run_modes = ["production"]
    else:
        set_log_handler(
            logger,
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
        logger.addHandler(handler2)
        logger.info(f"Configured logger for grabber, level={level}")

    ### global variables and auth cookies
    cmsweb_proxy_url: str = cfg["CMSWEB_FRONTEND_PROXY_URL"]
    cert_path: list[str] = [cfg["SERVER_GRID_CERT_PATH"], cfg["SERVER_GRID_KEY_PATH"]]

    env_secret: str = os.environ.get("DQM_FFF_SECRET")
    if env_secret:
        fff_secret = env_secret
        logger.debug("Found secret in environmental variables")
    else:
        logger.warning("No secret found in environmental variables")

    # Trailing whitespace in secret leads to crashes, strip it
    cookies: dict[str, str] = {str(cfg["FFF_SECRET_NAME"]): env_secret.strip()}

    # DB CONNECTION
    db_playback: DQM2MirrorDB = None
    db_production: DQM2MirrorDB = None

    if "playback" in run_modes:
        db_playback = DQM2MirrorDB(
            log=logger,
            host=cfg.get("DB_PLAYBACK_HOST"),
            port=cfg.get("DB_PLAYBACK_PORT"),
            username=cfg.get("DB_PLAYBACK_USERNAME"),
            password=cfg.get("DB_PLAYBACK_PASSWORD"),
            db_name=cfg.get("DB_PLAYBACK_NAME"),
        )
    if "production" in run_modes:
        db_production = DQM2MirrorDB(
            log=logger,
            host=cfg.get("DB_PRODUCTION_HOST"),
            port=cfg.get("DB_PRODUCTION_PORT"),
            username=cfg.get("DB_PRODUCTION_USERNAME"),
            password=cfg.get("DB_PRODUCTION_PASSWORD"),
            db_name=cfg.get("DB_PRODUCTION_NAME"),
        )

    logger.info("Starting loop for modes " + str(run_modes))

    # Main Loop.
    # Fetches data for CMSSW jobs from DQM^2, and stores it into the database.
    # For each mode (production/playback), loop over each available host FU/BU machine.
    # For each one, request "headers" (TODO: what are they?). This will return at most 1000
    # headers, starting from a specific revision (revision 0, i.e. the oldest, if not specified).
    # For each of the headers, "documents" are requested (logs and status for CMSSW jobs)
    # and stored into the database.
    # Once the loop goes over all the hosts and modes, it will have info for at most 1000 "headers" for each
    # host. Using the latest revision on each header, it asks for 1000 more headers on the next
    # iteration. This goes on forever, until the latest documents are fetched.
    def loop_info(
        machines: list[str],
        db: DQM2MirrorDB,
        timeout: int = cfg["GRABBER_SLEEP_TIME_INFO"],
    ):
        while True:
            try:
                get_latest_info_from_hosts(machines, db)
            except Exception as error:
                logger.warning(f"Crashed in info loop with error: {repr(error)}")
                logger.warning(f"Traceback: {traceback.format_exc()}")
                continue
            logger.debug(f"Sleeping for {timeout}s")
            time.sleep(timeout)

    # Loop for fetching cluster status.
    def loop_status(
        db: DQM2MirrorDB,
        cluster: str = "playback",
        timeout: int = cfg["GRABBER_SLEEP_TIME_STATUS"],
    ):
        while True:
            try:
                get_cluster_status(db, cluster)
            except Exception as error:
                logger.warning(f"Crashed in status loop with error: {repr(error)}")
                logger.warning(f"Traceback: {traceback.format_exc()}")
                continue
            logger.debug(f"Sleeping for {timeout}s")
            time.sleep(timeout)

    active_threads = []
    if "playback" in run_modes:
        active_threads.append(
            threading.Thread(
                target=loop_info,
                args=[playback_machines, db_playback, cfg["GRABBER_SLEEP_TIME_INFO"]],
                daemon=True,
            )
        )
        active_threads.append(
            threading.Thread(
                target=loop_status,
                args=[db_playback, "playback", cfg["GRABBER_SLEEP_TIME_STATUS"]],
                daemon=True,
            )
        )
    if "production" in run_modes:
        active_threads.append(
            threading.Thread(
                target=loop_info,
                args=[
                    production_machines,
                    db_production,
                    cfg["GRABBER_SLEEP_TIME_INFO"],
                ],
                daemon=True,
            )
        )
        active_threads.append(
            threading.Thread(
                target=loop_status,
                args=[db_production, "production", cfg["GRABBER_SLEEP_TIME_STATUS"]],
                daemon=True,
            )
        )
    for thread in active_threads:
        logger.info(f"Starting thread {thread._name}")
        thread.start()
    while True:
        time.sleep(1)
        # try:
        #     ### get content from active sites
        #     if "playback" in run_modes:
        #         # get_latest_info_from_hosts(playback_machines, db_playback)
        #         get_cluster_status(db_playback, "playback")
        #     if "production" in run_modes:
        #         # get_latest_info_from_hosts(production_machines, db_production)
        #         get_cluster_status(db_production, "production")
        # except KeyboardInterrupt:
        #     break
        # except Exception as error:
        #     logger.warning(f"Crashed in loop with error: {repr(error)}")
        #     logger.warning(f"Traceback: {traceback.format_exc()}")
        #     continue

        # time.sleep(int(cfg["GRABBER_SLEEP_TIME_INFO"]))

        # if len(bad_rvs):
        #     log.info(f"BAD REVISIONS: {bad_rvs}")
