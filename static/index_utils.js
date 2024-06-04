/*
    Helper JS functions.
*/

// After how many seconds to consider a status update stale
const STALE_STATUS_SEC = 120;


function update_table(run_id, data) {
    other_runs = data[0]
    global_data = data[1][0];
    clients_data = data[1][1];

    // Other runs info
    let run_navigation = document.getElementById("runNavigation");
    run_navigation.innerHTML = ""; // Clear all links

    if (other_runs[1] != null) {
        if (other_runs[1] < run_id) {
            let b = other_runs[0];
            other_runs[0] = other_runs[1];
            other_runs[1] = b;
        }
    };

    // Create links to next and previous run
    if (other_runs[0] != null) {
        let prev = document.createElement("a");
        prev.setAttribute("href", `${PREFIX}?run=${other_runs[0]}&db=${db}`);
        let i = document.createElement("i");
        i.classList.add("bi", "bi-caret-left-square-fill", "me-2");
        let span = document.createElement("span");
        span.innerHTML = other_runs[0];
        prev.appendChild(i);
        prev.appendChild(span);
        prev.classList.add("btn", "btn-light", "btn-outline-dark");
        prev.setAttribute("title", `Show info for run ${other_runs[0]}`)
        run_navigation.appendChild(prev);
    }
    // Current run
    let current = document.createElement("a");
    current.innerHTML = `${run_id}`;
    current.setAttribute("title", "This is the currently displayed run")
    current.classList.add("btn", "btn-light", "btn-outline-dark");
    run_navigation.appendChild(current);
    // Next run
    if (other_runs[1] != null) {
        let next = document.createElement("a");
        next.setAttribute("href", `${PREFIX}?run=${other_runs[1]}&db=${db}`);
        let i = document.createElement("i");
        i.classList.add("bi", "bi-caret-right-square-fill", "ms-2");
        let span = document.createElement("span");
        span.innerHTML = other_runs[1];
        next.appendChild(span);
        next.appendChild(i);
        next.classList.add("btn", "btn-light", "btn-outline-dark");
        next.setAttribute("title", `Show info for run ${other_runs[1]}`)
        run_navigation.appendChild(next);
    }

    // Table creation
    let tb_main = document.getElementById("runTable");
    tb_main.innerHTML = '';

    let tr = document.createElement("tr");
    for (let header of runs_table_config) {
        if (header.skip === true) {
            continue;
        }
        let td = document.createElement("th");
        td.innerText = header["title"];
        if (header.extra_classes !== undefined && header.extra_classes instanceof Array) {
            td.classList.add(...header.extra_classes);
        }
        tr.appendChild(td);
    }
    tb_main.appendChild(tr);

    // Count DQM clients in each state
    let num_clients_running = 0;
    let num_clients_stopped = 0;
    let num_clients_crashed = 0;
    let num_clients_stuck = 0;

    let diff_warning = runs_table_config.find(obj => obj.title == 'Time Diff').diff_warning

    // (timestamp, td, hostname, fi_state, client, cmssw_lumi, VmRSS, events_total, id, events_rate)
    for (let client_data of clients_data) {
        tr = document.createElement("tr");
        // Timestamp that client was running
        client_data[0] = new Date(client_data[0]).toLocaleString('en-GB', { hour12: false, timeZone: TIMEZONE });
        if (client_data[9] < 0) client_data[9] = 0
        // Event process speed
        client_data[7] = client_data[7] + " (" + client_data[9].toFixed(1) + " ev/s)"

        id = client_data[8]

        let exit_code = client_data[3];
        let state = exit_code;
        let is_process_running = false;
        let base_css_class;
        let custom_css_class;

        if ((exit_code === null) || (exit_code === undefined) || (exit_code === -1)) {
            is_process_running = true;
            if (client_data[1] >= diff_warning) {
                base_css_class = "table-dark";
                custom_css_clas = "table-dark-custom";
                num_clients_stuck += 1;
            } else {
                base_css_class = "table-success";
                custom_css_class = "table-success-custom";
                num_clients_running += 1; // Count running processes
            }
        } else if ((exit_code === 0) || (exit_code === "0")) {
            base_css_class = "table-warning";
            custom_css_class = "table-warning-custom";
            num_clients_stopped += 1; // Count stopped processes
            client_data[3] = state;
        } else {
            base_css_class = "table-danger";
            custom_css_class = "table-danger-custom";
            num_clients_crashed += 1; // Count failed processes
            client_data[3] = state;
        }
        
        tr.classList.add(base_css_class);
        tr.classList.add(custom_css_class);

        // Populate table
        for (const [i, data] of client_data.entries()) {
            if (runs_table_config[i].skip === true) {
                continue
            }

            let td = document.createElement("td");

            if (runs_table_config[i].extra_classes !== undefined && runs_table_config[i].extra_classes instanceof Array) {
                td.classList.add(...runs_table_config[i].extra_classes);
            }
            if (runs_table_config[i].hovertext !== undefined) {
                td.setAttribute("title", runs_table_config[i].hovertext);
            }
            // Color alternating columns darker
            if (is_process_running && i == 3) {
                // Div for spinner only for running processes
                let running_icon = document.createElement("i");
                running_icon.classList.add("bi", "bi-person-walking")
                running_icon.setAttribute("title", "Process is running")
                td.appendChild(running_icon)
            } else {
                let format_func = runs_table_config[i].format_function;
                if (format_func !== undefined && typeof (format_func) === "function") {
                    td.innerText = format_func(data);
                } else {
                    td.innerText = data;
                }
            }
            td.classList.add("align-middle")
            tr.appendChild(td);
        }

        // Link to logs
        let td = document.createElement("td");
        let log_link = `${PREFIX}api?what=get_logs&id=${id}&db=${db}`;
        let a = document.createElement("a");
        a.classList.add("hidden-link-dark");
        a.setAttribute("href", log_link);
        a.setAttribute("target", "#");
        let i = document.createElement("i");
        i.setAttribute("title", "Open log in a new tab");
        i.classList.add("bi", "bi-file-earmark-text-fill");
        a.appendChild(i);
        td.appendChild(a);
        tr.appendChild(td);
        tb_main.appendChild(tr);
    }

    // Run info table update
    let el_cmssw_version = document.getElementById("cmssw-version-badge");
    el_cmssw_version.innerHTML = `${global_data[0]}`;
    let el_run_key = document.getElementById("run-info-key-badge");
    el_run_key.innerHTML = `${global_data[1]}`;
    // let el_known_jobs = document.getElementById("run-info-known-jobs");
    // el_known_jobs.innerHTML = `${clients_data.length}`;

    let el_jobs_running = document.getElementById("jobs-running-badge");
    el_jobs_running.innerHTML = num_clients_running;

    let el_jobs_stopped = document.getElementById("jobs-stopped-badge");
    el_jobs_stopped.innerHTML = num_clients_stopped;

    let el_jobs_crashed = document.getElementById("jobs-crashed-badge");
    el_jobs_crashed.innerHTML = num_clients_crashed;
    
    let el_jobs_stuck = document.getElementById("jobs-stuck-badge");
    el_jobs_stuck.innerHTML = num_clients_stuck;

};
// timedelta is in ms
function get_time_diff(timedelta) {
    let days = Math.floor(timedelta / (3600 * 24));
    timedelta -= days * 3600 * 24;
    let hours = Math.floor(timedelta / 3600);
    timedelta -= hours * 3600;
    let minutes = Math.floor(timedelta / 60);
    let seconds = Math.floor(timedelta - minutes * 60);
    return { "days": days, "hours": hours, "minutes": minutes, "seconds": seconds }
}

function get_time_diff_str(timedelta_parsed) {
    let days = timedelta_parsed.days;
    let hours = timedelta_parsed.hours;
    let minutes = timedelta_parsed.minutes;
    let seconds = timedelta_parsed.seconds;
    return days > 0 ? days + " day" + (days > 1 ? "s" : "") :
        hours > 0 ? hours + " hour" + (hours > 1 ? "s" : "") :
            minutes > 0 ? minutes + " minute" + (minutes > 1 ? "s" : "") :
                seconds + " second" + (seconds > 1 ? "s" : "")
}

/*
  Updates both graphs (file delivery and events processed.)
  */
function update_graph(data) {
    const LUMI = 23.310893056;  // Time duration of a lumisection, in seconds
    if (data.length < 6) {
        return;
    };
    let stream_data = data[5];
    let global_start = data[4];


    const labels = [];  // Labels for different data series
    const array_delay_times = [];
    const array_events_accepted = [];

    if (typeof stream_data === 'undefined') { return };
    // For each stream, create two timeseries: delay times and events accepted
    for (const [stream, stream_datum] of Object.entries(stream_data)) {
        stream_name = stream.split('_')[0];
        labels.push(stream_name);
        const data_delay_times = [];
        const data_events_accepted = [];

        let lumis = stream_datum['lumis'];
        let mtimes = stream_datum['mtimes'];
        let evt_accepted = stream_datum['evt_accepted'];
        let delay_mtimes = Array(lumis.length);
        // copy paste logic from fff code
        for (index = 0; index < lumis.length; index++) {
            let start_offset_mtime = mtimes[index] - global_start - LUMI;
            let lumi_offset = (lumis[index] - 1) * LUMI;
            let delay_mtime = start_offset_mtime - lumi_offset;
            delay_mtimes[index] = delay_mtime;

            data_delay_times.push({ 'x': lumis[index], 'y': delay_mtimes[index] });
            data_events_accepted.push({ 'x': lumis[index], 'y': evt_accepted[index] });
        };
        array_delay_times.push(data_delay_times);
        array_events_accepted.push(data_events_accepted);

    }

    if (labels.length) {
        const spinner = document.getElementById("chartsSpinner");
        spinner.classList.add("d-none");
        const data_chart_delay_times = [];
        const data_chart_events_accepted = [];
        const borderColors = ["#3366CC", "#DC3912", "#FF9900", "#109618", "#990099", "#3B3EAC", "#0099C6", "#DD4477", "#66AA00", "#B82E2E", "#316395", "#994499", "#22AA99", "#AAAA11", "#6633CC", "#E67300", "#8B0707", "#329262", "#5574A6", "#651067"];
        for (index = 0; index < labels.length; index++) {
            data_chart_delay_times.push({ label: [labels[index]], data: array_delay_times[index], fill: false, borderColor: borderColors[index], });
            data_chart_events_accepted.push({ label: [labels[index]], data: array_events_accepted[index], fill: false, borderColor: borderColors[index], });
        }


        if (chart_delay_times instanceof Chart) {
            chart_delay_times.data = { datasets: data_chart_delay_times };
            chart_delay_times.update();
        } else {
            const div1 = document.getElementById('chartDelayTimes');
            const ctx1 = document.createElement("canvas");
            div1.appendChild(ctx1)
            chart_delay_times = new Chart(ctx1, {
                type: 'bubble',
                data: { datasets: data_chart_delay_times },
                options: {
                    animation: false,
                    plugins: {
                        title: {
                            display: true,
                            text: 'DQM File Delivery'
                        }
                    },
                    scales: {
                        x: {
                            title: {
                                display: true,
                                text: "LS"
                            }
                        },
                        y: {
                            title: {
                                display: true,
                                text: "File delivery delay, s"
                            }
                        },
                    },
                }
            });

        };


        if (chart_events_accepted instanceof Chart) {
            chart_events_accepted.data = { datasets: data_chart_events_accepted };
            chart_events_accepted.update();
        } else {
            const div2 = document.getElementById('chartEventsAccepted');
            const ctx2 = document.createElement("canvas");
            div2.appendChild(ctx2)

            chart_events_accepted = new Chart(ctx2, {
                type: 'bubble',
                data: { datasets: data_chart_events_accepted },
                options: {
                    animation: false,
                    plugins: {
                        title: {
                            display: true,
                            text: 'DQM Event Rate'
                        },
                    },
                    scales: {
                        x: {
                            title: {
                                display: true,
                                text: "LS"
                            }
                        },
                        y: {
                            title: {
                                display: true,
                                text: "Accepted events"
                            }
                        },
                    },
                }
            });
        }

    }
    else {
        let spinner = document.getElementById("chartsSpinner");
        spinner.classList.remove("d-none");
    };
};



/*
Get run data for a run, from specific db
*/
function fetch_and_update_table_data(run_id, db) {
    fetch(`${PREFIX}api?what=get_run&run=${run_id}&db=${db}`)
        .then(data => data.json())
        .then(data => { update_table(run_id, data) })
        .catch(error => console.log(`Error when getting table data: ${error}`));
}

/*
Get graph data for a run, from specific db
*/
function fetch_and_update_graph_data(run_id, db) {
    fetch(`${PREFIX}api?what=get_graph&run=${run_id}&db=${db}`)
        .then(data => data.json())
        .then(data => update_graph(data))
        .catch(error => console.log(`Error when getting graph data: ${error}`));
}

/*
Fetch data for a specific run and update tables & graphs
*/
function update_tables(run_number) {
    fetch_and_update_table_data(run_number, db);
    fetch_and_update_graph_data(run_number, db);
}

function start_live(start) {
    if (start !== true) {
        return;
    }
    window.timer_load_production = 0;
    window.timer_load_playback = 0;
    if (db == "playback") {
        load_playback();
    } else if (db == "production") {
        load_production()
    };
}

async function load_production() {
    db = "production";
    await fetch(
        `${PREFIX}api?what=get_info&db=${db}`,
        { method: 'GET' })
        .then(
            response => response.json())
        .then(
            data => update_tables(data[1])
        ).catch(
            error => console.error('error:', error)
        );
    window.timer_load_production = setTimeout(load_production, RELOAD_TIME);
    document.getElementById("btnProduction").classList.add('active-glamour');
};

async function load_playback() {
    db = "playback";
    await fetch(
        `${PREFIX}api?what=get_info&db=${db}`,
        { method: 'GET' })
        .then(
            response => response.json()
        ).then(
            (data) => update_tables(data[1])
        ).catch(
            error => console.error('error:', error)
        );

    window.timer_load_playback = setTimeout(load_playback, RELOAD_TIME);
    document.getElementById("btnPlayback").classList.add('active-glamour');
};


function init_load_playback(PREFIX) {
    window.location = `${PREFIX}?db=playback`;
}

function init_load_production(PREFIX) {
    window.location = `${PREFIX}?db=production`;
}

async function get_cluster_status(cluster) {
    return fetch(`${PREFIX}api?what=get_cluster_status&cluster=${cluster}`).then(response => {
        return response.json()
    }).then(data => {
        return data
    })
        .catch(reason => {
            console.error(`Failed to get ${cluster} cluster status: `, reason)
            return {};
        });
}

// Given an array of { hostname, is_up, last_update } objects, populate the cluster_status table
function update_cluster_status(cluster_status) {
    let table_cluster = document.getElementById("clusterStatus");
    table_cluster.innerHTML = "";
    cluster_status.forEach(element => {
        let hostname = element[0];
        let is_up = element[1]; //
        let msg = element[2]; // Error messages, if any
        let last_update = element[3]; // Last status udpate, in seconds
        let tr = document.createElement("tr");
        let td = document.createElement("td");
        td.innerHTML = hostname;
        let spinner = document.getElementById("clusterStatusSpinner");
        spinner.classList.add("d-none")
        let td_status = document.createElement("td");
        let td_badge = document.createElement("div");
        td_badge.classList.add("badge")

        let last_update_delta = (Date.now() / 1000 - last_update);
        if (last_update_delta > STALE_STATUS_SEC) {
            let badge = document.createElement("div")
            badge.classList.add("badge", "bg-secondary", "me-1");
            let clock = document.createElement("i");
            clock.classList.add("bi", "bi-hourglass-bottom")
            badge.appendChild(clock);
            let time_delta = get_time_diff(last_update_delta)
            tr.classList.add("table-warning")
            td_badge.innerHTML = "Unknown"
            td_badge.classList.add("bg-warning")
            badge.setAttribute("title", `Last update was ${get_time_diff_str(time_delta)} ago`)
            td_status.appendChild(badge);
        }
        else if (is_up === true) {
            td_badge.classList.add("bg-success")
            td_badge.innerHTML = "Up";
            tr.classList.add("table-success");
        }
        else if (is_up === false) {
            td_badge.classList.add("bg-danger")
            td_badge.innerHTML = "Down";
            tr.classList.add("table-danger");
        }
        td_status.appendChild(td_badge);

        if (msg !== null) {
            let badge_msg = document.createElement("div");
            badge_msg.classList.add("badge", "bg-danger", "ms-1")
            let msg_i = document.createElement("i");
            msg_i.classList.add("bi", "bi-info-lg")
            badge_msg.setAttribute("title", msg)
            badge_msg.appendChild(msg_i)
            td_status.appendChild(badge_msg)
        }
        tr.appendChild(td);
        tr.appendChild(td_status);
        table_cluster.appendChild(tr);
    });
}
