// SessionBar: shows the active SDK session_id, its mode badge (fresh/resume/
// fork) and parent lineage for forks. Hosts the resume and fork actions
// that open an inline follow-up prompt.

import { useState } from 'react';
import type { SessionMode } from '../api/client';
import { useI18n } from '../i18n/I18nContext';

interface Props {
  sessionId: string | null;
  parentSessionId: string | null;
  mode: SessionMode;
  onResume: (prompt: string) => void;
  onFork: (prompt: string, maxTurns?: number) => void;
}

function shortId(sid: string | null): string {
  if (!sid) return '-';
  return sid.length > 12 ? `${sid.slice(0, 8)}…` : sid;
}

export default function SessionBar({
  sessionId,
  parentSessionId,
  mode,
  onResume,
  onFork,
}: Props) {
  const { t } = useI18n();
  const [open, setOpen] = useState<null | 'resume' | 'fork'>(null);
  const [prompt, setPrompt] = useState('');
  const [maxTurns, setMaxTurns] = useState<number | ''>('');

  if (!sessionId) return null;

  const submit = () => {
    const text = prompt.trim();
    if (!text) return;
    if (open === 'resume') {
      onResume(text);
    } else if (open === 'fork') {
      const mt = typeof maxTurns === 'number' ? maxTurns : undefined;
      onFork(text, mt);
    }
    setPrompt('');
    setMaxTurns('');
    setOpen(null);
  };

  const modeLabel: Record<SessionMode, { text: string; cls: string }> = {
    fresh: { text: t('modeFresh'), cls: 'bg-blue-100 text-blue-700' },
    resume: { text: t('modeResume'), cls: 'bg-green-100 text-green-700' },
    fork: { text: t('modeFork'), cls: 'bg-purple-100 text-purple-700' },
  };
  const badge = modeLabel[mode];

  return (
    <div className="bg-white border border-gray-200 rounded-lg p-4 shadow-sm">
      <div className="flex flex-wrap items-center gap-3">
        <span className="text-sm text-gray-500">{t('sessionId')}</span>
        <code className="text-sm font-mono text-gray-800">{shortId(sessionId)}</code>
        <span className={`text-xs px-2 py-0.5 rounded ${badge.cls}`}>
          {badge.text}
        </span>

        {parentSessionId && (
          <span className="text-xs text-gray-500">
            {t('forkedFrom')} <code className="font-mono">{shortId(parentSessionId)}</code>
          </span>
        )}

        <div className="ml-auto flex gap-2">
          <button
            onClick={() => setOpen(open === 'resume' ? null : 'resume')}
            className="px-3 py-1 text-sm bg-green-600 text-white rounded hover:bg-green-700"
          >
            {t('resumeBtn')}
          </button>
          <button
            onClick={() => setOpen(open === 'fork' ? null : 'fork')}
            className="px-3 py-1 text-sm bg-purple-600 text-white rounded hover:bg-purple-700"
          >
            {t('forkBtn')}
          </button>
        </div>
      </div>

      {open && (
        <div className="mt-3 flex flex-col gap-2">
          <textarea
            className="w-full border border-gray-300 rounded-lg p-2 h-20 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            placeholder={open === 'resume' ? t('resumePlaceholder') : t('forkPlaceholder')}
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
          />
          {open === 'fork' && (
            <div className="flex items-center gap-2 text-sm text-gray-600">
              <label>{t('maxTurnsLabel')}</label>
              <input
                type="number"
                min={1}
                max={20}
                value={maxTurns}
                onChange={(e) =>
                  setMaxTurns(e.target.value === '' ? '' : Number(e.target.value))
                }
                className="w-20 border border-gray-300 rounded px-2 py-0.5"
              />
            </div>
          )}
          <div className="flex gap-2">
            <button
              onClick={submit}
              disabled={!prompt.trim()}
              className="px-4 py-1.5 text-sm bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
            >
              {t('submitBtn')}
            </button>
            <button
              onClick={() => setOpen(null)}
              className="px-4 py-1.5 text-sm bg-gray-200 rounded hover:bg-gray-300"
            >
              {t('cancelBtn')}
            </button>
          </div>
          {open === 'fork' && (
            <p className="text-xs text-gray-400">{t('forkHint')}</p>
          )}
        </div>
      )}
    </div>
  );
}
