// Composer: prompt input, PDF upload, SubAgent checkboxes, submit button.
// Calls POST /api/research (and /api/upload when a PDF is attached).

import { useState } from 'react';
import { startResearch, uploadPdf } from '../api/client';
import Disclaimer from './Disclaimer';
import LangToggle from './LangToggle';
import { useI18n } from '../i18n/I18nContext';

interface Props {
  onRun: (runId: string) => void;
}

// The three SubAgents the user can dispatch. Keys match the backend registry.
const AGENT_KEYS = ['financial-analyzer', 'industry_news_collector', 'a-share-risk-alert'] as const;

export default function Composer({ onRun }: Props) {
  const { t } = useI18n();
  const [prompt, setPrompt] = useState('');
  const [selectedAgents, setSelectedAgents] = useState<string[]>([
    'financial-analyzer',
    'industry_news_collector',
    'a-share-risk-alert',
  ]);
  const [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | undefined>();

  const agentLabels: Record<string, string> = {
    'financial-analyzer': t('financialAnalyzer'),
    industry_news_collector: t('industryNews'),
    'a-share-risk-alert': t('riskAlert'),
  };

  const toggleAgent = (id: string) => {
    setSelectedAgents((prev) =>
      prev.includes(id) ? prev.filter((a) => a !== id) : [...prev, id]
    );
  };

  const handleSubmit = async () => {
    if (!prompt.trim()) {
      setError(t('promptRequired'));
      return;
    }
    setLoading(true);
    setError(undefined);
    try {
      let fileId: string | undefined;
      if (file) {
        const up = await uploadPdf(file);
        fileId = up.file_id;
      }
      const res = await startResearch(prompt, fileId, selectedAgents);
      onRun(res.run_id);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-3xl mx-auto p-6 space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-800">{t('appTitle')}</h1>
        <LangToggle />
      </div>
      <p className="text-gray-500 text-sm">{t('appSubtitle')}</p>

      <textarea
        className="w-full border border-gray-300 rounded-lg p-3 h-32 focus:outline-none focus:ring-2 focus:ring-blue-500"
        placeholder={t('promptPlaceholder')}
        value={prompt}
        onChange={(e) => setPrompt(e.target.value)}
      />

      <div className="flex items-center gap-3">
        <label className="text-sm text-gray-600">{t('pdfLabel')}</label>
        <input
          type="file"
          accept=".pdf"
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          className="text-sm"
        />
        {file && <span className="text-xs text-gray-500">{file.name}</span>}
      </div>

      <div className="flex items-center gap-4">
        <span className="text-sm text-gray-600">{t('subAgentsLabel')}</span>
        {AGENT_KEYS.map((id) => (
          <label key={id} className="flex items-center gap-1 text-sm">
            <input
              type="checkbox"
              checked={selectedAgents.includes(id)}
              onChange={() => toggleAgent(id)}
            />
            {agentLabels[id]}
          </label>
        ))}
      </div>

      <button
        onClick={handleSubmit}
        disabled={loading}
        className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
      >
        {loading ? t('submitting') : t('submit')}
      </button>

      {error && <p className="text-red-600 text-sm">{error}</p>}

      <Disclaimer />
    </div>
  );
}
