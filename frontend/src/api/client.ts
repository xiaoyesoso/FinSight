// API client for the IIRAS backend.
// Wraps fetch calls for research submission and PDF upload, plus an
// EventSource factory for the SSE stream. All comments are in English.
//
// In development, VITE_API_BASE_URL should point to the backend
// (e.g. http://localhost:8000) so SSE streams bypass the Vite proxy,
// which buffers text/event-stream responses. In production, leave it
// empty to use same-origin relative paths.

const API_BASE = (import.meta.env.VITE_API_BASE_URL ?? '') + '/api';

export type SessionMode = 'fresh' | 'resume' | 'fork';

export interface ResearchRequest {
  prompt: string;
  file_id?: string;
  agents?: string[];
  // Required for resume / fork; ignored for fresh.
  session_id?: string;
  // Default "fresh".
  mode?: SessionMode;
  // Fork only; caps the branch's turn count (backend defaults to 5).
  max_turns?: number;
  // Optional OpenTelemetry attribution labels for per-user / per-tenant
  // cost rollups in Grafana. Ignored when telemetry is disabled.
  user_id?: string;
  tenant_id?: string;
}

export interface ResearchResponse {
  run_id: string;
  disclaimer: string;
}

export interface UploadResponse {
  file_id: string;
  path: string;
}

/** Submit a research task; returns the run_id used to open the SSE stream. */
export async function submitResearch(
  req: ResearchRequest
): Promise<ResearchResponse> {
  const res = await fetch(`${API_BASE}/research`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
  });
  if (!res.ok) {
    throw new Error(`research request failed: ${res.status} ${await res.text()}`);
  }
  return res.json();
}

/** Convenience wrapper: start a fresh research run. */
export async function startResearch(
  prompt: string,
  fileId?: string,
  agents?: string[]
): Promise<ResearchResponse> {
  return submitResearch({ prompt, file_id: fileId, agents, mode: 'fresh' });
}

/** Resume an existing session with a follow-up prompt (full context reuse). */
export async function resumeResearch(
  sessionId: string,
  prompt: string
): Promise<ResearchResponse> {
  return submitResearch({ prompt, session_id: sessionId, mode: 'resume' });
}

/** Fork a session into an isolated branch to explore alternative logic. */
export async function forkResearch(
  sessionId: string,
  prompt: string,
  maxTurns?: number
): Promise<ResearchResponse> {
  return submitResearch({
    prompt,
    session_id: sessionId,
    mode: 'fork',
    max_turns: maxTurns,
  });
}

/** Upload a PDF financial report; returns a file_id for the research request. */
export async function uploadPdf(file: File): Promise<UploadResponse> {
  const form = new FormData();
  form.append('file', file);
  const res = await fetch(`${API_BASE}/upload`, { method: 'POST', body: form });
  if (!res.ok) {
    throw new Error(`upload failed: ${res.status} ${await res.text()}`);
  }
  return res.json();
}

/** Open an EventSource for a run's typed SSE stream. */
export function streamResearch(runId: string): EventSource {
  return new EventSource(`${API_BASE}/research/${runId}/stream`);
}
