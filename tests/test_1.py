# tests to check DB
import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

import pytest
import hashlib
from datetime import datetime
from db import DQM2MirrorDB
from sqlalchemy import create_engine
from sqlalchemy_utils import create_database, database_exists, drop_database
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


pytest.production = [
    "bu-c2f11-09-01",
    "fu-c2f11-11-01",
    "fu-c2f11-11-02",
    "fu-c2f11-11-03",
    "fu-c2f11-11-04",
]


def test_db_1(testing_database):
    print("Check DQM2MirrorDB.get_rev()")
    revs = [
        6001382,
        7912099,
        2730841,
        2762604,
        12811635,
    ]
    revs = [testing_database.get_rev(host) for host in pytest.production]
    assert all(
        [
            testing_database.get_rev(host) == rev
            for host, rev in zip(pytest.production, revs)
        ]
    )


def test_db_2(testing_database):
    print("Check DQM2MirrorDB.get_runs_around()")
    test_runs = [358788, 358791, 358792]
    truth_answers = [
        [None, 358791],
        [358788, 358792],
        [None, 358791],
    ]
    # answer = [ sorted(testing_database.get_runs_around( run ), key=lambda x: 0 if not x else x ) for run in pytest.test_runs  ]
    answers = []

    for truth, run in zip(truth_answers, test_runs):
        around = testing_database.get_runs_around(run)
        answer = sorted(around, key=lambda x: 0 if not x else x)
        print("!!!", truth, run, around, answer)
        x = (truth[0] == answer[0]) and (truth[1] == answer[1])
        answers += [x]
    assert all(answers)


def test_db_3(testing_database):
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
        "",
    ]
    # for id in test_ids :
    #  logs = testing_database.get_logs( id )
    #  print( logs[0][-50:] + logs[1][-50:] )
    #  answer += [ logs[0][-50:] + logs[1][-50:] ]
    answers = []
    for truth, id in zip(truth_answers, test_ids):
        logs = testing_database.get_logs(id)
        x = truth == (logs[0][-50:] + logs[1][-50:])
        answers += [x]
    assert all(answers)


def test_db_4(testing_database):
    print("Check DQM2MirrorDB.get_info()")
    minmax = testing_database.get_info()
    assert minmax[0] == 358788 and minmax[1] == 358792


def test_db_5(testing_database):
    print("Check DQM2MirrorDB.update_min_max() & DQM2MirrorDB.get_info()")
    testing_database.update_min_max(350000, 360000)
    minmax = testing_database.get_info()
    print(minmax)
    assert minmax[0] == 350000 and minmax[1] == 360000


def test_db_6(testing_database):
    print("Check DQM2MirrorDB.get_clients()")
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


def test_db_7(testing_database):
    print("Check DQM2MirrorDB.get_timeline_data()")
    truth = "''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''((((((((((((((((((((((((((((((((())))))))))))))))))))))))))))))))),,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,---------.............................................................................................00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000011111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111122222222222222222222222222222222222222222222222222222222222222222222222222222222222222222222222222222222222222222222222222222223333333333333333333333333333333333333333333333333333333333333334444444444444444444444444444444444444444444444444444444444444444444444444444444444455555555555555555555555555566666666666666666666666666666666666666666666666666666666666666666666666666666666666666666666666666666666666666666666666666666777777777777777777777777888888888888888888888888888888888899999999999999999999999999999::::::::::::::::::::::::::::::::::<>BIP[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]___________aaaaaaaaaaaaaaaaaaaaaaaaaaabbbbbbbccccccccccccccccccccccccddddddddddeeeeeeeeeeeeeeeeeeeeeeeeeeeffffffffffffffffffffffffffffffffffgggggghhhhhhhiiiiiiiiiiiiiiiiiiiiiiiiiiikllllllllllllllllllllllllllllllmmmmmmmmmmmmmnnnnnnnnnnnnnnooooooooooopppppppppppqrrrrrrrrssssssssssssssssttttttttttttttttttttttttuuuuuuuuuuuuuuuuuuuuuuuuuuuuuuuuuuuuuuuuuvvvvvxxxzz{{{}}}"
    answer = testing_database.get_timeline_data(358791, 358791)
    answer = ("".join(sorted(str(answer)))).strip()
    assert truth == answer


def test_db_8(testing_database):
    print("Check DQM2MirrorDB.get_mirror_data()")
    truth = "''''(),11112223333333334445566899999________ccimnorsu"
    answer = testing_database.get_mirror_data(358788)[0]
    answer = ("".join(sorted(str(answer)))).strip()
    assert truth == answer


def test_db_9(testing_database):
    print("Check DQM2MirrorDB.get_graphs_data()")
    truth = 44645389

    answer = testing_database.get_graphs_data(358792)
    answer = ("".join(sorted(str(answer)))).strip()
    answer = int(hashlib.sha1(answer.encode("utf-8")).hexdigest(), 16) % (10**8)
    assert truth == answer


def test_db_10(testing_database):
    print("Check DQM2MirrorDB.fill_graph()")
    truth = [
        123456,
        -1,
        "id",
        datetime(2012, 3, 3, 10, 10, 10).isoformat(),
        datetime(2012, 3, 3, 10, 10, 10).isoformat(),
        "",
        "",
    ]
    header = {"_id": "id", "run": "123456", "extra": {}}
    document = {"extra": {None: None}}
    testing_database.fill_graph(header, document)
    answer = testing_database.get_graphs_data(123456)
    assert all([c1 == c2 for c1, c2 in zip(truth, answer)])


def test_db_11(testing_database):
    print("Check DQM2MirrorDB.fill() & get()")
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
        datetime(2012, 3, 3, 10, 10, 10),
        "",
    )
    header = {"_id": "id", "run": "123456"}
    document = {}
    testing_database.fill(header, document)
    answer = testing_database.get(123456, 123456)[0]

    with testing_database.engine.connect() as cur:
        session = testing_database.Session(bind=cur)
        session.execute(
            "DELETE FROM "
            + testing_database.TB_NAME
            + " WHERE run = "
            + str(123456)
            + ""
        )
        session.commit()

    assert all([c1 == c2 for c1, c2 in zip(truth, answer)])
