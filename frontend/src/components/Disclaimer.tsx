// Persistent disclaimer banner shown in every view state.
// The disclaimer text mirrors the backend DISCLAIMER constant.

import { useI18n } from '../i18n/I18nContext';

interface Props {
  text?: string;
}

export default function Disclaimer({ text }: Props) {
  const { t } = useI18n();
  return (
    <div className="w-full bg-amber-50 border border-amber-300 text-amber-800 text-sm py-2 px-4 rounded">
      ⚠️ {text || t('disclaimer')}
    </div>
  );
}
