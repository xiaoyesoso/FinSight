// SubAgentPanel: renders one SubAgent's live status, streamed markdown and
// charts. Shows a retry button on error.

import { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import type { AgentState, ToolCallEntry } from '../hooks/useSSEStream';
import { useI18n } from '../i18n/I18nContext';

interface Props {
  title: string;
  agentKey: string;
  state: AgentState;
  onRetry?: () => void;
}

// Extract a short summary from the tool input for quick display.
function summarizeToolInput(tool: string, input: Record<string, unknown>): string {
  if (tool === 'Read' || tool === 'Glob' || tool === 'Grep') {
    return String(input.file_path || input.pattern || input.path || '');
  }
  if (tool === 'Bash') {
    const cmd = String(input.command || '');
    return cmd.length > 80 ? cmd.slice(0, 80) + '…' : cmd;
  }
  if (tool === 'mcp__websearch__bochasearch') {
    return String(input.query || '');
  }
  if (tool === 'Write' || tool === 'Edit') {
    return String(input.file_path || '');
  }
  if (tool === 'Agent') {
    return String(input.prompt || input.description || '').slice(0, 80);
  }
  // Generic fallback: show first string value.
  const vals = Object.values(input).filter((v) => typeof v === 'string');
  return vals.length > 0 ? vals[0].slice(0, 80) : '';
}

// Tool icon map for visual distinction.
const TOOL_ICONS: Record<string, string> = {
  Read: '📄', Glob: '🔍', Grep: '🔎', Bash: '⚙️',
  Write: '✏️', Edit: '📝', Agent: '🤖',
  'mcp__websearch__bochasearch': '🌐',
};

function ToolCallItem({ entry, idx }: { entry: ToolCallEntry; idx: number }) {
  const [expanded, setExpanded] = useState(false);
  const icon = TOOL_ICONS[entry.tool] || '🔧';
  const summary = summarizeToolInput(entry.tool, entry.input);

  return (
    <div className="border-l-2 border-blue-200 pl-2 py-1">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full text-left flex items-center gap-1.5 text-xs hover:bg-gray-50 rounded px-1"
      >
        <span className="text-gray-400 font-mono text-[10px] w-6">{idx + 1}.</span>
        <span>{icon}</span>
        <span className="font-medium text-gray-700">{entry.tool}</span>
        {summary && <span className="text-gray-400 truncate flex-1">{summary}</span>}
        <span className="text-gray-300 font-mono text-[10px]">{entry.time}</span>
        <span className="text-gray-300 text-[10px]">{expanded ? '▲' : '▼'}</span>
      </button>
      {expanded && (
        <pre className="mt-1 ml-7 text-[11px] text-gray-600 bg-gray-50 rounded p-2 overflow-x-auto max-h-40 overflow-y-auto">
          {JSON.stringify(entry.input, null, 2)}
        </pre>
      )}
    </div>
  );
}

export default function SubAgentPanel({ title, state, onRetry }: Props) {
  const { t } = useI18n();
  const [showAllTools, setShowAllTools] = useState(false);

  const statusMap: Record<AgentState['status'], { label: string; cls: string }> = {
    idle: { label: t('statusIdle'), cls: 'bg-gray-200 text-gray-700' },
    running: { label: t('statusRunning'), cls: 'bg-blue-100 text-blue-700 animate-pulse' },
    done: { label: t('statusDone'), cls: 'bg-green-100 text-green-700' },
    error: { label: t('statusError'), cls: 'bg-red-100 text-red-700' },
  };
  const m = statusMap[state.status];

  // Show all or just the latest 8 tool calls.
  const visibleTools = showAllTools ? state.toolCalls : state.toolCalls.slice(-8);

  return (
    <div className="border border-gray-200 rounded-lg p-4 bg-white shadow-sm flex flex-col">
      <div className="flex items-center justify-between mb-2">
        <h3 className="font-semibold text-gray-800">{title}</h3>
        <div className="flex items-center gap-2">
          {state.toolCalls.length > 0 && (
            <span className="text-xs text-gray-400">{state.toolCalls.length} calls</span>
          )}
          <span className={`text-xs px-2 py-0.5 rounded ${m.cls}`}>{m.label}</span>
        </div>
      </div>

      {/* Tool call timeline */}
      {state.toolCalls.length > 0 && (
        <div className="mb-2 space-y-0.5">
          {visibleTools.map((entry, i) => (
            <ToolCallItem
              key={i}
              entry={entry}
              idx={showAllTools ? i : state.toolCalls.length - visibleTools.length + i}
            />
          ))}
          {state.toolCalls.length > 8 && (
            <button
              onClick={() => setShowAllTools(!showAllTools)}
              className="text-xs text-blue-500 hover:text-blue-700 ml-7"
            >
              {showAllTools
                ? `▲ ${t('collapse')}`
                : `▼ ${t('showAll')} (${state.toolCalls.length})`}
            </button>
          )}
        </div>
      )}

      {/* Streamed content: prefer the final result, fall back to partial text */}
      <div className="markdown-body text-sm text-gray-700 flex-1 overflow-y-auto max-h-96">
        {state.result ? (
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{state.result}</ReactMarkdown>
        ) : state.partial ? (
          <pre className="text-xs whitespace-pre-wrap text-gray-500">{state.partial}</pre>
        ) : (
          <p className="text-gray-400 text-xs">{t('waitingOutput')}</p>
        )}
      </div>

      {/* Error + retry */}
      {state.status === 'error' && (
        <div className="mt-2">
          <p className="text-red-600 text-xs">{state.error || t('execError')}</p>
          {onRetry && (
            <button
              onClick={onRetry}
              className="mt-1 text-xs text-blue-600 underline"
            >
              {t('retry')}
            </button>
          )}
        </div>
      )}
    </div>
  );
}
