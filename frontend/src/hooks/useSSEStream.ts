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

export function useSSEStream(runId: string | null) {
  const [state, setState] = useState<StreamState>(INITIAL_STATE);
  const sourceRef = useRef<EventSource | null>(null);

  const close = useCallback(() => {
    sourceRef.current?.close();
    sourceRef.current = null;
  }, []);

  const reset = useCallback(() => {
    close();
    // Deep-clone the initial agent state so we don't mutate the constant.
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
    // Reset state for a fresh run.
    setState({
      agents: JSON.parse(JSON.stringify(INITIAL_AGENTS)),
      finalReport: '',
      finalDisclaimer: '',
      sessionId: null,
      parentSessionId: null,
      done: false,
    });

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
        // The backend payload already includes `type`, `agent` and `data`.
        const payload = JSON.parse((e as MessageEvent).data) as SSEEvent;
        setState((prev) => reduceEvent(prev, payload));
      });
    });

    source.onerror = () => {
      setState((prev) => ({ ...prev, error: 'stream connection lost', done: true }));
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
