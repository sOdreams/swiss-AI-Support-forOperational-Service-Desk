import { useState } from "react";
import { Copy, Download, SendToBack } from "lucide-react";

export function HandoffPanel({ markdown, issueKey }: { markdown: string; issueKey: string }) {
  const [copied, setCopied] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const copy = async () => {
    try { await navigator.clipboard.writeText(markdown); setCopied(markdown); setError(null); }
    catch { setError("Clipboard unavailable. Download the handoff instead."); }
  };
  const download = () => {
    const url = URL.createObjectURL(new Blob([markdown], { type: "text/markdown;charset=utf-8" }));
    const a = document.createElement("a"); a.href = url;
    a.download = `${issueKey.replace(/[^a-zA-Z0-9_-]/g, "_")}-handoff.md`; a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  };
  return <section className="processor-section" aria-label="Handoff package">
    <div className="flex flex-wrap items-center justify-between gap-3"><div>
      <h3 className="flex items-center gap-2 font-semibold"><SendToBack className="h-4 w-4 text-blue-700" />Handoff package</h3>
      <p className="mt-1 text-xs text-slate-600">Current facts, triage, open questions, reviewed actions and your actual findings.</p>
    </div><div className="flex gap-2">
      <button type="button" onClick={() => void copy()} className="flex items-center gap-1 rounded-lg border border-slate-300 px-3 py-2 text-xs font-semibold"><Copy className="h-3.5 w-3.5" />{copied === markdown ? "Copied" : "Copy handoff"}</button>
      <button type="button" onClick={download} className="flex items-center gap-1 rounded-lg bg-blue-700 px-3 py-2 text-xs font-semibold text-white"><Download className="h-3.5 w-3.5" />Download handoff</button>
    </div></div>
    {error && <p role="alert" className="mt-2 text-xs text-amber-800">{error}</p>}
    <details className="mt-3"><summary className="cursor-pointer text-xs font-semibold">Preview handoff</summary>
      <pre className="mt-2 max-h-96 overflow-auto whitespace-pre-wrap rounded-lg bg-slate-50 p-3 text-xs leading-5">{markdown}</pre>
    </details>
    <p className="mt-2 text-xs text-slate-500">A draft you can share after review. Copying or downloading does not contact anyone.</p>
  </section>;
}
