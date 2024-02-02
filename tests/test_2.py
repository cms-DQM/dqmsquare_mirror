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


def get_or_create_db(db_uri: str):
    engine = create_engine(db_uri)
    if not database_exists(engine.url):
        create_database(db_uri)
    return DQM2MirrorDB(
        log=dummy_log(),
        db_uri=db_uri,
        server=False,
    )


@pytest.fixture
def cfg():
    yield load_cfg()


@pytest.fixture
def testing_databases():
    db_uri_prod = format_db_uri(
        username=os.environ.get("POSTGRES_USERNAME", "postgres"),
        password=os.environ.get("POSTGRES_PASSWORD", "postgres"),
        host=os.environ.get("POSTGRES_HOST", "127.0.0.1"),
        port=os.environ.get("POSTGRES_PORT", 5432),
        db_name=os.environ.get("POSTGRES_PRODUCTION_DB_NAME") + "_test",
    )
    db_uri_playback = format_db_uri(
        username=os.environ.get("POSTGRES_USERNAME", "postgres"),
        password=os.environ.get("POSTGRES_PASSWORD", "postgres"),
        host=os.environ.get("POSTGRES_HOST", "127.0.0.1"),
        port=os.environ.get("POSTGRES_PORT", 5432),
        db_name=os.environ.get("POSTGRES_PLAYBACK_DB_NAME") + "_test",
    )

    yield get_or_create_db(db_uri_prod), get_or_create_db(db_uri_playback)
    drop_database(db_uri_prod)
    drop_database(db_uri_playback)


@pytest.fixture
def app(cfg, testing_databases: list[DQM2MirrorDB]):
    cfg_test = cfg
    # Override databases for the test
    cfg_test["DB_PRODUCTION_URI"] = testing_databases[0].db_uri
    cfg_test["DB_PLAYBACK_URI"] = testing_databases[1].db_uri
    print(cfg_test["DB_PRODUCTION_URI"], cfg_test["DB_PLAYBACK_URI"])

    app = server.create_app(cfg_test)
    app.config.update(
        {
            "TESTING": True,
        }
    )
    yield app


@pytest.fixture
def client(app):
    """A Flask test client. An instance of :class:`flask.testing.TestClient`
    by default.
    """
    with app.test_client() as client:
        yield client


def test_server_1(client):
    response = client.get("/")
    assert response.status_code == 200


def test_server_2(client):
    response = client.get("/timeline/")
    # assert b"// DQM TIMELINE PAGE //" in response.data
    assert response.status_code == 200


def test_server_3(client):
    response = client.get("/cr/")
    assert response.status_code == 302
    assert response.headers.get("Location") == "/cr/login/"
