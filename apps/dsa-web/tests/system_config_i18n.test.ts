import { describe, expect, it } from 'vitest';
import { UI_TEXT } from '../src/i18n/uiText';
import { getSettingsHelpContent } from '../src/locales/settingsHelp';
import { getFieldDescriptionZh, getFieldOptionLabelZh, getFieldTitleZh } from '../src/utils/systemConfigI18n';

const requiredLocalizedKeys = [
  'TICKFLOW_API_KEY',
  'TICKFLOW_PRIORITY',
  'TICKFLOW_KLINE_ADJUST',
  'TICKFLOW_BATCH_DAILY_ENABLED',
  'TICKFLOW_BATCH_SIZE',
  'STOCK_INDEX_REMOTE_UPDATE_ENABLED',
  'SEARXNG_BASE_URLS',
  'ENABLE_REALTIME_QUOTE',
  'ENABLE_CHIP_DISTRIBUTION',
  'PYTDX_HOST',
  'PYTDX_PORT',
  'PYTDX_SERVERS',
  'BIAS_THRESHOLD',
  'GENERATION_BACKEND',
  'GENERATION_FALLBACK_BACKEND',
  'GENERATION_BACKEND_TIMEOUT_SECONDS',
  'GENERATION_BACKEND_MAX_OUTPUT_BYTES',
  'GENERATION_BACKEND_MAX_CONCURRENCY',
  'LOCAL_CLI_BACKEND_MAX_CONCURRENCY',
  'LLM_PROMPT_CACHE_TELEMETRY_ENABLED',
  'LLM_PROMPT_CACHE_HINTS_ENABLED',
  'LLM_PROMPT_CACHE_DIAGNOSTICS_LEVEL',
  'LLM_USAGE_HMAC_SECRET',
  'LLM_USAGE_HMAC_KEY_VERSION',
  'TELEGRAM_BOT_TOKEN',
  'TELEGRAM_CHAT_ID',
  'TELEGRAM_MESSAGE_THREAD_ID',
  'FEISHU_STREAM_ENABLED',
  'DINGTALK_STREAM_ENABLED',
  'EMAIL_SENDER',
  'EMAIL_PASSWORD',
  'EMAIL_RECEIVERS',
  'DISCORD_WEBHOOK_URL',
  'DISCORD_BOT_TOKEN',
  'DISCORD_MAIN_CHANNEL_ID',
  'DISCORD_INTERACTIONS_PUBLIC_KEY',
  'SLACK_BOT_TOKEN',
  'SLACK_CHANNEL_ID',
  'SLACK_WEBHOOK_URL',
  'PUSHPLUS_TOPIC',
  'PUSHOVER_USER_KEY',
  'PUSHOVER_API_TOKEN',
  'SERVERCHAN3_SENDKEY',
  'ASTRBOT_URL',
  'ASTRBOT_TOKEN',
  'CUSTOM_WEBHOOK_BEARER_TOKEN',
  'WEBHOOK_VERIFY_SSL',
  'SINGLE_STOCK_NOTIFY',
  'REPORT_TYPE',
  'REPORT_LANGUAGE',
  'REPORT_TEMPLATES_DIR',
  'REPORT_INTEGRITY_ENABLED',
  'REPORT_RENDERER_ENABLED',
  'REPORT_INTEGRITY_RETRY',
  'REPORT_HISTORY_COMPARE_N',
  'MERGE_EMAIL_NOTIFICATION',
  'NOTIFICATION_REPORT_CHANNELS',
  'NOTIFICATION_ALERT_CHANNELS',
  'NOTIFICATION_SYSTEM_ERROR_CHANNELS',
  'NOTIFICATION_DEDUP_TTL_SECONDS',
  'NOTIFICATION_COOLDOWN_SECONDS',
  'NOTIFICATION_QUIET_HOURS',
  'NOTIFICATION_TIMEZONE',
  'NOTIFICATION_MIN_SEVERITY',
  'NOTIFICATION_DAILY_DIGEST_ENABLED',
  'SCHEDULE_ENABLED',
  'SCHEDULE_RUN_IMMEDIATELY',
  'TRADING_DAY_CHECK_ENABLED',
  'WEBUI_HOST',
  'LOG_DIR',
  'WEBUI_ENABLED',
  'WEBUI_AUTO_BUILD',
  'ADMIN_AUTH_ENABLED',
  'TRUST_X_FORWARDED_FOR',
  'RUN_IMMEDIATELY',
  'MARKET_REVIEW_ENABLED',
  'DAILY_MARKET_CONTEXT_ENABLED',
  'MARKET_REVIEW_REGION',
  'ANALYSIS_DELAY',
  'SAVE_CONTEXT_SNAPSHOT',
  'DEBUG',
  'AGENT_GENERATION_BACKEND',
  'AGENT_NL_ROUTING',
  'AGENT_DEEP_RESEARCH_BUDGET',
  'AGENT_DEEP_RESEARCH_TIMEOUT',
  'AGENT_EVENT_MONITOR_ENABLED',
  'AGENT_EVENT_MONITOR_INTERVAL_MINUTES',
  'AGENT_EVENT_ALERT_RULES_JSON',
] as const;

describe('systemConfigI18n required key coverage', () => {
  it('provides zh title and description mapping for known missing keys', () => {
    requiredLocalizedKeys.forEach((key) => {
      expect(getFieldTitleZh(key, key)).not.toBe(key);
      expect(getFieldDescriptionZh(key, 'schema fallback description')).not.toBe('schema fallback description');
    });
  });

  it('uses a Chinese primary title for SearXNG base URLs', () => {
    const title = getFieldTitleZh('SEARXNG_BASE_URLS', 'SEARXNG_BASE_URLS');

    expect(title).toBe('SearXNG \u81ea\u5efa\u5b9e\u4f8b\u5730\u5740');
    expect(title).not.toBe('SearXNG Base URLs');
  });

  it('documents LLM usage HMAC privacy boundaries', () => {
    const zh = getSettingsHelpContent('settings.ai_model.LLM_USAGE_HMAC_SECRET', undefined, 'zh-CN');
    const en = getSettingsHelpContent('settings.ai_model.LLM_USAGE_HMAC_SECRET', undefined, 'en');

    expect(zh?.summary).toContain('HMAC');
    expect(zh?.notes?.join(' ')).toContain('\u4e0d\u8981');
    expect(en?.summary).toContain('HMAC');
    expect(en?.notes?.join(' ')).toContain('Do not');
  });
});

describe('systemConfigI18n option label localization', () => {
  const realSelectOptionCases = [
    ['NEWS_STRATEGY_PROFILE', 'ultra_short', undefined, '\u8d85\u77ed\u7ebf（1\u5929）'],
    ['NEWS_STRATEGY_PROFILE', 'short', undefined, '\u77ed\u671f（3\u5929）'],
    ['NEWS_STRATEGY_PROFILE', 'medium', undefined, '\u4e2d\u671f（7\u5929）'],
    ['NEWS_STRATEGY_PROFILE', 'long', undefined, '\u957f\u671f（30\u5929）'],
    ['REPORT_TYPE', 'simple', undefined, '\u7b80\u6d01'],
    ['REPORT_TYPE', 'full', undefined, '\u5b8c\u6574'],
    ['REPORT_TYPE', 'brief', undefined, '\u7b80\u62a5'],
    ['REPORT_LANGUAGE', 'zh', 'Chinese', '\u4e2d\u6587'],
    ['REPORT_LANGUAGE', 'en', 'English', '\u82f1\u6587'],
    ['NOTIFICATION_MIN_SEVERITY', '', 'Not set', '\u672a\u8bbe\u7f6e'],
    ['NOTIFICATION_MIN_SEVERITY', 'info', 'info', '\u4fe1\u606f'],
    ['NOTIFICATION_MIN_SEVERITY', 'warning', 'warning', '\u8b66\u544a'],
    ['NOTIFICATION_MIN_SEVERITY', 'error', 'error', '\u9519\u8bef'],
    ['NOTIFICATION_MIN_SEVERITY', 'critical', 'critical', '\u4e25\u91cd'],
    ['LOG_LEVEL', 'DEBUG', undefined, '\u8c03\u8bd5'],
    ['LOG_LEVEL', 'INFO', undefined, '\u4fe1\u606f'],
    ['LOG_LEVEL', 'WARNING', undefined, '\u8b66\u544a'],
    ['LOG_LEVEL', 'ERROR', undefined, '\u9519\u8bef'],
    ['LOG_LEVEL', 'CRITICAL', undefined, '\u4e25\u91cd'],
    ['LLM_PROMPT_CACHE_DIAGNOSTICS_LEVEL', 'off', undefined, '\u5173\u95ed'],
    ['LLM_PROMPT_CACHE_DIAGNOSTICS_LEVEL', 'basic', undefined, '\u57fa\u7840'],
    ['LLM_PROMPT_CACHE_DIAGNOSTICS_LEVEL', 'debug', undefined, '\u8c03\u8bd5'],
    ['MARKET_REVIEW_COLOR_SCHEME', 'green_up', 'Green Up / Red Down', '\u7eff\u6da8\u7ea2\u8dcc'],
    ['MARKET_REVIEW_COLOR_SCHEME', 'red_up', 'Red Up / Green Down', '\u7ea2\u6da8\u7eff\u8dcc'],
    ['GENERATION_BACKEND', 'litellm', undefined, '\u9ed8\u8ba4\u6a21\u578b\u914d\u7f6e'],
    ['GENERATION_FALLBACK_BACKEND', 'litellm', undefined, '\u9ed8\u8ba4\u6a21\u578b\u914d\u7f6e'],
    ['AGENT_GENERATION_BACKEND', 'auto', 'Auto', '\u81ea\u52a8'],
    ['AGENT_GENERATION_BACKEND', 'litellm', undefined, '\u9ed8\u8ba4\u6a21\u578b\u914d\u7f6e'],
    ['AGENT_ARCH', 'single', 'Single Agent', '\u5355 Agent'],
    ['AGENT_ARCH', 'multi', 'Multi Agent (Orchestrator)', '\u591a Agent（\u7f16\u6392）'],
    ['AGENT_ORCHESTRATOR_MODE', 'quick', 'Quick', '\u5feb\u901f'],
    ['AGENT_ORCHESTRATOR_MODE', 'standard', 'Standard', '\u6807\u51c6'],
    ['AGENT_ORCHESTRATOR_MODE', 'full', 'Full', '\u5b8c\u6574'],
    ['AGENT_ORCHESTRATOR_MODE', 'specialist', 'Specialist', '\u4e13\u5bb6'],
    ['AGENT_SKILL_ROUTING', 'auto', 'Auto (Regime-based)', '\u81ea\u52a8（\u6309\u5e02\u573a\u72b6\u6001）'],
    ['AGENT_SKILL_ROUTING', 'manual', 'Manual (Use AGENT_SKILLS)', '\u624b\u52a8（\u4f7f\u7528 AGENT_SKILLS）'],
  ] as const;

  it('localizes all select options currently exposed by system config schema', () => {
    realSelectOptionCases.forEach(([key, value, fallbackLabel, expectedLabel]) => {
      const label = getFieldOptionLabelZh(key, value, fallbackLabel);

      expect(label).toBe(expectedLabel);
      expect(label).not.toBe(value);
      if (fallbackLabel) {
        expect(label).not.toBe(fallbackLabel);
      }
    });
  });

  it('treats free-text config keys as passthrough for option labels', () => {
    expect(getFieldOptionLabelZh('MARKET_REVIEW_REGION', 'cn')).toBe('cn');
    expect(getFieldOptionLabelZh('MARKET_REVIEW_REGION', 'cn,us,jp,kr')).toBe('cn,us,jp,kr');
  });
});

describe('SAVE_CONTEXT_SNAPSHOT settings help contract', () => {
  it('describes the persistence boundary without implying old records are changed', () => {
    const help = getSettingsHelpContent('settings.system.SAVE_CONTEXT_SNAPSHOT', undefined, 'zh-CN');
    const text = [
      help?.summary,
      help?.usage,
      ...(help?.valueNotes ?? []),
      ...(help?.impact ?? []),
      ...(help?.notes ?? []),
    ].join('\n');

    expect(text).toContain('\u65b0\u5386\u53f2\u8bb0\u5f55');
    expect(text).toContain('\u4e0d\u5173\u95ed\u5f53\u6b21 AnalysisContextPack \u6784\u5efa');
    expect(text).toContain('\u4e0d\u5173\u95ed LLM Prompt');
    expect(text).not.toContain('\u65e7\u8bb0\u5f55');
  });
});

describe('generation backend settings help contract', () => {
  it('uses user-facing generation channel copy instead of implementation terms', () => {
    const zhInlineText = [
      getFieldTitleZh('GENERATION_BACKEND', ''),
      getFieldDescriptionZh('GENERATION_BACKEND', ''),
      getFieldTitleZh('GENERATION_FALLBACK_BACKEND', ''),
      getFieldDescriptionZh('GENERATION_FALLBACK_BACKEND', ''),
      getFieldTitleZh('GENERATION_BACKEND_TIMEOUT_SECONDS', ''),
      getFieldDescriptionZh('GENERATION_BACKEND_TIMEOUT_SECONDS', ''),
      getFieldTitleZh('GENERATION_BACKEND_MAX_OUTPUT_BYTES', ''),
      getFieldDescriptionZh('GENERATION_BACKEND_MAX_OUTPUT_BYTES', ''),
      getFieldTitleZh('GENERATION_BACKEND_MAX_CONCURRENCY', ''),
      getFieldDescriptionZh('GENERATION_BACKEND_MAX_CONCURRENCY', ''),
      getFieldTitleZh('LOCAL_CLI_BACKEND_MAX_CONCURRENCY', ''),
      getFieldDescriptionZh('LOCAL_CLI_BACKEND_MAX_CONCURRENCY', ''),
      getFieldTitleZh('AGENT_GENERATION_BACKEND', ''),
      getFieldDescriptionZh('AGENT_GENERATION_BACKEND', ''),
    ].join('\n');
    const zhBackend = getSettingsHelpContent('settings.ai_model.GENERATION_BACKEND', undefined, 'zh-CN');
    const enBackend = getSettingsHelpContent('settings.ai_model.GENERATION_BACKEND', undefined, 'en');
    const zhFallback = getSettingsHelpContent('settings.ai_model.GENERATION_FALLBACK_BACKEND', undefined, 'zh-CN');
    const enFallback = getSettingsHelpContent('settings.ai_model.GENERATION_FALLBACK_BACKEND', undefined, 'en');
    const zhAgent = getSettingsHelpContent('settings.agent.AGENT_GENERATION_BACKEND', undefined, 'zh-CN');
    const enAgent = getSettingsHelpContent('settings.agent.AGENT_GENERATION_BACKEND', undefined, 'en');
    const zhText = [
      zhBackend?.title,
      zhBackend?.summary,
      zhBackend?.usage,
      ...(zhBackend?.valueNotes ?? []),
      ...(zhBackend?.impact ?? []),
      ...(zhBackend?.notes ?? []),
      zhFallback?.title,
      zhFallback?.summary,
      zhFallback?.usage,
      ...(zhFallback?.valueNotes ?? []),
      ...(zhFallback?.impact ?? []),
      ...(zhFallback?.notes ?? []),
      zhAgent?.title,
      zhAgent?.summary,
      zhAgent?.usage,
      ...(zhAgent?.valueNotes ?? []),
      ...(zhAgent?.impact ?? []),
      ...(zhAgent?.notes ?? []),
    ].join('\n');
    const enText = [
      enBackend?.title,
      enBackend?.summary,
      enBackend?.usage,
      ...(enBackend?.valueNotes ?? []),
      ...(enBackend?.impact ?? []),
      ...(enBackend?.notes ?? []),
      enFallback?.title,
      enFallback?.summary,
      enFallback?.usage,
      ...(enFallback?.valueNotes ?? []),
      ...(enFallback?.impact ?? []),
      ...(enFallback?.notes ?? []),
      enAgent?.title,
      enAgent?.summary,
      enAgent?.usage,
      ...(enAgent?.valueNotes ?? []),
      ...(enAgent?.impact ?? []),
      ...(enAgent?.notes ?? []),
    ].join('\n');

    expect(zhBackend?.title).toBe('\u5206\u6790\u751f\u6210\u65b9\u5f0f');
    expect(zhFallback?.title).toBe('\u5907\u7528\u751f\u6210\u65b9\u5f0f');
    expect(zhAgent?.title).toBe('\u95ee\u80a1\u751f\u6210\u65b9\u5f0f');
    expect(getFieldTitleZh('GENERATION_BACKEND_TIMEOUT_SECONDS', '')).toBe('\u751f\u6210\u8d85\u65f6（\u79d2）');
    expect(getFieldTitleZh('GENERATION_BACKEND_MAX_OUTPUT_BYTES', '')).toBe('\u6700\u5927\u8f93\u51fa\u5927\u5c0f（\u5b57\u8282）');
    expect(getFieldTitleZh('GENERATION_BACKEND_MAX_CONCURRENCY', '')).toBe('\u6a21\u578b\u751f\u6210\u6700\u5927\u5e76\u53d1');
    expect(getFieldTitleZh('LOCAL_CLI_BACKEND_MAX_CONCURRENCY', '')).toBe('\u672c\u5730\u547d\u4ee4\u884c\u6700\u5927\u5e76\u53d1');
    expect(zhBackend?.showFieldKey).toBe(false);
    expect(zhFallback?.showFieldKey).toBe(false);
    expect(zhAgent?.showFieldKey).toBe(false);
    expect(zhBackend?.examples).toEqual([]);
    expect(zhFallback?.examples).toEqual([]);
    expect(zhAgent?.examples).toEqual([]);
    expect(zhInlineText).toContain('\u4e2a\u80a1\u5206\u6790');
    expect(zhInlineText).toContain('\u95ee\u80a1\u52a9\u624b');
    expect(zhInlineText).toContain('\u5f53\u524d\u53ef\u7528\u7684\u65b9\u5f0f');
    expect(zhInlineText).not.toContain('\u6cbf\u7528\u5f53\u524d\u53ef\u7528\u7684\u6a21\u578b\u901a\u9053');
    expect(zhText).toContain('\u4e2a\u80a1\u5206\u6790');
    expect(zhText).toContain('\u5927\u76d8\u590d\u76d8');
    expect(zhText).toContain('\u81ea\u52a8');
    expect(zhBackend?.usage).toContain('\u9ed8\u8ba4\u6a21\u578b\u914d\u7f6e');
    expect(zhFallback?.usage).toContain('\u9ed8\u8ba4\u6a21\u578b\u914d\u7f6e');
    expect(zhAgent?.usage).toContain('\u5f53\u524d\u53ef\u7528\u7684\u65b9\u5f0f');
    expect(zhAgent?.valueNotes).toContain('\u5982\u679c\u4e0d\u786e\u5b9a，\u9009\u62e9“\u81ea\u52a8”\u5373\u53ef。');
    expect(zhText).not.toContain('\u4f18\u5148\u9009\u62e9\u5f53\u524d\u53ef\u7528');
    expect(zhText).not.toContain('unsupported_tool_calling');
    expect(zhText).not.toContain('run_agent_loop');
    [
      'Backend',
      'backend',
      'backend-level',
      'generation backend',
      'self fallback',
      'stdout',
      'stderr',
      'contract',
      'MAX_WORKERS',
      'Router',
      'diagnostics',
      'executable',
      'coding-agent',
      'experimental/limited',
      'fail-fast',
      'LiteLLM',
    ].forEach((term) => {
      expect(zhInlineText).not.toContain(term);
      expect(zhText).not.toContain(term);
    });

    expect(enBackend?.title).toBe('Analysis Generation Method');
    expect(enFallback?.title).toBe('Fallback Generation Method');
    expect(enAgent?.title).toBe('Ask-Stock Generation Method');
    expect(enText).toContain('stock analysis');
    expect(enText).toContain('market reviews');
    expect(enText).toContain('Auto');
    expect(enBackend?.usage).toContain('Default model settings');
    expect(enFallback?.usage).toContain('Default model settings');
    expect(enAgent?.usage).toContain('currently available method');
    expect(enAgent?.valueNotes).toContain('If you are unsure, choose Auto.');
    expect(enBackend?.notes?.join('\n')).toContain('Default model settings continue');
    expect(enBackend?.notes?.join('\n')).not.toContain('Advanced note');
    expect(enBackend?.notes?.join('\n')).not.toContain('LiteLLM');
    expect(enText).not.toContain('current available model channel');
    expect(enText).not.toContain('unsupported_tool_calling');
    expect(enText).not.toContain('run_agent_loop');
  });
});

describe('generation backend status panel i18n contract', () => {
  it('keeps the new status panel copy localized in both UI languages', () => {
    expect(UI_TEXT.zh['settings.generationBackendStatus']).toBe('\u751f\u6210\u540e\u7aef\u72b6\u6001');
    expect(UI_TEXT.zh['settings.generationBackendSmokeTest']).toBe('JSON \u5192\u70df\u6d4b\u8bd5');
    expect(UI_TEXT.zh['settings.generationBackendPrimary']).toBe('\u4e3b\u540e\u7aef');
    expect(UI_TEXT.zh['settings.generationBackendFallback']).toBe('\u5907\u7528\u540e\u7aef');
    expect(UI_TEXT.zh['settings.generationBackendGenerationOnly']).toBe('\u4ec5\u751f\u6210');
    expect(UI_TEXT.zh['settings.generationBackendStatusDescription']).toContain('\u5feb\u901f\u68c0\u67e5');
    expect(UI_TEXT.zh['settings.generationBackendStatusDescription']).not.toContain('cheap check');
    expect(UI_TEXT.zh['settings.generationBackendSmokePassed']).not.toContain('Smoke test');

    expect(UI_TEXT.en['settings.generationBackendStatus']).toBe('Generation backend status');
    expect(UI_TEXT.en['settings.generationBackendSmokeTest']).toBe('JSON smoke test');
    expect(UI_TEXT.en['settings.generationBackendPrimary']).toBe('Primary backend');
    expect(UI_TEXT.en['settings.generationBackendFallback']).toBe('Fallback backend');
    expect(UI_TEXT.en['settings.generationBackendGenerationOnly']).toBe('Generation only');
  });
});

describe('decision signal settings guard', () => {
  it('does not add placeholder DecisionSignal setting translations without a real schema field', () => {
    const placeholderKeys = [
      'DECISION_SIGNAL_ENABLED',
      'DECISION_SIGNALS_ENABLED',
      'DECISION_SIGNAL_WRITE_ENABLED',
      'DECISION_SIGNAL_EXTRACT_ENABLED',
    ];

    placeholderKeys.forEach((key) => {
      expect(getFieldTitleZh(key, key)).toBe(key);
      expect(getFieldDescriptionZh(key, 'schema fallback description')).toBe('schema fallback description');
    });
  });
});
