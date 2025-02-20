# Tests to check DB and data filling and fetching
import os
import sys
import json

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
import pytest
from truth_values import TRUTH_VALUES_RUNS, TRUTH_VALUES_GRAPHS
from datetime import datetime
from db import DQM2MirrorDB, DEFAULT_DATETIME
from dqmsquare_cfg import TZ
from sqlalchemy.engine.row import RowMapping
from sqlalchemy.exc import IntegrityError

# Needed to be passed as a fixture
from fixtures import (
    db_test_db,
    MAGIC_NUMBER,
    MAGIC_RELEASE,
    MAGIC_HOSTNAME,
    MAGIC_HOSTNAME_CENSORED,
    MAGIC_HOSTNAME_2,
    MAGIC_HOSTNAME_2_CENSORED,
    PRODUCTION_MACHINES,
    VALID_METADATA,
    INVALID_METADATA,
    CLUSTER_STATUS,
    CLUSTER_STATUS_RESULT,
    CLUSTER_STATUS_RESULT_2,
)


class TestDBLatestRevision:
    def test_get(self, db_test_db: DQM2MirrorDB):
        revs = [
            6001382,
            7912099,
            2730841,
            2762604,
            12811635,
        ]
        revs = [db_test_db.get_latest_revision(host) for host in PRODUCTION_MACHINES]
        assert all(
            [
                db_test_db.get_latest_revision(host) == rev
                for host, rev in zip(PRODUCTION_MACHINES, revs)
            ]
        )


class TestDBRunsAround:
    def test_get(self, db_test_db: DQM2MirrorDB):
        test_runs = [358788, 358791, 358792]
        truth_answers = [
            [None, 358791],
            [358788, 358792],
            [None, 358791],
        ]
        answers = []

        for truth, run in zip(truth_answers, test_runs):
            around = db_test_db.get_runs_around(run)
            answer = sorted(around, key=lambda x: 0 if not x else x)
            x = (truth[0] == answer[0]) and (truth[1] == answer[1])
            answers += [x]
        assert all(answers)


class TestDBLogs:
    def test_get(self, db_test_db: DQM2MirrorDB):
        print("Check DQM2MirrorDB.get_logs()")
        test_ids = [
            "dqm-source-state-run358788-hostfu-c2f11-11-04-pid041551",
            "dqm-source-state-run358791-hostfu-c2f11-11-04-pid005346",
            "dqm-source-state-run358792-hostfu-c2f11-11-04-pid009963",
            "dqm-stats-fu-c2f11-11-03",
        ]
        truth_answers = [
            "/run358788_ls0009_streamDQM_sm-c2a11-43-01.jsn\\n']11-04_pid00041551\\n', '\\n-- process exit: 0 --\\n']",
            "g message count 0\\n', '\\n-- process exit: 0 --\\n']g message count 0\\n', '\\n-- process exit: 0 --\\n']",
            "ls0013_streamDQMCalibration_sm-c2a11-43-01.jsn\\n']_ls0465_streamDQMHistograms_sm-c2a11-43-01.jsn\\n']",
            None,
        ]

        for truth, id in zip(truth_answers, test_ids):
            logs = db_test_db.get_logs(id)
            if logs[0] and logs[1]:
                assert truth == (logs[0][-50:] + logs[1][-50:])
            else:
                assert logs[0] == truth and logs[1] == truth


class TestDBInfo:
    def test_get(self, db_test_db: DQM2MirrorDB):
        minmax = db_test_db.get_info()
        assert minmax[0] == 358788 and minmax[1] == 358792


class TestDBUpdateMinMax:
    def test_update(self, db_test_db: DQM2MirrorDB):
        db_test_db.update_min_max(350000, 360000)
        minmax = db_test_db.get_info()
        print(minmax)
        assert minmax[0] == 350000 and minmax[1] == 360000


class TestDBClients:
    def test_get(self, db_test_db: DQM2MirrorDB):
        clients_truth = [
            "beam",
            "beamhlt",
            "beampixel",
            "beamspotdip",
            "csc",
            "ctpps",
            "dt",
            "dt4ml",
            "ecal",
            "ecalcalib",
            "ecalgpu",
            "es",
            "fed",
            "gem",
            "hcal",
            "hcalcalib",
            "hcalgpu",
            "hcalreco",
            "hlt",
            "hlt_dqm_clientPB-live",
            "info",
            "l1tstage2",
            "l1tstage2emulator",
            "mutracking",
            "onlinebeammonitor",
            "pixel",
            "pixellumi",
            "rpc",
            "sistrip",
            "visualization-live",
            "visualization-live-secondInstance",
        ]
        clients = sorted(db_test_db.get_clients(0, 999999))
        minmax = db_test_db.get_info()
        assert all([c1 == c2 for c1, c2 in zip(clients, clients_truth)])


class TestDBTimelineData:
    def test_get(self, db_test_db: DQM2MirrorDB):
        truth = TRUTH_VALUES_RUNS
        answer = json.dumps(db_test_db.get_timeline_data(358791, 358791))
        assert truth == answer


class TestDBMirrorData:
    def test_get(self, db_test_db: DQM2MirrorDB):
        truth = "''''(),11112223333333334445566899999________ccimnorsu"  # Literally WTF
        answer = db_test_db.get_mirror_data(358788)[0]
        answer = ("".join(sorted(str(answer)))).strip()
        assert truth == answer


class TestDBGraphs:

    def test_get(self, db_test_db: DQM2MirrorDB):
        truth = TRUTH_VALUES_GRAPHS
        answer = db_test_db.get_graphs(358792)
        for i, item in enumerate(truth):
            if isinstance(item, float):  # timestamp
                assert TZ.localize(datetime.fromtimestamp(item)) == TZ.localize(
                    datetime.fromtimestamp(answer[i])
                )
            elif isinstance(answer[i], dict):
                assert item == json.dumps(answer[i])
            else:
                assert item == answer[i]

    def test_fill_and_get(self, db_test_db: DQM2MirrorDB):
        truth = [
            123456,
            -1,
            "id",
            DEFAULT_DATETIME.timestamp(),
            DEFAULT_DATETIME.timestamp(),
            "",
            "",
        ]
        header = {"_id": "id", "run": "123456", "extra": {}}
        document = {"extra": {None: None}}
        db_test_db.fill_graph(header, document)
        answer = db_test_db.get_graphs(123456)
        assert all([c1 == c2 for c1, c2 in zip(truth, answer)])


class TestDBRuns:
    def test_fill_and_get(self, db_test_db: DQM2MirrorDB):
        truth = (
            "id",
            "",
            123456,
            -1,
            "",
            -1,
            -1,
            -1.0,
            -1,
            -1,
            "",
            "",
            "",
            DEFAULT_DATETIME,
            "",
        )
        header = {"_id": "id", "run": "123456"}
        document = {}
        db_test_db.fill_run(header, document)
        answer = db_test_db.get_run(run_start=123456, run_end=123456)[0]

        assert all([c1 == c2 for c1, c2 in zip(truth, answer)])


class TestDBClusterHosts:
    def test_fill_and_get(self, db_test_db: DQM2MirrorDB):
        db_test_db.fill_cluster_host(MAGIC_HOSTNAME)
        r = db_test_db.get_cluster_host(name=MAGIC_HOSTNAME, censor=False)
        assert (
            r and r["name"] == MAGIC_HOSTNAME
        )  # Non censoring the output results in the proper hostname
        r = db_test_db.get_cluster_host(name=MAGIC_HOSTNAME)
        assert (
            r and r["name"] == MAGIC_HOSTNAME_CENSORED
        )  # Censoring "hides" the hostname

    def test_nonexistent(self, db_test_db: DQM2MirrorDB):
        r = db_test_db.get_cluster_host(name=MAGIC_HOSTNAME_2)
        assert not r  # This hostname has not been created yet

    def test_get_or_create(self, db_test_db: DQM2MirrorDB):
        r, created = db_test_db.get_or_create_cluster_host(name=MAGIC_HOSTNAME_2)
        assert (
            created
            and r["name"] == MAGIC_HOSTNAME_2_CENSORED
            and r["id"] == db_test_db.get_cluster_host(name=MAGIC_HOSTNAME_2)["id"]
        )


class TestDBClusterStatus:

    def test_fill_and_get(self, db_test_db: DQM2MirrorDB):
        r = db_test_db.fill_cluster_status(CLUSTER_STATUS)
        assert (
            r[0] and r[0].host_id == db_test_db.get_cluster_host(MAGIC_HOSTNAME)["id"]
        )
        assert (
            r[1] and r[1].host_id == db_test_db.get_cluster_host(MAGIC_HOSTNAME_2)["id"]
        )
        r = db_test_db.get_cluster_status()
        r[0].pop("created_at")
        r[1].pop("created_at")
        assert r[0] == CLUSTER_STATUS_RESULT
        assert r[1] == CLUSTER_STATUS_RESULT_2


class TestDBCMSSWPR:
    def test_db_cmssw_pr(self, db_test_db: DQM2MirrorDB):
        r = db_test_db.get_cmssw_pr(MAGIC_NUMBER)
        assert not r
        db_test_db.fill_cmssw_pr(MAGIC_NUMBER)
        r = db_test_db.get_cmssw_pr(MAGIC_NUMBER)
        assert r and "pr_num" in r and r["pr_num"] == MAGIC_NUMBER
        with pytest.raises(AssertionError):
            db_test_db.fill_cmssw_pr(str(MAGIC_NUMBER))


class TestDBCMSSWReleasePlain:
    def test_get_empty(self, db_test_db: DQM2MirrorDB):
        r = db_test_db.get_cmssw_release(MAGIC_RELEASE)
        assert not r

    def test_fill(self, db_test_db: DQM2MirrorDB):
        r = db_test_db.fill_cmssw_release(MAGIC_RELEASE)
        assert r and "cmssw_version" in r and r["cmssw_version"] == MAGIC_RELEASE

    def test_fill_wrong_input(self, db_test_db: DQM2MirrorDB):
        with pytest.raises(AssertionError):
            db_test_db.fill_cmssw_release(6565656565)

    def test_get_existing(self, db_test_db: DQM2MirrorDB):
        r = db_test_db.fill_cmssw_release(MAGIC_RELEASE)
        r2, created = db_test_db.get_or_create_cmssw_release(MAGIC_RELEASE)
        assert r == r2
        assert not created


class TestDBCMSSWReleaseWithPRs:
    def test_fill_duplicate_pr(self, db_test_db: DQM2MirrorDB):
        with pytest.raises(AssertionError):  # Duplicate PR number
            db_test_db.fill_cmssw_release_with_prs(
                cmssw_release=MAGIC_RELEASE, pr_nums=[MAGIC_NUMBER, MAGIC_NUMBER]
            )

    def test_fill_and_get(self, db_test_db: DQM2MirrorDB):
        r1 = db_test_db.fill_cmssw_release_with_prs(
            cmssw_release=MAGIC_RELEASE, pr_nums=[MAGIC_NUMBER, MAGIC_NUMBER + 1]
        )
        r2, created = db_test_db.get_or_create_cmssw_release_with_prs(
            cmssw_release=MAGIC_RELEASE, pr_nums=[MAGIC_NUMBER, MAGIC_NUMBER + 1]
        )
        assert not created
        assert r1 == r2

    def test_fill_and_get_no_prs(self, db_test_db: DQM2MirrorDB):
        r1 = db_test_db.fill_cmssw_release_with_prs(
            cmssw_release=MAGIC_RELEASE, pr_nums=[]
        )
        r2, created = db_test_db.get_or_create_cmssw_release_with_prs(
            cmssw_release=MAGIC_RELEASE, pr_nums=[]
        )
        assert not created
        assert r1 == r2


class TestDBComparisonReports:
    def test_fill_invalid(self, db_test_db: DQM2MirrorDB):
        with pytest.raises(AssertionError):
            # Expects more metadata
            db_test_db.fill_cmssw_comparison_report(
                **INVALID_METADATA,
            )

    def test_get_empty(self, db_test_db: DQM2MirrorDB):
        r = db_test_db.get_cmssw_comparison_reports(paginate=False)
        assert not r

    def test_fill(self, db_test_db: DQM2MirrorDB):
        r1 = db_test_db.fill_cmssw_comparison_report(
            **VALID_METADATA,
        )
        r = db_test_db.get_cmssw_comparison_reports(id=r1.id, paginate=False)
        r2 = r[0]
        assert r1 == r2
        assert (
            isinstance(r1, RowMapping)
            and isinstance(r2, RowMapping)
            and isinstance(r, list)
        )

    def test_fill_duplicate(self, db_test_db: DQM2MirrorDB):
        db_test_db.fill_cmssw_comparison_report(
            **VALID_METADATA,
        )
        with pytest.raises(IntegrityError):  # Try to reinsert the same id
            db_test_db.fill_cmssw_comparison_report(
                **VALID_METADATA,
            )
