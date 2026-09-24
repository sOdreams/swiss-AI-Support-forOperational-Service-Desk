"""Benchmark the serving pipeline on user-supplied tickets; no evaluation labels.

Read-only analysis. Output is local and should stay outside tracked source.
"""
import argparse
import asyncio
import getpass
import hashlib
import json
import os
from pathlib import Path
import statistics
import time

from openai import AsyncOpenAI
from service_desk.analysis import AnalysisConfig, TicketAnalysis, TicketInput
from service_desk.analysis.pipeline import _safe_error
from service_desk.retrieval import TicketRetriever
from service_desk.retrieval.documents import comment_parts
import service_desk.analysis.pipeline as pipeline_module


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def tickets(path):
    value = json.loads(path.read_text())
    rows = value["records"] if isinstance(value, dict) else value
    return [TicketInput(summary=r.get("Summary") or "", description=r.get("Description") or "",
                        comments=tuple(comment_parts(c)[1] for c in r.get("All Comments", [])),
                        current_services=tuple(r.get("Affected Business or IT Services") or []),
                        current_work_type=r.get("Work type")) for r in rows]


async def main(args, key):
    all_tickets = tickets(args.tickets)
    if args.limit:
        all_tickets = all_tickets[:args.limit]
    retriever = await asyncio.to_thread(TicketRetriever.load, args.artifact)
    root = Path(pipeline_module.__file__).parent
    hashes = {str(p.resolve()): hashlib.sha256(p.read_bytes()).hexdigest() for p in root.glob("*.py")}
    hashes[str(args.tickets.resolve())] = hashlib.sha256(args.tickets.read_bytes()).hexdigest()
    out = args.output; out.mkdir(parents=True, exist_ok=True)
    for model in args.models:
        dest = out / model
        dest.mkdir(exist_ok=True); (dest / "raw").mkdir(exist_ok=True)
        protocol = {"model": model, "reasoning_effort": args.reasoning_effort, "cases": len(all_tickets),
                    "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "hashes": hashes, "index_version": retriever.manifest["index_version"],
                    "concurrent_tickets": args.concurrency,
                    "evaluation": "No annotations in inference; later development-review comparison is not GT accuracy.",
                    "schedule": "clean(current narrative) || [FAISS(original narrative) -> filter]"}
        protocol_path = dest / "protocol.json"
        if protocol_path.exists():
            previous = json.loads(protocol_path.read_text())
            for k in ("hashes", "model", "reasoning_effort", "cases", "index_version"):
                if previous[k] != protocol[k]:
                    raise ValueError("Resume protocol mismatch; choose a new output directory")
        else:
            save(protocol_path, protocol)
        client = AsyncOpenAI(api_key=key, base_url="https://api.openai.com/v1", timeout=45, max_retries=0)
        try:
            info = await client.models.retrieve(model)
            save(dest / "access.json", {"ok": True, "id": info.id})
        except Exception as exc:
            save(dest / "access.json", {"ok": False, "error": _safe_error(exc)})
            print(json.dumps({"model": model, "access": _safe_error(exc)}), flush=True)
            await client.close()
            continue
        pipeline = TicketAnalysis(retriever, client=client,
            config=AnalysisConfig(model=model, reasoning_effort=args.reasoning_effort))
        gate = asyncio.Semaphore(args.concurrency)

        async def one(index, ticket):
            file = dest / "raw" / f"case_{index + 1:02d}.json"
            if file.exists():
                return json.loads(file.read_text())
            async with gate:
                result = await pipeline.analyze(ticket)
                result["case"] = index + 1
                save(file, result)
                print(json.dumps({"model": model, "case": index + 1, "status": result["status"],
                                  "elapsed_ms": round(result["elapsed_ms"]),
                                  "clean": result["stage_status"] if "stage_status" in result else result["stages"]["clean"]["ok"],
                                  "filter": result["stages"]["filter"]["ok"]}), flush=True)
                return result
        try:
            # Smoke test the first case before submitting the rest.
            first = await one(0, all_tickets[0])
            if first["status"] == "partial":
                print(json.dumps({"model": model, "stopped_after_first_case": True}), flush=True)
                continue
            results = [first, *await asyncio.gather(*(one(i, t) for i, t in enumerate(all_tickets) if i))]
            repeated = await pipeline.analyze(all_tickets[-1])
            calls = [call for r in results for stage in r["stages"].values() for call in stage["calls"]]
            usage = {"input_tokens": 0, "cached_input_tokens": 0, "output_tokens": 0, "reasoning_tokens": 0}
            for c in calls:
                u = c["usage"]
                usage["input_tokens"] += u.get("input_tokens", 0)
                usage["cached_input_tokens"] += (u.get("input_tokens_details") or {}).get("cached_tokens", 0)
                usage["output_tokens"] += u.get("output_tokens", 0)
                usage["reasoning_tokens"] += (u.get("output_tokens_details") or {}).get("reasoning_tokens", 0)
            summary = {"cases": len(results), "ready": sum(r["status"] == "ready" for r in results),
                       "partial": sum(r["status"] == "partial" for r in results),
                       "needs_review": sum(r["status"] == "needs_review" for r in results),
                       "recorded_calls": len(calls), "usage": usage,
                       "median_elapsed_ms": statistics.median(r["elapsed_ms"] for r in results),
                       "max_elapsed_ms": max(r["elapsed_ms"] for r in results),
                       "median_serial_stage_sum_ms": statistics.median(sum(r["timings"].values()) for r in results),
                       "warm_cache_probe": {"cache_hit": repeated["cache_hit"], "elapsed_ms": repeated["elapsed_ms"]}}
            save(dest / "summary.json", summary)
            print(json.dumps({"model": model, **summary}), flush=True)
        finally:
            await pipeline.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--tickets", type=Path, required=True)
    parser.add_argument("--artifact", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--models", nargs="+", default=["gpt-5.4-2026-03-05", "gpt-5.5-2026-04-23"])
    parser.add_argument("--reasoning-effort", default="none", choices=["none", "low", "medium", "high"])
    parser.add_argument("--concurrency", type=int, default=2)
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    if args.concurrency < 1 or (args.limit is not None and args.limit < 1):
        parser.error("Counts must be positive")
    key = os.environ.get("OPENAI_API_KEY") or getpass.getpass("OpenAI API key (hidden): ")
    try:
        asyncio.run(main(args, key.strip().replace("\\_", "_")))
    except Exception as exc:
        print(json.dumps({"fatal": _safe_error(exc)}), flush=True)
        raise SystemExit(1) from None
