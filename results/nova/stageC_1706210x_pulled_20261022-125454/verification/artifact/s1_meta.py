import json, glob, os, re
D="/Users/akshat/research/jannesari-swapp/results/nova/stageC_1706210x_pulled_20261022-125454/agentload_c_closed"
for r in sorted(glob.glob(D+"/*")):
    m=json.load(open(r+"/meta.json"))
    argv=" ".join(m["argv"])
    n=re.search(r"closed_n=(\d+)",argv).group(1)
    o=m["outcome"]
    print(os.path.basename(r), "n=",n, m["engine_label"], m["hostname"], m["hardware"], m["slurm_env"]["SLURM_JOB_ID"], m["t0_utc"], m["start_time"], "verified",m["start_state_verified"], m["start_state_detail"][:9],
          "req ok/err/canc",o["requests_ok"],o["requests_error"],o["requests_cancelled"],"maxinfl",o["max_inflight_seen"],"oids",o["output_ids_source_counts"],"ptmismatch",o["prompt_tokens_mismatch"],o["prompt_tokens_missing_in_response"],"errs",o["errors_by_kind"],"abort",o["abort_reason"],"scrapefail",o["metrics_scrape_failures"],o["metrics_skipped_ticks"], "git",m["git"]["commit"][:8],m["git"]["dirty"])
