// React hook that subscribes to a research SSE stream and dispatches typed
// events to per-SubAgent panel state. All comments are in English.

import { useCallback, useEffect, useRef, useState } from 'react';
import { streamResearch } from '../api/client';

// Typed SSE event shapes (mirror the backend taxonomy).
// final_result carries session_id (+ parent_session_id for forks) so the
// SessionBar can offer resume / fork actions on the active thread.
export type SSEEvent =
  | { type: 'subagent_dispatch'; agent: string; data: { prompt: string } }
  | { type: 'partial_message'; agent: string; data: { text: string } }
  | { type: 'tool_call'; agent: string; data: { tool: string; input: Record<string, unknown> } }
  | { type: 'subagent_result'; agent: string; data: { markdown: string; disclaimer?: string } }
  | {
      type: 'final_result';
      agent: 'orchestrator';
      data: {
        report: string;
        disclaimer: string;
        session_id: string;
        parent_session_id?: string;
      };
    }
  | { type: 'error'; agent: string; data: { message: string } }
  | { type: 'done' };

export type AgentStatus = 'idle' | 'running' | 'done' | 'error';

export interface ToolCallEntry {
  tool: string;
  input: Record<string, unknown>;
  time: string;
}

export interface AgentState {
  status: AgentStatus;
  partial: string;
  result: string;
  toolCalls: ToolCallEntry[];
  error?: string;
}

export interface StreamState {
  agents: Record<string, AgentState>;
  finalReport: string;
  finalDisclaimer: string;
  // SDK session_id captured from final_result; null until the run finishes.
  sessionId: string | null;
  // Parent session for fork runs (A -> A'); null for fresh/resume.
  parentSessionId: string | null;
  done: boolean;
  error?: string;
}

const INITIAL_AGENTS: Record<string, AgentState> = {
  'financial-analyzer': { status: 'idle', partial: '', result: '', toolCalls: [] },
  industry_news_collector: { status: 'idle', partial: '', result: '', toolCalls: [] },
  'a-share-risk-alert': { status: 'idle', partial: '', result: '', toolCalls: [] },
};

// Helper to format a timestamp for the tool call timeline.
function now(): string {
  return new Date().toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

const INITIAL_STATE: StreamState = {
  agents: INITIAL_AGENTS,
  finalReport: '',
  finalDisclaimer: '',
  sessionId: null,
  parentSessionId: null,
  done: false,
};

// sessionStorage keys for persisting run state across page refreshes.
const STATE_KEY_PREFIX = 'finsight:state:';
const RUN_KEY = 'finsight:runId';
const MODE_KEY = 'finsight:runMode';

function loadSavedState(runId: string): StreamState | null {
  try {
    const raw = sessionStorage.getItem(STATE_KEY_PREFIX + runId);
    if (!raw) return null;
    return JSON.parse(raw) as StreamState;
  } catch {
    return null;
  }
}

function saveState(runId: string, state: StreamState) {
  try {
    sessionStorage.setItem(STATE_KEY_PREFIX + runId, JSON.stringify(state));
  } catch {
    // sessionStorage may be full; silently ignore.
  }
}

export function clearRunStorage() {
  const runId = sessionStorage.getItem(RUN_KEY);
  if (runId) sessionStorage.removeItem(STATE_KEY_PREFIX + runId);
  sessionStorage.removeItem(RUN_KEY);
  sessionStorage.removeItem(MODE_KEY);
}

export function loadRunId(): string | null {
  return sessionStorage.getItem(RUN_KEY);
}

export function loadRunMode(): SessionMode | null {
  return sessionStorage.getItem(MODE_KEY) as SessionMode | null;
}

export function saveRunInfo(runId: string, mode: SessionMode) {
  sessionStorage.setItem(RUN_KEY, runId);
  sessionStorage.setItem(MODE_KEY, mode);
}

// Import type here to avoid circular dependency with client.ts.
type SessionMode = 'fresh' | 'resume' | 'fork';

export function useSSEStream(runId: string | null) {
  // Restore from sessionStorage on first mount so a page refresh keeps results.
  const [state, setState] = useState<StreamState>(() => {
    if (runId) {
      const saved = loadSavedState(runId);
      if (saved) return saved;
    }
    return INITIAL_STATE;
  });
  const sourceRef = useRef<EventSource | null>(null);

  const close = useCallback(() => {
    sourceRef.current?.close();
    sourceRef.current = null;
  }, []);

  const reset = useCallback(() => {
    close();
    setState({
      agents: JSON.parse(JSON.stringify(INITIAL_AGENTS)),
      finalReport: '',
      finalDisclaimer: '',
      sessionId: null,
      parentSessionId: null,
      done: false,
    });
  }, [close]);

  useEffect(() => {
    if (!runId) return;

    // Try restoring saved state; only reset if no saved state exists.
    const saved = loadSavedState(runId);
    if (!saved) {
      setState({
        agents: JSON.parse(JSON.stringify(INITIAL_AGENTS)),
        finalReport: '',
        finalDisclaimer: '',
        sessionId: null,
        parentSessionId: null,
        done: false,
      });
    }

    // If the run already completed, don't reconnect SSE (stream is gone).
    if (saved?.done) return;

    const source = streamResearch(runId);
    sourceRef.current = source;

    const eventTypes = [
      'subagent_dispatch',
      'partial_message',
      'tool_call',
      'subagent_result',
      'final_result',
      'error',
      'done',
    ] as const;

    eventTypes.forEach((eventName) => {
      source.addEventListener(eventName, (e) => {
        // The `done` event may carry no data payload; handle gracefully.
        const raw = (e as MessageEvent).data;
        if (!raw) {
          if (eventName === 'done') setState((prev) => {
            const next = { ...prev, done: true };
            saveState(runId, next);
            return next;
          });
          return;
        }
        // The backend payload already includes `type`, `agent` and `data`.
        const payload = JSON.parse(raw) as SSEEvent;
        setState((prev) => {
          const next = reduceEvent(prev, payload);
          saveState(runId, next);
          return next;
        });
      });
    });

    source.onerror = () => {
      setState((prev) => {
        // If we already have results (from sessionStorage restore), keep them
        // instead of showing "stream connection lost".
        if (prev.done || prev.finalReport || Object.values(prev.agents).some(a => a.result)) {
          return { ...prev, done: true };
        }
        return { ...prev, error: 'stream connection lost', done: true };
      });
      // Save the final state so a subsequent refresh still shows results.
      setState((prev) => { saveState(runId, prev); return prev; });
    };

    return () => source.close();
  }, [runId]);

  return { state, reset, close };
}

/** Pure reducer that folds a single SSE event into the stream state. */
function reduceEvent(prev: StreamState, event: SSEEvent): StreamState {
  switch (event.type) {
    case 'subagent_dispatch': {
      const agent = event.agent;
      return {
        ...prev,
        agents: {
          ...prev.agents,
          [agent]: { ...agentOrEmpty(prev, agent), status: 'running' },
        },
      };
    }
    case 'partial_message': {
      const agent = event.agent;
      return {
        ...prev,
        agents: {
          ...prev.agents,
          [agent]: {
            ...agentOrEmpty(prev, agent),
            status: 'running',
            partial: (agentOrEmpty(prev, agent).partial || '') + event.data.text,
          },
        },
      };
    }
    case 'tool_call': {
      const agent = event.agent;
      const cur = agentOrEmpty(prev, agent);
      return {
        ...prev,
        agents: {
          ...prev.agents,
          [agent]: {
            ...cur,
            status: 'running',
            toolCalls: [...cur.toolCalls, { tool: event.data.tool, input: event.data.input, time: now() }],
          },
        },
      };
    }
    case 'subagent_result': {
      const agent = event.agent;
      return {
        ...prev,
        agents: {
          ...prev.agents,
          [agent]: {
            ...agentOrEmpty(prev, agent),
            status: 'done',
            result: event.data.markdown,
            partial: '',
          },
        },
      };
    }
    case 'final_result':
      return {
        ...prev,
        finalReport: event.data.report,
        finalDisclaimer: event.data.disclaimer,
        // Capture session lineage so the SessionBar can offer resume / fork.
        sessionId: event.data.session_id || null,
        parentSessionId: event.data.parent_session_id ?? null,
      };
    case 'error':
      return {
        ...prev,
        error: event.data.message,
        agents: markAllError(prev, event.agent),
        done: true,
      };
    case 'done':
      return { ...prev, done: true };
    default:
      return prev;
  }
}

/** Return the agent state or an empty placeholder for unknown agents. */
function agentOrEmpty(prev: StreamState, agent: string): AgentState {
  return (
    prev.agents[agent] ?? {
      status: 'idle',
      partial: '',
      result: '',
      toolCalls: [],
    }
  );
}

function markAllError(prev: StreamState, agent: string): Record<string, AgentState> {
  const next = { ...prev.agents };
  if (next[agent]) {
    next[agent] = { ...next[agent], status: 'error', error: prev.error };
  }
  return next;
}
