import { AlertTriangle } from "lucide-react";

export function ErrorPanel({ title = "Could not load data", message }: { title?: string; message: string }) {
  return (
    <div role="alert" className="border border-red-200 bg-red-50 rounded-[var(--rl-radius)] p-4 flex gap-3">
      <AlertTriangle className="w-4 h-4 text-danger mt-0.5 shrink-0" />
      <div>
        <div className="text-sm font-medium text-danger">{title}</div>
        <div className="text-xs text-muted mt-1 break-words">{message}</div>
        <div className="text-xs text-muted mt-2">
          Start the backend with <code className="font-mono">uvicorn risklab_api.main:app --reload</code> in{" "}
          <code className="font-mono">backend/</code>, and check <code className="font-mono">NEXT_PUBLIC_API_URL</code>.
        </div>
      </div>
    </div>
  );
}
