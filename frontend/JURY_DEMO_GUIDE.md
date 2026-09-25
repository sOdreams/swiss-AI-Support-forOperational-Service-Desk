# Jury Demo Guide — V6

## 60–90 second story

1. **Upload the JSON queue** and show that the left side supports search, filters, sorting and pagination for a large ticket set.
2. Move to **Ticket Categories** and horizontally scroll through Work type, Request type, Priority, Status, Service team and Business entity.
3. Click a ticket directly inside a category.
4. Show the original ticket information.
5. In **Recommended Solutions**, select one AI suggestion — or demonstrate that the analyst can ignore all suggestions and write the **Real solution**.
6. Select one **Affected Business Aspect**.
7. Point out that **Send stays disabled until the required information is complete**.
8. Click **Send**. The ticket disappears from the active queue/categories and appears in **Processed Tickets** on the right.
9. Explain that the selected recommendation / real solution and business-impact label are stored as human feedback for AI evaluation and future improvement, rather than instantly retraining the model from unvalidated input.

## What this demonstrates

- Large-queue workflow rather than a chatbot.
- Clickable category exploration.
- Human-in-the-loop resolution.
- Structured feedback capture.
- Clear separation between active and processed work.
- Safe path toward AI improvement from reviewed analyst outcomes.


## V7 feedback moment

For one ticket, rate all three AI recommendations as Highly / Medium / Poor relevant. Select one recommendation, or reject all three and enter the Real Solution. Explain that the labels are stored as structured RAG feedback, while a human-entered real solution becomes a reviewed knowledge candidate for future vector-database ingestion.

Suggested line: **“The system does not blindly learn from every click. Human labels improve our retrieval evaluation, and validated real resolutions can become new knowledge for future RAG queries.”**
