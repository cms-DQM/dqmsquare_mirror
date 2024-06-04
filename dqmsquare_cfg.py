"""
Original Author: ~Mandrik, IHEP, https://github.com/pmandrik

Python file responsible for generating configuration data, depending on the
environment specified in environmental vars (or an .env file)
"""

import os
import pytz
import tempfile
from dotenv import load_dotenv

# Important for converting datetime objects (from the database)
# to timestamps. Github actions, for example, run in different timezones,
# leading to different timestamps and failing tests.
TIMEZONE = "Europe/Zurich"
TZ = pytz.timezone(TIMEZONE)


def format_db_uri(
    username: str = "postgres",
    password: str = "postgres",
    host: str = "postgres",
    port: int = 5432,
    db_name="postgres",
) -> str:
    """
    Helper function to format the DB URI for SQLAclhemy
    """
    return f"postgresql://{username}:{password}@{host}:{port}/{db_name}"


def load_cfg() -> dict:
    """
    Prepare configuration, using .env file
    """

    load_dotenv()
    mount_path = os.path.join("cinder", "dqmsquare")

    ### default values === >
    cfg = {}
    cfg["VERSION"] = "1.3.1"

    cfg["ENV"] = os.environ.get("ENV", "development")

    # How often to try to get CMSSW jobs info
    # sec, int
    cfg["GRABBER_SLEEP_TIME_INFO"] = os.environ.get("GRABBER_SLEEP_TIME_INFO", 5)

    # How often to ping the cluster machines for their status.
    # Keep it above 30 secs.
    # sec, int
    cfg["GRABBER_SLEEP_TIME_STATUS"] = os.environ.get("GRABBER_SLEEP_TIME_STATUS", 30)

    cfg["LOGGER_ROTATION_TIME"] = 24  # h, int
    cfg["LOGGER_MAX_N_LOG_FILES"] = 10  # int

    # Name of the header sent to fff_tools
    cfg["FFF_SECRET_NAME"] = "selenium-secret-secret"
    cfg["FFF_PORT"] = "9215"

    # Flask server config
    cfg["SERVER_DEBUG"] = os.environ.get("SERVER_DEBUG", False)
    # MACHETE
    if isinstance(cfg["SERVER_DEBUG"], str):
        cfg["SERVER_DEBUG"] = True if cfg["SERVER_DEBUG"] == "True" else False
    cfg["SERVER_HOST"] = "0.0.0.0"
    cfg["SERVER_PORT"] = 8084 if cfg["ENV"] != "development" else 8887

    cfg["FRONTEND_API_QUERY_INTERVAL"] = 3000  # msec, int
    cfg["SERVER_LOG_PATH"] = (
        os.path.join("/", mount_path, "log", "server.log")
        if cfg["ENV"] != "development"
        else os.path.join("log", "server.log")
    )

    # This is used both as part of URLs and local filenames, so it must not start with a "/"
    cfg["SERVER_DATA_PATH"] = mount_path if cfg["ENV"] != "development" else ""
    # The prefix is appended to the base URL, to create relative URLs.
    # Since the k8s deployment is served at /dqm/dqm-square, we always need to append
    # to the base URL (cmsweb.cern.ch) to have relative URLs.
    cfg["SERVER_URL_PREFIX"] = (
        os.environ.get("SERVER_URL_PREFIX", os.path.join("dqm", "dqm-square"))
        if cfg["ENV"] != "development"
        else ""
    )
    cfg["CMSWEB_FRONTEND_PROXY_URL"] = os.environ.get(
        "CMSWEB_FRONTEND_PROXY_URL",
        # If value is not found in .env
        (
            "https://cmsweb-testbed.cern.ch/dqm/dqm-square-origin-rubu"
            if cfg["ENV"] == "testbed"
            else (
                "https://cmsweb-testbed.cern.ch/dqm/dqm-square-origin-rubu"
                if cfg["ENV"] == "production"
                else (
                    "https://cmsweb-testbed.cern.ch/dqm/dqm-square-origin-rubu"
                    if cfg["ENV"] == "test4"
                    else "https://cmsweb-testbed.cern.ch/dqm/dqm-square-origin-rubu"
                )
            )
        ),
    )

    # FFF simulator machine
    # This is the machine that the grabber will try to access
    # through CMSWEB_FRONTEND_PROXY_URL
    cfg["SERVER_FFF_MACHINE"] = os.environ.get(
        "SERVER_FFF_MACHINE", "dqmrubu-c2a06-03-01"
    )

    # List of hostnames for playback machines
    cfg["FFF_PLAYBACK_MACHINES"] = os.environ.get(
        "FFF_PLAYBACK_MACHINES",
        "dqmrubu-c2a06-03-01;dqmfu-c2b01-45-01;dqmfu-c2b02-45-01",
    ).split(";")

    # List of hostnames for production machines
    cfg["FFF_PRODUCTION_MACHINES"] = os.environ.get(
        "FFF_PRODUCTION_MACHINES",
        "dqmrubu-c2a06-01-01;dqmfu-c2b03-45-01;dqmfu-c2b04-45-01",
    ).split(";")

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
    cfg["SERVER_SIMULATOR_RUN_KEYS"] = "cosmic_run,pp_run,hi_run"

    cfg["GRABBER_LOG_PATH_PRODUCTION"] = (
        os.path.join("/", mount_path, "log/grabber_production.log")
        if cfg["ENV"] != "development"
        else "log/grabber_production.log"
    )
    cfg["GRABBER_LOG_PATH_PLAYBACK"] = (
        os.path.join("/", mount_path, "log/grabber_playback.log")
        if cfg["ENV"] != "development"
        else "log/grabber_playback.log"
    )

    cfg["GRABBER_LOG_PATH"] = (
        os.path.join("/", mount_path, "log/grabber.log")
        if cfg["ENV"] != "development"
        else "log/grabber.log"
    )
    cfg["GRABBER_DEBUG"] = os.environ.get("GRABBER_DEBUG", False)
    # MACHETE
    if isinstance(cfg["GRABBER_DEBUG"], str):
        cfg["GRABBER_DEBUG"] = True if cfg["GRABBER_DEBUG"] == "True" else False

    cfg["DB_PLAYBACK_URI"] = format_db_uri(
        username=os.environ.get("POSTGRES_USERNAME", "postgres"),
        password=os.environ.get("POSTGRES_PASSWORD", "postgres"),
        host=os.environ.get("POSTGRES_HOST", "127.0.0.1"),
        port=os.environ.get("POSTGRES_PORT", 5432),
        db_name=os.environ.get("POSTGRES_PLAYBACK_DB_NAME", "postgres"),
    )
    cfg["DB_PRODUCTION_URI"] = format_db_uri(
        username=os.environ.get("POSTGRES_USERNAME", "postgres"),
        password=os.environ.get("POSTGRES_PASSWORD", "postgres"),
        host=os.environ.get("POSTGRES_HOST", "127.0.0.1"),
        port=os.environ.get("POSTGRES_PORT", 5432),
        db_name=os.environ.get("POSTGRES_PRODUCTION_DB_NAME", "postgres_production"),
    )
    cfg["TIMEZONE"] = TIMEZONE
    return cfg


### Other
def dump_tmp_file(data: any, path: str, prefix: str, postfix: str) -> str:
    f = tempfile.NamedTemporaryFile(
        mode="w", prefix=prefix, suffix=postfix, dir=path, delete=False
    )
    f.write(data)
    f.close()
    return os.path.basename(f.name)
