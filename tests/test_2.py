# tests to check Flask server
# TODO create tests using testing DB
import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

import pytest
import server


@pytest.fixture()
def app():
    app = server.gunicorn_app
    app.config.update(
        {
            "TESTING": True,
        }
    )
    yield app


@pytest.fixture()
def client(app):
    return app.test_client()


def test_1(client):
    response = client.get("/dqm/dqm-square-k8/")
    assert b"// DQM RUNS PAGE //" in response.data


def test_2(client):
    response = client.get("/dqm/dqm-square-k8/timeline/")
    assert b"// DQM TIMELINE PAGE //" in response.data


def test_3(client):
    response = client.get("/dqm/dqm-square-k8/cr/")
    assert b"/dqm/dqm-square-k8/cr/login" in response.data
