import { useEffect, useState } from "react";
import { retrieveEvidence } from "../../services/api";
import type { RetrievalResponse } from "../../types/retrieval";
import type { Ticket } from "../../types/ticket";

type Result = { ticket: Ticket; data: RetrievalResponse | null; error: string | null };

export function useRetrieval(ticket: Ticket) {
  const [result, setResult] = useState<Result | null>(null);
  useEffect(() => {
    const controller = new AbortController();
    let active = true;
    retrieveEvidence(ticket, controller.signal).then(
      (data) => { if (active) setResult({ ticket, data, error: null }); },
      (error: unknown) => {
        if (active) setResult({ ticket, data: null, error: error instanceof Error ? error.message : "Retrieval failed" });
      },
    );
    return () => { active = false; controller.abort(); };
  }, [ticket]);
  const current = result?.ticket === ticket ? result : null;
  return { data: current?.data ?? null, error: current?.error ?? null, loading: current === null };
}
