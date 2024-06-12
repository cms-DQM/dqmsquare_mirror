import json
from flask.testing import FlaskClient

# Tests to check Flask server and its responses
# Needed to be passed as a fixture
from fixtures import app, dqm2_config, client, testing_databases, testing_database


def test_server_home(client: FlaskClient):
    response = client.get("/")
    assert response.status_code == 200


def test_server_timeline(client: FlaskClient):
    response = client.get("/timeline/")
    # assert b"// DQM TIMELINE PAGE //" in response.data
    assert response.status_code == 200


def test_server_cr(client: FlaskClient):
    response = client.get("/cr/")
    assert response.status_code == 302
    assert response.headers.get("Location") == "/cr/login/"


def test_server_get_run(client: FlaskClient):
    # Wrong GET argument
    response = client.get("/api?what=get_run&run=381574&db_name=production")
    assert response.status_code == 400

    # Dumb string instead of number
    response = client.get(
        "/api?what=get_run&run=;DROP DATABASE postgres_test&db=production"
    )
    assert response.status_code == 400

    # Proper request
    response = client.get("/api?what=get_run&run=381574&db=production")
    assert response.status_code == 200
    response = json.loads(response.text)
    assert isinstance(response, list)
    assert response[0][0] == 358792
    assert response[0][1] == None

    response = client.get("/api?what=get_run&run=358791&db=production")
    assert response.status_code == 200
    response = json.loads(response.text)
    assert isinstance(response, list)
    assert response[0][0] == 358788
    assert response[0][1] == 358792


def test_server_get_clients(client: FlaskClient):
    # Wrong GET argument
    response = client.get(
        "/api?what=get_clients&from=377187&to=381574&db_name=production"
    )
    assert response.status_code == 400

    # Proper request
    response = client.get("/api?what=get_clients&from=358788&to=358792&db=production")
    assert response.status_code == 200
    response = json.loads(response.text)
    assert isinstance(response, list)
    assert response[0] == "beam"
    assert response[-1] == "visualization-live-secondInstance"
