| Metric (median of runs) | shared | isolated |
|---|---|---|
| Actions executed | 215 | 372 |
| Unique actions covered | 215 | 93 |
| Actions run by more than one explorer | 0 | 93 |
| Page reads | 27 | 84 |
| LLM calls | 0 | 0 |
| Time to B1 (s) | 19 | 60.6 |
| Time to B2 (s) | 21.4 | 73.9 |
| Time to B3 (s) | 28.6 | 97.9 |
| Time to B4 (s) | 165.9 | – |

Runs: 3 shared, 3 isolated. '–' = not found in any run.

Measured 2026-10-17 in Docker, 4 explorers, 4 minutes per session, `LLM_BACKEND=off` in both modes (LLM calls are therefore 0; page reads are the LLM-cost proxy). Times are seconds from session start to the first sighting of each planted bug.
