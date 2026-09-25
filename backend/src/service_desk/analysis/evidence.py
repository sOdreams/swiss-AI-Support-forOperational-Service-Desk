"""Build compact model inputs while retaining original server-owned provenance."""
from dataclasses import asdict
from functools import lru_cache
import hashlib
import re


@lru_cache(maxsize=4096)
def verification_excerpt(text):
    """Return a literal historical verification clause, never a current outcome."""
    matches = list(re.finditer(r"\b(?:confirmed|validated|verified|verifying|reconciled|reconciling|spot-checked)\b",
                               text, flags=re.I))
    excerpt = re.match(r"[^.!?]*(?:[.!?]|$)", text[matches[-1].start():]).group().strip() if matches else None
    return excerpt if excerpt and len(excerpt) <= 400 else None


def evidence_support(filtered, conflicts=()):
    """Describe selected evidence, not corpus-wide knowledge or answer confidence."""
    filtered = filtered or {}
    active = set(filtered.get("active_comment_ids", []))
    count = len({c["id"] for c in filtered.get("comments", [])
                 if c["id"] in active and c["status"] in {"reference", "conditional"}})
    if conflicts or filtered.get("status") == "needs_review":
        state, reason = "needs_review", "Service interpretations disagree; historical procedures are on hold."
    elif filtered.get("status") != "ready":
        state, reason = "unavailable", "Filtering is unavailable; evidence coverage has not been assessed."
    elif not filtered.get("service"):
        state, reason = "needs_review", "The affected service is unresolved; clarify it before using a historical procedure."
    elif count:
        state, reason = "procedure_reference", "Selected historical procedures are available; check their prerequisites and current applicability."
    elif filtered.get("primary_document_ids"):
        state, reason = "analogue_only", "Similar case narratives were selected, but no applicable historical procedure was selected."
    else:
        state, reason = "no_selected_evidence", "No applicable historical evidence was selected from this candidate pool; use current facts for diagnosis or clarification."
    return {"state": state, "reason": reason, "active_comment_count": count if state == "procedure_reference" else 0}


def current_facts(ticket):
    sources = [("summary", ticket.summary), ("description", ticket.description)]
    sources.extend((f"comment_{i}", text) for i, text in enumerate(ticket.comments))
    facts = {}
    for source, text in sources:
        for span in re.split(r"(?<=[.!?])\s+(?=[A-Z])", text or ""):
            if span.strip():
                facts[f"Q{len(facts) + 1}"] = {"source": source, "text": span}
    return facts


def prepare_evidence(documents, hits):
    """Deduplicate exact templates and comments; no research-corpus assumptions."""
    templates, template_ids, groups, comments, originals = {}, {}, [], {}, {}
    for hit in hits:
        alias = f"G{hit.rank}"
        doc = documents[hit.document_id]
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
                                            "verification_excerpt": verification_excerpt(evidence["body"]),
                                            "services": set(), "sources": []})
            if item["text"] != evidence["body"]:
                raise ValueError("Comment ID collision")
            item["services"].update(doc["services"])
            item["sources"].append({"document_id": hit.document_id, "original_rank": hit.rank,
                                    "occurrences": evidence["occurrences"], "examples": evidence["sources"]})
    for item in comments.values():
        item["services"] = sorted(item["services"])
    model_input = {"templates": templates, "groups": groups,
                   "comments": [{k: c[k] for k in ("id", "text", "services", "verification_excerpt")} for c in comments.values()]}
    return model_input, originals, comments
