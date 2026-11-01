"""Build provenance/push_times_2026-10.tsv from the archived server records.

For each registration or prediction commit it finds the first ref update in
GitHub's activity log (github_activity_2026-10.json) whose new head contains the
commit, the matching entry in GitHub's event log (github_events_2026-10.json),
and the Slurm submit/start/end times of the first job of the corresponding batch
(sacct_cited_jobs_2026-10-30.txt). Times are converted to CDT (UTC-5), the
cluster's local time. Run from the repository root:

    python provenance/make_push_times.py > provenance/push_times_2026-10.tsv

The refresh of 2026-11-01 reads a newer activity export and sacct snapshot and adds the rows of
rounds 11 to 14 (EXTRA_ROWS); the rows above are unchanged:

    python provenance/make_push_times.py --activity github_activity_2026-11-01.json         --sacct sacct_cited_jobs_2026-11-01.txt --extra > provenance/push_times_2026-11-01.tsv
"""
import argparse
import csv
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
CDT = timezone(timedelta(hours=-5))
ZERO = "0" * 40

# event, commit, batch label, first job ID of that batch
ROWS = [
    ("B1 predictions (E0a already run)", "64bc4e3", "SGLang E0a", "17072634"),
    ("B2 predictions (E0b already run, not yet pulled)", "64bc4e3", "SGLang E0b", "17084750"),
    ("B3 predictions", "64bc4e3", "SGLang E2", "17093387"),
    ("B4 predictions", "64bc4e3", "native-pool Stage C and E0a", "17096856"),
    ("E2 registration", "d279b7b", "SGLang E2", "17093387"),
    ("B1n and B4n predictions (native curve already run)", "e3ea48f", "native-pool Stage C and E0a", "17096856"),
    ("B2n predictions (native E0b running)", "e3ea48f", "native E0b", "17100938"),
    ("B3n predictions", "e3ea48f", "native E2", "17102173"),
    ("native registration", "b8c19ec", "native E2", "17102173"),
    ("vLLM exploratory registration", "a78ce07", "vLLM BURST (exploratory)", "17102318"),
    ("B4v predictions (round 9)", "cc01dbf", "vLLM Stage C", "17162959"),
    ("B2v predictions (round 9)", "cc01dbf", "vLLM E0b", "17162962"),
    ("B3v predictions (round 9)", "cc01dbf", "vLLM registered paired test", "17166121"),
    ("vLLM registration", "5a6fbcd", "vLLM registered paired test", "17166121"),
]

# rounds 11 to 14 (2026-10-30 evening to 2026-10-31); used with --extra
EXTRA_ROWS = [
    ("BASIN-1 simulator predictions (r11 S1 bundle 1)", "c600fd7", "BASIN-1", "17168500"),
    ("BASIN-1 registrations (tag r11-basin-reg)", "9b67c26", "BASIN-1", "17168500"),
    ("LPM-INF exploratory registration (tag r11-lpminf-pred)", "5064580", "LPM-INF", "17168743"),
    ("rescue simulator predictions (tag r11-rescue-pred)", "72501f0", "rescue R1", "17168966"),
    ("rescue registrations R1/R4 (tag r11-rescue-reg)", "f0bc3ad", "rescue R1", "17168966"),
    ("rescue registrations R1/R4 (tag r11-rescue-reg)", "f0bc3ad", "rescue R4", "17168972"),
    ("theory freeze (tag r13-theory-pred): rescue", "997d2c4", "rescue R1", "17168966"),
    ("theory freeze (tag r13-theory-pred): pool sweep", "997d2c4", "pool sweep Stage C", "17168864"),
    ("theory freeze (tag r13-theory-pred): H200 n=36/44/52", "997d2c4", "H200 Stage C n=36/44/52", "17169612"),
    ("theory freeze (tag r13-theory-pred): Llama-3.1-8B", "997d2c4", "Llama-3.1-8B Stage C", "17166814"),
    ("Llama-3.1-8B simulator predictions (tag r12-llama31-predictions-frozen)", "a62aea9", "Llama-3.1-8B E0b", "17169565"),
    ("BASIN-2 registrations (tag r14-basin2-reg)", "621d88f", "BASIN-2", "17169893"),
    ("TOOLSLOW/SHED registrations (tag r14-extra-reg)", "b006291", "TOOLSLOW", "17169902"),
    ("TOOLSLOW/SHED registrations (tag r14-extra-reg)", "b006291", "SHED", "17169908"),
    ("pred2 (tag r13-theory-pred2): BASIN-2", "cfa7712", "BASIN-2", "17169893"),
    ("pred2 (tag r13-theory-pred2): TOOLSLOW", "cfa7712", "TOOLSLOW", "17169902"),
    ("pred2 (tag r13-theory-pred2): SHED", "cfa7712", "SHED", "17169908"),
    ("pred2 (tag r13-theory-pred2): H200 600k Stage C", "cfa7712", "H200 600k Stage C", "17169672"),
    ("H200 600k registration", "4d1d431", "H200 600k E2", "17171020"),
    ("Llama-3.1-8B registration", "1559f8e", "Llama-3.1-8B E2", "17170409"),
    ("Llama-3.1-8B theory conditional", "a36f441", "Llama-3.1-8B E2", "17170409"),
]


def git(*args):
    return subprocess.run(["git", *args], capture_output=True, text=True)


def is_ancestor(a, b):
    return git("merge-base", "--is-ancestor", a, b).returncode == 0


def cdt(ts):
    return datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(CDT)


def fmt(dt):
    return dt.strftime("%Y-%m-%d %H:%M:%S") if dt else ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--activity", default="github_activity_2026-10.json")
    ap.add_argument("--events", default="github_events_2026-10.json")
    ap.add_argument("--sacct", default="sacct_cited_jobs_2026-10-30.txt")
    ap.add_argument("--extra", action="store_true", help="also the rounds 11-14 rows")
    args = ap.parse_args()
    activity = json.loads((HERE / args.activity).read_text(encoding="utf-8"))
    activity.sort(key=lambda a: (a["timestamp"], a["id"]))
    events = json.loads((HERE / args.events).read_text(encoding="utf-8"))
    jobs = {}
    with open(HERE / args.sacct, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f, delimiter="|"):
            jobs[r["JobID"]] = r

    def job_time(job, field):
        v = jobs[job][field]
        return datetime.fromisoformat(v).replace(tzinfo=CDT) if v[:2] == "20" else None

    def first_push(commit):
        for a in activity:
            if a["after"] != ZERO and is_ancestor(commit, a["after"]):
                return a
        return None

    def matching_event(a):
        ref = a["ref"].removeprefix("refs/heads/")
        t = cdt(a["timestamp"])
        for e in events:
            p = e["payload"]
            if e["type"] == "PushEvent" and p.get("head") == a["after"]:
                return e
            if (e["type"] == "CreateEvent" and p.get("ref_type") == "branch" and p.get("ref") == ref
                    and abs((cdt(e["created_at"]) - t).total_seconds()) < 10):
                return e
        return None

    sys.stdout.reconfigure(newline="\n")  # LF on Windows too
    out = csv.writer(sys.stdout, delimiter="\t", lineterminator="\n")
    out.writerow(["event", "commit", "committer_time_cdt", "first_on_github_cdt", "github_ref_update",
                  "activity_id", "event_created_cdt", "batch", "first_job", "submit_cdt", "start_cdt",
                  "end_cdt", "push_minus_submit_s", "push_minus_start_s"])
    for event, commit, batch, job in ROWS + (EXTRA_ROWS if args.extra else []):
        full = git("rev-parse", commit + "^{commit}").stdout.strip()
        committed = git("log", "-1", "--format=%cd", "--date=format:%Y-%m-%d %H:%M:%S", full).stdout.strip()
        a = first_push(full)
        pushed = cdt(a["timestamp"]) if a else None
        e = matching_event(a) if a else None
        submit, start, end = (job_time(job, k) for k in ("Submit", "Start", "End"))
        out.writerow([
            event, full[:7], committed, fmt(pushed),
            f"{a['activity_type']} {a['ref']} {a['before'][:7]}->{a['after'][:7]}" if a else "not found",
            a["id"] if a else "", fmt(cdt(e["created_at"])) if e else "not in event log",
            batch, job, fmt(submit), fmt(start), fmt(end),
            int((pushed - submit).total_seconds()) if pushed and submit else "",
            int((pushed - start).total_seconds()) if pushed and start else "",
        ])


if __name__ == "__main__":
    main()
