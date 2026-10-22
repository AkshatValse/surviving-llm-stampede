"""Turn parsed SGLang batch-log rows into per-iteration timing observations.

Source-derived definitions (SGLang 0.5.22, metrics_reporter.py / batch_result_processor.py on Nova):
  * A Prefill line is emitted when the prefill batch's RESULT is processed (every prefill batch).
    input throughput = (#new-token + replay) / (perf_counter now - perf_counter at the previous Prefill line).
    => gap_P = #new-token / thr is the wall time since the previous prefill RESULT, which includes any decode
       iterations and idle time in between.
  * A Decode line is emitted at result processing of every 40th decode batch (forward_ct_decode % 40 == 0).
    gen throughput = (sum of batch sizes of the decode batches since the previous Decode line) / (time since it).
    Prefill-generated first tokens are NOT counted (only process_batch_result_decode increments the counter).
  * #token (decode line) = max_total_num_tokens - (available + evictable) = KV tokens pinned by running requests.
  * #cached-token = radix prefix length of NEWLY admitted requests; continuation chunks of a chunked request
    report 0 (add_chunked_req passes prefix_len=0), so a continuation's prefix must be reconstructed.
  * Scheduler: prefill first if any prefill batch can be formed; a chunked request's continuation is always
    scheduled next ("that pass must proceed regardless"). Mixed chunk off, so P and D never share an iteration.

Clean observations:
  * Decode: consecutive Decode lines with no Prefill line between, equal #running-req R > 0 and
    #token growth == 40*R  =>  the 40 iterations all had exactly R sequences and nothing else ran;
    per-iteration time = R / thr (exact, no N_gen ambiguity).
  * Prefill: the previous batch line is a Prefill whose #new-token == 8192 (= chunked_prefill_size, budget
    exhausted => a request was truncated => it is a chunked request whose continuation is the very next batch).
    The gap is then the duration of this batch alone (GPU back-to-back; with the overlap scheduler the result of
    batch k is processed after batch k+1 is launched, so consecutive result times differ by batch k+1's time).
"""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd

CHUNK = 8192
DLI = 40


def add_prev(df: pd.DataFrame) -> pd.DataFrame:
    out = []
    for job, g in df.groupby("job", sort=False):
        g = g.sort_values("line").reset_index(drop=True)
        for c in ["kind", "new_tok", "new_seq", "pending", "running", "token", "epoch", "usage", "cached"]:
            g["prev_" + c] = g[c].shift(1)
        g["prev2_kind"] = g["kind"].shift(2)
        out.append(g)
    return pd.concat(out, ignore_index=True)


def decode_obs(df: pd.DataFrame) -> pd.DataFrame:
    D = df[df.kind == "D"].copy()
    m = ((D.prev_kind == "D") & (D.prev_epoch == D.epoch) & (D.prev_running == D.running) & (D.running > 0)
         & (D.token > 0) & (D.prev_token > 0))
    D = D[m].copy()
    D["dtok"] = D.token - D.prev_token
    D["growth_ok"] = D.dtok == DLI * D.running
    D["tau"] = D.running / D.thr
    # sum of contexts over the 40 iterations: iteration k (1..40) has ~ prev_token + k*R tokens pinned
    # (allocation of the k-th token happens before the forward); mean over k = prev_token + 20.5 R.
    D["sumctx"] = D.prev_token + 20.5 * D.running
    D["meanctx"] = D.sumctx / D.running
    return D


def prefill_obs(df: pd.DataFrame) -> pd.DataFrame:
    """Reconstruct chunk chains and the prefix of every continuation chunk."""
    rows = []
    for job, g in df.groupby("job", sort=False):
        g = g.reset_index(drop=True)
        # state of the chunked request after each batch line: processed tokens S (np.nan if unknown)
        S_prev = np.nan
        prev_is_chunked_P = False
        prev_epoch = None
        for r in g.itertuples(index=False):
            if r.kind != "P":
                prev_is_chunked_P = False
                S_prev = np.nan
                prev_epoch = r.epoch
                continue
            cont = prev_is_chunked_P and (prev_epoch == r.epoch)
            X = r.new_tok
            truncated = X == CHUNK
            prefix = np.nan       # prefix (KV length before the chunk) for single-seq batches
            attn_mid = np.nan     # exact causal (query,key) pairs: sum_j (prefix + j), j=1..X
            attn_end = np.nan     # simulator "end" convention: X * (prefix + X)
            S_new = np.nan
            if r.new_seq == 1:
                if cont:
                    prefix = S_prev                     # continuation of the chunked request
                else:
                    prefix = float(r.cached)            # newly admitted request, radix prefix
                if np.isfinite(prefix):
                    attn_mid = X * prefix + X * (X + 1) / 2.0
                    attn_end = X * (prefix + X)
                    S_new = prefix + X if truncated else np.nan
            else:
                S_new = np.nan                          # last (truncated) request's first-chunk size unknown
            rows.append(dict(job=job, line=r.line, epoch=r.epoch, ts=r.ts, X=X, new_seq=r.new_seq,
                             cached=r.cached, usage=r.usage, running=r.running, queue=r.queue,
                             pending=r.pending, cg=r.cg, thr=r.thr, gap=X / r.thr if r.thr > 0 else np.nan,
                             clean=bool(cont), cont=bool(cont), prefix=prefix,
                             attn_mid=attn_mid, attn_end=attn_end, truncated=truncated,
                             prev_usage=getattr(r, "prev_usage")))
            S_prev = S_new
            prev_is_chunked_P = truncated
            prev_epoch = r.epoch
    return pd.DataFrame(rows)


def main(inp: str, out_prefix: str) -> None:
    df = add_prev(pd.read_pickle(inp))
    D = decode_obs(df)
    P = prefill_obs(df)
    D.to_pickle(out_prefix + "_decode.pkl")
    P.to_pickle(out_prefix + "_prefill.pkl")
    print("decode candidates:", len(D), "growth_ok:", int(D.growth_ok.sum()))
    print(D[D.growth_ok].groupby("job").size().to_string())
    print("prefill lines:", len(P), "clean (after a truncated 8192 chunk):", int(P.clean.sum()))
    Pc = P[P.clean]
    print("clean by new_seq==1:", int((Pc.new_seq == 1).sum()), " with known prefix:", int(np.isfinite(Pc.attn_mid).sum()))
    print(Pc.groupby("job").size().to_string())
    k = Pc[np.isfinite(Pc.attn_mid)]
    print(k[["X", "prefix", "gap", "usage", "running"]].describe(percentiles=[.01, .05, .5, .95, .99]).T.to_string())


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
