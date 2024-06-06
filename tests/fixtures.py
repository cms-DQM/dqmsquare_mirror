import os
import sys
import pickle
import pytest
import sqlalchemy
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


def fill_db(db: DQM2MirrorDB) -> None:
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
                print(f"Skipping already inserted data", e)
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


@pytest.fixture
def dqm2_config():
    # If there's a local .env file, it will be used to override the environment vars
    config: dict = load_cfg()
    config["DB_PRODUCTION_NAME"] = DB_PROD_NAME
    config["DB_PLAYBACK_NAME"] = DB_PLAY_NAME
    yield config


@pytest.fixture
def testing_database():
    username = os.environ.get("POSTGRES_USERNAME", "postgres")
    password = os.environ.get("POSTGRES_PASSWORD", "postgres")
    host = os.environ.get("POSTGRES_HOST", "127.0.0.1")
    port = int(os.environ.get("POSTGRES_PORT", 5432))
    db_name = "postgres_test"
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

    fill_db(db)
    yield db
    drop_database(db_uri)


@pytest.fixture
def testing_databases():
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
    fill_db(db_prod)
    fill_db(db_play)
    yield db_prod, db_play
    drop_database(db_prod_uri)
    drop_database(db_play_uri)


@pytest.fixture
def app(dqm2_config: dict, testing_databases: tuple[DQM2MirrorDB, DQM2MirrorDB]):
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
