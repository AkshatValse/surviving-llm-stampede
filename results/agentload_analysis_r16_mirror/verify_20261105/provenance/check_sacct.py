"""Items 1, 6, 7: sacct SubmitLines vs the registered submit lines; Submit/Start margins vs the GitHub push of bc81ee7."""
import datetime as dt
import json
import re
import sys
from pathlib import Path

WT = Path(sys.argv[1])
REG_LINES = Path(sys.argv[2]).read_text().splitlines()
CST = dt.timezone(dt.timedelta(hours=-6))
UTC = dt.timezone.utc

sacct = []
for ln in (WT / "provenance/sacct_cited_jobs_2026-11-05-r16.txt").read_text().splitlines()[1:]:
    f = ln.split("|")
    sacct.append(dict(zip(["JobID", "JobName", "Account", "Partition", "Submit", "Start", "End", "State", "ExitCode",
                           "NodeList", "SubmitLine"], f)))
utc = {}
for ln in (WT / "provenance/sacct_cited_jobs_2026-11-05-r16_utc.txt").read_text().splitlines()[1:]:
    f = ln.split("|")
    utc[f[0]] = dict(Submit=f[4], Start=f[5], End=f[6])

act = json.loads((WT / "provenance/github_activity_2026-11-05-r16.json").read_text(encoding="utf-8"))
reg_ev = [e for e in act if e["ref"] == "refs/heads/r16/mirror" and e["after"].startswith("bc81ee71f7f5")]
assert len(reg_ev) == 1, reg_ev
push = dt.datetime.strptime(reg_ev[0]["timestamp"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
print(f"registration on GitHub: {reg_ev[0]['activity_type']} {reg_ev[0]['ref']} {reg_ev[0]['before'][:7]}->{reg_ev[0]['after']} "
      f"at {push.isoformat()} = {push.astimezone(CST).isoformat()} (activity id {reg_ev[0]['id']})")
commit_t = dt.datetime.fromtimestamp(1793909228, UTC)
print(f"commit/tagger time {commit_t.astimezone(CST).isoformat()}; push - commit = {(push - commit_t).total_seconds():.0f} s")

# registered lines keyed by (job-name, SEEDS); GEN_EXTRA prefix stripped (it is an env assignment, not part of sbatch's argv)
reg = {}
for ln in REG_LINES:
    if "sbatch " not in ln:
        continue
    gen = re.match(r"^GEN_EXTRA='([^']*)' (sbatch .*)$", ln)
    line = gen.group(2) if gen else ln
    name = re.search(r"--job-name=(\S+)", line).group(1)
    seeds = re.search(r"[,=]SEEDS=(\d+)", line).group(1)
    reg[(name, seeds)] = (line, gen.group(1) if gen else None)

def parse(s, tz=CST):
    return dt.datetime.strptime(s, "%Y-%m-%dT%H:%M:%S").replace(tzinfo=tz)

print()
print("job      name        state     exit  acct/part/qos(SubmitLine)                         time      submit_CST           start_CST            "
      "submit-push  start-push  utc_offset_ok  SubmitLine==registered")
for r in sacct:
    sl = r["SubmitLine"]
    acct = re.search(r"--account=(\S+)", sl).group(1)
    part = re.search(r"--partition=(\S+)", sl).group(1)
    qos = re.search(r"--qos=(\S+)", sl).group(1)
    tlim = re.search(r"--time=(\S+)", sl).group(1)
    seeds = re.search(r"[,=]SEEDS=(\d+)", sl).group(1)
    sub, st = parse(r["Submit"]), parse(r["Start"])
    u = utc[r["JobID"]]
    off_ok = all(parse(u[k], UTC) == parse(r[k]) for k in ("Submit", "Start", "End"))
    rl = reg.get((r["JobName"], seeds))
    same = (rl is not None and rl[0] == sl)
    diff = ""
    if rl is not None and not same:
        a, b = rl[0].split(" "), sl.split(" ")
        diff = "; ".join(f"{x} -> {y}" for x, y in zip(a, b) if x != y) + ("" if len(a) == len(b) else f" (len {len(a)} vs {len(b)})")
    print(f"{r['JobID']} {r['JobName']:<11} {r['State']:<9} {r['ExitCode']:<5} {acct}/{part}/{qos}  "
          f"Account-col={r['Account']} Partition-col={r['Partition']}  {tlim:<9} {sub.isoformat()} {st.isoformat()} "
          f"{(sub - push).total_seconds():>8.0f} s {(st - push).total_seconds():>8.0f} s  {off_ok}  {same} {diff}")
first_sub = min(parse(r["Submit"]) for r in sacct)
first_start = min(parse(r["Start"]) for r in sacct)
nine = [r for r in sacct if r["JobID"] in {"17264055", "17264056", "17264057", "17264058", "17264059", "17264060", "17264062", "17264063", "17264064"}]
print(f"\nearliest Submit {first_sub.isoformat()} margin {(first_sub - push).total_seconds():.0f} s = {(first_sub - push).total_seconds()/60:.2f} min")
print(f"earliest Start  {first_start.isoformat()} margin {(first_start - push).total_seconds():.0f} s")
print(f"nine counted jobs: Submit {min(parse(r['Submit']) for r in nine).isoformat()}..{max(parse(r['Submit']) for r in nine).isoformat()}, "
      f"Start {min(parse(r['Start']) for r in nine).isoformat()}..{max(parse(r['Start']) for r in nine).isoformat()}")
print(f"  min margin submit {(min(parse(r['Submit']) for r in nine) - push).total_seconds():.0f} s, start {(min(parse(r['Start']) for r in nine) - push).total_seconds():.0f} s")
# registered order of submission: lines 5-14 order vs JobID order
order_reg = [(re.search(r"--job-name=(\S+)", l).group(1), re.search(r"[,=]SEEDS=(\d+)", l).group(1)) for l in REG_LINES if "sbatch " in l]
order_obs = [(r["JobName"], re.search(r"[,=]SEEDS=(\d+)", r["SubmitLine"]).group(1)) for r in sorted(sacct, key=lambda r: int(r["JobID"]))]
print("registered order:", order_reg)
print("observed order  :", order_obs)
