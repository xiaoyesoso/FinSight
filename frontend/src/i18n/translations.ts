// Lightweight i18n: translation dictionary for zh / en.

export type Lang = 'zh' | 'en';

export const translations = {
  zh: {
    // App
    appTitle: 'FinSight 全链路智能投研平台',
    appSubtitle: '多代理编排：财报分析 · 行业新闻 · 风险预警，并行执行，实时流式输出。',
    resultsTitle: '投研结果',
    newResearch: '← 新建研究',

    // Composer
    promptPlaceholder: '例如：请对燕京啤酒进行全面投研分析，包括财报、行业热点和风险评估。',
    pdfLabel: '财报 PDF（可选）：',
    subAgentsLabel: '子代理：',
    submit: '开始研究',
    submitting: '提交中...',
    promptRequired: '请输入研究提示词',

    // Agent labels
    financialAnalyzer: '📈 财报分析',
    industryNews: '📰 行业新闻',
    riskAlert: '⚠️ 风险预警',

    // Panel status
    statusIdle: '等待',
    statusRunning: '运行中',
    statusDone: '完成',
    statusError: '错误',
    waitingOutput: '等待子代理输出...',
    execError: '执行出错',
    retry: '重试',
    showAll: '展开全部',
    collapse: '收起',

    // Summary
    summaryTitle: '📊 综合研报',

    // Session bar
    sessionId: '会话 ID:',
    modeFresh: '新会话',
    modeResume: '续问',
    modeFork: '分叉',
    forkedFrom: '← 分叉自',
    resumeBtn: '继续追问',
    forkBtn: '分叉探索',
    resumePlaceholder: '输入追问内容，例如：请补充最新一周行业利空',
    forkPlaceholder: '输入分叉探索内容，例如：基于现有分析，额外用 DCF 模型重做估值',
    maxTurnsLabel: '最大轮次（可选，默认 5）：',
    submitBtn: '提交',
    cancelBtn: '取消',
    forkHint: '分叉会克隆当前会话为新分支，原会话不受影响，适合探索不同投资逻辑。',

    // Disclaimer
    disclaimer: '本工具仅供学习和研究使用，不构成投资建议。股市有风险，投资需谨慎。',

    // Language toggle
    switchToEn: 'EN',
    switchToZh: '中',
  },
  en: {
    appTitle: 'FinSight Full-Stack Investment Research',
    appSubtitle: 'Multi-agent orchestration: financial reports · industry news · risk alerts, running in parallel with real-time streaming.',
    resultsTitle: 'Research Results',
    newResearch: '← New Research',

    promptPlaceholder: 'e.g. Conduct a comprehensive investment research on Yanjing Beer, covering financials, industry trends, and risk assessment.',
    pdfLabel: 'Financial PDF (optional):',
    subAgentsLabel: 'SubAgents:',
    submit: 'Start Research',
    submitting: 'Submitting...',
    promptRequired: 'Please enter a research prompt',

    financialAnalyzer: '📈 Financial Report',
    industryNews: '📰 Industry News',
    riskAlert: '⚠️ Risk Alert',

    statusIdle: 'Idle',
    statusRunning: 'Running',
    statusDone: 'Done',
    statusError: 'Error',
    waitingOutput: 'Waiting for SubAgent output...',
    execError: 'Execution error',
    retry: 'Retry',
    showAll: 'Show all',
    collapse: 'Collapse',

    summaryTitle: '📊 Aggregated Report',

    sessionId: 'Session ID:',
    modeFresh: 'Fresh',
    modeResume: 'Resume',
    modeFork: 'Fork',
    forkedFrom: '← forked from',
    resumeBtn: 'Resume',
    forkBtn: 'Fork',
    resumePlaceholder: 'Enter follow-up, e.g. Add the latest weekly industry headwinds',
    forkPlaceholder: 'Enter fork exploration, e.g. Redo valuation with DCF model based on current analysis',
    maxTurnsLabel: 'Max turns (optional, default 5):',
    submitBtn: 'Submit',
    cancelBtn: 'Cancel',
    forkHint: 'Forking clones the current session into a new branch without affecting the original, ideal for exploring alternative investment logic.',

    disclaimer: 'This tool is for learning and research purposes only and does not constitute investment advice. Stock markets carry risks; invest with caution.',

    switchToEn: 'EN',
    switchToZh: '中',
  },
} as const;

export type TranslationKey = keyof typeof translations.zh;
