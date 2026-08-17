# The breadth frontier

Generated 2026-08-17 by `scripts/breadth_frontier.py`,
using the cost model validated against real contract notes
(`docs/cost_model_validation.md`).

**No returns are read.** This is cost arithmetic, so it spends no trial
budget and can settle breadth before any hypothesis is tested. Choosing N
by which value backtested best would be selection; choosing it by what
trading costs is not.

Every figure is the cost of **one full turnover** — buying and selling
each position once — as a percentage of capital.

## Capital ₹300,000

One sell order per exit — the optimistic case.

| names | position | DP | brokerage | statutory | **total** |
|---:|---:|---:|---:|---:|---:|
| 10 | ₹30,000 | 0.079% | 0.157% | 0.222% | **0.458%** |
| 15 | ₹20,000 | 0.118% | 0.236% | 0.222% | **0.576%** |
| 20 | ₹15,000 | 0.157% | 0.236% | 0.222% | **0.616%** |
| 30 | ₹10,000 | 0.236% | 0.236% | 0.222% | **0.694%** |
| 50 | ₹6,000 | 0.393% | 0.236% | 0.222% | **0.852%** |
| 100 | ₹3,000 | 0.787% | 0.393% | 0.222% | **1.402%** |

Total cost of one full turnover, by orders per exit:

| names | 1 order | 1.5 orders | 3 orders |
|---:|---:|---:|---:|
| 10 | 0.458% | 0.498% | 0.616% |
| 15 | 0.576% | 0.635% | 0.812% |
| 20 | 0.616% | 0.694% | 0.930% |
| 30 | 0.694% | 0.812% | 1.166% |
| 50 | 0.852% | 1.048% | 1.638% |
| 100 | 1.402% | 1.796% | 2.976% |

### Capital needed to keep one full turnover under 0.50%

| names | required capital |
|---:|---:|
| 10 | ₹255,118 |
| 15 | ₹382,677 |
| 20 | ₹510,236 |
| 30 | ₹765,354 |
| 50 | ₹1,275,589 |
| 100 | ₹2,551,179 |

