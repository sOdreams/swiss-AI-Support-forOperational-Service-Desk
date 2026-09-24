import { useEffect, useRef, useState } from "react";
import { cleanAndFilterTicket } from "../../services/api";
import type { TicketAnalysisResponse } from "../../types/analysis";
import type { Ticket } from "../../types/ticket";

type State = { ticket: Ticket; data: TicketAnalysisResponse | null; error: string | null; loading: boolean };

export function useTicketAnalysis(ticket: Ticket) {
  const [state, setState] = useState<State | null>(null);
  const controller = useRef<AbortController | null>(null);
  useEffect(() => () => { controller.current?.abort(); }, [ticket]);

  const run = async () => {
    controller.current?.abort();
    const request = new AbortController();
    controller.current = request;
    setState({ ticket, data: null, error: null, loading: true });
    try {
      const data = await cleanAndFilterTicket(ticket, request.signal);
      if (!request.signal.aborted) setState({ ticket, data, error: null, loading: false });
    } catch (error: unknown) {
      if (!request.signal.aborted) setState({ ticket, data: null, loading: false,
        error: error instanceof Error ? error.message : "Ticket analysis failed" });
    }
  };
  const current = state?.ticket === ticket ? state : null;
  return { data: current?.data ?? null, error: current?.error ?? null, loading: current?.loading ?? false, run };
}
