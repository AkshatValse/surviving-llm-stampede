# Lit-check: LRU cliff from cyclic agent re-reference (Claim 3′)

Scout (sonnet), 2026-10-21. Pages were opened by the scout; several full texts went through a fetch summarizer.

**Verdict: NARROW.** The theory half is textbook. The remedy half is partly done.

**Classical sources (pages opened):**
- LIRS (Jiang & Zhang, SIGMETRICS 2002): LRU on loops slightly larger than the cache. https://u.cs.biu.ac.il/~wisemay/2os/lru/lirs.pdf
- EELRU (Smaragdakis, Kaplan & Wilson; extended version opened). https://u.cs.biu.ac.il/~wisemay/2os/lru/eelru.pdf
- Chou & DeWitt, VLDB 1985: MRU for looping scans. https://www.vldb.org/conf/1985/P127.PDF
- ARC (FAST 2003).

**Agent and KV prior work:**
- **RR-Evict** (Pan et al., 2026, arXiv 2609.32278; PDF read):
  - Names "recency synchronization" under LRU.
  - Proposes round-robin tail-chunk eviction for gradual degradation in SGLang.
  - Its model assumes uniformly random returns and excludes overload (m ≤ n_a).
  - Baselines are LRU only, with no MRU, random or Belady comparison.
  - **Closest.**
- **Randomization Boosts KV Caching** (Wu, Silwal & Zhang, ICLR 2026, arXiv 2601.18999):
  - Randomized marking eviction beats leaf-LRU under round-robin arrivals.
  - Setting is non-agent.
- **When Fancy Eviction Fails** (arXiv 2609.28870):
  - Compares 14 policies on 2 production agentic traces, with no MRU or random.
  - LRU trails but does not collapse (0.403 vs 0.491), because session pacing makes recency predictive. This is counter-evidence in their regime.
- KVFlow, CacheWise (LRU thrashing at N>10), ScaleSim, CacheScout, Continuum, MORI, ThunderAgent, CONCUR, PEEK, Marconi: none uses the cyclic framing or compares MRU or random.
- GitHub replication (not peer-reviewed): LRU-leaf beats alternatives on 393 Claude Code sessions.

**Implication for us:** The LRU-cyclic cliff is a supporting mechanism at most, explaining why the cap band is narrow. It is not the headline. If used, cite LIRS, EELRU, Chou-DeWitt, RR-Evict, and Randomization Boosts. Whether real tool gaps are cyclic enough is untested: heavy-tailed gaps look like RR-Evict's random-return model.
