// FinSight workbench: composes a research task, then renders three live
// SubAgent panels and the aggregated summary as SSE events arrive.
// After a run finishes, the SessionBar offers resume and fork actions
// so analysts can continue or branch the session.

import { useState } from 'react';
import Composer from './components/Composer';
import SubAgentPanel from './components/SubAgentPanel';
import SummaryView from './components/SummaryView';
import SessionBar from './components/SessionBar';
import Disclaimer from './components/Disclaimer';
import LangToggle from './components/LangToggle';
import { useSSEStream, loadRunId, loadRunMode, saveRunInfo, clearRunStorage } from './hooks/useSSEStream';
import { resumeResearch, forkResearch, type SessionMode } from './api/client';
import { useI18n } from './i18n/I18nContext';
import type { TranslationKey } from './i18n/translations';

export default function App() {
  const { t } = useI18n();
  // Restore runId / runMode from sessionStorage so a page refresh keeps results.
  const [runId, setRunId] = useState<string | null>(() => loadRunId());
  const [runMode, setRunMode] = useState<SessionMode>(() => loadRunMode() ?? 'fresh');
  const { state, reset } = useSSEStream(runId);

  const panelTitles: Record<string, TranslationKey> = {
    'financial-analyzer': 'financialAnalyzer',
    industry_news_collector: 'industryNews',
    'a-share-risk-alert': 'riskAlert',
  };

  const handleRun = (id: string) => {
    setRunMode('fresh');
    setRunId(id);
    saveRunInfo(id, 'fresh');
  };

  const handleBack = () => {
    reset();
    setRunId(null);
    clearRunStorage();
  };

  const handleResume = async (prompt: string) => {
    if (!state.sessionId) return;
    try {
      const res = await resumeResearch(state.sessionId, prompt);
      setRunMode('resume');
      reset();
      setRunId(res.run_id);
      saveRunInfo(res.run_id, 'resume');
    } catch (e) {
      console.error('resume failed', e);
    }
  };

  const handleFork = async (prompt: string, maxTurns?: number) => {
    if (!state.sessionId) return;
    try {
      const res = await forkResearch(state.sessionId, prompt, maxTurns);
      setRunMode('fork');
      reset();
      setRunId(res.run_id);
      saveRunInfo(res.run_id, 'fork');
    } catch (e) {
      console.error('fork failed', e);
    }
  };

  if (!runId) {
    return <Composer onRun={handleRun} />;
  }

  return (
    <div className="min-h-screen bg-gray-50 p-6 space-y-4">
      <div className="flex items-center justify-between max-w-7xl mx-auto">
        <h1 className="text-xl font-bold text-gray-800">{t('resultsTitle')}</h1>
        <div className="flex items-center gap-3">
          <LangToggle />
          <button
            onClick={handleBack}
            className="px-4 py-1.5 text-sm bg-gray-200 rounded hover:bg-gray-300"
          >
            {t('newResearch')}
          </button>
        </div>
      </div>

      <div className="max-w-7xl mx-auto space-y-4">
        <SessionBar
          sessionId={state.sessionId}
          parentSessionId={state.parentSessionId}
          mode={runMode}
          onResume={handleResume}
          onFork={handleFork}
        />

        <SummaryView report={state.finalReport} disclaimer={state.finalDisclaimer} />

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {Object.entries(panelTitles).map(([key, titleKey]) => (
            <SubAgentPanel
              key={key}
              title={t(titleKey)}
              agentKey={key}
              state={
                state.agents[key] ?? {
                  status: 'idle',
                  partial: '',
                  result: '',
                  toolCalls: [],
                }
              }
              onRetry={handleBack}
            />
          ))}
        </div>

        {state.error && (
          <p className="text-red-600 text-sm text-center">{state.error}</p>
        )}

        <div className="max-w-7xl mx-auto">
          <Disclaimer />
        </div>
      </div>
    </div>
  );
}
