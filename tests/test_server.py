from flask.testing import FlaskClient


# Tests to check Flask server and its responses
# Needed to be passed as a fixture
from db import DQM2MirrorDB
from fixtures import (
    app,
    dqm2_config,
    client,
    server_test_dbs,
    RUN_NUMBER_GRAPHS,
    CLUSTER_STATUS_RESULT,
    CLUSTER_STATUS_RESULT_2,
)
from truth_values import TRUTH_VALUES_GRAPHS


class TestServerHome:
    def test_get(self, client: FlaskClient):
        response = client.get("/")
        assert response.status_code == 200


class TestServerTimeline:
    def test_get(self, client: FlaskClient):
        response = client.get("/timeline/")
        # assert b"// DQM TIMELINE PAGE //" in response.data
        assert response.status_code == 200


class TestServerCR:
    def test_server_cr(self, client: FlaskClient):
        response = client.get("/cr/")
        assert response.status_code == 302
        assert response.headers.get("Location") == "/cr/login/"


class TestServerRuns:
    def test_get_wrong_arg(self, client: FlaskClient):
        # Wrong GET argument
        response = client.get("/api/get_run?run=381574&db_name=production")
        assert response.status_code == 400

    def test_get_inject(self, client: FlaskClient):
        # Dumb string instead of number
        response = client.get(
            "/api/get_run?run=;DROP DATABASE postgres_test&db=production"
        )
        assert response.status_code == 400

    def test_get_proper_1(self, client: FlaskClient):
        # Proper request
        response = client.get("/api/get_run?run=381574&db=production")
        assert response.status_code == 200
        response = response.json
        assert isinstance(response, list)
        assert response[0][0] == 358792
        assert response[0][1] == None

    def test_get_proper_2(self, client: FlaskClient):
        response = client.get("/api/get_run?run=358791&db=production")
        assert response.status_code == 200
        response = response.json
        assert isinstance(response, list)
        assert response[0][0] == 358788
        assert response[0][1] == 358792


class TestServerClients:
    def test_get_wrong_arg(self, client: FlaskClient):
        # Wrong GET argument
        response = client.get(
            "/api/get_clients?from=377187&to=381574&db_name=production"
        )
        assert response.status_code == 400

    def test_get_wrong_proper(self, client: FlaskClient):
        # Proper request
        response = client.get("/api/get_clients?from=358788&to=358792&db=production")
        assert response.status_code == 200
        response = response.json
        assert isinstance(response, list)
        assert response[0] == "beam"
        assert response[-1] == "visualization-live-secondInstance"


class TestServerAPI:
    def test_get_comparison_reports(
        self,
        client: FlaskClient,
        server_test_dbs: tuple[DQM2MirrorDB, DQM2MirrorDB],
    ):
        r = client.get("/api/get_cmssw_comparison_reports").json
        assert r and isinstance(r, dict)
        assert all(r and [key in r for key in ["page", "total_pages"]])

    def test_get_graph_no_args(
        self,
        client: FlaskClient,
        server_test_dbs: tuple[DQM2MirrorDB, DQM2MirrorDB],
    ):
        r = client.get("/api/get_graph").json
        assert not r

    def test_get_graph_no_args_w_run(
        self,
        client: FlaskClient,
        server_test_dbs: tuple[DQM2MirrorDB, DQM2MirrorDB],
    ):
        r = client.get(
            f"/api/get_graph?run={RUN_NUMBER_GRAPHS}",
        )
        assert not r.json and r.status_code == 400

    def test_get_graph_w_args(
        self,
        client: FlaskClient,
        server_test_dbs: tuple[DQM2MirrorDB, DQM2MirrorDB],
    ):
        r = client.get(
            f"/api/get_graph?run={RUN_NUMBER_GRAPHS}&db=playback",
        ).json
        assert r and isinstance(r, list)
        for i in range(5):
            assert r[i] == TRUTH_VALUES_GRAPHS[i]
        t_eval = eval(TRUTH_VALUES_GRAPHS[5])
        assert r[5] == t_eval

    def test_get_run_no_args(
        self,
        client: FlaskClient,
        server_test_dbs: tuple[DQM2MirrorDB, DQM2MirrorDB],
    ):

        r = client.get("/api/get_run")
        assert not r.json and r.status_code == 400

    def test_get_run_w_args(
        self,
        client: FlaskClient,
        server_test_dbs: tuple[DQM2MirrorDB, DQM2MirrorDB],
    ):
        r = client.get(f"/api/get_run?run={RUN_NUMBER_GRAPHS}&db=playback")
        assert r.status_code == 200

        r = r.json
        assert isinstance(r, list) and isinstance(r[0], list) and isinstance(r[1], list)

    def test_get_cluster_status(
        self, client: FlaskClient, server_test_dbs: tuple[DQM2MirrorDB, DQM2MirrorDB]
    ):
        r = client.get("/api/get_cluster_status")
        assert r.status_code == 200
        r = r.json
        assert r and isinstance(r, list) and len(r) == 2
        r[0].pop("created_at")
        r[1].pop("created_at")
        assert r[0] == CLUSTER_STATUS_RESULT and r[1] == CLUSTER_STATUS_RESULT_2
