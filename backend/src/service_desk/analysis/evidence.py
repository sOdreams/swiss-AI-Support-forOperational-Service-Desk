"""Build compact model inputs while retaining original server-owned provenance."""
from dataclasses import asdict
import hashlib
import re


def current_facts(ticket):
    sources = [("summary", ticket.summary), ("description", ticket.description)]
    sources.extend((f"comment_{i}", text) for i, text in enumerate(ticket.comments))
    facts = {}
    for source, text in sources:
        for span in re.split(r"(?<=[.!?])\s+(?=[A-Z])", text or ""):
            if span.strip():
                facts[f"Q{len(facts) + 1}"] = {"source": source, "text": span}
    return facts


def prepare_evidence(retriever, hits):
    """Deduplicate exact templates and comments; no research-corpus assumptions."""
    templates, template_ids, groups, comments, originals = {}, {}, [], {}, {}
    for hit in hits:
        alias = f"G{hit.rank}"
        doc = retriever.describe(hit.document_id)
        summary, description = doc["summary"], doc["description"]
        if len(doc["services"]) == 1:
            summary = summary.replace(doc["services"][0], "{service}")
            description = description.replace(doc["services"][0], "{service}")
        key = (summary, description)
        if key not in template_ids:
            tid = f"T{len(templates) + 1}"
            template_ids[key] = tid
            templates[tid] = {"summary": summary, "description": description}
        groups.append({"id": alias, "template": template_ids[key], "services": doc["services"]})
        originals[alias] = {**asdict(hit), "description": doc["description"], "services": doc["services"]}
        for evidence in hit.evidence:
            # The indexed corpus includes repeated status boilerplate. Preserve
            # it in original hits, but send specific resolution narratives here.
            if not evidence["body"].startswith("Resolution:"):
                continue
            cid = "E" + hashlib.sha256(evidence["body"].encode()).hexdigest()[:12]
            item = comments.setdefault(cid, {"id": cid, "text": evidence["body"],
                                            "services": set(), "sources": []})
            if item["text"] != evidence["body"]:
                raise ValueError("Comment ID collision")
            item["services"].update(doc["services"])
            item["sources"].append({"document_id": hit.document_id, "original_rank": hit.rank,
                                    "occurrences": evidence["occurrences"], "examples": evidence["sources"]})
    for item in comments.values():
        item["services"] = sorted(item["services"])
    model_input = {"templates": templates, "groups": groups,
                   "comments": [{k: c[k] for k in ("id", "text", "services")} for c in comments.values()]}
    return model_input, originals, comments
