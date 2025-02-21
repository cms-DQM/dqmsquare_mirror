-- Add indices
CREATE INDEX IF NOT EXISTS runs_run_index ON runs (run);

CREATE INDEX IF NOT EXISTS runs_hostname_index ON runs (hostname);

CREATE INDEX IF NOT EXISTS hostnames_name_index ON hostnames (name);

CREATE INDEX IF NOT EXISTS hoststatuses_host_id_index ON hoststatuses (host_id);

CREATE INDEX IF NOT EXISTS hoststatuses_host_id_created_at ON hoststatuses (host_id, created_at DESC);

CREATE INDEX IF NOT EXISTS cmsswcomparisonreports_id_comparison_ran_at ON cmssw_comparison_reports (id, comparison_ran_at DESC);

CREATE INDEX IF NOT EXISTS cmssw_releases_cmssw_version ON cmssw_releases (cmssw_version);

CREATE INDEX IF NOT EXISTS cmssw_release_with_prs_to_cmssw_prs_pk ON cmssw_release_with_prs_to_cmssw_prs (cmssw_release_w_prs_id, cmssw_pr_id);