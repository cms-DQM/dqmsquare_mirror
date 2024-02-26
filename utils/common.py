from datetime import datetime
from dqmsquare_cfg import TZ


def _censor_hostname(hostname: str) -> str:
    """Hide part of the hostname for safety reasons"""
    var = hostname.split("-")
    return (
        f"{var[0]}-{var[1]}-.."
        if hostname.startswith("dqm")
        else "..".join([var[0], var[-1]])
    )


def get_short_client_name(client):
    return (
        client[: -len("_dqm_sourceclient-live")]
        if "_dqm_sourceclient-live" in client
        else client
    )


def filter_clients(name):
    if not name:
        return False
    if name == "__init__":
        return False
    return True


def format_table_entry(data: tuple) -> list:
    """ """
    answer = []
    (
        _,
        client,
        run,
        _,
        hostname,
        exit_code,
        events_total,
        _,
        cmssw_run,
        cmssw_lumi,
        client_path,
        runkey,
        fi_state,
        timestamp,
        _,
    ) = data
    client = get_short_client_name(client)
    hostname = _censor_hostname(hostname)
    runkey = runkey[len("runkey=") :]

    cmssw_path = ""
    subfolders = client_path.split("/")
    for folder in subfolders:
        if "CMSSW" in folder:
            cmssw_path = folder
            break

    cmssw_v = cmssw_path.split("CMSSW_")[1]

    answer = [
        run,
        client,
        (
            hostname,
            events_total,
            cmssw_lumi,
            fi_state,
            exit_code,
            timestamp.isoformat(),
        ),
        (cmssw_run, runkey, cmssw_v),
    ]

    return answer


def format_run_data(data: tuple) -> list:
    """
    Given run data from the DB, format them for the front-end.
    """
    answer = []
    (
        id,
        client,
        _,
        _,
        hostname,
        exit_code,
        events_total,
        events_rate,
        _,
        cmssw_lumi,
        client_path,
        runkey,
        _,
        timestamp,
        VmRSS,
    ) = data
    client = get_short_client_name(client)
    # Hide part of the hostname for safety reasons
    hostname = _censor_hostname(hostname)
    # Timestamp is of type datetime, and is tz-aware,
    # as it's coming straight from the DB.
    td = TZ.localize(datetime.now()) - timestamp
    td = td.total_seconds()

    cmssw_path = ""
    subfolders = client_path.split("/")
    for folder in subfolders:
        if "CMSSW" in folder:
            cmssw_path = folder
            break
    cmssw_v = cmssw_path.split("CMSSW_")[1]
    runkey = runkey[len("runkey=") :]

    answer = [
        (
            timestamp.timestamp() * 1000,  # Make it seconds, mot ms
            td,
            hostname,
            exit_code,
            client,
            cmssw_lumi,
            VmRSS,
            events_total,
            id,
            events_rate,
        ),
        (cmssw_v, runkey),
    ]
    return answer
