"""Paired cold-workflow comparison; raw evidence stays in a local artifact folder."""
import argparse
import ast
import asyncio
import getpass
import hashlib
import json
import math
import os
from pathlib import Path
import statistics
import subprocess
import time

from benchmark_analysis import save, tickets
from service_desk.analysis import AnalysisConfig, TicketAnalysis
from service_desk.analysis.pipeline import _safe_error
from service_desk.retrieval import TicketRetriever
import service_desk.analysis.pipeline as pipeline_module


REPO = Path(__file__).resolve().parents[2]


def frozen_prompt(ref, file, name):
    source = subprocess.check_output(["git", "show", f"{ref}:backend/src/service_desk/analysis/{file}"], cwd=REPO, text=True)
    for node in ast.parse(source).body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name for t in node.targets):
            return ast.literal_eval(node.value)
    raise ValueError("Baseline prompt was not found")


class BaselineAnalysis(TicketAnalysis):
    def __init__(self, *args, baseline_prompts, **kwargs):
        super().__init__(*args, **kwargs)
        self.baseline_prompts = baseline_prompts

    async def _generate(self, stage, prompt, payload, schema, validate):
        return await super()._generate(stage, self.baseline_prompts.get(stage, prompt), payload, schema, validate)


def summarize(results):
    calls = [c for r in results for s in r["stages"].values() for c in s["calls"]]
    latency = [r["elapsed_ms"] for r in results]
    return {"cases": len(results), "ready": sum(r["status"] == "ready" for r in results),
        "partial": sum(r["status"] == "partial" for r in results),
        "needs_review": sum(r["status"] == "needs_review" for r in results),
        "filter_failures": sum(not r["stages"]["filter"]["ok"] for r in results),
        "resolution_unavailable": sum(r["resolution"]["status"] != "ready" for r in results),
        "provider_calls": len(calls), "reasoning_tokens": sum(c["usage"].get("output_tokens_details", {}).get("reasoning_tokens", 0) for c in calls),
        "input_tokens": sum(c["usage"].get("input_tokens", 0) for c in calls),
        "output_tokens": sum(c["usage"].get("output_tokens", 0) for c in calls),
        "cached_input_tokens": sum(c["usage"].get("input_tokens_details", {}).get("cached_tokens", 0) for c in calls),
        "median_elapsed_ms": round(statistics.median(latency), 1), "max_elapsed_ms": round(max(latency), 1),
        "p95_elapsed_ms": round(sorted(latency)[max(0, math.ceil(.95 * len(latency)) - 1)], 1),
        "all_top50_retained": all(r["retrieval"] is not None and
            [h["rank"] for h in r["retrieval"]["hits"]] == list(range(1, 51)) for r in results)}


async def run(args, key):
    inputs = tickets(args.tickets)
    if len(inputs) != 20:
        raise ValueError("This development comparison requires exactly 20 tickets")
    old = {"candidate_filter": frozen_prompt(args.baseline_ref, "prompts.py", "FILTER_PROMPT"),
           "ticket_resolve": frozen_prompt(args.baseline_ref, "resolution.py", "RESOLVE_PROMPT")}
    if frozen_prompt(args.baseline_ref, "prompts.py", "CLEAN_PROMPT") != pipeline_module.CLEAN_PROMPT:
        raise ValueError("Clean changed; this baseline no longer isolates Filter/Resolve changes")
    args.output.mkdir(parents=True, exist_ok=False)
    for arm in ("baseline", "compact", "fast"):
        (args.output / arm).mkdir()
    retriever = await asyncio.to_thread(TicketRetriever.load, args.artifact)
    config = AnalysisConfig(cache_size=0)
    pipelines = {"baseline": BaselineAnalysis(retriever, api_key=key, config=config, baseline_prompts=old),
                 "compact": TicketAnalysis(retriever, api_key=key, config=config),
                 "fast": TicketAnalysis(retriever, api_key=key, config=config)}
    protocol = {"created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "baseline_ref": args.baseline_ref, "model": config.model, "reasoning_effort": config.reasoning_effort,
        "index_version": retriever.manifest["index_version"], "data_sha256": hashlib.sha256(args.tickets.read_bytes()).hexdigest(),
        "code_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in Path(pipeline_module.__file__).parent.glob("*.py")},
        "baseline_prompt_sha256": {k: hashlib.sha256(v.encode()).hexdigest() for k, v in old.items()},
        "cases": 20, "case_concurrency": args.concurrency, "cache_size": 0, "retries": 0,
        "schedule": "Each ticket runs all three arms sequentially in rotating order; first ticket alone, then bounded concurrent tickets. Encoder load excluded.",
        "arms": {"baseline": "Previous Filter/Resolve prompts, three calls", "compact": "Concise Filter/Resolve prompts, three calls",
                 "fast": "Clean parallel with retrieval and joint Filter/Resolve, two calls; post-reconciliation validation"},
        "evaluation": "Public development cases; no answer annotations in inference. One paired pass, not GT accuracy or a production latency guarantee."}
    save(args.output / "protocol.json", protocol)
    gate = asyncio.Semaphore(args.concurrency)

    async def one(index, ticket):
        async with gate:
            arms = ["baseline", "compact", "fast"]
            shift = index % len(arms)
            for arm in arms[shift:] + arms[:shift]:
                pipeline = pipelines[arm]
                method = pipeline.analyze_and_resolve_fast if arm == "fast" else pipeline.analyze_and_resolve
                result = await method(ticket)
                result.update(case=index + 1, benchmark_arm=arm)
                save(args.output / arm / f"case_{index + 1:02d}.json", result)
                print(json.dumps({"arm": arm, "case": index + 1, "status": result["status"],
                    "elapsed_ms": round(result["elapsed_ms"]), "filter_ok": result["stages"]["filter"]["ok"],
                    "resolve_ok": result["stages"]["resolve"]["ok"]}), flush=True)
                if any(s.get("error", {}).get("http_status") in (401, 403, 429) for s in result["stages"].values() if s.get("error")):
                    raise RuntimeError("Provider access or capacity error; comparison stopped")
    try:
        await one(0, inputs[0])
        await asyncio.gather(*(one(i, t) for i, t in enumerate(inputs) if i))
        results = {arm: [json.loads(p.read_text()) for p in sorted((args.output / arm).glob("case_*.json"))] for arm in pipelines}
        report = {"protocol": protocol, "arms": {arm: summarize(rows) for arm, rows in results.items()},
            "paired_median_delta_ms": {arm: round(statistics.median(r["elapsed_ms"] - b["elapsed_ms"]
                for r, b in zip(results[arm], results["baseline"])), 1) for arm in ("compact", "fast")}}
        save(args.output / "summary.json", report)
        print(json.dumps(report["arms"]), flush=True)
    finally:
        for pipeline in pipelines.values():
            await pipeline.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tickets", type=Path, required=True)
    parser.add_argument("--artifact", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--baseline-ref", default="2b6862200887fbf4f2a91b820e8bee6a85fc4db3")
    parser.add_argument("--concurrency", type=int, default=2)
    args = parser.parse_args()
    if args.concurrency < 1:
        parser.error("Concurrency must be positive")
    key = os.environ.get("OPENAI_API_KEY") or getpass.getpass("OpenAI API key (hidden): ")
    try:
        asyncio.run(run(args, key.strip().replace("\\_", "_")))
    except Exception as exc:
        print(json.dumps({"fatal": _safe_error(exc)}), flush=True)
        raise SystemExit(1) from None
