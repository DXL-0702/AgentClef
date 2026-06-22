export type HealthResponse = {
  status: string;
  service: string;
  version: string;
  environment: string;
  postgres_configured: boolean;
  redis_configured: boolean;
  file_storage_configured: boolean;
  upload_limits: {
    max_mb: number;
    max_seconds: number;
  };
  llm_provider: string;
};

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";
const HEALTH_TIMEOUT_MS = 7_500;

export async function fetchHealth(): Promise<HealthResponse> {
  const controller = new AbortController();
  const timeoutId = window.setTimeout(() => {
    controller.abort();
  }, HEALTH_TIMEOUT_MS);

  try {
    const response = await fetch(`${API_BASE_URL}/health`, {
      signal: controller.signal,
    });
    if (!response.ok) {
      throw new Error(`Health check failed: ${response.status}`);
    }
    return response.json() as Promise<HealthResponse>;
  } finally {
    window.clearTimeout(timeoutId);
  }
}
