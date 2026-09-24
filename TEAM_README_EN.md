# SwissLife 2026: AI-Powered Jira Ticket Triage

This document summarizes the current implementation for the team.

## Executive summary

We have built an explainable Jira ticket-triage baseline based on historical-ticket retrieval and business rules. It reads 20,000 historical tickets, analyzes 20 challenge tickets, and predicts:

- Work type
- Actual affected service
- Service team
- Assignee
- Urgency
- Impact
- Priority
- Resolution status
- Resolution comment

The current implementation uses only the Python standard library. It does not require an external LLM, vector database, or third-party Python package.

## Current implementation

### Phase 1: Data and rule foundation

- Loads and normalizes the training and challenge JSON files.
- Handles null values, list fields, comments, and Jira text fields.
- Preserves operational identifiers such as `MT536`, `TMA-402`, `NAV_EOD_GE_375`, and `SECLINK-7549`.
- Builds historical indexes for:
  - Service → Service Team
  - Service + Team → Assignee candidates
  - Keywords → historical tickets
  - Service → historical resolution owners and resolution comments
- Encodes the critical-service list and the README Priority matrix.

### Phase 2: Retrieval and triage

- Uses keyword overlap, IDF weighting, and identifier weighting to retrieve similar historical tickets.
- Classifies Incident vs Service Request from the ticket narrative rather than copying the title.
- Uses business clues in the description to correct an incorrect selected service.
- Maps the inferred service to the observed service team.
- Uses similar historical resolution owners when selecting an Assignee.
- Estimates Urgency and Impact from criticality, blocked processing, scope, deadlines, and workaround availability.
- Calculates Priority deterministically from the Urgency × Impact matrix.

### Phase 3: Resolution generation

- Extracts concrete Resolution comments from historical tickets.
- Prefers a matching service and Work type resolution pattern.
- Falls back to a service-specific template when historical text is too generic.
- Generates targeted clarification requests when evidence is insufficient.
- Uses only the allowed Resolution values:
  - `done`
  - `cancelled`
  - `clarification`
  - `cannot reproduce`

## Main files

- `triage_pipeline.py`: main pipeline for indexing, retrieval, triage, priority calculation, and Resolution generation.
- `test_triage_pipeline.py`: five unit tests covering routing, service correction, priority rules, and Phase 3 behavior.
- `triage_phase3_output.json`: latest output for all 20 challenge tickets, including evidence and similar historical tickets.
- `triage_phase2_output.json`: older Phase 1–2 intermediate output; it is not the final result.
- `environment.yml`: Conda environment definition.
- `requirements.txt`: confirms that no third-party packages are required.
- `PROPOSAL.md`: project proposal.
- `TEAM_README.md`: Chinese team summary.

## Conda setup and execution

From Git Bash:

```bash
cd /e/ZurichHack_SwissLife/SwissLife-2026
```

Create the environment for the first time:

```bash
conda env create -f environment.yml
conda activate swisslife-triage
```

If the environment already exists:

```bash
conda env update -f environment.yml
conda activate swisslife-triage
```

Run the tests:

```bash
python -m unittest -v test_triage_pipeline.py
```

Run the complete pipeline:

```bash
python triage_pipeline.py --output triage_phase3_output.json
```

Expected console output:

```text
Loaded 20000 training records and 20 challenge records.
Indexed 20 services.
Wrote triage_phase3_output.json
Validation: all phase 1-3 predictions are structurally consistent.
```

## Examples of corrections identified

The pipeline can override misleading intake fields when the narrative provides stronger evidence:

- Benchmark publication delay: `SharePoint & File Storage` → `Rimes Data Feed`
- LEI submission rejection: `CRM & Client Portal` → `Regulatory Reporting`
- Bulk deactivated-user cleanup: `Incident` → `Service Request`
- Shared mailbox creation: title suggests an outage, but the narrative indicates a `Service Request`

## How to review the output

For each record, review:

```text
prediction.work_type
prediction.affected_services
prediction.service_teams
prediction.assignee
prediction.urgency
prediction.impact
prediction.priority
prediction.resolution
prediction.resolution_comment
```

Then inspect:

- `reasoning_summary`: why the prediction was made.
- `similar_historical_tickets`: which historical cases were used as evidence.
- `confidence`: confidence for Work type, Service, and ownership.

Pay particular attention to:

- Rimes Data Feed and other services without a single dominant resolution owner.
- Vendor-warning tickets and their Resolution status.
- Low-confidence Assignee predictions.
- Priority values for critical services, to ensure the impact was not overstated.

## Known limitations

1. Retrieval is currently standard-library lexical/hybrid retrieval, not embedding-based semantic search.
2. Assignee history is distributed across several services, so some Assignee predictions are estimates.
3. Urgency and Impact are explainable heuristics and still need pseudo-holdout calibration and human review.
4. Historical Resolution comments are useful patterns but do not guarantee the hidden evaluation label or Assignee.
5. Structural validation confirms schema and matrix consistency; it does not guarantee the hidden evaluation score.

## Recommended next steps

- Manually review all 20 outputs, especially Rimes, Regulatory Reporting, Cash Management, Settlement, and Assignee selections.
- Add more Resolution-pattern tests.
- Run pseudo-holdout evaluation by hiding fields from historical tickets and measuring reconstruction accuracy.
- Add stronger semantic retrieval or embeddings.
- Improve Assignee ranking using service, request type, business entity, and Resolution owner together.
- Export the final fields in the exact format required by the evaluation harness or Jira import process.

