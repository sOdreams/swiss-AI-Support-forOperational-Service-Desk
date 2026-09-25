import { useEffect, useRef, useState } from "react";
import { resolveTicket } from "../../services/api";
import type { TicketAnalysisResponse } from "../../types/analysis";
import type { ResolutionEdits, ResolutionResponse } from "../../types/resolution";
import type { Ticket } from "../../types/ticket";

type State = { ticket: Ticket; analysis: TicketAnalysisResponse; data: ResolutionResponse | null; loading: boolean; error: string | null };

export function useResolution(ticket: Ticket, analysis: TicketAnalysisResponse | null) {
  const [state, setState] = useState<State | null>(null);
  const [review, setReview] = useState<ResolutionEdits | null>(null);
  const controller = useRef<AbortController | null>(null);
  useEffect(() => () => { controller.current?.abort(); }, [ticket, analysis]);

  const run = async () => {
    if (!analysis) return;
    controller.current?.abort();
    const request = new AbortController();
    controller.current = request;
    setReview(null);
    setState({ ticket, analysis, data: null, loading: true, error: null });
    try {
      const data = await resolveTicket(ticket, request.signal);
      if (request.signal.aborted) return;
      setState({ ticket, analysis, data, loading: false, error: null });
      if (data.resolution.status === "ready") setReview({
        proposal_id: data.resolution.proposal_id,
        actions: data.resolution.actions.map((action) => ({ action_id: action.id, decision: "unreviewed", edited_next_step: null })),
        reply_draft: data.resolution.reply_draft,
      });
    } catch (error: unknown) {
      if (!request.signal.aborted) setState({ ticket, analysis, data: null, loading: false,
        error: error instanceof Error ? error.message : "Next-step suggestions failed" });
    }
  };
  const current = state?.ticket === ticket && state.analysis === analysis ? state : null;
  return { data: current?.data ?? null, loading: current?.loading ?? false, error: current?.error ?? null,
    review: current?.data?.resolution.status === "ready" ? review : null, setReview, run };
}
