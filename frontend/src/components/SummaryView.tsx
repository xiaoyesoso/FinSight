// SummaryView: renders the orchestrator's aggregated final report and the
// mandatory disclaimer.

import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import Disclaimer from './Disclaimer';
import { useI18n } from '../i18n/I18nContext';

interface Props {
  report: string;
  disclaimer?: string;
}

export default function SummaryView({ report, disclaimer }: Props) {
  const { t } = useI18n();
  if (!report) return null;
  return (
    <div className="bg-white border border-gray-200 rounded-lg p-5 shadow-sm">
      <h2 className="text-lg font-bold text-gray-800 mb-3">{t('summaryTitle')}</h2>
      <div className="markdown-body text-sm text-gray-700">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{report}</ReactMarkdown>
      </div>
      <div className="mt-4">
        <Disclaimer text={disclaimer} />
      </div>
    </div>
  );
}
