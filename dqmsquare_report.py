# P.S.~Mandrik, IHEP, https://github.com/pmandrik

import time
import datetime
from datetime import datetime, timezone
import logging
import pandas
import matplotlib.pyplot as plt
import numpy as np

import dqmsquare_cfg
from db import DQM2MirrorDB
from collections import defaultdict

log = logging.getLogger(__name__)
if __name__ == "__main__":
    cfg = dqmsquare_cfg.load_cfg()
    path_out = "tmp"

    mode = ["p7"]

    ### DQM^2-MIRROR DB
    DB_PLAYBACK_URI = DQM2MirrorDB(log, cfg["DB_PLAYBACK_URI"], server=True)
    db_production = DQM2MirrorDB(log, cfg["DB_PRODUCTION_URI"], server=True)

    ###
    db = db_production

    start_date = "01/06/2022"
    end_date = "01/09/2022"
    start_stamp = (
        time.mktime(datetime.strptime(start_date, "%d/%m/%Y").timetuple()) + 7200.0
    )
    end_stamp = (
        time.mktime(datetime.strptime(end_date, "%d/%m/%Y").timetuple()) + 7200.0
    )  # UTC to GENEVA SHIFT

    print("Analyse the runs from " + start_date + " to " + end_date)

    cur = db.engine.connect()

    answer = cur.execute(
        "SELECT run FROM "
        + db.TB_NAME_GRAPHS
        + " WHERE global_start > %s AND global_start < %s;" % (start_stamp, end_stamp)
    ).all()
    start_run = answer[0][0]
    end_run = answer[-1][0]
    runs_number = len(answer)

    print(
        " Start run = %s \n End Run = %s \n Number of runs = %s"
        % (start_run, end_run, runs_number)
    )

    df = pandas.read_sql_query(
        "SELECT client_path, id, client , run , hostname , exit_code , events_total , events_rate , cmssw_run , cmssw_lumi , runkey , fi_state, timestamp, vmrss FROM "
        + db.TB_NAME_RUNS
        + " WHERE run > %s AND run < %s;" % (start_run, end_run),
        cur,
    )

    # df_x = pandas.read_sql_query( "SELECT client , run , events_total , events_rate FROM " + db.TB_NAME_RUNS + " WHERE client = 'hlt_dqm_clientPB-live' AND events_total > 0;", cur )
    # print( df_x )
    # exit()

    df_lumi = df[df["cmssw_lumi"] > 0]
    df_good = df_lumi[df_lumi["exit_code"] == 0]

    runs = df["run"].unique()
    runs_lumi = df_lumi["run"].unique()
    print(" Runs/Non-zero-lumi-runs = ", len(runs), "/", len(runs_lumi))

    # df_lumi = df[ df['run'].isin(runs_lumi) ]

    clients = df_lumi["client"].unique()
    print(" Clients: ", clients)

    exit_codes = df["exit_code"].unique()
    print(" Exit codes: ", exit_codes)

    print("Exit code / N runs/ N runs with lumi")
    for exit_code in exit_codes:
        n_runs = df[df["exit_code"] == exit_code]["run"].unique()
        n_runs_lumi = df_lumi[df_lumi["exit_code"] == exit_code]["run"].unique()
        print(exit_code, "/", len(n_runs), "/", len(n_runs_lumi), n_runs_lumi)

    ### PLOT 1    ###     ###     ###     ###     ###     ###     ###     ###     ###     ###     ###     ###     ###
    if "all" in mode or "p1" in mode:
        print("Create plot # 1 ...")
        runs_good = list(df_lumi[df_lumi["exit_code"] == 0]["run"].unique())
        runs_bad = []

        for exit_code in exit_codes:
            if exit_code == 0:
                continue
            error_clients = df_lumi[df_lumi["exit_code"] == exit_code]
            print(exit_code, type(exit_code))
            for run, client in zip(error_clients["run"], error_clients["id"]):
                answer = cur.execute(
                    "SELECT stdlog_end FROM "
                    + db.TB_NAME_RUNS
                    + " WHERE id = '%s';" % (client)
                ).all()[0]
                answer = "".join(eval(answer[0]))
                if "Internal error, cannot get data file:" in answer:
                    runs_good.append(run)
                    pass  # skip this end of the run error
                else:
                    runs_bad.append(run)

        runs_good = set(runs_good)
        runs_bad = set(runs_bad)

        runs_good = [x for x in runs_good if x not in runs_bad]

        print(
            "GOOD/BAD/NOLUMI/SUM = ",
            len(runs_good),
            len(runs_bad),
            len(runs) - len(runs_lumi),
            len(runs_good) + len(runs_bad) + len(runs) - len(runs_lumi),
        )
        import matplotlib.pyplot as plt

        outname = "runs"
        y = [len(runs_good), len(runs_bad), len(runs) - len(runs_lumi)]
        mylabels = ["No client crashes", "1 or more client crashes/stuck", "< 0 LS"]
        mycolors = ["#4CAF50", "#DD7596", "#4F6272"]

        mylabels = [
            m + "\n{:.0f} ({:.0f}%)".format(yy, yy / sum(y) * 100)
            for m, yy in zip(mylabels, y)
        ]

        plt.pie(
            y,
            labels=mylabels,
            colors=mycolors,
            wedgeprops={"linewidth": 3, "edgecolor": "white"},
            pctdistance=0.7,
        )
        plt.title(label="Number of runs", bbox={"facecolor": "0.8", "pad": 5})
        plt.savefig(path_out + "/" + outname + ".pdf", bbox_inches="tight")

    ### PLOT 2    ###     ###     ###     ###     ###     ###     ###     ###     ###     ###     ###     ###     ###
    if "all" in mode or "p2" in mode:
        print("Create plot # 2 ...")
        clients_dic_good = defaultdict(list)
        clients_dic_bad = defaultdict(list)
        clients_dic_stuck = defaultdict(list)

        for exit_code in exit_codes:
            error_clients = df_lumi[df_lumi["exit_code"] == exit_code]
            print(exit_code, type(exit_code))
            for run, client, clinet_name in zip(
                error_clients["run"], error_clients["id"], error_clients["client"]
            ):
                if exit_code == 0:
                    clients_dic_good[clinet_name] += [run]
                    continue
                elif exit_code == -1:
                    clients_dic_stuck[clinet_name] += [run]
                    continue

                answer = cur.execute(
                    "SELECT stdlog_end FROM "
                    + db.TB_NAME_RUNS
                    + " WHERE id = '%s';" % (client)
                ).all()[0]
                answer = "".join(eval(answer[0]))

                if "Internal error, cannot get data file:" in answer:
                    clients_dic_good[clinet_name] += [run]
                else:
                    clients_dic_bad[clinet_name] += [run]

        results = {}
        for client in clients:
            g = set(clients_dic_good[client])
            b = set(clients_dic_bad[client])
            s = set(clients_dic_stuck[client])

            g = [x for x in g if x not in b]
            g = [x for x in g if x not in s]

            s = [x for x in s if x not in b]

            results[client.split("_")[0]] = [len(b), len(g), len(s)]

        category_names = ["Crash", "Good", "Stuck"]

        print(results)

        def survey(results, category_names):
            """
            Parameters
            ----------
            results : dict
                A mapping from question labels to a list of answers per category.
                It is assumed all lists contain the same number of entries and that
                it matches the length of *category_names*.
            category_names : list of str
                The category labels.
            """
            labels = list(results.keys())
            data = np.array(list(results.values()))
            data_cum = data.cumsum(axis=1)
            category_colors = ["#DD7596", "#4CAF50", "#4F6272"]

            fig, ax = plt.subplots(figsize=(9.2, 5))
            ax.invert_yaxis()
            ax.xaxis.set_visible(False)
            ax.set_xlim(0, np.sum(data, axis=1).max())

            for i, (colname, color, tcolor) in enumerate(
                zip(category_names, category_colors, ["Red", "Green", "Black"])
            ):
                widths = data[:, i]
                starts = data_cum[:, i] - widths
                rects = ax.barh(
                    labels, widths, left=starts, height=0.8, label=colname, color=color
                )
                # ax.bar_label(rects, label_type='center', color='white')

                for j, (w, s) in enumerate(zip(widths, starts)):
                    if w == 0:
                        continue
                    ax.text(
                        s + w / 2, j + 0.25, str(w), color=tcolor, fontweight="bold"
                    )

            ax.legend(
                ncol=len(category_names),
                bbox_to_anchor=(0, 1),
                loc="lower left",
                fontsize="small",
            )
            return fig, ax

        outname = "clients"
        survey(results, category_names)
        plt.title(
            label="Number of runs (LS > 0) per client",
            bbox={"facecolor": "0.8", "pad": 5},
            loc="right",
        )
        plt.savefig(path_out + "/" + outname + ".pdf", bbox_inches="tight")

    ### PLOT 3    ###     ###     ###     ###     ###     ###     ###     ###     ###     ###     ###     ###     ###
    if "all" in mode or "p3" in mode:
        print("Create plot # 3 ...")
        clients_dic_bad = defaultdict(list)
        clients_dic_stuck = defaultdict(list)

        for exit_code in exit_codes:
            error_clients = df_lumi[df_lumi["exit_code"] == exit_code]
            print(exit_code, type(exit_code))
            for run, client, clinet_name in zip(
                error_clients["run"], error_clients["id"], error_clients["client"]
            ):
                if exit_code == 0:
                    continue
                elif exit_code == -1:
                    clients_dic_stuck[clinet_name] += [run]
                    continue

                answer = cur.execute(
                    "SELECT stdlog_end FROM "
                    + db.TB_NAME_RUNS
                    + " WHERE id = '%s';" % (client)
                ).all()[0]
                answer = "".join(eval(answer[0]))

                if "Internal error, cannot get data file:" in answer:
                    pass
                else:
                    clients_dic_bad[clinet_name] += [run]

        results = []
        clients_names = []
        for client in clients:
            b = set(clients_dic_bad[client])
            s = set(clients_dic_stuck[client])

            s = [x for x in s if x not in b]

            if len(b):
                clients_names += [client.split("_")[0]]
                results += [len(b)]
                print(client.split("_")[0], b)

        outname = "clients_bad"
        print(results)

        mylabels = [
            m + "\n{:.0f} ({:.0f}%)".format(yy, yy / sum(results) * 100)
            for m, yy in zip(clients_names, results)
        ]

        plt.pie(
            results,
            labels=mylabels,
            wedgeprops={"linewidth": 3, "edgecolor": "white"},
            pctdistance=0.7,
        )
        plt.title(
            label="Number of bad runs (LS > 0) per client",
            bbox={"facecolor": "0.8", "pad": 5},
        )
        plt.savefig(path_out + "/" + outname + ".pdf", bbox_inches="tight")

    ### PLOT 4    ###     ###     ###     ###     ###     ###     ###     ###     ###     ###     ###     ###     ###
    if "all" in mode or "p4" in mode:
        print("Create plot # 4 ...")

        keys = df_lumi["runkey"].unique()
        results = []
        names = []
        for name in keys:
            rows = df_lumi[df_lumi["runkey"] == name]["run"].unique()
            names += [name]
            results += [len(rows)]

        outname = "runkey"
        print(results)

        mylabels = [
            m + "\n{:.0f} ({:.0f}%)".format(yy, yy / sum(results) * 100)
            for m, yy in zip(names, results)
        ]

        plt.pie(
            results,
            labels=mylabels,
            wedgeprops={"linewidth": 3, "edgecolor": "white"},
            pctdistance=0.7,
        )
        plt.title(
            label="Number of runs (LS > 0) per runkey",
            bbox={"facecolor": "0.8", "pad": 5},
        )
        plt.savefig(path_out + "/" + outname + ".pdf", bbox_inches="tight")

    ### PLOT 5    ###     ###     ###     ###     ###     ###     ###     ###     ###     ###     ###     ###     ###
    if "all" in mode or "p5" in mode:
        print("Create plot # 5 ...")

        for client in clients:
            if client == "hlt_dqm_clientPB-live":
                continue
            print(client)
            df_clients = df_good[df_good["client"] == client]
            # df_clients = df_clients[ df_clients["cmssw_lumi"] > 200]
            df_clients = df_clients[df_clients["events_rate"] > 0]
            df_clients_pp = df_clients[df_clients["runkey"] == "runkey=pp_run"]
            df_clients_co = df_clients[df_clients["runkey"] == "runkey=cosmic_run"]
            y_points = df_clients_co["events_rate"]
            x_points = df_clients_co["run"]
            y_points_pp = df_clients_pp["events_rate"]
            x_points_pp = df_clients_pp["run"]
            # print( client, "info\n", y_points_pp.describe() )

            plt.plot(
                x_points,
                y_points,
                "bo",
                markersize=1.5,
                label="cosmic ER mean = %.1f +- %.1f STD"
                % (y_points.mean(), y_points.std()),
            )
            plt.plot(
                x_points_pp,
                y_points_pp,
                "ro",
                markersize=1.5,
                label="pp ER mean = %.1f +- %.1f STD"
                % (y_points_pp.mean(), y_points_pp.std()),
            )
            plt.xlabel("Run Number")
            plt.ylabel("Event Rate (evt/s)")
            plt.title(
                label="Event rate of " + client.split("_")[0] + " client",
                bbox={"facecolor": "0.8", "pad": 5},
            )
            plt.legend(loc="lower left")
            # plt.xscale('log')
            plt.yscale("log")

            plt.savefig(
                path_out + "/XXXEvR_" + client.split("_")[0] + ".pdf",
                bbox_inches="tight",
            )
            plt.show()

            x_points = df_clients_co["cmssw_lumi"]
            x_points_pp = df_clients_pp["cmssw_lumi"]

            plt.plot(
                x_points,
                y_points,
                "bo",
                markersize=1.5,
                label="cosmic ER mean = %.1f +- %.1f STD"
                % (y_points.mean(), y_points.std()),
            )
            plt.plot(
                x_points_pp,
                y_points_pp,
                "ro",
                markersize=1.5,
                label="pp ER mean = %.1f +- %.1f STD"
                % (y_points_pp.mean(), y_points_pp.std()),
            )
            plt.xlabel("Number of LS")
            plt.ylabel("Event Rate (evt/s)")
            plt.title(
                label="Event rate vs Number of LS of "
                + client.split("_")[0]
                + " client",
                bbox={"facecolor": "0.8", "pad": 5},
            )
            plt.legend(loc="lower left")
            plt.xscale("log")
            plt.yscale("log")

            plt.savefig(
                path_out + "/XXXEvR_vs_LS_" + client.split("_")[0] + ".pdf",
                bbox_inches="tight",
            )

            plt.show()

    ### PLOT 6    ###     ###     ###     ###     ###     ###     ###     ###     ###     ###     ###     ###     ###
    if "all" in mode or "p6" in mode:
        print("Create plot # 6 ...")
        if True:
            # df_clients = df_clients[ df_clients["cmssw_lumi"] > 200]
            df_clients = df_good[df_good["events_total"] > 0]
            df_clients_pp = df_clients[df_clients["runkey"] == "runkey=pp_run"]
            df_clients_co = df_clients[df_clients["runkey"] == "runkey=cosmic_run"]

            def get_release(name):
                x = name.split("/")[4].split("_")[2:]
                answer = [x[0]]
                for xx in x:
                    if len(xx) == 0:
                        continue
                    if len(xx) >= 5:
                        continue
                    answer += [xx]

                return "_".join(answer)

            df_points = df_clients_co[["run", "client_path"]]
            df_points["client_path"] = df_points["client_path"].apply(
                lambda x: get_release(x)
            )

            df_points_pp = df_clients_pp[["run", "client_path"]]
            df_points_pp["client_path"] = df_points_pp["client_path"].apply(
                lambda x: get_release(x)
            )

            releases = df_points["client_path"].unique()

            x_points = []
            y_points, y_points_pp = [], []
            for release in releases:
                y_points += [
                    len(df_points[df_points["client_path"] == release]["run"].unique())
                ]
                y_points_pp += [
                    len(
                        df_points_pp[df_points_pp["client_path"] == release][
                            "run"
                        ].unique()
                    )
                ]
                x_points += [release]

            print(x_points, y_points)

            plt.plot(x_points, y_points, markersize=1.5, label="cosmic runs")
            plt.plot(x_points, y_points_pp, markersize=1.5, label="pp runs")
            plt.xlabel("CMSSW release")
            plt.ylabel("Number of runs")
            plt.title(
                label="Number of runs per release", bbox={"facecolor": "0.8", "pad": 5}
            )
            plt.legend(loc="lower left")
            plt.xticks(rotation=90)

            plt.savefig(path_out + "/releases.pdf", bbox_inches="tight")
            plt.show()

    ### PLOT 7    ###     ###     ###     ###     ###     ###     ###     ###     ###     ###     ###     ###     ###
    if "all" in mode or "p7" in mode:
        import re

        answer = cur.execute(
            "SELECT client , run , exit_code , events_rate , stdlog_start, stdlog_end FROM "
            + db.TB_NAME_RUNS
            + " WHERE run > %s AND run < %s;" % (start_run, end_run)
        ).all()
        for row in answer:
            log_s = row[-2]
            log_e = row[-1]

            log_s += log_e

            result1 = [_.start() for _ in re.finditer("Warning", log_s)]

            for result in result1:
                warning_data = log_s[result : result + 200]
                if "warnings of this type will be suppressed" in warning_data:
                    continue
                print(row[0], log_s[result : result + 200])
