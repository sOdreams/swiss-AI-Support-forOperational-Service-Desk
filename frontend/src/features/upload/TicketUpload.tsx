import { FileJson, UploadCloud, XCircle } from "lucide-react";
import { useRef } from "react";
import { parseTicketJson } from "../../lib/ticketJson";
import type { Ticket } from "../../types/ticket";

export interface UploadState {
  fileName: string | null;
  error: string | null;
}

export function TicketUpload({
  onLoaded,
  onError,
  state,
}: {
  onLoaded: (tickets: Ticket[], fileName: string) => void;
  onError: (fileName: string, message: string) => void;
  state: UploadState;
}) {
  const inputRef = useRef<HTMLInputElement | null>(null);

  const handleFile = async (file?: File) => {
    if (!file) return;
    try {
      const text = await file.text();
      const payload = JSON.parse(text) as unknown;
      const tickets = parseTicketJson(payload);
      if (tickets.length === 0) throw new Error("No Jira-style tickets were found in this JSON file.");
      onLoaded(tickets, file.name);
    } catch (error) {
      const message = error instanceof Error ? error.message : "The JSON file could not be loaded.";
      onError(file.name, message);
    }
  };

  return (
    <div className="space-y-2.5">
      <input
        ref={inputRef}
        type="file"
        accept="application/json,.json"
        className="hidden"
        onChange={(event: { target: { files: FileList | null; value: string } }) => {
          void handleFile(event.target.files?.[0]);
          event.target.value = "";
        }}
      />
      <button
        type="button"
        onClick={() => inputRef.current?.click()}
        className="group flex w-full items-center justify-between rounded-xl border border-[#E9C39E] bg-white px-3.5 py-3.5 text-left shadow-[0_3px_10px_rgba(74,55,37,0.05)] transition-all duration-150 hover:-translate-y-0.5 hover:border-[#D9965B] hover:bg-[#FFFDFC] hover:shadow-[0_8px_18px_rgba(74,55,37,0.09)]"
      >
        <span className="flex min-w-0 items-center gap-3">
          <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-[#D97735] text-white shadow-sm transition group-hover:bg-[#C7662C]">
            <UploadCloud className="h-4 w-4" />
          </span>
          <span className="min-w-0">
            <span className="block text-[14px] font-extrabold text-slate-900">Upload ticket JSON</span>
            <span className="mt-0.5 block truncate text-[11px] text-slate-500">Choose a JSON file with one or more Jira tickets</span>
          </span>
        </span>
        <FileJson className="h-4 w-4 shrink-0 text-[#B25D27]" />
      </button>

      {state.fileName ? (
        <div className="flex items-start gap-2 rounded-lg border border-[#F0D2B5] bg-white/75 px-2.5 py-2.5">
          {state.error ? <XCircle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-red-500" /> : <FileJson className="mt-0.5 h-3.5 w-3.5 shrink-0 text-[#B25D27]" />}
          <div className="min-w-0">
            <p className="truncate text-[11px] font-semibold text-slate-700">{state.fileName}</p>
            <p className={`mt-0.5 text-[11px] leading-4 ${state.error ? "text-red-600" : "text-slate-400"}`}>
              {state.error ?? "JSON loaded successfully"}
            </p>
          </div>
        </div>
      ) : null}
    </div>
  );
}
