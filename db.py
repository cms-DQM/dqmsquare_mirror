### DQM^2 Mirror DB === >
import psycopg2
import sqlalchemy
from sqlalchemy_utils import database_exists
from sqlalchemy.orm import sessionmaker
from collections import defaultdict
from datetime import datetime
from exceptions import DatabaseNotFoundError


class DQM2MirrorDB:
    """
    DB Schema description.
    Three tables: runs, graphs, meta
    """

    TB_NAME_RUNS = "runs"
    TB_DESCRIPTION_RUNS = "( id TEXT PRIMARY KEY NOT NULL, client TEXT, run INT, rev INT, hostname TEXT, exit_code INT, events_total INT, events_rate REAL, cmssw_run INT, cmssw_lumi INT, client_path TEXT, runkey TEXT, fi_state TEXT, timestamp TIMESTAMP, vmrss TEXT, stdlog_start TEXT, stdlog_end TEXT )"
    TB_DESCRIPTION_RUNS_SHORT = [
        "id",
        "client",
        "run",
        "rev",
        "hostname",
        "exit_code",
        "events_total",
        "events_rate",
        "cmssw_run",
        "cmssw_lumi",
        "client_path",
        "runkey",
        "fi_state",
        "timestamp",
        "vmrss",
        "stdlog_start",
        "stdlog_end",
    ]
    TB_DESCRIPTION_RUNS_SHORT_NOLOGS = "id , client , run , rev , hostname , exit_code , events_total , events_rate , cmssw_run , cmssw_lumi , client_path , runkey , fi_state, timestamp, vmrss"

    TB_NAME_GRAPHS = "graphs"
    TB_DESCRIPTION_GRAPHS = "( run INT PRIMARY KEY NOT NULL, rev INT, id TEXT, timestamp TIMESTAMP, global_start TIMESTAMP, stream_data TEXT, hostname TEXT )"
    TB_DESCRIPTION_GRAPHS_SHORT = [
        "run",
        "rev",
        "id",
        "timestamp",
        "global_start",
        "stream_data",
        "hostname",
    ]

    TB_NAME_META = "meta"  # Metadata table, storing data on stored runs, unclear if it's used or not
    TB_DESCRIPTION_META = "( name TEXT PRIMARY KEY NOT NULL, data TEXT )"
    TB_DESCRIPTION_META_SHORT = "( name, data )"

    def __str__(self):
        return f"{self.__class__.__name__}: {self.db_str}"

    def __init__(self, log, db=None, server=False):
        """
        The server flag will determine if table creation will take place or not, upon
        initialization.
        """
        self.log = log
        self.log.info("\n\n DQM2MirrorDB ===== init ")
        self.db_str = db

        if not self.db_str:
            self.db_str = ":memory:"

        self.engine = sqlalchemy.create_engine(
            self.db_str,
            poolclass=sqlalchemy.pool.QueuePool,
            pool_size=20,
            max_overflow=0,
        )
        if not database_exists(self.engine.url):
            raise DatabaseNotFoundError(
                f"Database name was not found when connecting to '{self.db_str}'"
            )

        self.Session = sessionmaker(bind=self.engine)

        if not server:
            self.create_tables()
        self.db_meta = sqlalchemy.MetaData(bind=self.engine)
        self.db_meta.reflect()

    def create_tables(self):
        """
        Initialize the databases
        """
        self.log.debug("DQM2MirrorDB.create_tables()")
        with self.engine.connect() as cur:
            session = self.Session(bind=cur)
            try:
                session.execute(
                    "CREATE TABLE IF NOT EXISTS "
                    + self.TB_NAME_RUNS
                    + " "
                    + self.TB_DESCRIPTION_RUNS
                )
                session.execute(
                    "CREATE TABLE IF NOT EXISTS "
                    + self.TB_NAME_GRAPHS
                    + " "
                    + self.TB_DESCRIPTION_GRAPHS
                )
                session.execute("DROP TABLE IF EXISTS " + self.TB_NAME_META)
                session.execute(
                    "CREATE TABLE IF NOT EXISTS "
                    + self.TB_NAME_META
                    + " "
                    + self.TB_DESCRIPTION_META
                )
                session.commit()
            except psycopg2.IntegrityError as e:
                self.log.error("Error occurred: ", e)
                session.rollback()

    def fill_graph(self, header: dict, document: dict) -> int:
        """
        Fill DB graph data from an FFF document. Documents
        Example header:
        {
            'tag': 'analyze_files',
            'run': 334388,
            'type': 'dqm-files',
            'timestamp': 1579729985.921526,
            '_rev': 10050,
            'hostname': 'bu-c2f11-09-01',
            '_id': 'dqm-files-bu-c2f11-09-01-analyze_files-run334388'
        }
        Example document:
        {
            'extra': {
                'global_start': 1579722020.7529602,
                'global_start_source': 'global_file',
                'streams': {...},
                'lumi': 23.310893056
            },
            'run': 334388,
            'sequence': 0,
            'timestamp': 1579729985.921526,
            '_rev': 10050,
            'hostname': 'bu-c2f11-09-01',
            'pid': 8066,
            'tag': 'analyze_files',
            '_id': 'dqm-files-bu-c2f11-09-01-analyze_files-run334388',
            'type': 'dqm-files'
        }
        """
        extra = document.get("extra", None)
        if not extra:
            self.log.debug("No 'extra' key found in document")
            return

        id = header.get("_id")
        run = header.get("run", None)
        if not run:
            self.log.warning(
                "\n\n DQM2MirrorDB.fill_graph(): no 'run' for header id '%s'" % (id)
            )
            return

        rev = header.get("_rev", -1)
        timestamp = extra.get(
            "timestamp", datetime(2012, 3, 3, 10, 10, 10, 0).timestamp()
        )
        global_start = extra.get(
            "global_start", datetime(2012, 3, 3, 10, 10, 10, 0).timestamp()
        )

        stream_data = str(extra.get("streams", ""))
        hostname = header.get("hostname", "")

        if not isinstance(global_start, datetime):
            try:
                global_start = datetime.fromtimestamp(global_start)
            except Exception as e:
                self.log.warning(
                    f"Could not parse {global_start} as a timestamp. Error: '{repr(e)}'"
                )

        if not isinstance(timestamp, datetime):
            try:
                timestamp = datetime.fromtimestamp(timestamp)
            except Exception as e:
                self.log.warning(
                    f"Could not parse {timestamp} as a timestamp. Error: '{repr(e)}'"
                )
        values = [run, rev, id, timestamp, global_start, stream_data, hostname]
        values_dic = {}
        for val, name in zip(values, self.TB_DESCRIPTION_GRAPHS_SHORT):
            values_dic[name] = val

        with self.engine.connect() as cur:
            session = self.Session(bind=cur)
            try:
                session.execute(
                    f"DELETE FROM {self.TB_NAME_GRAPHS} WHERE id = '{str(id)}';"
                )
                session.execute(
                    sqlalchemy.insert(self.db_meta.tables[self.TB_NAME_GRAPHS]).values(
                        values_dic
                    )
                )
                session.commit()
            except Exception as e:
                self.log.error("Error occurred: ", e)
                session.rollback()
                return 1

        return 0

    def get_graphs_data(self, run) -> list:
        self.log.debug("DQM2MirrorDB.get_graphs_data() - " + str(run))
        with self.engine.connect() as cur:
            answer = cur.execute(
                f"SELECT * FROM {self.TB_NAME_GRAPHS} WHERE CAST(run as INTEGER) = {str(run)};"
            ).all()
        if not len(answer):
            return []
        answer = list(answer[0])
        if answer[-2]:
            answer[-2] = eval(answer[-2])  # TODO: Not secure!!!!!!
        answer[3] = answer[3].timestamp()
        answer[4] = answer[4].timestamp()

        return answer

    def fill(self, header: dict, document: dict) -> int:
        """
        fill 'runs' table with clients data
        """
        id = header.get("_id")
        client = header.get("tag", "")
        run = header.get("run", -1)
        rev = header.get("_rev", -1)
        hostname = header.get("hostname", "")
        exit_code = document.get("exit_code", -1)
        events_total = document.get("events_total", -1)
        events_rate = document.get("events_rate", -1)
        cmssw_run = document.get("cmssw_run", -1)
        cmssw_lumi = document.get("cmssw_lumi", -1)
        client_path, runkey = "", ""
        try:
            client_path = document.get("cmdline")[1]
            for item in document.get("cmdline"):
                if "runkey" in item:
                    runkey = item
        except:
            pass
        fi_state = document.get("fi_state", "")
        timestamp = header.get(
            "timestamp", datetime(2012, 3, 3, 10, 10, 10, 0).timestamp()
        )
        try:
            timestamp = datetime.fromtimestamp(timestamp)
        except Exception as e:
            self.log.warn(
                f"Timestamp {timestamp} could not be cast to datetime: {repr(e)}"
            )
        extra = document.get("extra", {})
        ps_info = extra.get("ps_info", {})
        VmRSS = ps_info.get("VmRSS", "")

        stdlog_start = str(extra.get("stdlog_start", ""))
        stdlog_end = str(extra.get("stdlog_end", ""))

        values = (
            id,
            client,
            run,
            rev,
            hostname,
            exit_code,
            events_total,
            events_rate,
            cmssw_run,
            cmssw_lumi,
            client_path,
            runkey,
            fi_state,
            timestamp,
            VmRSS,
            stdlog_start,
            stdlog_end,
        )
        self.log.debug(
            f"DQM2MirrorDB.fill() - {str(values[:-2])}, {str(values[-2][:10])}..{str(values[-2][-10:])}, {str(values[-1][:10])}..{str(values[-1][-10:])}"
        )
        values_dic = {}
        for val, name in zip(values, self.TB_DESCRIPTION_RUNS_SHORT):
            values_dic[name] = val

        with self.engine.connect() as cur:
            session = self.Session(bind=cur)
            try:
                # cur.execute("INSERT OR REPLACE INTO " + self.TB_NAME_RUNS + " " + self.TB_DESCRIPTION_RUNS_SHORT + " VALUES " + template, values)
                session.execute(f"DELETE FROM {self.TB_NAME_RUNS} WHERE id = '{id}';")
                session.execute(
                    sqlalchemy.insert(self.db_meta.tables[self.TB_NAME_RUNS]).values(
                        values_dic
                    )
                )
                session.commit()
            except Exception as e:
                self.log.error(
                    f"Error when inserting into '{self.engine.url}': {repr(e)}"
                )
                session.rollback()
                return 1

        ###
        if not run:
            return 0

        old_min_max = [999999999, -1]
        with self.engine.connect() as cur:
            answer = cur.execute(
                f"SELECT data FROM {self.TB_NAME_META} WHERE name = 'min_max_runs';"
            ).all()
            if answer:
                old_min_max = eval(answer[0][0])
            else:
                answer = cur.execute(
                    f"SELECT MIN(run), MAX(run) FROM {self.TB_NAME_RUNS};"
                ).all()
                if answer:
                    old_min_max = answer[0]

        # print( old_min_max )
        new_min = min(int(run), old_min_max[0])
        new_max = max(int(run), old_min_max[1])
        if new_min != old_min_max[0] or new_max != old_min_max[1]:
            self.update_min_max(new_min, new_max)

        return 0

    def get(self, run_start, run_end, bad_only=False, with_ls_only=False):
        """
        get data from 'runs' table with client's data
        """
        self.log.debug("DQM2MirrorDB.get() - " + str(run_start) + " " + str(run_end))
        with self.engine.connect() as cur:
            postfix = ""
            if bad_only:
                postfix = " AND (exit_code <> 0 OR exit_code IS NULL) " + postfix
            if with_ls_only:
                postfix = " AND cmssw_lumi > 0 " + postfix
            if run_start == run_end:
                answer = cur.execute(
                    f"SELECT {self.TB_DESCRIPTION_RUNS_SHORT_NOLOGS} FROM {self.TB_NAME_RUNS} "
                    + f"WHERE run = {run_start} {postfix} ORDER BY client, id;"
                ).all()
            else:
                answer = cur.execute(
                    f"SELECT {self.TB_DESCRIPTION_RUNS_SHORT_NOLOGS} FROM {self.TB_NAME_RUNS} "
                    + f"WHERE run BETWEEN {run_start} AND {run_end} {postfix}"
                ).all()
        self.log.debug(f"Read DB for runs {run_start}-{run_end}: {answer}")
        return answer

    def make_mirror_entry(self, data):
        answer = []
        (
            id,
            client,
            _,
            _,
            hostname,
            exit_code,
            events_total,
            events_rate,
            _,
            cmssw_lumi,
            client_path,
            runkey,
            _,
            timestamp,
            VmRSS,
        ) = data

        client = self.get_short_client_name(client)
        # Hide part of the hostname for safety reasons
        var = hostname.split("-")
        hostname = "..".join([var[0], var[-1]])
        td = datetime.now() - timestamp
        days = int(td.days)
        hours = int((td.seconds / (60 * 60)) % 24)
        minutes = int((td.seconds / 60) % 60)
        seconds = int(td.seconds % 60)
        td = "%02d:%02d" % (minutes, seconds)
        td = "%02d:" % (hours) + td
        td = "%d days " % (days) + td

        cmssw_path = ""
        subfolders = client_path.split("/")
        for folder in subfolders:
            if "CMSSW" in folder:
                cmssw_path = folder
                break
        cmssw_v = cmssw_path.split("CMSSW_")[1]
        runkey = runkey[len("runkey=") :]

        answer = [
            (
                timestamp.isoformat(),
                td,
                hostname,
                exit_code,
                client,
                cmssw_lumi,
                VmRSS,
                events_total,
                id,
                events_rate,
            ),
            (cmssw_v, runkey),
        ]
        return answer

    def make_table_entry(self, data: dict):
        answer = []
        (
            _,
            client,
            run,
            _,
            hostname,
            exit_code,
            events_total,
            _,
            cmssw_run,
            cmssw_lumi,
            client_path,
            runkey,
            fi_state,
            timestamp,
            _,
        ) = data

        client = self.get_short_client_name(client)
        # Hide part of the hostname for safety reasons
        var = hostname.split("-")
        hostname = "..".join([var[0], var[-1]])
        runkey = runkey[len("runkey=") :]

        cmssw_path = ""
        subfolders = client_path.split("/")
        for folder in subfolders:
            if "CMSSW" in folder:
                cmssw_path = folder
                break

        cmssw_v = cmssw_path.split("CMSSW_")[1]

        answer = [
            run,
            client,
            (
                hostname,
                events_total,
                cmssw_lumi,
                fi_state,
                exit_code,
                timestamp.isoformat(),
            ),
            (cmssw_run, runkey, cmssw_v),
        ]
        return answer

    def filter_clients(self, name):
        if not name:
            return False
        if name == "__init__":
            return False
        return True

    def get_mirror_data(self, run_number: int) -> tuple:
        """
        Gets information for a specific run from the DB.

        Returns a tuple: global_data and clients_data (???)
        """
        runs = self.get(run_number, run_number)
        runs_out = [self.make_mirror_entry(run) for run in runs]
        clients_data = [run[0] for run in runs_out]
        global_data = runs_out[0][1] if runs_out else []
        return global_data, clients_data

    def get_timeline_data(
        self,
        run_start: int,
        run_end: int,
        bad_only: bool = False,
        with_ls_only: bool = False,
    ) -> dict:
        runs = self.get(run_start, run_end, bad_only, with_ls_only)
        runs_out = [self.make_table_entry(run) for run in runs]

        dic = defaultdict(dict)
        for run in runs_out:
            run_number = run[0]
            client_name = run[1]
            client_data = run[2]
            run_data = run[3]
            run_item = dic[run_number]
            run_item["run_data"] = run_data
            if "clients" not in run_item:
                run_item["clients"] = defaultdict(dict)
            clients_item = run_item["clients"]

            if client_name not in clients_item:
                clients_item[client_name] = [client_data]
            else:
                clients_item[client_name].append(client_data)

        return dict(dic)

    def get_short_client_name(self, client):
        return (
            client[: -len("_dqm_sourceclient-live")]
            if "_dqm_sourceclient-live" in client
            else client
        )

    def get_clients(self, run_start: int, run_end: int) -> list:
        self.log.debug("DQM2MirrorDB.get_clients()")
        with self.engine.connect() as cur:
            answer = cur.execute(
                f"SELECT DISTINCT client FROM {self.TB_NAME_RUNS} "
                + f"WHERE run BETWEEN {run_start} AND {run_end} ORDER BY client;"
            ).all()
        answer = [
            self.get_short_client_name(name[0])
            for name in answer
            if self.filter_clients(name[0])
        ]
        # self.log.debug( "return " + str(answer) )
        return answer

    def update_min_max(self, new_min: int, new_max: int):
        """
        update metadata table with info about min and max run number in runs table for fast fetch
        """
        with self.engine.connect() as cur:
            session = self.Session(bind=cur)
            try:
                session.execute(
                    f"DELETE FROM {self.TB_NAME_META} WHERE name = 'min_max_runs';"
                )
                session.execute(
                    f"INSERT INTO {self.TB_NAME_META} {self.TB_DESCRIPTION_META_SHORT} "
                    + f"VALUES('min_max_runs', '[{new_min},{new_max}]');"
                )
                session.commit()
            except Exception as e:
                self.log.error("Error occurred: ", e)
                session.rollback()
                return 1
        return 0

    def get_info(self) -> list:
        """
        Fetches the max and min run numbers from the database.
        Used for navigating runs.
        """
        self.log.debug("DQM2MirrorDB.get_info()")

        with self.engine.connect() as cur:
            answer = cur.execute(
                f"SELECT data FROM {self.TB_NAME_META} WHERE name = 'min_max_runs';"
            ).all()

            if answer:
                return eval(answer[0][0])

            answer = cur.execute(
                f"SELECT MIN(run), MAX(run) FROM {self.TB_NAME_RUNS};"
            ).all()
            if not answer:
                return [-1, -1]

            answer = list(answer[0])
            # self.update_min_max( answer[0], answer[1] )  # Updates meta table for faster next query

        return answer

    def get_latest_revision(self, host: str) -> int:
        """
        Search the runs table in the DB for get latest rev for a given dqm machine
        """
        self.log.debug("DQM2MirrorDB.get_rev()")
        if ".cms" in host:
            host = host[: -len(".cms")]

        with self.engine.connect() as cur:
            if "fu" in host:
                answer = cur.execute(
                    f"SELECT MAX(rev) FROM {self.TB_NAME_RUNS} WHERE hostname = '{host}';"
                ).all()
                answer = list(answer[0])
                return answer[0]
            else:
                answer = cur.execute(
                    f"SELECT MAX(rev) FROM {self.TB_NAME_GRAPHS} WHERE hostname = '{host}';"
                ).all()
                answer = list(answer[0])
                return answer[0]

    def get_logs(self, client_id: int) -> list:
        self.log.debug("DQM2MirrorDB.get_logs()")
        with self.engine.connect() as cur:
            answer = cur.execute(
                f"SELECT stdlog_start, stdlog_end FROM {self.TB_NAME_RUNS} WHERE id = '{client_id}';"
            ).all()
            if not answer:
                answer = ["None", "None"]
            else:
                answer = answer[0]
        return answer

    def get_runs_around(self, run: int) -> list:
        """
        get next run and prev run, unordered
        """
        answer = []
        self.log.debug("DQM2MirrorDB.get_runs_around()")
        with self.engine.connect() as cur:
            answer = cur.execute(
                f"SELECT min(run) FROM {self.TB_NAME_RUNS} WHERE run > {run} union SELECT max(run) FROM {self.TB_NAME_RUNS} WHERE run < {run};"
            ).all()
            answer = [item[0] for item in answer]
        return answer
