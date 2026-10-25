### P1. CAPPED and NOBURST arms beyond the declared test (POST-HOC, not part of the verdicts)

The estimate column is arithmetic on two measured numbers (see the module docstring), not a simulation. `CAPPED hit > 0.8` ignores the backlog condition of RECOVERED; the declared verdict is the `recovered (declared)` columns.

| workload | x lambda_miss | lambda (sessions/s) | cap n | mu(cap) (sessions/s) | [estimate] drain time of the burst (s) | [estimate] / eval window start (5000 s) | CAPPED recovered (declared) | CAPPED hit > 0.8 (hit only) | CAPPED hit (mean) | CAPPED backlog (mean over seeds) | CAPPED backlog slope < 0 | NOBURST recovered (declared) | NOBURST trapped |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Exp(5 s) (record, control) | 1.35 | 0.09745 | 20 | 0.2144 | 1710 | 0.3421 | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0.9307 | 0.0184 | 5/10 (0.50) [0.24, 0.76] | 10/10 (1.00) [0.72, 1.00] | 0/10 (0.00) [0.00, 0.28] |
| Exp(5 s) (record, control) | 1.65 | 0.1191 | 20 | 0.2144 | 2099 | 0.4198 | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0.9313 | 0.01706 | 3/10 (0.30) [0.11, 0.60] | 10/10 (1.00) [0.72, 1.00] | 0/10 (0.00) [0.00, 0.28] |
| TraceLab per-turn (empirical) | 1.4 | 0.1024 | 32 | 0.2178 | 1733 | 0.3466 | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0.9311 | 0.01183 | 3/10 (0.30) [0.11, 0.60] | 10/10 (1.00) [0.72, 1.00] | 0/10 (0.00) [0.00, 0.28] |
| TraceLab per-turn (empirical) | 1.85 | 0.1353 | 32 | 0.2178 | 2424 | 0.4849 | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0.9304 | 0.05485 | 5/10 (0.50) [0.24, 0.76] | 10/10 (1.00) [0.72, 1.00] | 0/10 (0.00) [0.00, 0.28] |
| TraceLab idle gap (empirical, upper bound) | 1.35 | 0.09664 | 40 | 0.1694 | 2751 | 0.5501 | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0.9271 | 0.01639 | 4/10 (0.40) [0.17, 0.69] | 10/10 (1.00) [0.72, 1.00] | 0/10 (0.00) [0.00, 0.28] |
| TraceLab idle gap (empirical, upper bound) | 1.65 | 0.1181 | 40 | 0.1694 | 3903 | 0.7807 | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0.9223 | 0.03218 | 5/10 (0.50) [0.24, 0.76] | 10/10 (1.00) [0.72, 1.00] | 0/10 (0.00) [0.00, 0.28] |
| mini-SWE-agent v2 tool time (empirical) | 1.65 | 0.1204 | 20 | 0.3802 | 769.6 | 0.1539 | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0.931 | 0.01629 | 6/10 (0.60) [0.31, 0.83] | 10/10 (1.00) [0.72, 1.00] | 0/10 (0.00) [0.00, 0.28] |
| mini-SWE-agent v2 tool time (empirical) | 2.35 | 0.1714 | 20 | 0.3802 | 957.8 | 0.1916 | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0.9327 | 0.02991 | 8/10 (0.80) [0.49, 0.94] | 10/10 (1.00) [0.72, 1.00] | 0/10 (0.00) [0.00, 0.28] |
| mini-SWE-agent v2 full workload (empirical) | 1.65 | 0.01974 | 12 | 0.05035 | 6533 | 1.307 | 8/10 (0.80) [0.49, 0.94] | 10/10 (1.00) [0.72, 1.00] | 0.9692 | 13.81 | 10/10 (1.00) [0.72, 1.00] | 10/10 (1.00) [0.72, 1.00] | 0/10 (0.00) [0.00, 0.28] |
| mini-SWE-agent v2 full workload (empirical) | 2.35 | 0.02811 | 12 | 0.05035 | 8993 | 1.799 | 0/10 (0.00) [0.00, 0.28] | 10/10 (1.00) [0.72, 1.00] | 0.963 | 58.03 | 10/10 (1.00) [0.72, 1.00] | 8/10 (0.80) [0.49, 0.94] | 2/10 (0.20) [0.06, 0.51] |

### P2. NOBURST runs that are not RECOVERED (POST-HOC): when did they collapse? (edge stage horizon 3000 s, paired runs 8700 s)

| workload | x lambda_miss | seed | label | first window with backlog > 50 ends (s) | first window after t_burst with hit < 0.2 ends (s) | final backlog | final hit |
|---|---|---|---|---|---|---|---|
| mini-SWE-agent v2 full workload (empirical) | 2.35 | 2 | TRAPPED | 6200 | 2600 | 96.98 | 0 |
| mini-SWE-agent v2 full workload (empirical) | 2.35 | 5 | TRAPPED | n/a | 4400 | 40.13 | 0 |
