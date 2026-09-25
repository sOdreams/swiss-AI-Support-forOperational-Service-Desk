"""Experimental joint inference; final validation still uses reconciled evidence."""
import jsonschema

from .contracts import filter_schema, obj
from .prompts import FILTER_PROMPT
from .resolution import RESOLVE_PROMPT, resolution_context, resolution_schema, validate_resolution


FAST_PROMPT = FILTER_PROMPT + "\n\n" + RESOLVE_PROMPT + """

Return two objects in order: filter, then resolution. Apply the filtering rules to
filter; the instruction not to produce a final fix applies to that object only.
For resolution, use only current facts plus the evidence you selected in filter:
at most the first five primary groups in ORIGINAL rank order and the first eight
active comments in INPUT comment order. A comment is active only when reference
or conditional. Never cite omitted, reserve or uncertain evidence in an action.
Expand each selected group's template with its service before interpreting it.
Use the filter's signals and prerequisites, but check their current fact citations.
There are no clean_suggestions in this call: Clean runs independently. If the
service is null or stage is unknown, prefer clarification over a speculative fix.
The server will reconcile Clean and Filter and validate resolution against the
surviving source IDs. A later conflict can withhold this draft without another call.
"""


def fast_schema(facts, catalog, groups, comments):
    # The model can see all IDs. Final validation narrows them to active sources.
    return obj({"filter": filter_schema(facts, catalog, groups, comments),
                "resolution": resolution_schema(facts, {**facts, **groups, **comments})})


def validate_fast_resolution(value, ticket, analysis):
    """Reject even real candidate IDs unless they survived filtering/reconciliation."""
    payload, sources = resolution_context(ticket, analysis)
    try:
        jsonschema.validate(value, resolution_schema(payload["current_facts"], sources))
    except jsonschema.ValidationError:
        return ["Resolution does not match the reconciled active-source schema"], sources
    return validate_resolution(value, payload, sources), sources
