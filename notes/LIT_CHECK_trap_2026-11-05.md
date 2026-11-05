# Literature check for the trap theorem (2026-11-05, reframe-draft session)

Purpose: before writing any novelty sentence about Theorem 1/2 and Corollary 3 (model F, `notes/THEORY_ICML_2026-11.md`),
check the closest mathematics and verify every citation. Two passes: a scout agent (Crossref-keyed metadata; publisher pages
were blocked) and a direct read by this session of the one lead the scout could not open (Khanin et al. 2001).

## Verified citations (Crossref metadata keyed by DOI unless stated)

| key in refs.bib | record | note |
|---|---|---|
| grishechkin1992processor | S. Grishechkin, On a relationship between processor-sharing queues and Crump-Mode-Jagers branching processes, Adv. Appl. Probab. 24(3):653-698, 1992, doi 10.2307/1427484 | |
| jeanmarie1994transient | A. Jean-Marie, P. Robert, On the transient behavior of the processor sharing queue, Queueing Systems 17(1-2):129-136, 1994, doi 10.1007/BF01158692 | year is 1994 |
| puha2006overloaded | A. L. Puha, A. L. Stolyar, R. J. Williams, The fluid limit of an overloaded processor sharing queue, Math. Oper. Res. 31(2):316-350, 2006, doi 10.1287/moor.1050.0181 | fluid shape converges to an invariant shape |
| chen1991discrete | H. Chen, A. Mandelbaum, Discrete flow networks: bottleneck analysis and fluid approximations, Math. Oper. Res. 16(2):408-446, 1991, doi 10.1287/moor.16.2.408 | |
| kumar1993reentrant | P. R. Kumar, Re-entrant lines, Queueing Systems 13(1-3):87-110, 1993, doi 10.1007/BF01158930 | |
| dai1996stability | J. G. Dai, G. Weiss, Stability and instability of fluid models for reentrant lines, Math. Oper. Res. 21(1):115-134, 1996, doi 10.1287/moor.21.1.115 | |
| jennings2013fluid | O. B. Jennings, A. L. Puha, Fluid limits for overloaded multiclass FIFO single-server queues with general abandonment, Stochastic Systems 3(1):262-321, 2013, doi 10.1214/12-SSY085 | no re-entry |
| dong2022metastability | J. Dong, Metastability in queues, Queueing Systems 100(3-4):413-415, 2022, doi 10.1007/s11134-022-09795-2 | open-problem note |
| kendall1951some | D. G. Kendall, Some problems in the theory of queues, JRSS B 13(2):151-173, 1951, doi 10.1111/j.2517-6161.1951.tb00080.x | pages 151-173 per Crossref (not 151-158 or 151-185) |
| takacs1963feedback | L. Takacs, A single-server queue with feedback, Bell Syst. Tech. J. 42(2):505-519, 1963, doi 10.1002/j.1538-7305.1963.tb00510.x | stable regime |
| vandenberg1989deterministic | J. L. van den Berg, O. J. Boxma, W. P. Groenendijk, Sojourn times in the M/G/1 queue with deterministic feedback, Stochastic Models 5(1):115-129, 1989, doi 10.1080/15326348908807101 | closest classical model; stable regime |
| bramson1996convergence | M. Bramson, Convergence to equilibria for fluid models of FIFO queueing networks, Queueing Systems 22(1-2):5-45, 1996, doi 10.1007/BF01159391 | Kelly-type, load <= 1 |
| khanin2001steady | K. Khanin, D. Khmelev, A. Rybko, A. Vladimirov, Steady solutions for FIFO networks, Moscow Math. J. 1(3):407-419, 2001 | read in full by this session from the authors' PDF (philol.msu.ru/~lex/khmelev/local/khanin.pdf); journal header checked on page 1 |
| feller1968introduction | W. Feller, An Introduction to Probability Theory and Its Applications, Vol. I, 3rd ed., Wiley, 1968 | catalog records only |

Also verified, not cited in the draft: Disney, McNickle & Simon 1980 (NRLQ 27(4):635-644); van den Berg & Boxma 1991 (QS 9(4):365-401);
Kleinrock 1964 (NRLQ 11(1):59-73); Kleinrock 1967 (JACM 14(2):242-261); Coffman & Kleinrock 1968 (JACM 15(4):549-576);
Reiman 1988 (AAP 20(1):179-207, heavy traffic); Bramson 1994 (AAP 4(2):414-431); Frolkova, Foss & Zwart 2014 (AAP 46:76-101,
overloaded polling with a branching fluid limit).

## The closest prior result: Khanin, Khmelev, Rybko, Vladimirov (2001)

Read by this session (pages 407-419). Fluid model of a FIFO reentrant line: K nodes, n stages, stage j at node i(j) with mean
service time v_j ("viscosity"), unit inflow. A *steady solution* has constant flows x_j from the empty state. A node is
overloaded if sum_{j in J_i} x_{j-1} v_j > 1, "in this case the queue length at the node i increases linearly in time"; if all
nodes are overloaded the steady flows are fixed points of x_s = x_{s-1} / sum_{j in J_i} x_{j-1} v_j (their 2.3). Results:
existence (Brouwer), uniqueness for Kelly-type lines (v_j = V_i), an example of multiple steady solutions with two nodes and
different viscosities, uniqueness when each node has at most two stages, and a remark extending uniqueness to lines with a
fixed fraction of flow leaving at each node. Uniqueness of general (non-steady) trajectories is stated as a conjecture.

At a single node with n stages: x_s = a^s with sum_j v_j a^j = 1. With a = 1/z and inflow lambda this is exactly model F's
Perron equation lambda sum_k c_k G_k z^{-k} = 1 for deterministic T = n, and the steady flows give Theorem 1(c)'s gap slope
z - 1, the z^{-k} composition and the departure rate lambda z^{-n}.

**Consequence for our wording.** The self-similar regime of Theorem 1(c) is not new (deterministic stages). As far as we found,
new are: random turn counts; the linear renewal recursion along FIFO orbits, which proves convergence from an arbitrary initial
state (a burst leaves the engine far from a steady solution), geometric in the generation index and with an exact virtual
origin (Theorem 1(d), (f)); Theorem 2 (departures against the capacity at the stationary mix, H x Gamma); Corollary 3 (the
recovery threshold against the throughput measured in a trap); and the engine test. The theory session was told
(2026-11-05) so that `notes/THEORY_ICML_2026-11.md` section 5 can be updated.

## Answer to the targeted questions (scout, plus the above)

- (i) A linear-renewal / Perron-root growth law along FIFO orbits for an overloaded FIFO feedback queue from arbitrary initial
  states: not found. The steady (self-similar) solutions themselves: Khanin et al. 2001.
- (ii) The trapped composition G_k z^{-k} with random T: not found as such; for deterministic stages it is implied by the
  steady flows of Khanin et al.
- (iii) Departures above the stationary-mix capacity in overload (youth premium): not found.

Search terms used by the scout: "overloaded queue feedback FIFO re-entrant fluid limit growth rate Perron root linear
renewal"; "Galton-Watson branching FIFO queue with feedback generations busy period overload"; "round robin overload fluid
limit multi-turn feedback queue growth rate"; "single-server feedback queue instability traffic intensity > 1 linear growth";
"Foss Miyazawa feedback queue". This session: "Khanin Khmelev Rybko Vladimirov Steady solutions for FIFO networks"; "self-similar
fluid solutions overloaded FIFO reentrant line linear growth Kelly type steady solutions convergence". Sources: Crossref,
arXiv, web search; MathSciNet, zbMATH and Google Scholar were not checked. The search is targeted, not exhaustive.
