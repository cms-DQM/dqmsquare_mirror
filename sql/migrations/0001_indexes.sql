-- Add indexes
CREATE INDEX IF NOT EXISTS runs_run_index ON runs (run);

CREATE INDEX IF NOT EXISTS runs_hostname_index ON runs (hostname);

CREATE INDEX IF NOT EXISTS hostnames_name_index ON hostnames (name);

CREATE INDEX IF NOT EXISTS hoststatuses_host_id_index ON hoststatuses (host_id);