# tests to check Flask server
import pytest
import dqmsquare_server_flask

# TODO create tests using testing DB


@pytest.fixture()
def app():
    app = dqmsquare_server_flask.gunicorn_app
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
