// Language toggle button: switches between zh and en.

import { useI18n } from '../i18n/I18nContext';

export default function LangToggle() {
  const { lang, setLang } = useI18n();
  return (
    <button
      onClick={() => setLang(lang === 'zh' ? 'en' : 'zh')}
      className="px-2.5 py-1 text-xs font-medium border border-gray-300 rounded hover:bg-gray-100 transition-colors"
      title={lang === 'zh' ? 'Switch to English' : '切换为中文'}
    >
      {lang === 'zh' ? 'EN' : '中'}
    </button>
  );
}
