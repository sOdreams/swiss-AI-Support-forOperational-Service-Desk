# Parallel Ticket Cleaning and Candidate Filtering

**Historical experiment report.** The current lightweight default uses GPT-5.5
with `reasoning_effort=none`, a 1,500-token ceiling per call and no automatic
validation retry. It has not been rerun on all 20 live examples. The measurements
below describe the earlier configurations, whose retry and output budgets differ.
The current default has a separate three-ticket latency smoke check: median
4.08s, with zero reasoning tokens. See [the current handoff](ANALYSIS_HANDOFF.md)
and [the recorded measurements](../backend/validation/lite-latency.json).

**Previously selected profile: `gpt-5.5-2026-04-23`, low reasoning.** On the 20 development tickets, the integrated pipeline completed all branches with a median elapsed time of **6.06s** (maximum 12.17s; nearest-rank p95 11.74s). It proposed four field corrections across three tickets and kept all original Top-50 IDs, ranks, scores and source relationships.

The pipeline runs `clean(current facts)` concurrently with `FAISS(original narrative) → filter`. Clean predictions never prefilter or rewrite retrieval inputs. The deterministic merge checks service disagreements; a disagreement holds both service correction and active evidence selections for review.

**These are development diagnostics, not official GT accuracy.** Earlier assistant annotations supply comparison labels only after inference. The data and failures informed prompt development. Each setting was run once; provider load, schema/cache state and run order can affect latency. The comparison is not a controlled ablation of model, prompt, reasoning or concurrency.

## Measured comparison

| Version / model / reasoning | Median total | Max total | Clean service agreement | Work-type agreement | Reference primary coverage | Active comments: reference / total | Ready / review / partial |
|---|---:|---:|---:|---:|---:|---:|---|
| V1 / gpt-5.4-2026-03-05 / none | 3.91s | 7.59s | 18/19 | 19/19 | 18/18 | 21 / 24 | 19 / 1 / 0 |
| V1 / gpt-5.5-2026-04-23 / none | 3.77s | 5.19s | 18/19 | 19/19 | 18/18 | 21 / 23 | 18 / 2 / 0 |
| V2 / gpt-5.4-2026-03-05 / low | 6.36s | 9.01s | 19/19 | 19/19 | 18/18 | 19 / 19 | 19 / 1 / 0 |
| V2 / gpt-5.5-2026-04-23 / low | 6.06s | 12.17s | 19/19 | 19/19 | 18/18 | 19 / 19 | 20 / 0 / 0 |

Service comparison excludes unresolved #9; work-type comparison excludes ambiguous #7; primary coverage excludes #7 and #9, where the prior review chose no primary analogue. Coverage is measured after merge holds. V1 only held the service field on disagreement; V2 also holds active filter selections, so coverage semantics are stricter in V2.

V1 used compact outputs with no reasoning. V2 clarifies application-specific service selection, adds explicit current/comment stage tags and enforces matching supported stages for active comments, then uses low reasoning. Both models saw the same tickets within each version. Inference code snapshots and per-run hashes are preserved.

## Why this default

- GPT-5.4 without reasoning made an unsupported Rimes correction on #9 and misidentified the service for #11. The latter was caught by the independent branch disagreement.
- GPT-5.5 without reasoning misclassified the application access request #2 as IAM in its clean branch. It also disagreed on the unknown vendor service in #9. Both cases were exposed for review.
- With V2, GPT-5.4 low still guessed Rimes in the #9 filter branch; the merge held that selection. GPT-5.5 low abstained in both branches, matched the earlier review on the 19 judgeable services, and separated external/internal Settlement evidence in #4 and #19.
- Both V2 models retained 19 reference comment pairs actively and the two vague cash-cutoff hypotheses in reserve. Thus all 21 earlier comment references remain active or reserved, but #7 does not feed a proposed financial adjustment into active evidence.

## Selected-profile qualitative review

| Case | Clean service / type | Primary candidates | Active comments | Reserved reference comments | Corrections | Total time |
|---|---|---:|---:|---|---|---:|
| 1 | Tax Reporting / Service Request | 1 | 2 | None | None | 3.50s |
| 2 | Portfolio Accounting / Service Request | 1 | 0 | None | None | 4.59s |
| 3 | Risk & Compliance Monitoring / Service Request | 2 | 0 | None | None | 4.44s |
| 4 | Securities Settlement / Incident | 1 | 1 | None | None | 9.09s |
| 5 | Trade Matching / Incident | 2 | 2 | None | None | 5.96s |
| 6 | Client Reporting / Incident | 1 | 2 | None | None | 6.16s |
| 7 | Cash Management / Incident | 2 | 0 | Eb2b7aaa9d34a, Ef11d23378034 | None | 11.74s |
| 8 | Rimes Data Feed / Incident | 4 | 0 | None | None | 7.47s |
| 9 | Unresolved / Incident | 0 | 0 | None | None | 10.28s |
| 10 | Regulatory Reporting / Incident | 2 | 2 | None | affected_business_or_it_services, work_type | 7.71s |
| 11 | SimCorp Dimension / Incident | 2 | 2 | None | None | 7.00s |
| 12 | NAV Calculation / Incident | 2 | 0 | None | None | 5.58s |
| 13 | Risk & Compliance Monitoring / Incident | 2 | 0 | None | None | 4.25s |
| 14 | CRM & Client Portal / Service Request | 1 | 0 | None | None | 4.07s |
| 15 | SharePoint & File Storage / Service Request | 1 | 0 | None | None | 3.77s |
| 16 | Outlook & Email / Service Request | 1 | 2 | None | summary | 8.70s |
| 17 | Corporate Actions / Incident | 2 | 2 | None | None | 5.67s |
| 18 | Order Management / Incident | 1 | 2 | None | None | 8.60s |
| 19 | Securities Settlement / Incident | 2 | 2 | None | None | 12.17s |
| 20 | Identity & Access Management / Service Request | 2 | 0 | None | work_type | 4.11s |

- #10: Regulatory Reporting and Incident replace the incompatible intake service/type.
- #16: a mailbox/distribution-list request replaces the outage-like title; the matching historical request is retained.
- #20: routine identity cleanup is classified as Service Request.
- #9: no named vendor/service is inferred from generic benchmark-publication text; no correction is proposed.
- #7: the clean branch still uses Incident, whereas the prior review left type unresolved. The filter marks its failure stage unknown and reserves both cutoff stories. This remaining ambiguity is not counted as work-type accuracy.
- #4/#19: external delivery and internal queue recovery are separated. Stage tags are model judgments, so the deterministic consistency check does not establish that the model identified the stage correctly.
- Historical comment labels remain references or conditional hypotheses. The server always sets `requires_current_verification=true` and `execution_authorized=false`; source text is never rewritten into a confirmed current cause.

## Speed and cost

- Selected-profile median parallel elapsed time: 6.06s. The median sum of the recorded branch timings is 8.34s. This sum is a scheduling comparison, not a separately measured serial run.
- The earlier verbose MiniLM-candidate filter alone had a median of 38.91s. This new complete pipeline is faster in this run, with a different model, shorter output, lower reasoning budget and concurrent branches; the gain cannot be attributed to concurrency alone.
- The repeated-request cache probe returned in 35.4ms without new model calls. This is one Python-level measurement, excluding HTTP and browser rendering.
- Selected run: 40 recorded API calls, 95,880 input tokens and 11,215 output tokens, including 4,632 reasoning tokens. Estimated cost **$0.8158** for 20 tickets.
- Recorded cost across the four comparison runs: **$2.2345**. Estimates use standard documented token rates, not an account invoice: [GPT-5.4](https://developers.openai.com/api/docs/models/gpt-5.4), [GPT-5.5](https://developers.openai.com/api/docs/models/gpt-5.5).

## Serving implementation

- Python: `from service_desk.analysis import AnalysisConfig, TicketAnalysis, TicketInput`.
- HTTP: `POST /tickets/analyze`; the existing `/retrieval/search` contract remains available.
- UI: **Clean & filter**, review field suggestions and prerequisites, switch between primary candidates and all 50, download a correction preview without mutating the imported ticket.
- One shared API client, at most six model calls at once per process, a 45-second deadline per model stage including queue/retry, one validation retry, and explicit partial results on failure.
- Identical in-flight requests share work; successful results have a bounded 64-entry, five-minute memory cache keyed by narrative, current comparison fields, model/config, prompts and index version.
- Model outputs list selected IDs only. Unmentioned candidates are `not_selected`, not proven irrelevant. The server retains all raw ranks, scores, full candidate text and comment source relationships.
- Runtime input construction uses the actual FAISS artifact and exact templates; no 20-case lookup or research annotations are imported into serving code. The current corpus identifies specific resolution narratives by their `Resolution:` prefix; other comments remain in the original retrieval output.

Production defaults were selected after these measurements. The benchmark used explicit model/reasoning parameters; the final default-only configuration edit does not change either measured call payload. Startup/model loading and cold-process import time are excluded from per-ticket measurements.

A separate real HTTP smoke check with the final default returned HTTP 200 for the mailbox-request example: 9.56s request time, 9.47s pipeline compute time, and 23.7ms cached pipeline time on repetition. It proposed the title correction, preserved all 50 candidates and retained the primary analogue's original rank 9. This one additional request is a deployment-path check, not another 20-ticket comparison.
