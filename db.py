### DQM^2 Mirror DB === >
import os
import sys
import shutil
import logging
import psycopg2
import sqlalchemy
from sqlalchemy import text, pool
from sqlalchemy.sql import functions, sqltypes
from sqlalchemy_utils import database_exists
from sqlalchemy.orm import sessionmaker
from sqlalchemy.dialects import postgresql
from collections import defaultdict
from datetime import datetime
from exceptions import DatabaseNotFoundError
from utils.common import _censor_hostname
from decorators import paginate

sys.path.append(os.path.join(os.path.dirname(__file__), "."))

from dqmsquare_cfg import TZ, TIMEZONE, load_cfg
from utils.common import (
    get_short_client_name,
    filter_clients,
    format_table_entry,
    format_run_data,
)

DEFAULT_DATETIME = TZ.localize(datetime(2012, 3, 3, 10, 10, 10, 0))
cfg = load_cfg()


class DQM2MirrorDB:
    """
    DB Schema description.
    """

    TB_NAME_RUNS = "runs"
    TB_DESCRIPTION_RUNS = (
        "( id TEXT PRIMARY KEY NOT NULL, "
        "client TEXT, run INT, rev INT, hostname TEXT, "
        "exit_code INT, events_total INT, events_rate REAL, "
        "cmssw_run INT, cmssw_lumi INT, client_path TEXT, "
        "runkey TEXT, fi_state TEXT, "
        "timestamp TIMESTAMP WITH TIME ZONE, vmrss TEXT, "
        "stdlog_start TEXT, stdlog_end TEXT )"
    )
    TB_DESCRIPTION_RUNS_COLS = [
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
    TB_DESCRIPTION_RUNS_COLS_NOLOGS = "id , client , run , rev , hostname , exit_code , events_total , events_rate , cmssw_run , cmssw_lumi , client_path , runkey , fi_state, timestamp, vmrss"

    TB_NAME_GRAPHS = "graphs"
    TB_DESCRIPTION_GRAPHS = (
        "( run INT PRIMARY KEY NOT NULL, rev INT, "
        "id TEXT, timestamp TIMESTAMP WITH TIME ZONE, "
        "global_start TIMESTAMP WITH TIME ZONE, "
        "stream_data TEXT, hostname TEXT )"
    )
    TB_DESCRIPTION_GRAPHS_COLS = [
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

    # Store status for each cluster host
    TB_NAME_HOST_NAME = "hostnames"
    TB_DESCRIPTION_HOST_NAME = (
        "( id SERIAL PRIMARY KEY, name VARCHAR(50) NOT NULL UNIQUE )"
    )
    TB_DESCRIPTION_HOST_NAME_COLS = ["name"]

    TB_NAME_HOST_STATUS = "hoststatuses"
    TB_DESCRIPTION_HOST_STATUS = (
        "( id SERIAL PRIMARY KEY, "
        "created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(), "
        f"host_id INT NOT NULL REFERENCES {TB_NAME_HOST_NAME} ON DELETE CASCADE, "
        "is_up BOOLEAN NOT NULL, "
        "message VARCHAR)"
    )
    TB_DESCRIPTION_HOST_STATUS_COLS = ["host_id", "is_up", "message"]

    # Unique CMSSW releases mentioned in comparison reports received.
    TB_NAME_CMSSW_RELEASES = "cmssw_releases"
    TB_DESCRIPTION_CMSSW_RELEASES = (
        "( id SERIAL PRIMARY KEY, "
        + "cmssw_version VARCHAR NOT NULL UNIQUE, "
        + "created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW())"
    )
    TB_DESCRIPTION_CMSSW_RELEASES_COLS = ["cmssw_version"]

    # Unique CMSSW PRs mentioned in comparison reports received.
    TB_NAME_CMSSW_PRS = "cmssw_prs"
    TB_DESCRIPTION_CMSSW_PRS = (
        "( pr_num INTEGER PRIMARY KEY NOT NULL, "
        + "created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW())"
    )
    TB_DESCRIPTION_CMSSW_PRS_COLS = ["pr_num"]

    # Table that combines CMSSW base PR and PRs. The rows in this table are
    # referenced by the cmsswreleasetoprs rows, to allow a Many to one relationship.
    TB_NAME_CMSSW_RELEASES_WITH_PRS = "cmssw_release_with_prs"
    TB_DESCRIPTION_CMSSW_RELEASES_WITH_PRS = (
        "( id SERIAL PRIMARY KEY, "
        + f"cmssw_release_id INT REFERENCES {TB_NAME_CMSSW_RELEASES} ON DELETE CASCADE, "
        + "created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW())"
    )
    TB_DESCRIPTION_CMSSW_RELEASES_WITH_PRS_COLS = ["cmssw_release_id"]

    # Intermediate table to link many PRs to a single entry in cmssw_release_with_prs
    TB_NAME_RELEASE_WITH_PRS_TO_PRS = "cmssw_release_with_prs_to_cmssw_prs"
    TB_DESCRIPTION_RELEASE_WITH_PRS_TO_PRS = (
        f"( cmssw_release_w_prs_id INT NOT NULL REFERENCES {TB_NAME_CMSSW_RELEASES_WITH_PRS} ON DELETE CASCADE, "
        + f"cmssw_pr_id INT NOT NULL REFERENCES {TB_NAME_CMSSW_PRS} ON DELETE CASCADE, "
        + "PRIMARY KEY (cmssw_release_w_prs_id, cmssw_pr_id) )"
    )
    TB_DESCRIPTION_RELEASE_WITH_PRS_TO_PRS_COLS = [
        "cmssw_release_w_prs_id",
        "cmssw_pr_id",
    ]

    # Table for storing info on CMSSW comparison reports.
    TB_NAME_CMSSW_COMPARISON_REPORTS = "cmssw_comparison_reports"
    TB_DESCRIPTION_CMSSW_COMPARISON_REPORTS = (
        "( id VARCHAR PRIMARY KEY, "
        "created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(), "
        "comparison_ran_at TIMESTAMP WITH TIME ZONE NOT NULL, "
        f"base_cmssw_version INT NOT NULL REFERENCES {TB_NAME_CMSSW_RELEASES_WITH_PRS} ON DELETE CASCADE, "
        f"comp_cmssw_version INT NOT NULL REFERENCES {TB_NAME_CMSSW_RELEASES_WITH_PRS} ON DELETE CASCADE)"
    )
    TB_DESCRIPTION_CMSSW_COMPARISON_REPORTS_COLS = [
        "id",
        "comparison_ran_at",
        "base_cmssw_version",
        "comp_cmssw_version",
    ]

    def __str__(self):
        return f"{self.__class__.__name__}: {self.db_uri}"

    def __init__(
        self,
        log: logging.Logger,
        username: str = "postgres",
        password: str = "postgres",
        host: str = "postgres",
        port: int = 5432,
        db_name: str = "postgres",
        server: bool = False,
    ):
        """
        The server flag will determine if table creation will take place or not, upon
        initialization.
        """
        self.password: str = password
        self.username: str = username
        self.host: str = host
        self.port: int = port
        self.db_name: str = db_name

        self.log: logging.Logger = log
        self.log.info("\n\n DQM2MirrorDB ===== init ")
        self.db_uri: str = self.format_db_uri(
            host=self.host,
            port=self.port,
            username=self.username,
            password=self.password,
            db_name=self.db_name,
        )

        if self.host == ":memory:":
            self.db_uri = ":memory:"

        self.log.info(
            f"Connecting to database {self.db_name} on {self.username}@{self.host}:{self.port}"
        )

        self.engine: sqlalchemy.engine.base.Engine = sqlalchemy.create_engine(
            url=self.db_uri,
            poolclass=pool.QueuePool,
            pool_size=20,
            max_overflow=0,
        )

        if not self.engine or not database_exists(self.engine.url):
            raise DatabaseNotFoundError(
                f"Database {self.db_name} was not found on '{self.host}:{self.port}'"
            )

        self.Session = sessionmaker(bind=self.engine)
        if not server:
            self.create_tables()
        self.db_meta = sqlalchemy.MetaData(bind=self.engine)
        self.db_meta.reflect()

    @staticmethod
    def format_db_uri(
        username: str = "postgres",
        password: str = "postgres",
        host: str = "postgres",
        port: int = 5432,
        db_name="postgres",
    ) -> str:
        """
        Helper function to format the DB URI for SQLAclhemy
        """
        return f"postgresql://{username}:{password}@{host}:{port}/{db_name}"

    def create_tables(self):
        """
        Initialize the databases
        """
        self.log.debug("DQM2MirrorDB.create_tables()")
        with self.engine.connect() as cur:
            session = self.Session(bind=cur)
            for name, description in [
                (self.TB_NAME_RUNS, self.TB_DESCRIPTION_RUNS),
                (self.TB_NAME_GRAPHS, self.TB_DESCRIPTION_GRAPHS),
                (self.TB_NAME_HOST_NAME, self.TB_DESCRIPTION_HOST_NAME),
                (self.TB_NAME_HOST_STATUS, self.TB_DESCRIPTION_HOST_STATUS),
                (self.TB_NAME_META, self.TB_DESCRIPTION_META),
                (self.TB_NAME_CMSSW_PRS, self.TB_DESCRIPTION_CMSSW_PRS),
                (self.TB_NAME_CMSSW_RELEASES, self.TB_DESCRIPTION_CMSSW_RELEASES),
                (
                    self.TB_NAME_CMSSW_RELEASES_WITH_PRS,
                    self.TB_DESCRIPTION_CMSSW_RELEASES_WITH_PRS,
                ),
                (
                    self.TB_NAME_RELEASE_WITH_PRS_TO_PRS,
                    self.TB_DESCRIPTION_RELEASE_WITH_PRS_TO_PRS,
                ),
                (
                    self.TB_NAME_CMSSW_COMPARISON_REPORTS,
                    self.TB_DESCRIPTION_CMSSW_COMPARISON_REPORTS,
                ),
            ]:

                try:
                    self.log.info(f"Creating table {name}")
                    session.execute(
                        text("CREATE TABLE IF NOT EXISTS " + name + " " + description)
                    )
                    session.commit()
                except psycopg2.IntegrityError as e:
                    self.log.error("Error occurred: ", e)
                    session.rollback()

            try:
                self.log.info("Adding indices to DB")
                with open("./sql/migrations/add_indices.sql") as f:
                    sql = text(f.read())
                session.execute(sql)
                session.commit()
            except psycopg2.IntegrityError as e:
                self.log.error(f"Error occurred: ", e)
                session.rollback()

    def get_graphs(self, run: int) -> list:
        """
        Load graph data for a specific run
        """
        self.log.debug(f"DQM2MirrorDB.get_graphs() - Run {run}")
        with self.engine.connect() as cur:
            answer = cur.execute(
                text(
                    f"SELECT * FROM {self.TB_NAME_GRAPHS} WHERE CAST(run as INTEGER)=:run;"
                ),
                run=run,
            ).all()
        if not len(answer):
            return []
        answer = list(answer[0])
        if answer[-2]:
            answer[-2] = eval(answer[-2])  # TODO: Not secure!!!!!!
        answer[3] = answer[3].timestamp()
        answer[4] = answer[4].timestamp()

        return answer

    def fill_graph(self, header: dict, document: dict) -> None:
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

        _id = header.get("_id")
        run = header.get("run", None)
        if not run:
            self.log.warning(
                "\n\n DQM2MirrorDB.fill_graph(): no 'run' for header id '%s'" % (_id)
            )
            return

        rev = header.get("_rev", -1)
        timestamp = extra.get(
            "timestamp",
            DEFAULT_DATETIME,
        )
        global_start = extra.get(
            "global_start",
            DEFAULT_DATETIME,
        )

        stream_data = str(extra.get("streams", ""))
        hostname = header.get("hostname", "")

        # Make timestamps TZ aware
        if not isinstance(global_start, datetime):
            try:
                global_start = TZ.localize(datetime.fromtimestamp(global_start))
            except Exception as e:
                self.log.warning(
                    f"Could not parse {global_start} as a timestamp. Error: '{repr(e)}'"
                )

        if not isinstance(timestamp, datetime):
            try:
                timestamp = TZ.localize(datetime.fromtimestamp(timestamp))
            except Exception as e:
                self.log.warning(
                    f"Could not parse {timestamp} as a timestamp. Error: '{repr(e)}'"
                )
        values = [run, rev, _id, timestamp, global_start, stream_data, hostname]
        values_dic = {}
        for val, name in zip(values, self.TB_DESCRIPTION_GRAPHS_COLS):
            values_dic[name] = val

        with self.engine.connect() as cur:
            session = self.Session(bind=cur)
            try:
                cur.execute(
                    text(f"DELETE FROM {self.TB_NAME_GRAPHS} WHERE id=:id;"), id=_id
                )
                session.execute(
                    sqlalchemy.insert(self.db_meta.tables[self.TB_NAME_GRAPHS]).values(
                        values_dic
                    )
                )
                session.commit()
            except Exception as e:
                self.log.error(f"Error occurred: {repr(e)}")
                session.rollback()

    def get_run(
        self,
        run_start: int,
        run_end: int,
        bad_only: bool = False,
        with_ls_only: bool = False,
    ) -> list[tuple]:
        """
        Get data from 'runs' table.
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
                    text(
                        f"SET TIMEZONE = '{TIMEZONE}'; SELECT {self.TB_DESCRIPTION_RUNS_COLS_NOLOGS} FROM {self.TB_NAME_RUNS} "
                        + f"WHERE run=:run_start {postfix} ORDER BY client, id;"
                    ),
                    run_start=run_start,
                ).all()
            else:
                answer = cur.execute(
                    text(
                        f"SET TIMEZONE = '{TIMEZONE}'; SELECT {self.TB_DESCRIPTION_RUNS_COLS_NOLOGS} FROM {self.TB_NAME_RUNS} "
                        + f"WHERE run BETWEEN :run_start AND :run_end {postfix};"
                    ),
                    run_start=run_start,
                    run_end=run_end,
                ).all()
        self.log.debug(f"Read DB for runs {run_start}-{run_end}: {answer}")
        return answer

    def fill_run(self, header: dict, document: dict) -> None:
        """
        Fill 'runs' table with clients' data
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
            "timestamp",
            DEFAULT_DATETIME,
        )
        if not isinstance(timestamp, datetime):
            try:
                # Make timestamp TZ aware
                timestamp = TZ.localize(datetime.fromtimestamp(timestamp))
            except Exception as e:
                self.log.warning(
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
            f"DQM2MirrorDB.fill_run() - {str(values[:-2])}, {str(values[-2][:10])}..{str(values[-2][-10:])}, {str(values[-1][:10])}..{str(values[-1][-10:])}"
        )
        values_dic = {}
        for val, name in zip(values, self.TB_DESCRIPTION_RUNS_COLS):
            values_dic[name] = val

        with self.engine.connect() as cur:
            session = self.Session(bind=cur)
            try:
                cur.execute(
                    text(f"DELETE FROM {self.TB_NAME_RUNS} WHERE id=:id;"), id=id
                )
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
                return

        if not run:
            return

        old_min_max = [999999999, -1]
        with self.engine.connect() as cur:
            answer = cur.execute(
                text(f"SELECT data FROM {self.TB_NAME_META} WHERE name='min_max_runs';")
            ).all()
            if answer:
                old_min_max = eval(answer[0][0])
            else:
                answer = cur.execute(
                    text(f"SELECT MIN(run), MAX(run) FROM {self.TB_NAME_RUNS};")
                ).all()
                if answer:
                    old_min_max = answer[0]

        new_min = min(int(run), old_min_max[0])
        new_max = max(int(run), old_min_max[1])
        if new_min != old_min_max[0] or new_max != old_min_max[1]:
            self.update_min_max(new_min, new_max)

        return

    def get_cluster_host(self, name: str = "", censor: bool = True) -> dict:
        assert isinstance(name, str)
        table_hostnames = self.db_meta.tables[self.TB_NAME_HOST_NAME]
        with self.engine.connect() as cur:
            result = (
                cur.execute(
                    sqlalchemy.select(table_hostnames).where(
                        (table_hostnames.c.name == name if name else True)
                    )
                )
                .mappings()
                .first()
            )
        if result and censor:
            result = {
                k: _censor_hostname(v) if k == "name" else v for k, v in result.items()
            }

        return result

    def fill_cluster_host(self, name: str) -> None:
        assert isinstance(name, str)
        table_hostnames = self.db_meta.tables[self.TB_NAME_HOST_NAME]
        with self.engine.connect() as cur:
            cur.execute(
                sqlalchemy.insert(table_hostnames).values(
                    dict(zip(self.TB_DESCRIPTION_HOST_NAME_COLS, [name]))
                )
            )

    def get_or_create_cluster_host(
        self, name: str = "", censor: bool = True
    ) -> tuple[dict, bool]:
        if result := self.get_cluster_host(name):
            return result, False
        self.fill_cluster_host(name)
        return self.get_cluster_host(name), True

    def get_cluster_status(
        self,
        timestamp_from: datetime = datetime.now(),  # TODO
        timestamp_to: datetime = datetime.now(),  # TODO
    ) -> list:
        """Returns the latest available status of all the unique hostnames stored in the database"""
        self.log.debug("DQM2MirrorDB.get_cluster_status()")
        with self.engine.connect() as cur:
            results = (
                cur.execute(
                    text(
                        "SELECT h.name, t.is_up, t.message, t.created_at "
                        + f"FROM {self.TB_NAME_HOST_STATUS} t "
                        + "JOIN "
                        + "(SELECT host_id, MAX(created_at) AS max_created_at "
                        + f"FROM {self.TB_NAME_HOST_STATUS} "
                        + "GROUP BY host_id) "
                        + "sub ON t.host_id = sub.host_id AND t.created_at = sub.max_created_at "
                        + f"JOIN {self.TB_NAME_HOST_NAME} h ON t.host_id = h.id;"
                    )
                )
                .mappings()
                .all()
            )
        results = [
            {
                k: (
                    datetime.timestamp(v)
                    if k == "created_at"
                    else _censor_hostname(v) if k == "name" else v
                )
                for k, v in result.items()
            }
            for result in results
        ]
        return results

    def fill_cluster_status(self, cluster_status: dict) -> dict | None:
        """
        Function to store data received after running get_cluster_status into the DB.
        """
        assert isinstance(cluster_status, dict)
        assert len(cluster_status.keys()) > 0
        self.log.debug(f"Filling data: {cluster_status}")
        table_host_statuses = self.db_meta.tables[self.TB_NAME_HOST_STATUS]
        with self.engine.connect() as cur:
            for hostname, status in cluster_status.items():
                assert isinstance(status, dict)
                assert all(key in status for key in ["up", "msg"])
                result, created = self.get_or_create_cluster_host(name=hostname)
                host_id = result["id"]  # id of host in db
                return (
                    cur.execute(
                        sqlalchemy.insert(table_host_statuses)
                        .values(
                            dict(
                                zip(
                                    self.TB_DESCRIPTION_HOST_STATUS_COLS,
                                    [host_id, status["up"], status["msg"]],
                                )
                            )
                        )
                        .returning(table_host_statuses)
                    )
                    .mappings()
                    .first()
                )

    @paginate(table=TB_NAME_CMSSW_COMPARISON_REPORTS)
    def get_cmssw_comparison_reports(
        self,
        id: str = "",
        base_cmssw_version: str = "",
        comp_cmssw_version: str = "",
        base_prs: list[int] = [],
        comp_prs: list[int] = [],
    ) -> sqlalchemy.sql.Selectable:
        """
        Check if comparison report exists in DB and return result
        """

        table = self.db_meta.tables[self.TB_NAME_CMSSW_COMPARISON_REPORTS]
        return sqlalchemy.select(table).where(
            table.c.id == id
            and (
                table.c.comp_cmssw_version == comp_cmssw_version
                if comp_cmssw_version
                else True
            )
            and (
                table.c.base_cmssw_version == base_cmssw_version
                if base_cmssw_version
                else True
            )
            # + ("WHERE id=:id " if id else "")
            # + (
            #     "WHERE base_cmssw_version=:base_cmssw_version "
            #     if base_cmssw_version
            #     else ""
            # )
            # + (
            #     "WHERE comp_cmssw_version=:comp_cmssw_version "
            #     if comp_cmssw_version
            #     else ""
            # )
            # + "ORDER BY comparison_ran_at DESC;"
            # + "LIMIT :limit OFFSET :offset ;"
            # ),
            # base_cmssw_version=base_cmssw_version,
            # comp_cmssw_version=comp_cmssw_version,
            # id=id,
            # # limit=items_per_page,
            # # offset=offset,
            # base_prs=base_prs,
        )

    def fill_cmssw_comparison_report(
        self,
        id: str,
        base: str,
        comp: str,
        base_prs: list[int],
        comp_prs: list[int],
        timestamp: datetime,
        comparison_report_html: str,
    ) -> dict:
        """
        For the given report, check if it exists in the DB
        and store it, if not.
        """
        assert isinstance(id, str)
        assert isinstance(base, str)
        assert isinstance(comp, str)
        assert isinstance(comp_prs, list)
        assert isinstance(base_prs, list)
        assert isinstance(timestamp, datetime)
        assert isinstance(comparison_report_html, str)
        self.log.debug(f"Filling data for comparison {id}")

        # Insert PRs if they don't exist
        pr_db_ids = []  # Ids from DB
        for pr_num in set([*base_prs, *comp_prs]):
            pr_id, _ = self.get_or_create_cmssw_pr(cmssw_pr=pr_num)
            pr_db_ids.append(pr_id)

        # Insert releases if they don't exist
        base_rel_id, _ = self.get_or_create_cmssw_release(cmssw_release=base)
        comp_rel_id, _ = self.get_or_create_cmssw_release(cmssw_release=comp)

        with self.engine.connect() as cur:
            result = cur.execute(
                sqlalchemy.insert(
                    self.db_meta.tables[self.TB_NAME_CMSSW_COMPARISON_REPORTS]
                ).values(
                    dict(
                        zip(
                            self.TB_DESCRIPTION_CMSSW_COMPARISON_REPORTS_COLS,
                            [id, timestamp, base_rel_id, comp_rel_id],
                        )
                    )
                )
            )
        # Store the HTML in the appropriate directory
        self._store_cmssw_comparison_report_html(
            comparison_id=id,
            comparison_report_html=comparison_report_html,
        )
        return result

    def _store_cmssw_comparison_report_html(
        self, comparison_id: str, comparison_report_html: str
    ) -> None:
        """
        Given a unique comparison id, and the contents of the HTML report, store
        it into a unique directory under the SERVER_DATA_PATH.

        This is preferred to storing the file as a blob inside the db, which
        is generally advised against.
        """
        if not cfg["CMSSW_COMPARISON_REPORTS_STORE_PATH"].exists():
            self.log.debug(f"Creating {cfg['CMSSW_COMPARISON_REPORTS_STORE_PATH']}")
            cfg["CMSSW_COMPARISON_REPORTS_STORE_PATH"].mkdir()

        comparison_report_dir = cfg["CMSSW_COMPARISON_REPORTS_STORE_PATH"].joinpath(
            comparison_id
        )
        if comparison_report_dir.exists():
            shutil.rmtree(comparison_report_dir)
        self.log.info(f"Creating {comparison_report_dir}")
        comparison_report_dir.mkdir()
        self.log.info(
            f"Storing {comparison_report_dir.joinpath('dqm-histo-comparison-summary.html')}"
        )
        with open(
            comparison_report_dir.joinpath("dqm-histo-comparison-summary.html"),
            "w+",
        ) as f:
            f.write(comparison_report_html)

    def get_cmssw_release(self, cmssw_release: str) -> dict:
        table_cmssw_releases = self.db_meta.tables[self.TB_NAME_CMSSW_RELEASES]
        with self.engine.connect() as cur:
            result = cur.execute(
                sqlalchemy.select(table_cmssw_releases).where(
                    table_cmssw_releases.c.cmssw_version == cmssw_release
                )
            )
        if result:
            return result.mappings().first()
        return {}

    def fill_cmssw_release(self, cmssw_release: str) -> dict | None:
        assert isinstance(cmssw_release, str), "cmssw_release must be a str"
        table = self.db_meta.tables[self.TB_NAME_CMSSW_RELEASES]
        with self.engine.connect() as cur:
            return (
                cur.execute(
                    sqlalchemy.insert(table)
                    .values(
                        dict(
                            zip(
                                self.TB_DESCRIPTION_CMSSW_RELEASES_COLS, [cmssw_release]
                            )
                        )
                    )
                    .returning(table)
                )
                .mappings()
                .first()
            )

    def get_or_create_cmssw_release(self, cmssw_release: str) -> tuple[dict, bool]:
        if result := self.get_cmssw_release(cmssw_release=cmssw_release):
            return result, False
        return self.fill_cmssw_release(cmssw_release=cmssw_release), True

    def get_or_create_cmssw_release_with_prs(
        self, id: int | None = None, cmssw_release: str = "", pr_nums: list = []
    ) -> tuple[dict | None, bool]:
        if result := self.get_cmssw_release_with_prs(
            id=id, cmssw_release=cmssw_release, pr_nums=pr_nums
        ):
            return result[0], False
        return (
            self.fill_cmssw_release_with_prs(
                cmssw_release=cmssw_release, pr_nums=pr_nums
            ),
            True,
        )

    def get_cmssw_release_with_prs(
        self, id: int | None = None, cmssw_release: str = "", pr_nums: list = []
    ) -> list[dict | None]:
        assert isinstance(cmssw_release, str), "cmssw_release must be a str"
        assert isinstance(pr_nums, list) and all(
            isinstance(pr_num, int) for pr_num in pr_nums
        )
        table_rels = self.db_meta.tables[self.TB_NAME_CMSSW_RELEASES]
        table_rel_w_prs = self.db_meta.tables[self.TB_NAME_CMSSW_RELEASES_WITH_PRS]
        table_rel_w_prs_to_prs = self.db_meta.tables[
            self.TB_NAME_RELEASE_WITH_PRS_TO_PRS
        ]
        # table_prs = self.db_meta.tables[self.TB_NAME_CMSSW_PRS]

        with self.engine.connect() as cur:
            # Thanks Geovanny!

            #
            pr_agg_cte = (
                sqlalchemy.select(
                    table_rel_w_prs_to_prs.c.cmssw_release_w_prs_id,
                    functions.array_agg(
                        postgresql.aggregate_order_by(
                            table_rel_w_prs_to_prs.c.cmssw_pr_id,
                            table_rel_w_prs_to_prs.c.cmssw_pr_id.asc(),
                        )
                    ).label("pr_list"),
                )
                .group_by(table_rel_w_prs_to_prs.c.cmssw_release_w_prs_id)
                .cte("pr_agg")
            )
            query = (
                sqlalchemy.select(
                    table_rel_w_prs.c.id,
                    table_rel_w_prs.c.cmssw_release_id,
                    table_rels.c.cmssw_version,
                    pr_agg_cte.c.pr_list,
                )
                .join(
                    pr_agg_cte,
                    table_rel_w_prs.c.id == pr_agg_cte.c.cmssw_release_w_prs_id,
                )
                .join(
                    table_rels,
                    table_rel_w_prs.c.cmssw_release_id == table_rels.c.id,
                )
            )
            # Finally, filter by the passed arguments
            if id:
                query = query.where(table_rel_w_prs.c.id == id)
            if pr_nums:
                query = query.where(
                    pr_agg_cte.c.pr_list
                    == sqlalchemy.cast(
                        text(
                            f"ARRAY[{','.join([str(pr_num) for pr_num in sorted(pr_nums)])}]"
                        ),
                        sqltypes.ARRAY(sqltypes.Integer),
                    )
                )
            if cmssw_release:
                query = query.where(table_rels.c.cmssw_version == cmssw_release)

            return cur.execute(query).mappings().all()

    def fill_cmssw_release_with_prs(
        self, cmssw_release: str, pr_nums: list = []
    ) -> dict | None:
        """ """
        assert isinstance(cmssw_release, str), "cmssw_release must be a str"
        assert isinstance(pr_nums, list) and all(
            isinstance(pr_num, int) for pr_num in pr_nums
        )
        assert list(set(sorted(pr_nums))) == sorted(
            pr_nums
        ), "Duplicate PR given in list"
        cmssw_release_db, _ = self.get_or_create_cmssw_release(
            cmssw_release=cmssw_release
        )
        cmssw_release_id = cmssw_release_db["id"]
        prs_in_db = []
        for pr_num in pr_nums:
            pr_id, _ = self.get_or_create_cmssw_pr(cmssw_pr=pr_num)
            assert pr_id
            prs_in_db.append(pr_id)

        with self.engine.connect() as cur:
            table_rel_w_prs = self.db_meta.tables[self.TB_NAME_CMSSW_RELEASES_WITH_PRS]
            rel_w_prs = (
                cur.execute(
                    sqlalchemy.insert(table_rel_w_prs)
                    .values(
                        dict(
                            zip(
                                self.TB_DESCRIPTION_CMSSW_RELEASES_WITH_PRS_COLS,
                                [cmssw_release_id],
                            )
                        )
                    )
                    .returning(table_rel_w_prs)
                )
                .mappings()
                .first()
            )
            table_rel_w_prs_to_prs = self.db_meta.tables[
                self.TB_NAME_RELEASE_WITH_PRS_TO_PRS
            ]
            if prs_in_db:
                # Fill the Many to Many intermediate table
                cur.execute(
                    sqlalchemy.insert(table_rel_w_prs_to_prs)
                    .values(
                        [
                            dict(
                                zip(
                                    self.TB_DESCRIPTION_RELEASE_WITH_PRS_TO_PRS_COLS,
                                    [
                                        rel_w_prs["id"],
                                        pr_in_db["pr_num"],
                                    ],
                                )
                            )
                            for pr_in_db in prs_in_db
                        ]
                    )
                    .returning(table_rel_w_prs_to_prs)
                )
            return self.get_cmssw_release_with_prs(id=rel_w_prs["id"])[0]

    def get_cmssw_pr(self, cmssw_pr: int) -> dict:
        with self.engine.connect() as cur:
            result = cur.execute(
                sqlalchemy.select(self.db_meta.tables[self.TB_NAME_CMSSW_PRS]).where(
                    self.db_meta.tables[self.TB_NAME_CMSSW_PRS].c.pr_num == cmssw_pr
                )
            )
            if result:
                return result.mappings().first()
            return {}

    def fill_cmssw_pr(self, cmssw_pr: int) -> dict | None:
        assert isinstance(cmssw_pr, int), "cmssw_pr must be an int"
        table = self.db_meta.tables[self.TB_NAME_CMSSW_PRS]
        with self.engine.connect() as cur:
            return (
                cur.execute(
                    sqlalchemy.insert(table)
                    .values(dict(zip(self.TB_DESCRIPTION_CMSSW_PRS_COLS, [cmssw_pr])))
                    .returning(table)
                )
                .mappings()
                .first()
            )

    def get_or_create_cmssw_pr(self, cmssw_pr: int) -> tuple[dict | None, bool]:
        if result := self.get_cmssw_pr(cmssw_pr=cmssw_pr):
            return result, False
        return self.fill_cmssw_pr(cmssw_pr=cmssw_pr), True

    def get_mirror_data(self, run_number: int) -> tuple:
        """
        Gets information for a specific run from the DB.

        Returns a tuple: global_data and clients_data (???)
        """
        runs = self.get_run(run_number, run_number)
        runs_out = [format_run_data(run) for run in runs]
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
        runs = self.get_run(run_start, run_end, bad_only, with_ls_only)
        runs_out = [format_table_entry(run) for run in runs]

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

    def get_clients(self, run_start: int, run_end: int) -> list:
        self.log.debug("DQM2MirrorDB.get_clients()")
        with self.engine.connect() as cur:
            answer = cur.execute(
                text(
                    f"SELECT DISTINCT client FROM {self.TB_NAME_RUNS} "
                    + "WHERE run BETWEEN :run_start AND :run_end ORDER BY client;"
                ),
                run_start=run_start,
                run_end=run_end,
            ).all()
        answer = [
            get_short_client_name(name[0]) for name in answer if filter_clients(name[0])
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
                    text(
                        f"DELETE FROM {self.TB_NAME_META} WHERE name = 'min_max_runs';"
                    )
                )
                with self.engine.connect() as cur:
                    cur.execute(
                        text(
                            f"INSERT INTO {self.TB_NAME_META} {self.TB_DESCRIPTION_META_SHORT} VALUES('min_max_runs', '[:min,:max]');"
                        ),
                        min=new_min,
                        max=new_max,
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
                text(
                    f"SELECT data FROM {self.TB_NAME_META} WHERE name = 'min_max_runs';"
                )
            ).all()

            if answer:
                return eval(answer[0][0])

            answer = cur.execute(
                text(f"SELECT MIN(run), MAX(run) FROM {self.TB_NAME_RUNS};")
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
                    text(
                        f"SELECT MAX(rev) FROM {self.TB_NAME_RUNS} WHERE hostname=:host;"
                    ),
                    host=host,
                ).all()
                answer = list(answer[0])
                return answer[0]
            else:
                answer = cur.execute(
                    text(
                        f"SELECT MAX(rev) FROM {self.TB_NAME_GRAPHS} WHERE hostname=:host;"
                    ),
                    host=host,
                ).all()
                answer = list(answer[0])
                return answer[0]

    def get_logs(self, client_id: str) -> list:
        self.log.debug("DQM2MirrorDB.get_logs()")
        with self.engine.connect() as cur:
            answer = cur.execute(
                text(
                    f"SELECT stdlog_start, stdlog_end FROM {self.TB_NAME_RUNS} WHERE id=:client_id;"
                ),
                client_id=client_id,
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
                text(
                    f"SELECT min(run) FROM {self.TB_NAME_RUNS} WHERE run>:run_number union "
                    + f"SELECT max(run) FROM {self.TB_NAME_RUNS} WHERE run<:run_number;"
                ),
                run_number=run,
            ).all()
            answer = [item[0] for item in answer]
        return answer


if __name__ == "__main__":
    logging.basicConfig()
    logging.getLogger("sqlalchemy.engine").setLevel(logging.DEBUG)
    db_playback = DQM2MirrorDB(
        log=logging.getLogger(__name__),
        host=cfg.get("DB_PLAYBACK_HOST"),
        port=cfg.get("DB_PLAYBACK_PORT"),
        username=cfg.get("DB_PLAYBACK_USERNAME"),
        password=cfg.get("DB_PLAYBACK_PASSWORD"),
        db_name=cfg.get("DB_PLAYBACK_NAME"),
    )
