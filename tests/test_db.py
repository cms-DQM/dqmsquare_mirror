# Tests to check DB and data filling and fetching
import os
import sys
import json

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
import pytest
from truth_values import TEST_DB_7_TRUTH, TEST_DB_9_TRUTH
from datetime import datetime
from db import DQM2MirrorDB, DEFAULT_DATETIME
from dqmsquare_cfg import TZ
from sqlalchemy.exc import IntegrityError

# Needed to be passed as a fixture
from fixtures import (
    testing_database,
    MAGIC_NUMBER,
    MAGIC_RELEASE,
    MAGIC_HOSTNAME,
    MAGIC_HOSTNAME_CENSORED,
    MAGIC_HOSTNAME_2,
    MAGIC_HOSTNAME_2_CENSORED,
    PRODUCTION_MACHINES,
    VALID_METADATA,
    INVALID_METADATA,
)


def test_db_latest_revision(testing_database: DQM2MirrorDB):
    revs = [
        6001382,
        7912099,
        2730841,
        2762604,
        12811635,
    ]
    revs = [testing_database.get_latest_revision(host) for host in PRODUCTION_MACHINES]
    assert all(
        [
            testing_database.get_latest_revision(host) == rev
            for host, rev in zip(PRODUCTION_MACHINES, revs)
        ]
    )


def test_db_runs_around(testing_database: DQM2MirrorDB):
    test_runs = [358788, 358791, 358792]
    truth_answers = [
        [None, 358791],
        [358788, 358792],
        [None, 358791],
    ]
    answers = []

    for truth, run in zip(truth_answers, test_runs):
        around = testing_database.get_runs_around(run)
        answer = sorted(around, key=lambda x: 0 if not x else x)
        x = (truth[0] == answer[0]) and (truth[1] == answer[1])
        answers += [x]
    assert all(answers)


def test_db_logs(testing_database: DQM2MirrorDB):
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
        logs = testing_database.get_logs(id)
        if logs[0] and logs[1]:
            assert truth == (logs[0][-50:] + logs[1][-50:])
        else:
            assert logs[0] == truth and logs[1] == truth


def test_db_info(testing_database: DQM2MirrorDB):
    minmax = testing_database.get_info()
    assert minmax[0] == 358788 and minmax[1] == 358792


def test_db_update_min_max(testing_database: DQM2MirrorDB):
    testing_database.update_min_max(350000, 360000)
    minmax = testing_database.get_info()
    print(minmax)
    assert minmax[0] == 350000 and minmax[1] == 360000


def test_db_clients(testing_database: DQM2MirrorDB):
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
    clients = sorted(testing_database.get_clients(0, 999999))
    minmax = testing_database.get_info()
    assert all([c1 == c2 for c1, c2 in zip(clients, clients_truth)])


def test_db_timeline_data(testing_database: DQM2MirrorDB):
    truth = TEST_DB_7_TRUTH
    answer = json.dumps(testing_database.get_timeline_data(358791, 358791))
    assert truth == answer


def test_db_mirror_data(testing_database: DQM2MirrorDB):
    truth = "''''(),11112223333333334445566899999________ccimnorsu"  # Literally WTF
    answer = testing_database.get_mirror_data(358788)[0]
    answer = ("".join(sorted(str(answer)))).strip()
    assert truth == answer


def test_db_get_graphs(testing_database: DQM2MirrorDB):
    truth = TEST_DB_9_TRUTH
    answer = testing_database.get_graphs(358792)
    for i, item in enumerate(truth):
        if isinstance(item, float):  # timestamp
            assert TZ.localize(datetime.fromtimestamp(item)) == TZ.localize(
                datetime.fromtimestamp(answer[i])
            )
        elif isinstance(answer[i], dict):
            assert item == json.dumps(answer[i])
        else:
            assert item == answer[i]


def test_db_graphs(testing_database: DQM2MirrorDB):
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
    testing_database.fill_graph(header, document)
    answer = testing_database.get_graphs(123456)
    assert all([c1 == c2 for c1, c2 in zip(truth, answer)])


def test_db_runs(testing_database: DQM2MirrorDB):
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
    testing_database.fill_run(header, document)
    answer = testing_database.get_run(run_start=123456, run_end=123456)[0]

    assert all([c1 == c2 for c1, c2 in zip(truth, answer)])


def test_db_cluster_hosts(testing_database: DQM2MirrorDB):
    testing_database.fill_cluster_host(MAGIC_HOSTNAME)
    r = testing_database.get_cluster_host(name=MAGIC_HOSTNAME, censor=False)
    assert (
        r and r["name"] == MAGIC_HOSTNAME
    )  # Non censoring the output results in the proper hostname
    r = testing_database.get_cluster_host(name=MAGIC_HOSTNAME)
    assert r and r["name"] == MAGIC_HOSTNAME_CENSORED  # Censoring "hides" the hostname

    r = testing_database.get_cluster_host(name=MAGIC_HOSTNAME_2)
    assert not r  # This hostname has not been created yet

    r, created = testing_database.get_or_create_cluster_host(name=MAGIC_HOSTNAME_2)
    assert (
        created
        and r["name"] == MAGIC_HOSTNAME_2_CENSORED
        and r["id"] == testing_database.get_cluster_host(name=MAGIC_HOSTNAME_2)["id"]
    )


def test_db_cluster_status(testing_database: DQM2MirrorDB):
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
    r = testing_database.fill_cluster_status(CLUSTER_STATUS)
    assert (
        r[0] and r[0].host_id == testing_database.get_cluster_host(MAGIC_HOSTNAME)["id"]
    )
    assert (
        r[1]
        and r[1].host_id == testing_database.get_cluster_host(MAGIC_HOSTNAME_2)["id"]
    )
    r = testing_database.get_cluster_status()
    r[0].pop("created_at")
    r[1].pop("created_at")
    assert r[0] == CLUSTER_STATUS_RESULT
    assert r[1] == CLUSTER_STATUS_RESULT_2


def test_db_cmssw_pr(testing_database: DQM2MirrorDB):
    r = testing_database.get_cmssw_pr(MAGIC_NUMBER)
    assert not r
    testing_database.fill_cmssw_pr(MAGIC_NUMBER)
    r = testing_database.get_cmssw_pr(MAGIC_NUMBER)
    assert r and "pr_num" in r and r["pr_num"] == MAGIC_NUMBER
    with pytest.raises(AssertionError):
        testing_database.fill_cmssw_pr(str(MAGIC_NUMBER))


def test_db_cmssw_release_plain(testing_database: DQM2MirrorDB):
    r = testing_database.get_cmssw_release(MAGIC_RELEASE)
    assert not r
    r = testing_database.fill_cmssw_release(MAGIC_RELEASE)
    assert r and "cmssw_version" in r and r["cmssw_version"] == MAGIC_RELEASE
    with pytest.raises(AssertionError):
        testing_database.fill_cmssw_release(6565656565)
    r2, created = testing_database.get_or_create_cmssw_release(MAGIC_RELEASE)
    assert r == r2
    assert not created


def test_db_cmssw_release_with_prs(testing_database: DQM2MirrorDB):
    with pytest.raises(AssertionError):  # Duplicate PR number
        testing_database.fill_cmssw_release_with_prs(
            cmssw_release=MAGIC_RELEASE, pr_nums=[MAGIC_NUMBER, MAGIC_NUMBER]
        )

    r1 = testing_database.fill_cmssw_release_with_prs(
        cmssw_release=MAGIC_RELEASE, pr_nums=[MAGIC_NUMBER, MAGIC_NUMBER + 1]
    )
    r2, created = testing_database.get_or_create_cmssw_release_with_prs(
        cmssw_release=MAGIC_RELEASE, pr_nums=[MAGIC_NUMBER, MAGIC_NUMBER + 1]
    )
    assert not created
    assert r1 == r2


def test_db_cmssw_comparison_reports(testing_database: DQM2MirrorDB):

    with pytest.raises(AssertionError):
        # Expects more metadata
        testing_database.fill_cmssw_comparison_report(
            **INVALID_METADATA,
        )

    r = testing_database.get_cmssw_comparison_reports(paginate=False)
    assert not r
    r1 = testing_database.fill_cmssw_comparison_report(
        **VALID_METADATA,
    )
    r2 = testing_database.get_cmssw_comparison_reports(id=r1.id, paginate=False)[0]
    assert r1 == r2
    with pytest.raises(IntegrityError):  # Try to reinsert the same id
        testing_database.fill_cmssw_comparison_report(
            **VALID_METADATA,
        )
