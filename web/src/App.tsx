import { useQuery } from "@tanstack/react-query";

import { fetchHealth } from "./lib/api";

export function App() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["health"],
    queryFn: fetchHealth,
    retry: false,
    refetchInterval: 10_000,
  });

  const backendStatus = isLoading ? "Checking..." : isError ? "Offline" : "Online";
  const serviceLabel = isLoading ? "Checking..." : isError ? "-" : (data?.service ?? "-");
  const versionLabel = isLoading ? "Checking..." : isError ? "-" : (data?.version ?? "-");

  return (
    <main className="app-shell">
      <section className="hero-panel">
        <p className="eyebrow">v0.1 transcription review loop</p>
        <h1>AgentClef</h1>
        <p className="lede">
          Audio is evidence. Score is state. The workbench will turn draft
          transcriptions into reviewable, confirmable score edits.
        </p>
      </section>

      <section className="status-grid" aria-label="service status">
        <div className="status-card">
          <span>Backend</span>
          <strong>{backendStatus}</strong>
        </div>
        <div className="status-card">
          <span>Service</span>
          <strong>{serviceLabel}</strong>
        </div>
        <div className="status-card">
          <span>Version</span>
          <strong>{versionLabel}</strong>
        </div>
      </section>
    </main>
  );
}
