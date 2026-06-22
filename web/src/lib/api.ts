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

export async function fetchHealth(): Promise<HealthResponse> {
  const response = await fetch(`${API_BASE_URL}/health`);
  if (!response.ok) {
    throw new Error(`Health check failed: ${response.status}`);
  }
  return response.json() as Promise<HealthResponse>;
}
