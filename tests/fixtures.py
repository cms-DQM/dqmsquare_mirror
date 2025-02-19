import os
import sys
import pickle
import pytest
import sqlalchemy
from datetime import datetime
from sqlalchemy import create_engine, text
from sqlalchemy_utils import create_database, database_exists, drop_database
from sqlalchemy.exc import IntegrityError
from flask import Flask

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
import server
from custom_logger import dummy_log
from db import DQM2MirrorDB
from dqmsquare_cfg import load_cfg

DB_PROD_NAME = "postgres_production_test"
DB_PLAY_NAME = "postgres_playback_test"
MAGIC_NUMBER = 69420
MAGIC_RELEASE = "CMSSW_6_6_6_patch6"
MAGIC_HOSTNAME = "dqmfu-c9b99-99-99"
MAGIC_HOSTNAME_2 = "dqmfu-c0b00-00-00"
MAGIC_HOSTNAME_CENSORED = "dqmfu-c9b99-.."
MAGIC_HOSTNAME_2_CENSORED = "dqmfu-c0b00-.."
PRODUCTION_MACHINES = [
    "bu-c2f11-09-01",
    "fu-c2f11-11-01",
    "fu-c2f11-11-02",
    "fu-c2f11-11-03",
    "fu-c2f11-11-04",
]
INVALID_METADATA = {
    "id": "20250113-145715_comparison_base_0113_CMSSW_14_2_0_pre3_46854_vs_comparison_comp_0113_CMSSW_14_2_0_pre3_46928",
    "base": 1111,
    "comp": ("hehehe"),
    "comp_prs": None,
    "base_prs": "hehe",
    "comparison_report_html": "",
    "timestamp": 99999,
}
RUN_NUMBER_GRAPHS = 358792
CLUSTER_STATUS = {
    MAGIC_HOSTNAME: {"up": False, "msg": "TEST"},
    MAGIC_HOSTNAME_2: {"up": False, "msg": "TEST"},
}  # Cluster status with many hosts in it
CLUSTER_STATUS_RESULT = {
    "name": MAGIC_HOSTNAME_CENSORED,
    "is_up": False,
    "message": "TEST",
}
CLUSTER_STATUS_RESULT_2 = {
    "name": MAGIC_HOSTNAME_2_CENSORED,
    "is_up": False,
    "message": "TEST",
}


def get_or_create_db(
    db_uri: str, username: str, password: str, host: str, port: int, db_name: str
):
    engine: sqlalchemy.engine.Engine = create_engine(db_uri)
    if not database_exists(engine.url):
        print(f"Creating database {db_uri}")
        create_database(db_uri)
    return DQM2MirrorDB(
        log=dummy_log(),
        username=username,
        password=password,
        host=host,
        port=port,
        db_name=db_name,
        server=False,
    )


def format_entry_to_db_entry(graph_entry: list, datetime_cols: list):
    return_value = ""
    for i, col in enumerate(graph_entry):
        if i in datetime_cols:
            return_value += f"'{col.isoformat()}', "
        else:
            return_value += (
                f"""{"'" + str(col).replace("'", "''") + "'" if col else 'NULL'}, """
            )

    return return_value[:-2]


def get_valid_metadata(i: int = 0) -> dict:
    return {
        "id": f"{datetime.now().strftime(r'%Y%m%d')}-{datetime.now().strftime(r'%H%M%S')}_comparison_base_0113_vs_comparison_comp_0113_{MAGIC_RELEASE}_{MAGIC_NUMBER+i}",
        "base": MAGIC_RELEASE,
        "comp": MAGIC_RELEASE,
        "comp_prs": [],
        "base_prs": [MAGIC_NUMBER + i],
        "timestamp": datetime.now(),
        "comparison_report_html": "<h1>THIS IS VALID HTML</h1>",
    }


VALID_METADATA = get_valid_metadata()


def fill_db(db: DQM2MirrorDB, extra: bool = False) -> None:
    runs = []
    graphs = []
    runs_file = os.path.join(
        os.path.dirname(os.path.realpath(__file__)), "runs_data.pkl"
    )
    graphs_file = os.path.join(
        os.path.dirname(os.path.realpath(__file__)), "graphs_data.pkl"
    )

    print(f"Filling database {db.db_uri} using files {runs_file}, {graphs_file}")
    with open(runs_file, "rb") as f:
        runs = pickle.load(f)
    with open(graphs_file, "rb") as f:
        graphs = pickle.load(f)

    with db.engine.connect() as cur:
        session = db.Session(bind=cur)
        for run in runs:
            try:
                session.execute(
                    text(
                        "INSERT into runs "
                        + f"""({str(db.TB_DESCRIPTION_RUNS_COLS).replace("[", "").replace("]", "").replace("'", "")}) """
                        + f"""VALUES ({format_entry_to_db_entry(run, [13])})"""
                    )
                )
                session.commit()
            except IntegrityError as e:
                print("Skipping already inserted data", e)
                continue
            except Exception as e:
                print("Error when creating run fixture:", e)
                session.rollback()

        for graph in graphs:
            try:
                session.execute(
                    text(
                        "INSERT into graphs "
                        + f"""({str(db.TB_DESCRIPTION_GRAPHS_COLS).replace("[", "").replace("]", "").replace("'", "")}) """
                        + f"""VALUES ({format_entry_to_db_entry(graph, [3, 4])})"""
                    )
                )
                session.commit()
            except IntegrityError as e:
                print(f"Skipping already inserted data")
                continue
            except Exception as e:
                print("Error when creating graph fixture:", e)
                session.rollback()
    if extra:
        # Add a comparison report
        db.fill_cmssw_comparison_report(
            **VALID_METADATA,
        )
        db.fill_cluster_status(CLUSTER_STATUS)


@pytest.fixture(scope="session")
def dqm2_config():
    # If there's a local .env file, it will be used to override the environment vars
    config: dict = load_cfg()
    config["DB_PRODUCTION_NAME"] = DB_PROD_NAME
    config["DB_PLAYBACK_NAME"] = DB_PLAY_NAME
    yield config


@pytest.fixture(scope="function")
def db_test_db():
    """
    Test DB for dedicated db tests. This should be dropped after
    each test.
    """
    username = os.environ.get("POSTGRES_USERNAME", "postgres")
    password = os.environ.get("POSTGRES_PASSWORD", "postgres")
    host = os.environ.get("POSTGRES_HOST", "127.0.0.1")
    port = int(os.environ.get("POSTGRES_PORT", 5432))
    db_name = DB_PLAY_NAME
    db_uri = DQM2MirrorDB.format_db_uri(
        username=username, password=password, host=host, port=port, db_name=db_name
    )

    db: DQM2MirrorDB = get_or_create_db(
        db_uri=db_uri,
        username=username,
        password=password,
        host=host,
        port=port,
        db_name=db_name,
    )

    fill_db(db, extra=False)
    yield db
    drop_database(db_uri)


@pytest.fixture(scope="module")
def server_test_dbs():
    """
    Test DBs for server-related tests. They should persist for all
    the server tests as most server tests rely on the same data
    and they only need to read.
    """
    username = os.environ.get("POSTGRES_USERNAME", "postgres")
    password = os.environ.get("POSTGRES_PASSWORD", "postgres")
    host = os.environ.get("POSTGRES_HOST", "127.0.0.1")
    port: int = int(os.environ.get("POSTGRES_PORT", 5432))

    db_prod_uri: str = DQM2MirrorDB.format_db_uri(
        username=username, password=password, host=host, port=port, db_name=DB_PROD_NAME
    )
    db_play_uri: str = DQM2MirrorDB.format_db_uri(
        username=username, password=password, host=host, port=port, db_name=DB_PLAY_NAME
    )
    db_prod: DQM2MirrorDB = get_or_create_db(
        db_uri=db_prod_uri,
        username=username,
        password=password,
        host=host,
        port=port,
        db_name=DB_PROD_NAME,
    )
    db_play: DQM2MirrorDB = get_or_create_db(
        db_uri=db_play_uri,
        username=username,
        password=password,
        host=host,
        port=port,
        db_name=DB_PLAY_NAME,
    )
    fill_db(db_prod, extra=True)
    fill_db(db_play, extra=True)
    yield db_prod, db_play
    drop_database(db_prod_uri)
    drop_database(db_play_uri)


@pytest.fixture
def app(dqm2_config: dict, server_test_dbs: tuple[DQM2MirrorDB, DQM2MirrorDB]):
    app: Flask = server.create_app(dqm2_config)
    app.config.update(
        {
            "TESTING": True,
        }
    )
    yield app


@pytest.fixture
def client(app: Flask):
    """Returns a FlaskClient (An instance of :class:`flask.testing.TestClient`)"""
    with app.test_client() as client:
        yield client
