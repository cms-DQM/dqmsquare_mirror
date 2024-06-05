import os
import sys
import pickle
import pytest
import sqlalchemy
from sqlalchemy import create_engine, text
from sqlalchemy_utils import create_database, database_exists, drop_database
from flask import Flask

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
import server
from custom_logger import dummy_log
from db import DQM2MirrorDB
from dqmsquare_cfg import load_cfg


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
    with open(
        os.path.join(os.path.dirname(os.path.realpath(__file__)), "runs_data.pkl"), "rb"
    ) as f:
        runs = pickle.load(f)
    with open(
        os.path.join(os.path.dirname(os.path.realpath(__file__)), "graphs_data.pkl"),
        "rb",
    ) as f:
        graphs = pickle.load(f)

    with db.engine.connect() as cur:
        session = db.Session(bind=cur)
        for run in runs:
            try:
                session.execute(
                    text(
                        f"""INSERT into runs ({str(db.TB_DESCRIPTION_RUNS_COLS).replace("[", "").replace("]", "").replace("'", "")}) VALUES ({format_entry_to_db_entry(run, [13])})"""
                    )
                )
                session.commit()
            except Exception as e:
                print("Error when creating run fixture:", e)
                session.rollback()

        for graph in graphs:
            try:
                session.execute(
                    text(
                        f"""INSERT into graphs ({str(db.TB_DESCRIPTION_GRAPHS_COLS).replace("[", "").replace("]", "").replace("'", "")}) VALUES ({format_entry_to_db_entry(graph, [3, 4])})"""
                    )
                )
                session.commit()
            except Exception as e:
                print("Error when creating graph fixture:", e)
                session.rollback()


@pytest.fixture
def testing_database():
    db_uri = DQM2MirrorDB.format_db_uri(
        username=os.environ.get("POSTGRES_USERNAME", "postgres"),
        password=os.environ.get("POSTGRES_PASSWORD", "postgres"),
        host=os.environ.get("POSTGRES_HOST", "127.0.0.1"),
        port=os.environ.get("POSTGRES_PORT", 5432),
        db_name="postgres_test",
    )
    engine = create_engine(db_uri)
    if not database_exists(engine.url):
        create_database(db_uri)
    db = DQM2MirrorDB(
        log=dummy_log(),
        username=os.environ.get("POSTGRES_USERNAME", "postgres"),
        password=os.environ.get("POSTGRES_PASSWORD", "postgres"),
        host=os.environ.get("POSTGRES_HOST", "127.0.0.1"),
        port=os.environ.get("POSTGRES_PORT", 5432),
        db_name="postgres_test",
        server=False,
    )

    fill_db(db)
    yield db
    drop_database(db_uri)


def get_or_create_db(
    db_uri: str, username: str, password: str, host: str, port: str, db_name: str
):
    engine: sqlalchemy.engine.Engine = create_engine(db_uri)
    if not database_exists(engine.url):
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


@pytest.fixture
def cfg():
    yield load_cfg()


@pytest.fixture
def testing_databases():
    db_uri_prod = DQM2MirrorDB.format_db_uri(
        username=os.environ.get("POSTGRES_USERNAME", "postgres"),
        password=os.environ.get("POSTGRES_PASSWORD", "postgres"),
        host=os.environ.get("POSTGRES_HOST", "127.0.0.1"),
        port=os.environ.get("POSTGRES_PORT", 5432),
        db_name=os.environ.get("POSTGRES_PRODUCTION_DB_NAME") + "_test",
    )
    db_uri_playback = DQM2MirrorDB.format_db_uri(
        username=os.environ.get("POSTGRES_USERNAME", "postgres"),
        password=os.environ.get("POSTGRES_PASSWORD", "postgres"),
        host=os.environ.get("POSTGRES_HOST", "127.0.0.1"),
        port=os.environ.get("POSTGRES_PORT", 5432),
        db_name=os.environ.get("POSTGRES_PLAYBACK_DB_NAME") + "_test",
    )
    db_prod = get_or_create_db(
        db_uri=db_uri_prod,
        username=os.environ.get("POSTGRES_USERNAME", "postgres"),
        password=os.environ.get("POSTGRES_PASSWORD", "postgres"),
        host=os.environ.get("POSTGRES_HOST", "127.0.0.1"),
        port=os.environ.get("POSTGRES_PORT", 5432),
        db_name=os.environ.get("POSTGRES_PRODUCTION_DB_NAME") + "_test",
    )
    db_play = get_or_create_db(
        db_uri=db_uri_playback,
        username=os.environ.get("POSTGRES_USERNAME", "postgres"),
        password=os.environ.get("POSTGRES_PASSWORD", "postgres"),
        host=os.environ.get("POSTGRES_HOST", "127.0.0.1"),
        port=os.environ.get("POSTGRES_PORT", 5432),
        db_name=os.environ.get("POSTGRES_PLAYBACK_DB_NAME") + "_test",
    )
    fill_db(db_prod)
    fill_db(db_play)
    yield db_prod, db_play
    drop_database(db_uri_prod)
    drop_database(db_uri_playback)


@pytest.fixture
def app(cfg, testing_databases: tuple[DQM2MirrorDB, DQM2MirrorDB]):
    cfg_test = cfg
    # Override databases for the test
    cfg_test["DB_PRODUCTION_URI"] = testing_databases[0].db_uri
    cfg_test["DB_PLAYBACK_URI"] = testing_databases[1].db_uri
    print(cfg_test["DB_PRODUCTION_URI"], cfg_test["DB_PLAYBACK_URI"])

    app: Flask = server.create_app(cfg_test)
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
