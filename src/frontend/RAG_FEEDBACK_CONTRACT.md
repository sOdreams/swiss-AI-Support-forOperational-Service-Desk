# RAG Feedback Contract

The frontend sends one structured feedback object after the analyst completes the human review.

```json
{
  "issue_id": "201208",
  "issue_key": "INC-1208",
  "selected_solution_id": "solution_1",
  "selected_solution": "Validate ...",
  "real_solution": null,
  "affected_business_aspect": "Critical business / regulatory impact ...",
  "solution_feedback": [
    {
      "solution_id": "solution_1",
      "text": "Validate ...",
      "relevance": "highly_relevant",
      "selected": true
    },
    {
      "solution_id": "solution_2",
      "text": "Route or escalate ...",
      "relevance": "medium_relevant",
      "selected": false
    },
    {
      "solution_id": "solution_3",
      "text": "Apply the relevant documented troubleshooting procedure ...",
      "relevance": "poor_relevant",
      "selected": false
    }
  ],
  "rag_context": {
    "work_type": "Incident",
    "request_type": "Service unavailable",
    "priority": "P1",
    "status": "In Progress",
    "business_entity": "Finance",
    "service_teams": ["Application Support L1"],
    "affected_services": ["Portfolio Reporting"]
  },
  "knowledge_candidate": false,
  "processed_at": "2026-09-24T10:00:00.000Z",
  "source": "human_in_the_loop_rag_feedback"
}
```

If no AI solution is selected, `selected_solution_id` and `selected_solution` are `null`, the analyst must provide `real_solution`, and `knowledge_candidate` becomes `true`.

## Recommended backend pipeline

```text
Human feedback
   ↓
Feedback store
   ↓
Offline evaluation / retrieval metrics
   ↓
Knowledge candidate review
   ↓
Normalize + chunk + metadata
   ↓
Embedding
   ↓
Vector database
   ↓
Improved future RAG retrieval
```

Do not ingest every human text directly into the vector DB without validation.
