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

// Strip CLI-internal metadata from displayed text (both partial and result).
const CLI_METADATA_RES = [
  /Async agent launched successfully\./g,
  /\(This tool result is internal metadata.*?into a user-facing reply\.\)/gs,
  /agentId: [0-9a-f]+ \(internal ID.*?to continue this agent\.\)/gs,
  /agentId: [0-9a-f]+ \(use SendMessage.*?\)/gs,
  /The agent is working in the background\..*?(?:completion notification|when it completes)\./gs,
  /Do not duplicate this agent's work.*?it is using\./gs,
  /output_file: \S+\.output/g,
  /Do NOT Read or tail this file.*?overflow your context\./gs,
  /If the user asks for progress.*?completion notification\./gs,
  /You know nothing about its results.*?in the meantime\./gs,
  /<usage>.*?<\/usage>/gs,
];

function cleanCliMetadata(text: string): string {
  let cleaned = text;
  for (const re of CLI_METADATA_RES) {
    cleaned = cleaned.replace(re, '');
  }
  // Collapse multiple spaces/newlines left by stripping.
  cleaned = cleaned.replace(/\n{3,}/g, '\n\n').replace(/[ \t]{2,}/g, ' ').trim();
  return cleaned;
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
  const vals = Object.values(input).filter((v) => typeof v === 'string');
  return vals.length > 0 ? vals[0].slice(0, 80) : '';
}

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

  const visibleTools = showAllTools ? state.toolCalls : state.toolCalls.slice(-8);

  // Clean CLI metadata from both result and partial text.
  const cleanResult = state.result ? cleanCliMetadata(state.result) : '';
  const cleanPartial = state.partial ? cleanCliMetadata(state.partial) : '';

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

      <div className="markdown-body text-sm text-gray-700 flex-1 overflow-y-auto max-h-96">
        {cleanResult ? (
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{cleanResult}</ReactMarkdown>
        ) : cleanPartial ? (
          <pre className="text-xs whitespace-pre-wrap text-gray-500">{cleanPartial}</pre>
        ) : state.status === 'done' ? (
          <p className="text-gray-400 text-xs italic">SubAgent completed.</p>
        ) : (
          <p className="text-gray-400 text-xs">{t('waitingOutput')}</p>
        )}
      </div>

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
