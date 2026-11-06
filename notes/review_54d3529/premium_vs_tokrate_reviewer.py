import json, sys, math
d = json.load(open(sys.argv[1], encoding="utf-8"))
rows = []
for g in d["groups"]:
    m = g["measured"]; a = g["asym"]
    lr = g["lam_ref"]
    tref = m.get("tokens_ref")
    for i, run in enumerate(g["runs"]):
        comp = m["completion_rate"][i] / lr
        tok = m["uncached_tok_per_s"][i]
        tr = None
        if isinstance(tref, list):
            tr = tref[i]
        elif isinstance(tref, (int, float)):
            tr = tref
        ratio = tok / tr if tr else float("nan")
        rows.append((g["kind"], g["label"], g["cell"], g["rate_mult"], g["seeds"][i] if i < len(g["seeds"]) else None,
                     comp, a["D"] / lr, ratio, a["tok_ratio"], comp / ratio if tr else float("nan")))
print("keys of measured:", list(d["groups"][0]["measured"].keys()))
print("n rows", len(rows))
for r in sorted(rows, key=lambda r: r[5]):
    print("%-4s %-28s %-10s %4.2f s%s comp/lref=%.3f D/lref=%.3f tokratio_meas=%.3f tokratio_comp=%.3f comp/(lref*tokratio)=%.3f" % r)
e2 = [r for r in rows if r[0] != "e0b"]
print("E2-protocol runs:", len(e2))
print("min comp/lref", min(r[5] for r in e2), "min comp/(lref*tok)", min(r[9] for r in e2 if not math.isnan(r[9])))
print("tok ratios range", min(r[7] for r in rows if not math.isnan(r[7])), max(r[7] for r in rows if not math.isnan(r[7])))
