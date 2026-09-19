# Jury Demo Guide — Service Desk Copilot

## The product story

Do not present this as "a chatbot for Jira". Present it as:

> An operational copilot that turns a large ticket queue into evidence-backed recommendations while keeping the analyst in control.

The visual story of the frontend is intentionally left-to-right:

`20,000-ticket queue → original ticket → evidence-backed AI proposal → analyst decision → feedback record`

## 90-second demo sequence

1. Upload a JSON queue and point out that the interface is designed for a large operational dataset rather than a 5-ticket mock.
2. Search/select a high-impact ticket.
3. In the center, show that the source Jira fields remain untouched and missing fields are explicitly "Not recorded".
4. In the AI panel, show the proposed priority/team, confidence, the short reason and the supporting knowledge source.
5. Show a ticket where the current priority is weaker than the evidence suggests.
6. Approve or edit the proposal. Point out that the human decision is captured separately and nothing is applied automatically.
7. End on the feedback-loop message: analyst decisions can be measured and used for evaluation/improvement.

## Three cases worth preparing

### 1. Priority correction
Recorded priority is too low, while comments show multiple users + critical service + deadline. This demonstrates business value immediately.

### 2. Insufficient information
Urgency/impact are null and the description is vague. The AI should ask clarifying questions instead of inventing values. This demonstrates trustworthiness.

### 3. Resolved + Duplicate
Status = Resolved while Resolution = Duplicate and another linked issue remains active. This demonstrates that the model understands Jira semantics rather than only summarizing text.

## Metrics that strengthen the project

Measure these on a small labeled evaluation set during the hackathon:

- classification accuracy,
- priority recommendation accuracy,
- routing/team accuracy,
- evidence/source coverage,
- analyst accept/edit/reject rate,
- median time from opening a ticket to a reviewed proposal.

Only present measured numbers as results. If a number is a target or prototype estimate, label it as such.

## Architecture to defend technically

Production direction:

`Jira/API → backend search/pagination → selected ticket → AI classification + RAG → proposal → frontend human review → feedback API`

For ~20,000 tickets, production search/filter/sort/pagination should be server-side. The hackathon frontend can parse a large JSON file for the demo, but it deliberately renders only 50 tickets per page.

## What judges should remember

- It scales conceptually beyond a toy list.
- It does not hide the original data.
- It separates recorded facts from AI suggestions.
- It exposes evidence and confidence.
- It handles insufficient evidence explicitly.
- It keeps a human decision in the loop.
- It creates a feedback record suitable for evaluation and future improvement.
