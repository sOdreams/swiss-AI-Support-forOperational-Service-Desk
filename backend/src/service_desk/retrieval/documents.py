"""The evaluated SDC recipe and source provenance; no routing predictions."""
import hashlib
import json
import re
from collections import Counter, defaultdict

MODEL = "sentence-transformers/all-MiniLM-L6-v2"
REVISION = "1110a243fdf4706b3f48f1d95db1a4f5529b4d41"
RECIPE = "sdc-grouped-v1"
DIMENSION = 384


def comment_parts(value):
    if isinstance(value, str):
        match = re.match(r"^(\S+@\S+):\s*(.*)$", value, flags=re.S)
        return (match[1], match[2]) if match else (None, value)
    if isinstance(value, dict):
        author = value.get("author")
        if isinstance(author, dict):
            author = author.get("id") or author.get("display_name") or author.get("name")
        return author, str(value.get("body") or value.get("text") or "")
    raise ValueError("Comments must be strings or objects")


def query_text(query):
    return query.summary + "\n" + (query.description or "") + "\n" + "\n".join(
        comment_parts(comment)[1] for comment in query.comments
    )


def build_documents(rows):
    if not isinstance(rows, list) or not rows or not all(isinstance(r, dict) for r in rows):
        raise ValueError("Training JSON must be a nonempty array of ticket objects")
    groups = defaultdict(list)
    for index, row in enumerate(rows):
        groups[(str(row.get("Summary") or ""), str(row.get("Description") or ""))].append((index, row))
    documents = []
    for (summary, description), members in sorted(groups.items()):
        counts = Counter()
        sources = defaultdict(list)
        for index, row in members:
            for comment_index, raw in enumerate(row.get("All Comments") or []):
                author, body = comment_parts(raw)
                counts[body] += 1
                sources[body].append({
                    "row_index": index,
                    "ticket_id": str(row.get("Issue ID") or row.get("Issue Key") or f"row-{index}"),
                    "comment_index": comment_index,
                    "author": author,
                    "services": row.get("Affected Business or IT Services") or [],
                    "teams": row.get("Service Team(s)") or [],
                    "assignee": row.get("Assignee"),
                    "resolution_date": row.get("Resolution date"),
                })
        patterns = [body for body, _ in counts.most_common()]
        identity = json.dumps([summary, description], ensure_ascii=False).encode()
        documents.append({
            "document_id": hashlib.sha256(identity).hexdigest(),
            "summary": summary,
            "description": description,
            "text": summary + "\n" + description + "\n" + "\n".join(patterns),
            "historical_count": len(members),
            "row_indices": [index for index, _ in members],
            "evidence": [{"body": body, "sources": sources[body]} for body in patterns],
        })
    return documents


def chunk_documents(encoder, documents):
    budget = encoder.max_seq_length - 8
    if budget <= 32:
        raise ValueError("Encoder context is too short for the chunk recipe")
    chunks, owners = [], []
    for owner, document in enumerate(documents):
        text = document["text"]
        tokens = encoder.tokenizer.encode(text, add_special_tokens=False)
        if len(tokens) <= budget:
            chunks.append(text)
            owners.append(owner)
            continue
        start = 0
        while start < len(tokens):
            chunks.append(encoder.tokenizer.decode(tokens[start:start + budget], skip_special_tokens=True))
            owners.append(owner)
            if start + budget >= len(tokens):
                break
            start += budget - 32
    if any(len(encoder.tokenizer.encode(chunk)) > encoder.max_seq_length for chunk in chunks):
        raise ValueError("Chunk exceeds encoder context")
    return chunks, owners
