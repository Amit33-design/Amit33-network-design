export function Loading({ label = "Scanning the market…" }: { label?: string }) {
  return (
    <div className="flex items-center gap-3 text-slate-500 py-10">
      <div className="h-4 w-4 rounded-full border-2 border-alpha border-t-transparent animate-spin" />
      {label}
    </div>
  );
}

export function ErrorBox({ error }: { error: string }) {
  return (
    <div className="bg-red-50 border border-red-200 text-red-700 rounded p-4 text-sm">
      <div className="font-semibold">Couldn't reach the backend.</div>
      <div className="mt-1">{error}</div>
      <div className="mt-2 text-red-500">
        Start it with <code>uvicorn backend.main:app --port 8000</code> in{" "}
        <code>alphahunter-ai/</code>.
      </div>
    </div>
  );
}
