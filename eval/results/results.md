# Evaluation results

## Recovery / diagnosis time (seconds)

| Scenario | Agent runs | Agent mean | Agent min-max | Manual runs | Manual mean | Improvement |
|---|---|---|---|---|---|---|
| Faulty release (crash): detect + rollback | 5 | 28.9 | 20.1-43.1 | 4 | 22.3 | -30% |
| Service down: detect + restart | 3 | 28.6 | 6.6-59.6 | 3 | 10.4 | -175% |
| Memory leak: detect + recover | 3 | 102.0 | 27.7-217.0 | 0 | - | - |
| CI failure: time to root cause | 5 | 31.2 | 18-44 | 2 | 93.8 | 67% |

## Root cause analysis accuracy (Pipeline Agent)

Accuracy: **20%** (1 correct of 5 analysed; 6 bugs injected)

| Bug | Test found | File found | Correct | Analysed by |
|---|---|---|---|---|
| user_lookup | True | True | True | llm |
| discount_formula | True | False | False | llm |
| health_status | True | False | False | llm |
| home_status_code | True | False | False | fallback |
| user_name | True | False | False | llm |
| user_lookup | False | False | False | - |

Notes: manual times come from a person who is actively watching; the sample is small (few runs per scenario).