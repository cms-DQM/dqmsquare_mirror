""" 
Original Author: ~Mandrik, IHEP, https://github.com/pmandrik

Python file responsible for generating configuration data, depending on the
environment specified in environmental vars (or an .env file)
"""

import os
import tempfile
from dotenv import load_dotenv


def load_cfg() -> dict:
    """
    Prepare configuration, using .env file
    """

    load_dotenv()
    mount_path_cinder = os.path.join("/", "cinder", "dqmsquare")
    mount_path = mount_path_cinder

    ### default values === >
    cfg = {}
    cfg["VERSION"] = "1.1.0"

    cfg["ENV"] = os.environ.get("ENV", "development")
    cfg["SLEEP_TIME"] = 5  # sec, int

    cfg["LOGGER_ROTATION_TIME"] = 24  # h, int
    cfg["LOGGER_MAX_N_LOG_FILES"] = 10  # int

    # Name of the header sent to fff_tools
    cfg["FFF_SECRET_NAME"] = "selenium-secret-secret"
    cfg["FFF_PORT"] = "9215"

    # Flask server config
    cfg["SERVER_DEBUG"] = os.environ.get("SERVER_DEBUG", False)
    cfg["SERVER_HOST"] = "0.0.0.0"
    cfg["SERVER_PORT"] = 8084 if cfg["ENV"] != "development" else 8887

    # ?
    cfg["SERVER_PATH_TO_PRODUCTION_PAGE"] = (
        os.path.join(mount_path, "api?what=get_production")
        if cfg["ENV"] != "development"
        else "api?what=get_production"
    )

    # ?
    cfg["SERVER_PATH_TO_PLAYBACK_PAGE"] = (
        os.path.join(mount_path, "api?what=get_playback")
        if cfg["ENV"] != "development"
        else "api?what=get_playback"
    )
    cfg["FRONTEND_API_QUERY_INTERVAL"] = 5000  # msec, int
    cfg["SERVER_LOG_PATH"] = (
        os.path.join(mount_path, "log", "server.log")
        if cfg["ENV"] != "development"
        else os.path.join("/", "log", "server.log")
    )
    cfg["SERVER_DATA_PATH"] = mount_path if cfg["ENV"] != "development" else ""
    cfg["SERVER_URL_PREFIX"] = (
        os.path.join("/", "dqm", "dqm-square-k8")
        if cfg["ENV"] != "development"
        else "/"
    )
    cfg["SERVER_FFF_CR_PATH"] = (
        "https://cmsweb-testbed.cern.ch/dqm/dqm-square-origin"
        if cfg["ENV"] == "testbed"
        else "https://cmsweb.cern.ch/dqm/dqm-square-origin"
        if cfg["ENV"] == "production"
        else "https://cmsweb-test4.cern.ch/dqm/dqm-square-origin"
        if cfg["ENV"] == "test4"
        else "https://cmsweb-testbed.cern.ch/dqm/dqm-square-origin"
    )

    # FFF simulator machine
    # This is the machine that the grabber will try to acces
    # through SERVER_FFF_CR_PATH
    cfg["SERVER_FFF_MACHINE"] = "bu-c2f11-13-01"

    cfg["SERVER_GRID_CERT_PATH"] = (
        "/etc/robots/robotcert.pem"
        if cfg["ENV"] != "development"
        else os.environ.get(
            "SERVER_GRID_CERT_PATH", os.path.expanduser("~/.globus/usercert.pem")
        )
    )
    cfg["SERVER_GRID_KEY_PATH"] = (
        "/etc/robots/robotkey.pem"
        if cfg["ENV"] != "development"
        else os.environ.get(
            "SERVER_GRID_KEY_PATH", os.path.expanduser("~/.globus/userkey.pem")
        )
    )
    cfg["SERVER_SIMULATOR_RUN_KEYS"] = "cosmic_run,pp_run,commisioning_run"

    cfg["ROBBER_LOG_PATH"] = (
        os.path.join(mount_path, "log/robber1.log")
        if cfg["ENV"] != "development"
        else "log/robber1.log"
    )
    cfg["ROBBER_OLDRUNS_LOG_PATH"] = (
        os.path.join(mount_path, "log/robber2.log")
        if cfg["ENV"] != "development"
        else "log/robber2.log"
    )

    cfg["GRABBER_LOG_PATH"] = (
        os.path.join(mount_path, "log/grabber.log")
        if cfg["ENV"] != "development"
        else "log/grabber.log"
    )
    cfg["GRABBER_DEBUG"] = os.environ.get("GRABBER_DEBUG", False)

    cfg["DB_PLAYBACK_URI"] = (
        "postgresql:///postgres"
        if cfg["ENV"] != "development"
        else os.environ.get(
            "DB_PLAYBACK_URI", "sqlite:///../dqm2m.db?check_same_thread=False"
        )
    )
    cfg["DB_PRODUCTION_URI"] = (
        "postgresql:///postgres_production"
        if cfg["ENV"] != "development"
        else os.environ.get(
            "DB_PRODUCTION_URI",
            "sqlite:///../dqm2m_production.db?check_same_thread=False",
        )
    )

    return cfg


### Print values === >
if __name__ == "__main__":
    cfg_ = load_cfg()
    items = list(cfg_.items())
    items = sorted(items, key=lambda x: x[0])
    for item in items:
        print(item)


### Other
def dump_tmp_file(data, path, prefix, postfix):
    f = tempfile.NamedTemporaryFile(
        mode="w", prefix=prefix, suffix=postfix, dir=path, delete=False
    )
    f.write(data)
    f.close()
    return os.path.basename(f.name)
