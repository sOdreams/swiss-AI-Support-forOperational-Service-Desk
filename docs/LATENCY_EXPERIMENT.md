# Shorter output and an experimental joint workflow

The original workflow runs Clean in parallel with FAISS followed by Filter, then
Resolve. The latency experiment compares its previous prompts, more concise prompts,
and a two-call workflow. All use the same pinned GPT-5.5 model, reasoning `none`,
1,500-token ceiling per request, original-query Top-50 and source validators.

Concise prompts set soft word targets for observations, reasons, conditions, action
cards and reply drafts. Necessary conditions may exceed them. No generated string
is truncated, and exact source quotations are still attached by code. Lowering a
token ceiling alone would not guarantee shorter complete responses.

## Experimental Python entry point

```python
# Reuse the same loaded retriever/pipeline as the documented default workflow.
result = await pipeline.analyze_and_resolve_fast(ticket)
print(result["resolution"])
```

This is an explicit alternative to `analyze_and_resolve()`, not an extra stage to
run after it. Independent `clean()`, `retrieve()`, `filter()` and `resolve()` APIs
remain available. The experiment adds no frontend button or HTTP default switch.

HTTP callers can explicitly use `POST /tickets/resolve-fast` with the same raw-ticket
body as `/tickets/resolve`. No client-written analysis is accepted. The response
uses the existing analysis/proposal shape and strips raw provider diagnostics.
The normal UI continues to use `/tickets/analyze` and `/tickets/resolve`.

```text
Original facts → Clean ────────────────────────────────┐
              → FAISS Top-50 → joint Filter + Resolve ┴→ Validate → Review
```

The joint call sees the candidate packet once and emits two objects, filter then
resolution. Clean stays independent. The server validates Filter, materializes its
exact evidence, reconciles Clean's service interpretation, and rebuilds the allowed
Resolve sources from the surviving selection. It then revalidates the draft against
that smaller source schema and the existing procedure/mode rules. Even a real ID
is rejected if it refers to an unselected group/comment. Conditional source checks
are attached to the cards by code.

Invalid Filter output retains the candidate pool and withholds the joint draft.
Invalid Resolve output preserves valid Clean/Filter results but withholds actions.
A service conflict permits only a valid current-fact clarification; incompatible
drafts are withheld. There is no automatic repair/retry or extra fallback call.
As with the default flow, source membership does not prove semantic correctness.
Unlike separate Resolve, joint inference can be influenced by candidates it later
omits; narrower post-validation constrains citations, not everything the model saw.

The full response adds `workflow="fast"`. Cache and in-flight keys are separate
from default workflows. A warm default analysis does not avoid the fast call, so
use ordinary Resolve when the analyst has already run Clean & filter.
Fast has no `analysis_cache_hit` field because it does not call cached `analyze()`;
its top-level `cache_hit` refers to reuse of the complete fast result.

In Python diagnostics, `stages.filter_resolve` owns the joint provider call and
usage. `stages.filter` and `stages.resolve` are logical validation views with empty
`calls` and `shared_call="filter_resolve"`. Count provider calls once. Timings use
`filter_resolve_ms` instead of separate Filter/Resolve inference durations.

## Reproduce the comparison

From repository root, with the public 20-case development file and a built index:

```sh
OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 \
python backend/scripts/benchmark_latency.py \
  --tickets /path/to/jira_hackathon_blind_eval_challenge_20260923083915-1141.json \
  --artifact artifacts/retrieval/minilm-sdc-v1 \
  --output artifacts/latency/my-comparison
```

The script reads `OPENAI_API_KEY` or prompts without echo. Use a new output directory;
raw outputs contain source evidence and stay in ignored artifacts. The fixed
baseline is commit `2b6862200887fbf4f2a91b820e8bee6a85fc4db3`; a shallow checkout may
need that commit fetched. It reads the old Filter/Resolve prompt constants without
executing old source, and verifies that Clean is unchanged. Runtime, schemas and
model settings are shared to isolate the compared changes.

Each ticket runs the three arms in rotating order, with two concurrent tickets
after the initial smoke. Pipeline result caching is disabled; provider prompt
caching remains enabled and is reported. The full comparison uses 160 generation
requests: 60 baseline, 60 concise and 40 joint. Model loading is excluded.

Review latency together with schema/semantic-validation failures, service conflicts,
source validity, preserved conditions, useful next steps and unanswered questions.
These are public development examples, not held-out ground truth. A single paired
pass does not establish production p95 or a general accuracy improvement.

## Recorded results and deployment decision

The [complete comparison](../backend/validation/latency-comparison.json) preserves
both rounds, protocols/source hashes, token usage, per-case latency and validation
failures. In the first round, concise output reduced latency but sometimes lost
qualifiers: a required approval became a satisfied approval, a pending queue became
safe to replay, and missing target identifiers disappeared. Those outputs were not
silently replaced. The prompts were refined to preserve those distinctions, then
all 20 cases and all three arms were rerun with fresh calls.

The second round measured:

| Metric | Previous prompts | Refined concise prompts | Refined joint workflow |
|---|---:|---:|---:|
| Median full workflow | 9.97 s | **7.53 s** | **6.16 s** |
| Sample p95 (20 observations) | 11.12 s | 8.77 s | 8.29 s |
| Calls per cold ticket | 3 | 3 | 2 |
| Output tokens across 20 tickets | 16,823 | 13,428 | 14,193 |
| Filter validation failures | 3 | 1 | 0 |
| Resolution unavailable | 0 | 0 | 1 |
| Overall `ready` / `needs_review` / `partial` | 16 / 1 / 3 | 18 / 1 / 1 | 19 / 0 / 1 |

Relative to the measured baseline median, concise output was **24.5% faster** and
joint inference **38.2% faster**. Concise output used **20.2% fewer output tokens**.
Reasoning tokens stayed zero. All 50 original candidates, ranks, scores and source
provenance were identical across paired arms in both rounds. The final concise
Filter/Resolve medians were 4.24/3.07 seconds, versus 5.02/4.19 seconds in baseline.
These are measured development observations, not guaranteed speedups.

**Keep refined concise prompts as the normal default. Keep joint inference opt-in.**
Both fast rounds withheld case 9's entire draft after independent service
interpretations conflicted. Separate Resolve could instead generate a current-fact
clarification after reconciliation. The first fast round also withheld case 20;
sampling changed that service agreement in the second round. Faster inference does
not by itself justify losing that fallback. A caller with cached analysis should
also use normal Resolve, which needs just one additional call.

## Qualitative review of the refined outputs

This is assistant review against the original narratives and returned evidence,
not independent human annotation or GT. Cases are numbered by their 1-based
position in the public 20-ticket file. No aggregate semantic accuracy score is
claimed. Both variants still need analyst review, even when all validators pass.

| Case | Observation and remaining limitation |
|---|---|
| 1 | Both concise and joint request missing user/entitlement details. Concise adds an unconfirmed approval prerequisite; whether approval is required is not established in the current narrative. |
| 2 | Both preserve standard processing plus dashboard read scope and request the target identity. Concise returns a focused question without padding action cards. |
| 3 | Both request the analyst identity and validate the requested standard dashboard entitlement; neither claims it has been provisioned. |
| 4 | Concise keeps the external custodian stage and asks whether fail-chasing applies. Joint's reply says it can “remain paused,” implying a pause not established in current facts. |
| 5 | Both preserve already-booked trades and check unmatched references/setup/mapping. Replay eligibility remains unknown; the joint proposal is conditional. |
| 6 | Both separate working preview from defective PDF output and condition template correction on a confirmed defect, followed by output verification. |
| 7 | Both concise and joint ask for the missing account before ledger investigation. Baseline Filter failed validation in this round; separate Resolve still returned diagnostics. |
| 8 | Concise Filter chose two groups outside its supported service and was rejected. Current-fact diagnostics remained available. Joint validated, but redundantly asked to confirm the explicitly named Rimes service. |
| 9 | The source does not name a provider/platform. Independent service interpretations conflict. Concise retains a consumer-platform clarification; joint releases no draft. |
| 10 | Joint targets affected LEI records and a conditional classification correction. Concise spends its critical question on service ownership despite clear regulatory-submission context. |
| 11 | Both treat a database lock as a hypothesis to check. Joint conditions recovery on a confirmed lock and restart eligibility; concise stays diagnostic. |
| 12 | Both now request fund identifiers rather than treating the fund count as an identifier list. Both still label “tolerance breach details” satisfied too broadly; per-fund values are not supplied. |
| 13 | Both now keep the dashboard refresh mechanism unknown and request affected breach IDs; the initial concise claim of a confirmed propagation failure is absent. |
| 14 | Both recognize recorded approval and request the missing account. Neither repeats approval as an unanswered requirement. |
| 15 | Both now ask for the contractor identity and preserve direct, synchronized-folder and inherited-group scope. |
| 16 | Both now mark approval unknown and distinguish the mailbox request from an outage. Concise conditions provisioning on confirmed approval and required details. |
| 17 | Both request the exact event/mapping context before correction or reprocessing. Joint includes a conditional historical procedure. |
| 18 | Both retain missing broker mapping identifiers. Joint offers conditional mapping/routing procedures; concise first narrows the affected route. |
| 19 | Both mark replay eligibility unknown. Concise explicitly requires both a stall and replayability before restart/replay. Joint separates these checks less clearly across cards, so all prerequisites need review. |
| 20 | Both request the deactivation batch/user list. Completed deactivation is not treated as proof that portal access is removed. |

The tests cover two-call concurrency, cache separation, retained ranks/source
conditions, unsupported real IDs, unselected comments, filter failures, conflict
holds, current-fact clarification and HTTP diagnostic stripping. The full suite
passes **56 backend tests and 15 browser tests**, plus frontend type checking,
lint and production build.

The approach follows the [OpenAI latency optimization guide](https://developers.openai.com/api/docs/guides/latency-optimization):
generate less text and compare fewer sequential requests. Measured results, rather
than the general guidance, determine whether an experimental workflow is promoted.
