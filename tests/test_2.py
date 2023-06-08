# tests to check Flask server
# TODO create tests using testing DB
import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

import pytest
from sqlalchemy import create_engine
from sqlalchemy_utils import create_database, database_exists, drop_database
import server
from db import DQM2MirrorDB
from custom_logger import dummy_log
from dqmsquare_cfg import format_db_uri, load_cfg


@pytest.fixture
def testing_database():
    cfg = load_cfg()
    db_uri = format_db_uri(
        env=cfg["ENV"],
        username=os.environ.get("POSTGRES_USERNAME_TEST", "postgres"),
        password=os.environ.get("POSTGRES_PASSWORD_TEST", "postgres"),
        host=os.environ.get("POSTGRES_HOST_TEST", "127.0.0.1"),
        port=os.environ.get("POSTGRES_PORT_TEST", 5432),
        db_name=os.environ.get("POSTGRES_PLAYBACK_DB_NAME_TEST", "postgres_test"),
    )

    engine = create_engine(db_uri)
    if not database_exists(engine.url):
        create_database(db_uri)

    db = DQM2MirrorDB(
        log=dummy_log(),
        db=db_uri,
        server=False,
    )
    yield db
    drop_database(db_uri)


@pytest.fixture
def app(testing_database):
    app = server.gunicorn_app
    app.config.update(
        {
            "TESTING": True,
        }
    )
    yield app


@pytest.fixture
def client(app):
    return app.test_client()


def test_server_1(client):
    response = client.get("/")
    assert b"// DQM RUNS PAGE //" in response.data


def test_server_2(client):
    response = client.get("/timeline/")
    assert b"// DQM TIMELINE PAGE //" in response.data


def test_server_3(client):
    response = client.get("/cr/")
    assert b"/cr/login" in response.data
