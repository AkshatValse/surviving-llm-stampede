# Pre-registered predictions: evaluation

## (a) full batch, Adam
verdict: **FAIL**  (all three bands pass: False)

- sync beta1=0.9: max eta*S_P over all runs/times = 47.30 (gate > 10.0: True); median last-1000 by eta: {'0.003': 37.58, '0.01': 39.56, '0.03': 39.371}
- delay_beta0.9: band [0.75, 1.25], etas ok 0/3 -> passed=False
    - eta=0.003: per-seed median eta*S_P [2.1363, 2.1366, 2.2993], in band 0/3
    - eta=0.01: per-seed median eta*S_P [2.4213, 5.9797, 2.6765], in band 0/3
    - eta=0.03: per-seed median eta*S_P [9.7638, 8.338, 3.0432], in band 0/3
- ef_beta0.9: band [2.0, 3.4], etas ok 0/3 -> passed=False
    - eta=0.003: per-seed median eta*S_P [4.2643, 4.2462, 4.1953], in band 0/3
    - eta=0.01: per-seed median eta*S_P [4.4621, 4.7888, 4.3797], in band 0/3
    - eta=0.03: per-seed median eta*S_P [4.6664, 5.8401, 6.369], in band 0/3
- delay_beta0.99: band [0.75, 1.25], etas ok 0/3 -> passed=False
    - eta=0.003: per-seed median eta*S_P [3.7426, 4.9533, 4.4136], in band 0/3
    - eta=0.01: per-seed median eta*S_P [6.1795, 5.3364, 4.9219], in band 0/3
    - eta=0.03: per-seed median eta*S_P [6.7656, 1.9074, 5.7334], in band 0/3

## (b) minibatch B=64
- Adam beta0.9: sync best eta=0.003; sync eta*S_P there=6.706; delay eta*S_P there=1.855; loss sync=0.00763, delay=0.02261; penalty at sync-best eta=+196.3%; tuned penalty=+196.3% (best delay eta=0.003); downgrade(matched)=False, downgrade(tuned)=False, GO-clause=False
    - matched-eta penalties: {'0.003': '+196.3%', '0.01': '+670.9%', '0.03': '+2016.7%'}
- Adam beta0.99: sync best eta=0.003; sync eta*S_P there=10.320; delay eta*S_P there=2.611; loss sync=0.005996, delay=0.03297; penalty at sync-best eta=+449.8%; tuned penalty=+449.8% (best delay eta=0.003); downgrade(matched)=False, downgrade(tuned)=False, GO-clause=False
    - matched-eta penalties: {'0.003': '+449.8%', '0.01': '+3411.3%', '0.03': '+8633.4%'}

## (c) beta1=0.99 vs 0.9 under delay
- batch1000: matched penalties 0.9={'0.003': '+445.9%', '0.01': '+2187.2%', '0.03': '+10472.6%'}, 0.99={'0.003': '+3887.9%', '0.01': '+11230.2%', '0.03': '+36417.4%'}; tuned 0.9=+514.7%, 0.99=+3887.9%; smaller at 0.99 for 0/3 etas; supported(tuned)=False, supported(matched majority)=False
- batch64: matched penalties 0.9={'0.003': '+196.3%', '0.01': '+670.9%', '0.03': '+2016.7%'}, 0.99={'0.003': '+449.8%', '0.01': '+3411.3%', '0.03': '+8633.4%'}; tuned 0.9=+196.3%, 0.99=+449.8%; smaller at 0.99 for 0/3 etas; supported(tuned)=False, supported(matched majority)=False

## (d) Muon-like vs Adam delay penalty (tuned eta per mode)
- batch1000: Adam0.9 +514.7%, Adam0.99 +3887.9%, Muon +385.6% (best eta sync 0.003, delay 0.003); negative(Muon>=Adam0.9)=False, negative(Muon>=Adam0.99)=False
- batch64: Adam0.9 +196.3%, Adam0.99 +449.8%, Muon +67.1% (best eta sync 0.003, delay 0.003); negative(Muon>=Adam0.9)=False, negative(Muon>=Adam0.99)=False

## GO rule
{"a_delayed_and_ef_pass_and_sync_reaches_gate": false, "b_go_clause_beta0.9": false, "GO": false}
