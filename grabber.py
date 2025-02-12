# P.S.~Mandrik, IHEP, https://github.com/pmandrik
import os
import sys
import json
import time
import logging
import urllib3
import requests
import threading
from datetime import datetime
from collections.abc import Callable
from urllib.parse import urljoin, urlencode
import dqmsquare_cfg
from custom_logger import custom_formatter, set_log_handler
from db import DQM2MirrorDB

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)
cfg = dqmsquare_cfg.load_cfg()


def _request_wrapper(
    method: Callable, url: str, *args, **kwargs
) -> requests.Response | None:
    """
    Simple wrapper to be used on request methods to handle common exceptions.
    On exception, None is returned, else the response is returned.
    """
    try:
        response = method(url, *args, **kwargs)
    except urllib3.exceptions.ReadTimeoutError:
        logger.warning(
            f"Timeout when running {method.__name__} on {url}", exc_info=True
        )
        return None
    except requests.exceptions.ConnectionError:
        logger.warning(f"Could not connect to {url}", exc_info=True)
        return None
    except Exception:
        logger.warning(
            f"Unhandled exception when running {method.__name__} on {url}",
            exc_info=True,
        )
        return None
    return response


def get_documents_from_fff(
    host: str, port: int = cfg["FFF_PORT"], runs_ids: list = []
) -> bytes | None:
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

    r = _request_wrapper(
        requests.post,
        url,
        data=data,
        cert=cert_path,
        verify=False,
        headers={},
        cookies=_get_cookies(),
        timeout=30,
    )
    if r:
        if r.status_code != 200:
            logger.warning(
                f"Got response {r.status_code} when POSTing to {url}: {r.content}."
            )
            return None
        else:
            return r.content
    return None


def process_headers_and_store_data(host: str, db: DQM2MirrorDB, headers: list[dict]):
    """
    Process headers as received from the DQM cluster, triage and then store the data
    in the database.
    """
    for i, header in enumerate(headers):
        id = header["_id"]
        logger.info(f"Processing header {str(id)} ({i+1}/{len(headers)})")

        is_bu = host.startswith("bu") or host.startswith("dqmrubu")
        if is_bu and "analyze_files" not in id:
            logger.debug("Skipping, no 'analyze_files' key found")
            continue
        document_answer = get_documents_from_fff(host, runs_ids=[id])
        if not document_answer:
            continue
        document = json.loads(json.loads(document_answer)["messages"][0])["documents"][
            0
        ]
        logger.debug("Filling info into DB ... ")

        # BU sends us file delivery graph info, FUs sends us logs and event processing rates.
        db.fill_graph(header, document) if is_bu else db.fill_run(header, document)


def get_headers_from_fff(
    host: str, port: int = cfg["FFF_PORT"], revision: int = 0
) -> bytes | None:
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

    r = _request_wrapper(
        requests.post,
        url,
        data=data,
        cert=cert_path,
        verify=False,
        headers={},
        cookies=_get_cookies(),
        timeout=30,
    )
    if r:
        if r.status_code != 200:
            logger.warning(
                f"Got response {r.status_code} when POSTing to {url}: {r.content}."
            )
            return None
        else:
            return r.content
    return None


def process_cluster_status(cluster_status: requests.Response) -> dict | None:
    """
    The response is expected to be a JSON like:

    {
    'dqmrubu-c2a06-03...cms': {'up': True, 'msg': None},
    'dqmfu-c2b01-45...cms': {'up': True, 'msg': None},
    'dqmfu-c2b02-45...cms': {'up': True, 'msg': None}
    }
    """
    return_value = None
    try:
        return_value = cluster_status.json()
        assert all(
            "up" in return_value[host] and "msg" in return_value[host]
            for host in return_value
        )
    except AssertionError:
        logger.error(f"Unexpected status response received: {return_value}")
        return_value = None
    except Exception:
        logger.error(
            f"Unhandled exception when parsing {cluster_status} status: {cluster_status.text}",
            exc_info=True,
        )
    return return_value


def get_cluster_status(cluster: str = "playback") -> dict | None:
    """
    Function that queries the gateway playback machine periodically to get the status of the
    production or playback cluster machines.
    """
    logger.debug(f"Requesting {cluster} cluster status.")
    url = urljoin(
        cfg["CMSWEB_FRONTEND_PROXY_URL"] + "/",
        "cr/exe?" + urlencode({"cluster": cluster, "what": "get_cluster_status"}),
    )
    response = _request_wrapper(
        requests.get,
        url,
        cookies=_get_cookies(),
        verify=False,
        cert=([cfg["SERVER_GRID_CERT_PATH"], cfg["SERVER_GRID_KEY_PATH"]]),
    )
    if response:
        if response.status_code != 200:
            logger.error(
                f"fff_dqmtools ({url}) returned {response.status_code}. Response: "
                f"{response.text}"
            )
            raise Exception(
                f"Failed to fetch {cluster} status. Got ({response.status_code}) {response.text}"
            )
        logger.debug(f"Got {cluster} cluster status.")
        return process_cluster_status(cluster_status=response)
    return None


def get_list_of_comparison_reports() -> list[dict]:
    url = urljoin(
        cfg["CMSWEB_FRONTEND_PROXY_URL"] + "/",
        "cr/exe?" + urlencode({"what": "cmssw_comparison_reports"}),
    )
    response = _request_wrapper(
        requests.get,
        url,
        cookies=_get_cookies(),
        verify=False,
        cert=([cfg["SERVER_GRID_CERT_PATH"], cfg["SERVER_GRID_KEY_PATH"]]),
    )
    if response:
        if response.status_code != 200:
            logger.error(
                f"fff_dqmtools ({url}) returned {response.status_code}. Response: "
                f"{response.text}"
            )
            raise Exception(
                f"Failed to fetch list of CMSSW comparison reports. Got ({response.status_code}) {response.text}"
            )
        logger.debug("Got list of CMSSW comparison reports")
        return response.json()

    return []


def get_single_comparison_report(comparison_id: str) -> str:
    url = urljoin(
        cfg["CMSWEB_FRONTEND_PROXY_URL"] + "/",
        "cr/exe?"
        + urlencode({"what": "cmssw_comparison_reports", "id": comparison_id}),
    )
    response = _request_wrapper(
        requests.get,
        url,
        cookies=_get_cookies(),
        verify=False,
        cert=([cfg["SERVER_GRID_CERT_PATH"], cfg["SERVER_GRID_KEY_PATH"]]),
    )
    if response:
        if response.status_code != 200:
            logger.error(
                f"fff_dqmtools ({url}) returned {response.status_code}. Response: "
                f"{response.text}"
            )
            raise Exception(
                f"Failed to fetch list of CMSSW comparison reports. Got ({response.status_code}) {response.text}"
            )
        logger.debug("Got list of CMSSW comparison reports")
        return response.text

    return ""


def get_latest_info_from_host(host: str, rev: int) -> list[dict]:
    """
    Given a host and a revision, it gets the latest headers from the host specified,
    and for each one it gets the appropriate "documents", storing them in the
    database.
    """
    # global bad_rvs
    logger.info(f"Updating host {host}, starting from revision {str(rev)}")
    if not rev:
        rev = 0
    headers = []
    headers_answer = get_headers_from_fff(host, revision=rev)
    if headers_answer:
        try:
            headers_answer = json.loads(json.loads(headers_answer)["messages"][0])
            headers = headers_answer["headers"]
            rev = headers_answer["rev"]
            logger.debug(
                f"Got {headers_answer['total_sent']} headers, from {rev[0]} to {rev[1]}."
            )
        except Exception:
            logger.warning("Error when getting headers: ", exc_info=True)
            logger.warning(f"Got response: {headers_answer}")
            return []

    return headers


def get_latest_info_from_hosts(hosts: list[str], db: DQM2MirrorDB) -> None:
    """
    Function that gets updated information on each of the hosts specified
    in hostnames, storing the new information into db.
    """
    for host in hosts:
        logger.debug(f"Getting latest rev for {host} from DB.")
        rev = db.get_latest_revision(host)
        headers = get_latest_info_from_host(host=host, rev=rev)
        process_headers_and_store_data(host=host, db=db, headers=headers)


def _get_cookies() -> dict[str, str]:
    env_secret: str = os.environ.get("DQM_FFF_SECRET", "")
    assert env_secret, "No secret found in environmental variables"

    # Trailing whitespace in secret leads to crashes, strip it
    return {str(cfg["FFF_SECRET_NAME"]): env_secret.strip()}


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

    cookies = _get_cookies()

    # DB CONNECTION
    db_playback: DQM2MirrorDB
    db_production: DQM2MirrorDB

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

    # Loop for fetching job information from the cluster.
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
        hosts: list[str],
        db: DQM2MirrorDB,
        timeout: int = cfg["GRABBER_SLEEP_TIME_INFO"],
    ):
        while True:
            try:
                get_latest_info_from_hosts(hosts, db)
            except Exception:
                logger.warning("Unhandled exception in info loop", exc_info=True)
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
                cluster_status = get_cluster_status(cluster)
                if cluster_status:
                    db.fill_cluster_status(cluster_status)
            except Exception:
                logger.warning("Unhandled exception in status loop", exc_info=True)
            logger.debug(f"Sleeping for {timeout}s")
            time.sleep(timeout)

    def loop_cmssw_comparison_reports(
        db: DQM2MirrorDB,
        timeout: int = cfg["GRABBER_SLEEP_TIME_COMP"],
    ):
        while True:
            try:
                results = get_list_of_comparison_reports()
                if results:
                    logger.debug(f"There are {len(results)} comparisons available.")

                    for report in results:
                        assert all(
                            [
                                key in report
                                for key in [
                                    "id",
                                    "timestamp",
                                    "comp",
                                    "base",
                                    "base_prs",
                                    "comp_prs",
                                ]
                            ]
                        )
                        report["timestamp"] = datetime.fromisoformat(
                            report["timestamp"]
                        )
                        report["base_prs"] = [int(pr) for pr in report["base_prs"]]
                        report["comp_prs"] = [int(pr) for pr in report["comp_prs"]]

                        if db.get_cmssw_comparison_reports(
                            id=report["id"], paginate=False
                        ):
                            logger.debug(f"Report {report['id']} already in db")
                            continue
                        logger.debug(f"Requesting HTML report for {report['id']}")
                        print(report)
                        html_report = get_single_comparison_report(report["id"])
                        db.fill_cmssw_comparison_report(
                            **report,
                            comparison_report_html=html_report,
                        )
            except Exception:
                logger.warning("Unhandled exception in status loop", exc_info=True)
            logger.debug(f"Sleeping for {timeout}s")
            time.sleep(timeout)

    active_threads = []
    if "playback" in run_modes:
        # active_threads.append(
        #     threading.Thread(
        #         target=loop_info,
        #         args=[playback_machines, db_playback, cfg["GRABBER_SLEEP_TIME_INFO"]],
        #         daemon=True,
        #     )
        # )
        # active_threads.append(
        #     threading.Thread(
        #         target=loop_status,
        #         args=[db_playback, "playback", cfg["GRABBER_SLEEP_TIME_STATUS"]],
        #         daemon=True,
        #     )
        # )
        active_threads.append(
            threading.Thread(
                target=loop_cmssw_comparison_reports,
                args=[db_playback, cfg["GRABBER_SLEEP_TIME_COMP"]],
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
        try:
            time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Keyboard interrupt detected, exiting")
            break

        # if len(bad_rvs):
        #     log.info(f"BAD REVISIONS: {bad_rvs}")
