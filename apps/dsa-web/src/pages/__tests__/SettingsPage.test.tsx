import type React from 'react';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { resolveWebBuildInfo } from '../../utils/constants';
import type { SetupStatusResponse } from '../../types/systemConfig';
import SettingsPage from '../SettingsPage';

const {
  analyzeAsync,
  exportEnv,
  getSchedulerStatus,
  getSetupStatus,
  importEnv,
  runSchedulerNow,
  updateSystemConfig,
  alphasiftEnable,
  alphasiftInstall,
  notifyAlphaSiftConfigChanged,
  notifySystemConfigChanged,
  desktopCheckForUpdates,
  desktopGetUpdateState,
  desktopInstallDownloadedUpdate,
  desktopOnUpdateStateChange,
  desktopOpenReleasePage,
  load,
  clearToast,
  setActiveCategory,
  save,
  resetDraft,
  setDraftValue,
  applyPartialUpdate,
  getChangedItems,
  refreshAfterExternalSave,
  refreshStatus,
  settingsPanelErrorBoundary,
  useAuthMock,
  useSystemConfigMock,
  webBuildInfoMock,
} = vi.hoisted(() => ({
  analyzeAsync: vi.fn(),
  exportEnv: vi.fn(),
  getSchedulerStatus: vi.fn(),
  getSetupStatus: vi.fn(),
  importEnv: vi.fn(),
  runSchedulerNow: vi.fn(),
  updateSystemConfig: vi.fn(),
  alphasiftEnable: vi.fn(),
  alphasiftInstall: vi.fn(),
  notifyAlphaSiftConfigChanged: vi.fn(),
  notifySystemConfigChanged: vi.fn(),
  desktopCheckForUpdates: vi.fn(),
  desktopGetUpdateState: vi.fn(),
  desktopInstallDownloadedUpdate: vi.fn(),
  desktopOnUpdateStateChange: vi.fn(),
  desktopOpenReleasePage: vi.fn(),
  load: vi.fn(),
  clearToast: vi.fn(),
  setActiveCategory: vi.fn(),
  save: vi.fn(),
  resetDraft: vi.fn(),
  setDraftValue: vi.fn(),
  applyPartialUpdate: vi.fn(),
  getChangedItems: vi.fn(),
  refreshAfterExternalSave: vi.fn(),
  refreshStatus: vi.fn(),
  settingsPanelErrorBoundary: vi.fn(),
  useAuthMock: vi.fn(),
  useSystemConfigMock: vi.fn(),
  webBuildInfoMock: {
    version: '3.11.0',
    rawVersion: '3.11.0',
    buildId: 'build-20260329-021530Z',
    buildTime: '2026-03-29T02:15:30.000Z',
    isFallbackVersion: false,
  },
}));

const mockedAnchorClick = vi.fn();

vi.mock('../../hooks', () => ({
  useAuth: () => useAuthMock(),
  useSystemConfig: () => useSystemConfigMock(),
}));

vi.mock('../../api/systemConfig', () => ({
  systemConfigApi: {
    exportEnv: (...args: unknown[]) => exportEnv(...args),
    getSchedulerStatus: (...args: unknown[]) => getSchedulerStatus(...args),
    getSetupStatus: (...args: unknown[]) => getSetupStatus(...args),
    importEnv: (...args: unknown[]) => importEnv(...args),
    runSchedulerNow: (...args: unknown[]) => runSchedulerNow(...args),
    update: (...args: unknown[]) => updateSystemConfig(...args),
  },
}));

vi.mock('../../api/analysis', () => ({
  analysisApi: {
    analyzeAsync: (...args: unknown[]) => analyzeAsync(...args),
  },
}));

vi.mock('../../api/alphasift', () => ({
  alphasiftApi: {
    enable: (...args: unknown[]) => alphasiftEnable(...args),
    install: (...args: unknown[]) => alphasiftInstall(...args),
  },
  notifyAlphaSiftConfigChanged: (...args: unknown[]) => notifyAlphaSiftConfigChanged(...args),
  notifySystemConfigChanged: (...args: unknown[]) => notifySystemConfigChanged(...args),
}));

vi.mock('../../utils/constants', async () => {
  const actual = await vi.importActual<typeof import('../../utils/constants')>('../../utils/constants');
  return {
    ...actual,
    WEB_BUILD_INFO: webBuildInfoMock,
  };
});

vi.mock('../../components/settings', () => ({
  AuthSettingsCard: () => <div>\u8ba4\u8bc1\u4e0e\u767b\u5f55\u4fdd\u62a4</div>,
  ChangePasswordCard: () => <div>\u4fee\u6539\u5bc6\u7801</div>,
  IntelligentImport: ({ onMerged }: { onMerged: (value: string) => void }) => (
    <button type="button" onClick={() => onMerged('SZ000001,SZ000002')}>
      merge stock list
    </button>
  ),
  LLMChannelEditor: ({
    items,
    onSaved,
    onDraftItemsChange,
  }: {
    items: Array<{ key: string; value: string }>;
    onSaved: (items: Array<{ key: string; value: string }>) => void;
    onDraftItemsChange?: (items: Array<{ key: string; value: string }>) => void;
  }) => (
    <div>
      <div data-testid="llm-channel-editor-items">{items.map((item) => item.key).join(',')}</div>
      <button
        type="button"
        onClick={() => onDraftItemsChange?.([
          { key: 'LLM_CHANNELS', value: 'draft,backup' },
          { key: 'LITELLM_MODEL', value: 'openai/draft-model' },
          { key: 'GENERATION_BACKEND', value: 'codex_cli' },
        ])}
      >
        emit llm draft
      </button>
      <button
        type="button"
        onClick={() => onSaved([{ key: 'LLM_CHANNELS', value: 'primary,backup' }])}
      >
        save llm channels
      </button>
    </div>
  ),
  GenerationBackendStatusPanel: ({ items }: { items: Array<{ key: string; value: string }> }) => (
    <div data-testid="generation-backend-status-items">
      {items.map((item) => `${item.key}=${item.value}`).join('|')}
    </div>
  ),
  NotificationTestPanel: ({ items }: { items: Array<{ key: string; value: string }> }) => (
    <div>\u901a\u77e5\u6d4b\u8bd5\u9762\u677f:{items.map((item) => item.key).join(',')}</div>
  ),
  SettingsAlert: ({
    title,
    message,
    actionLabel,
    onAction,
  }: {
    title: string;
    message: string;
    actionLabel?: string;
    onAction?: () => void;
  }) => (
    <div>
      {title}:{message}
      {actionLabel ? (
        <button type="button" onClick={onAction}>
          {actionLabel}
        </button>
      ) : null}
    </div>
  ),
  SettingsCategoryNav: ({
    categories,
    activeCategory,
    onSelect,
  }: {
    categories: Array<{ category: string; title: string }>;
    activeCategory: string;
    onSelect: (value: string) => void;
  }) => (
    <nav>
      {categories.map((category) => (
        <button
          key={category.category}
          type="button"
          aria-pressed={activeCategory === category.category}
          onClick={() => onSelect(category.category)}
        >
          {category.title}
        </button>
      ))}
    </nav>
  ),
  SettingsField: ({
    item,
  }: {
    item: {
      key: string;
      schema?: {
        description?: string;
        options?: Array<string | { label: string; value: string }>;
      };
    };
  }) => (
    <div data-testid={`settings-field-${item.key}`}>
      <div>{item.key}</div>
      {item.schema?.description ? <p>{item.schema.description}</p> : null}
      {item.schema?.options?.map((option) => {
        const label = typeof option === 'string' ? option : option.label;
        const value = typeof option === 'string' ? option : option.value;
        return <span key={`${item.key}-${value}`}>{label}</span>;
      })}
    </div>
  ),
  SettingsLoading: () => <div>loading</div>,
  SettingsPanelErrorBoundary: ({
    title,
    diagnosticHint,
    children,
  }: {
    title: string;
    diagnosticHint?: React.ReactNode;
    children: React.ReactNode;
  }) => {
    settingsPanelErrorBoundary(title);
    return (
      <>
        {diagnosticHint ? <div>{diagnosticHint}</div> : null}
        {children}
      </>
    );
  },
  SettingsSectionCard: ({
    title,
    description,
    children,
  }: {
    title: string;
    description?: string;
    children: React.ReactNode;
  }) => (
    <section>
      <h2>{title}</h2>
      {description ? <p>{description}</p> : null}
      {children}
    </section>
  ),
}));

function createDesktopRuntime(overrides: Record<string, unknown> = {}) {
  return {
    version: '3.12.0',
    getUpdateState: desktopGetUpdateState,
    checkForUpdates: desktopCheckForUpdates,
    installDownloadedUpdate: desktopInstallDownloadedUpdate,
    openReleasePage: desktopOpenReleasePage,
    onUpdateStateChange: desktopOnUpdateStateChange,
    ...overrides,
  };
}

const baseCategories = [
  { category: 'system', title: 'System', description: '\u7cfb\u7edf\u8bbe\u7f6e', displayOrder: 1, fields: [] },
  { category: 'base', title: 'Base', description: '\u57fa\u7840\u914d\u7f6e', displayOrder: 2, fields: [] },
  { category: 'ai_model', title: 'AI', description: '\u6a21\u578b\u914d\u7f6e', displayOrder: 3, fields: [] },
  { category: 'notification', title: 'Notification', description: '\u901a\u77e5\u914d\u7f6e', displayOrder: 4, fields: [] },
  { category: 'agent', title: 'Agent', description: 'Agent \u914d\u7f6e', displayOrder: 5, fields: [] },
];

type ConfigState = {
  categories: Array<{ category: string; title: string; description: string; displayOrder: number; fields: [] }>;
  itemsByCategory: Record<string, Array<Record<string, unknown>>>;
  issueByKey: Record<string, unknown[]>;
  activeCategory: string;
  setActiveCategory: typeof setActiveCategory;
  hasDirty: boolean;
  dirtyCount: number;
  toast: null;
  clearToast: typeof clearToast;
  isLoading: boolean;
  isSaving: boolean;
  loadError: null;
  saveError: null;
  retryAction: null;
  load: typeof load;
  retry: ReturnType<typeof vi.fn>;
  save: typeof save;
  resetDraft: typeof resetDraft;
  setDraftValue: typeof setDraftValue;
  applyPartialUpdate: typeof applyPartialUpdate;
  getChangedItems: () => Array<{ key: string; value: string }>;
  refreshAfterExternalSave: typeof refreshAfterExternalSave;
  configVersion: string;
  maskToken: string;
};

type ConfigOverride = Partial<ConfigState>;

function buildSystemConfigState(overrides: ConfigOverride = {}) {
  return {
    categories: baseCategories,
    itemsByCategory: {
      system: [
        {
          key: 'ADMIN_AUTH_ENABLED',
          value: 'true',
          rawValueExists: true,
          isMasked: false,
          schema: {
            key: 'ADMIN_AUTH_ENABLED',
            category: 'system',
            dataType: 'boolean',
            uiControl: 'switch',
            isSensitive: false,
            isRequired: false,
            isEditable: true,
            options: [],
            validation: {},
            displayOrder: 1,
          },
        },
      ],
      base: [
        {
          key: 'STOCK_LIST',
          value: 'SH600000',
          rawValueExists: true,
          isMasked: false,
          schema: {
            key: 'STOCK_LIST',
            category: 'base',
            dataType: 'string',
            uiControl: 'textarea',
            isSensitive: false,
            isRequired: false,
            isEditable: true,
            options: [],
            validation: {},
            displayOrder: 1,
          },
        },
      ],
      ai_model: [
        {
          key: 'LLM_CHANNELS',
          value: 'primary',
          rawValueExists: true,
          isMasked: false,
          schema: {
            key: 'LLM_CHANNELS',
            category: 'ai_model',
            dataType: 'string',
            uiControl: 'textarea',
            isSensitive: false,
            isRequired: false,
            isEditable: true,
            options: [],
            validation: {},
            displayOrder: 1,
          },
        },
      ],
      agent: [
        {
          key: 'AGENT_ORCHESTRATOR_TIMEOUT_S',
          value: '600',
          rawValueExists: true,
          isMasked: false,
          schema: {
            key: 'AGENT_ORCHESTRATOR_TIMEOUT_S',
            category: 'agent',
            dataType: 'integer',
            uiControl: 'number',
            isSensitive: false,
            isRequired: false,
            isEditable: true,
            options: [],
            validation: {},
            displayOrder: 1,
          },
        },
      ],
      notification: [
        {
          key: 'WECHAT_WEBHOOK_URL',
          value: 'https://qyapi.example.com/hook',
          rawValueExists: true,
          isMasked: false,
          schema: {
            key: 'WECHAT_WEBHOOK_URL',
            category: 'notification',
            dataType: 'string',
            uiControl: 'password',
            isSensitive: true,
            isRequired: false,
            isEditable: true,
            options: [],
            validation: {},
            displayOrder: 1,
          },
        },
      ],
    },
    issueByKey: {},
    activeCategory: 'system',
    setActiveCategory,
    hasDirty: false,
    dirtyCount: 0,
    toast: null,
    clearToast,
    isLoading: false,
    isSaving: false,
    loadError: null,
    saveError: null,
    retryAction: null,
    load,
    retry: vi.fn(),
    save,
    resetDraft,
    setDraftValue,
    applyPartialUpdate,
    getChangedItems: () => [],
    refreshAfterExternalSave,
    configVersion: 'v1',
    maskToken: '******',
    ...overrides,
  };
}

function createDeferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((promiseResolve, promiseReject) => {
    resolve = promiseResolve;
    reject = promiseReject;
  });
  return { promise, resolve, reject };
}

describe('SettingsPage', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.clearAllMocks();
    Object.assign(webBuildInfoMock, {
      version: '3.11.0',
      rawVersion: '3.11.0',
      buildId: 'build-20260329-021530Z',
      buildTime: '2026-03-29T02:15:30.000Z',
      isFallbackVersion: false,
    });
    load.mockResolvedValue(true);
    exportEnv.mockResolvedValue({
      content: 'STOCK_LIST=600519\n',
      configVersion: 'v1',
      updatedAt: '2026-03-21T00:00:00Z',
    });
    getSchedulerStatus.mockResolvedValue({
      enabled: true,
      running: false,
      scheduleTimes: ['09:20', '15:10'],
      nextRunAt: '2026-06-21T09:20:00+08:00',
      lastRunAt: null,
      lastSuccessAt: null,
      lastError: null,
    });
    getSetupStatus.mockResolvedValue({
      isComplete: true,
      readyForSmoke: true,
      requiredMissingKeys: [],
      nextStepKey: null,
      checks: [
        {
          key: 'stock_list',
          title: '\u81ea\u9009\u80a1',
          category: 'base',
          required: true,
          status: 'configured',
          message: '\u5df2\u914d\u7f6e\u81ea\u9009\u80a1。',
          nextStep: null,
        },
        {
          key: 'llm_channels',
          title: '\u6a21\u578b\u6e20\u9053',
          category: 'ai_model',
          required: true,
          status: 'configured',
          message: '\u5df2\u914d\u7f6e\u6a21\u578b\u6e20\u9053。',
          nextStep: null,
        },
        {
          key: 'notification',
          title: '\u901a\u77e5',
          category: 'notification',
          required: false,
          status: 'optional',
          message: '\u901a\u77e5\u53ef\u9009。',
          nextStep: null,
        },
      ],
    });
    analyzeAsync.mockResolvedValue({
      taskId: 'task-setup-smoke',
      status: 'pending',
      message: 'accepted',
    });
    runSchedulerNow.mockResolvedValue({
      accepted: true,
      running: true,
    });
    importEnv.mockResolvedValue({
      success: true,
      configVersion: 'v2',
      appliedCount: 1,
      skippedMaskedCount: 0,
      reloadTriggered: true,
      updatedKeys: ['STOCK_LIST'],
      warnings: [],
    });
    updateSystemConfig.mockResolvedValue({
      success: true,
      configVersion: 'v2',
      updatedKeys: ['ALPHASIFT_ENABLED'],
      reloadTriggered: true,
    });
    alphasiftInstall.mockResolvedValue({
      installed: true,
      alreadyInstalled: true,
      installSpecIsDefault: true,
    });
    alphasiftEnable.mockResolvedValue(undefined);
    desktopGetUpdateState.mockResolvedValue({
      status: 'idle',
      currentVersion: '3.12.0',
      latestVersion: '',
      message: '',
    });
    desktopCheckForUpdates.mockResolvedValue({
      status: 'up-to-date',
      currentVersion: '3.12.0',
      latestVersion: '3.12.0',
      message: '\u5f53\u524d\u684c\u9762\u7aef\u5df2\u662f\u6700\u65b0\u7248\u672c。',
    });
    desktopInstallDownloadedUpdate.mockResolvedValue(true);
    desktopOpenReleasePage.mockResolvedValue(true);
    desktopOnUpdateStateChange.mockImplementation(() => () => undefined);
    useAuthMock.mockReturnValue({
      authEnabled: true,
      passwordChangeable: true,
      refreshStatus,
    });
    useSystemConfigMock.mockReturnValue(buildSystemConfigState());
    delete (window as { dsaDesktop?: unknown }).dsaDesktop;
    vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:mock');
    vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => undefined);
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(mockedAnchorClick);
  });

  it('renders category navigation and auth settings modules', async () => {
    render(<SettingsPage />);

    expect(await screen.findByRole('heading', { name: '\u7cfb\u7edf\u8bbe\u7f6e' })).toBeInTheDocument();
    expect(screen.getByText('\u8ba4\u8bc1\u4e0e\u767b\u5f55\u4fdd\u62a4')).toBeInTheDocument();
    expect(screen.getByText('\u4fee\u6539\u5bc6\u7801')).toBeInTheDocument();
    expect(load).toHaveBeenCalled();
  });

  it('renders first-run setup checks and routes setup actions', async () => {
    useSystemConfigMock.mockReturnValue(buildSystemConfigState({ activeCategory: 'base' }));

    render(<SettingsPage />);

    expect(await screen.findByTestId('first-run-setup-card')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: '\u9996\u6b21\u542f\u52a8\u914d\u7f6e\u68c0\u67e5' })).toBeInTheDocument();
    expect(screen.getByText('\u81ea\u9009\u80a1')).toBeInTheDocument();
    expect(screen.getAllByText('\u5df2\u914d\u7f6e')).toHaveLength(2);

    fireEvent.click(screen.getByRole('button', { name: '\u914d\u7f6e\u6a21\u578b' }));
    fireEvent.click(screen.getByRole('button', { name: '\u7ef4\u62a4\u81ea\u9009\u80a1' }));
    fireEvent.click(screen.getByRole('button', { name: '\u914d\u7f6e\u901a\u77e5' }));

    expect(setActiveCategory).toHaveBeenNthCalledWith(1, 'ai_model');
    expect(setActiveCategory).toHaveBeenNthCalledWith(2, 'base');
    expect(setActiveCategory).toHaveBeenNthCalledWith(3, 'notification');
  });

  it('keeps first-run setup summary neutral while setup status is loading', async () => {
    getSetupStatus.mockImplementation(() => new Promise(() => undefined));
    useSystemConfigMock.mockReturnValue(buildSystemConfigState({ activeCategory: 'base' }));

    render(<SettingsPage />);

    expect(await screen.findByText('\u6b63\u5728\u68c0\u67e5\u9996\u6b21\u542f\u52a8\u914d\u7f6e')).toBeInTheDocument();
    expect(screen.getByText('\u6b63\u5728\u8bfb\u53d6\u914d\u7f6e\u72b6\u6001，\u5b8c\u6210\u540e\u4f1a\u663e\u793a\u7f3a\u5931\u9879\u548c\u8bd5\u8dd1\u5165\u53e3。')).toBeInTheDocument();
    expect(screen.queryByText('\u57fa\u7840\u914d\u7f6e\u5df2\u6ee1\u8db3\u6700\u5c0f\u53ef\u7528\u5206\u6790')).not.toBeInTheDocument();
    expect(screen.queryByText('\u8fd8\u6709\u57fa\u7840\u914d\u7f6e\u9700\u8981\u5904\u7406')).not.toBeInTheDocument();
    expect(screen.queryByText('\u6240\u6709\u5fc5\u9700\u9879\u5df2\u5c31\u7eea，\u53ef\u8fd0\u884c\u4e00\u6b21\u7b80\u77ed\u5206\u6790\u9a8c\u8bc1\u94fe\u8def。')).not.toBeInTheDocument();
  });

  it('keeps first-run setup summary neutral when setup status fails', async () => {
    getSetupStatus.mockRejectedValue(new Error('setup status unavailable'));
    useSystemConfigMock.mockReturnValue(buildSystemConfigState({ activeCategory: 'base' }));

    render(<SettingsPage />);

    expect(await screen.findByText('\u6682\u65e0\u6cd5\u5224\u65ad\u914d\u7f6e\u72b6\u6001')).toBeInTheDocument();
    expect(screen.getByText('\u914d\u7f6e\u72b6\u6001\u8bfb\u53d6\u5931\u8d25。\u53ef\u5148\u68c0\u67e5\u6216\u4fee\u6539\u8bbe\u7f6e\u9879，\u7a0d\u540e\u5237\u65b0\u68c0\u67e5\u7ed3\u679c。')).toBeInTheDocument();
    expect(screen.queryByText('\u57fa\u7840\u914d\u7f6e\u5df2\u6ee1\u8db3\u6700\u5c0f\u53ef\u7528\u5206\u6790')).not.toBeInTheDocument();
    expect(screen.queryByText('\u8fd8\u6709\u57fa\u7840\u914d\u7f6e\u9700\u8981\u5904\u7406')).not.toBeInTheDocument();
    expect(screen.queryByText('\u6240\u6709\u5fc5\u9700\u9879\u5df2\u5c31\u7eea，\u53ef\u8fd0\u884c\u4e00\u6b21\u7b80\u77ed\u5206\u6790\u9a8c\u8bc1\u94fe\u8def。')).not.toBeInTheDocument();
  });

  it('keeps the latest first-run setup status when refresh responses resolve out of order', async () => {
    const staleRefresh = createDeferred<SetupStatusResponse>();
    const latestRefresh = createDeferred<SetupStatusResponse>();
    const initialStatus: SetupStatusResponse = {
      isComplete: true,
      readyForSmoke: true,
      requiredMissingKeys: [],
      nextStepKey: null,
      checks: [
        {
          key: 'initial-status',
          title: '\u521d\u59cb\u72b6\u6001',
          category: 'base',
          required: true,
          status: 'configured',
          message: '\u521d\u59cb\u914d\u7f6e\u72b6\u6001。',
          nextStep: null,
        },
      ],
    };
    const staleStatus: SetupStatusResponse = {
      isComplete: false,
      readyForSmoke: false,
      requiredMissingKeys: ['LLM_CHANNELS'],
      nextStepKey: 'LLM_CHANNELS',
      checks: [
        {
          key: 'stale-status',
          title: '\u8fc7\u671f\u72b6\u6001',
          category: 'ai_model',
          required: true,
          status: 'needs_action',
          message: '\u8fc7\u671f\u7684\u914d\u7f6e\u72b6\u6001。',
          nextStep: '\u8fd9\u6761\u65e7\u54cd\u5e94\u4e0d\u5e94\u8986\u76d6\u6700\u65b0\u72b6\u6001。',
        },
      ],
    };
    const latestStatus: SetupStatusResponse = {
      isComplete: true,
      readyForSmoke: true,
      requiredMissingKeys: [],
      nextStepKey: null,
      checks: [
        {
          key: 'latest-status',
          title: '\u6700\u65b0\u72b6\u6001',
          category: 'base',
          required: true,
          status: 'configured',
          message: '\u6700\u65b0\u914d\u7f6e\u72b6\u6001。',
          nextStep: null,
        },
      ],
    };

    getSetupStatus
      .mockResolvedValueOnce(initialStatus)
      .mockImplementationOnce(() => staleRefresh.promise)
      .mockImplementationOnce(() => latestRefresh.promise);
    useSystemConfigMock.mockReturnValue(buildSystemConfigState({ activeCategory: 'base' }));

    render(<SettingsPage />);

    expect(await screen.findByText('\u521d\u59cb\u72b6\u6001')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: '\u5237\u65b0\u68c0\u67e5' }));
    fireEvent.click(screen.getByRole('button', { name: 'merge stock list' }));

    await waitFor(() => expect(getSetupStatus).toHaveBeenCalledTimes(3));

    await act(async () => {
      latestRefresh.resolve(latestStatus);
      await latestRefresh.promise;
    });

    expect(await screen.findByText('\u6700\u65b0\u72b6\u6001')).toBeInTheDocument();
    expect(screen.queryByText('\u8fc7\u671f\u72b6\u6001')).not.toBeInTheDocument();

    await act(async () => {
      staleRefresh.resolve(staleStatus);
      await staleRefresh.promise;
    });

    await waitFor(() => expect(screen.getByText('\u6700\u65b0\u72b6\u6001')).toBeInTheDocument());
    expect(screen.queryByText('\u8fc7\u671f\u72b6\u6001')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: '\u7b80\u77ed\u8bd5\u8dd1' })).toBeEnabled();
  });

  it('runs a brief setup smoke analysis with the first watchlist stock', async () => {
    useSystemConfigMock.mockReturnValue(buildSystemConfigState({ activeCategory: 'base' }));

    render(<SettingsPage />);

    await screen.findByText('\u57fa\u7840\u914d\u7f6e\u5df2\u6ee1\u8db3\u6700\u5c0f\u53ef\u7528\u5206\u6790');
    fireEvent.click(screen.getByRole('button', { name: '\u7b80\u77ed\u8bd5\u8dd1' }));

    await waitFor(() => expect(analyzeAsync).toHaveBeenCalledWith({
      stockCode: 'SH600000',
      reportType: 'brief',
      asyncMode: true,
      notify: false,
      originalQuery: 'SH600000',
      selectionSource: 'manual',
    }));
    expect(await screen.findByText(/task-setup-smoke/)).toBeInTheDocument();
  });

  it('allows brief setup smoke when only the Agent channel is incomplete', async () => {
    useSystemConfigMock.mockReturnValue(buildSystemConfigState({ activeCategory: 'base' }));
    getSetupStatus.mockResolvedValue({
      isComplete: false,
      readyForSmoke: true,
      requiredMissingKeys: ['llm_agent'],
      nextStepKey: 'llm_agent',
      checks: [
        {
          key: 'llm_primary',
          title: 'LLM \u4e3b\u6e20\u9053',
          category: 'ai_model',
          required: true,
          status: 'configured',
          message: '\u5df2\u542f\u7528 Claude Code CLI \u672c\u5730\u751f\u6210 Backend（experimental/limited）。',
          nextStep: null,
        },
        {
          key: 'llm_agent',
          title: 'Agent \u6e20\u9053',
          category: 'agent',
          required: true,
          status: 'needs_action',
          message: 'Agent \u5de5\u5177\u8c03\u7528\u9700\u8981 LiteLLM \u6a21\u578b\u914d\u7f6e；local CLI \u4e3b\u751f\u6210\u65b9\u5f0f\u4e0d\u4f1a\u88ab\u81ea\u52a8\u7ee7\u627f。',
          nextStep: '\u5982\u9700\u4f7f\u7528 Ask-Stock Agent，\u8bf7\u914d\u7f6e LiteLLM \u6a21\u578b。',
        },
        {
          key: 'stock_list',
          title: '\u81ea\u9009\u80a1',
          category: 'base',
          required: true,
          status: 'configured',
          message: '\u5df2\u914d\u7f6e 1 \u53ea\u80a1\u7968。',
          nextStep: null,
        },
      ],
    });

    render(<SettingsPage />);

    await screen.findByText('\u8fd8\u7f3a\u5c11 1 \u9879：Agent \u6e20\u9053');
    expect(screen.getByRole('button', { name: '\u7b80\u77ed\u8bd5\u8dd1' })).toBeEnabled();

    fireEvent.click(screen.getByRole('button', { name: '\u7b80\u77ed\u8bd5\u8dd1' }));

    await waitFor(() => expect(analyzeAsync).toHaveBeenCalledWith({
      stockCode: 'SH600000',
      reportType: 'brief',
      asyncMode: true,
      notify: false,
      originalQuery: 'SH600000',
      selectionSource: 'manual',
    }));
  });

  it('shows missing setup items and lets the user reopen the setup check', async () => {
    getSetupStatus.mockResolvedValue({
      isComplete: false,
      readyForSmoke: false,
      requiredMissingKeys: ['LLM_CHANNELS'],
      nextStepKey: 'LLM_CHANNELS',
      checks: [
        {
          key: 'llm_channels',
          title: '\u6a21\u578b\u6e20\u9053',
          category: 'ai_model',
          required: true,
          status: 'needs_action',
          message: '\u8fd8\u6ca1\u6709\u914d\u7f6e\u6a21\u578b\u6e20\u9053。',
          nextStep: '\u8bf7\u5148\u914d\u7f6e\u6a21\u578b\u6e20\u9053。',
        },
      ],
    });
    useSystemConfigMock.mockReturnValue(buildSystemConfigState({ activeCategory: 'base' }));

    render(<SettingsPage />);

    expect(await screen.findByText('\u8fd8\u6709\u57fa\u7840\u914d\u7f6e\u9700\u8981\u5904\u7406')).toBeInTheDocument();
    expect(screen.getByText('\u8fd8\u7f3a\u5c11 1 \u9879：\u6a21\u578b\u6e20\u9053')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '\u7b80\u77ed\u8bd5\u8dd1' })).toBeDisabled();

    fireEvent.click(screen.getByRole('button', { name: '\u6682\u65f6\u9690\u85cf' }));
    expect(screen.getByText('\u9996\u6b21\u542f\u52a8\u914d\u7f6e\u68c0\u67e5\u5df2\u9690\u85cf')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: '\u5c55\u5f00\u68c0\u67e5' }));
    expect(screen.getByText('\u9996\u6b21\u542f\u52a8\u914d\u7f6e\u68c0\u67e5')).toBeInTheDocument();
  });

  it('renders web build info in system settings', async () => {
    render(<SettingsPage />);

    expect(await screen.findByRole('heading', { name: '\u7248\u672c\u4fe1\u606f' })).toBeInTheDocument();
    expect(screen.getByText('3.11.0')).toBeInTheDocument();
    expect(screen.getByText('build-20260329-021530Z')).toBeInTheDocument();
    expect(screen.getByText('2026-03-29T02:15:30.000Z')).toBeInTheDocument();
  });

  it('renders desktop app version in system settings during desktop runtime', async () => {
    (window as { dsaDesktop?: unknown }).dsaDesktop = { version: '3.12.0' };

    render(<SettingsPage />);

    expect(await screen.findByRole('heading', { name: '\u7248\u672c\u4fe1\u606f' })).toBeInTheDocument();
    expect(screen.getByText('\u684c\u9762\u7aef\u7248\u672c')).toBeInTheDocument();
    expect(screen.getByText('3.12.0')).toBeInTheDocument();
  });

  it('keeps version grid at three columns when desktop runtime has no usable version', async () => {
    (window as { dsaDesktop?: unknown }).dsaDesktop = { version: '   ' };

    render(<SettingsPage />);

    const section = (await screen.findByRole('heading', { name: '\u7248\u672c\u4fe1\u606f' })).closest('section');
    const versionGrid = section?.querySelector('div.grid.grid-cols-1.gap-3');

    expect(screen.queryByText('\u684c\u9762\u7aef\u7248\u672c')).not.toBeInTheDocument();
    expect(versionGrid).toHaveClass('md:grid-cols-3');
    expect(versionGrid).not.toHaveClass('md:grid-cols-4');
  });

  it('ignores non-string desktop runtime version values without breaking render', async () => {
    (window as { dsaDesktop?: unknown }).dsaDesktop = { version: 3120 };

    render(<SettingsPage />);

    const section = (await screen.findByRole('heading', { name: '\u7248\u672c\u4fe1\u606f' })).closest('section');
    const versionGrid = section?.querySelector('div.grid.grid-cols-1.gap-3');

    expect(screen.queryByText('\u684c\u9762\u7aef\u7248\u672c')).not.toBeInTheDocument();
    expect(versionGrid).toHaveClass('md:grid-cols-3');
  });

  it('normalizes malformed desktop update payloads instead of throwing', async () => {
    desktopGetUpdateState.mockResolvedValue({
      status: 123,
      currentVersion: 3120,
      latestVersion: null,
      releaseUrl: { href: 'https://example.com' },
      checkedAt: ['2026-04-25T01:02:00Z'],
      message: false,
      releaseName: { text: 'v3.13.0' },
      tagName: undefined,
    });
    (window as { dsaDesktop?: unknown }).dsaDesktop = createDesktopRuntime();

    render(<SettingsPage />);

    await waitFor(() => {
      expect(desktopGetUpdateState).toHaveBeenCalledTimes(1);
    });
    expect(screen.getByRole('button', { name: '\u68c0\u67e5\u66f4\u65b0' })).toBeInTheDocument();
    expect(screen.queryByText('\u68c0\u67e5\u66f4\u65b0\u5931\u8d25')).not.toBeInTheDocument();
    expect(screen.queryByText('\u53d1\u73b0\u65b0\u7248\u672c')).not.toBeInTheDocument();
  });

  it('falls back to build identifier when package version is still placeholder', () => {
    expect(resolveWebBuildInfo({
      packageVersion: '0.0.0',
      buildTimestamp: '2026-03-29T02:15:30.000Z',
    })).toEqual({
      version: 'build-20260329-021530Z',
      rawVersion: '0.0.0',
      buildId: 'build-20260329-021530Z',
      buildTime: '2026-03-29T02:15:30.000Z',
      isFallbackVersion: true,
    });
  });

  it('renders fallback version hint when package version is placeholder', async () => {
    Object.assign(webBuildInfoMock, {
      version: 'build-20260329-021530Z',
      rawVersion: '0.0.0',
      buildId: 'build-20260329-021530Z',
      buildTime: '2026-03-29T02:15:30.000Z',
      isFallbackVersion: true,
    });

    render(<SettingsPage />);

    expect(await screen.findByRole('heading', { name: '\u7248\u672c\u4fe1\u606f' })).toBeInTheDocument();
    expect(screen.getByText(/\u5f53\u524d package\.json \u4ecd\u4e3a\u5360\u4f4d\u7248\u672c 0\.0\.0/)).toBeInTheDocument();
    expect(screen.getAllByText('build-20260329-021530Z')).toHaveLength(2);
  });

  it('resets local drafts from the page header button', () => {
    useSystemConfigMock.mockReturnValue(buildSystemConfigState({ hasDirty: true, dirtyCount: 2 }));

    render(<SettingsPage />);

    // Clear the initial load call from useEffect
    vi.clearAllMocks();

    fireEvent.click(screen.getByRole('button', { name: '\u91cd\u7f6e' }));

    // Reset should call resetDraft and NOT call load
    expect(resetDraft).toHaveBeenCalledTimes(1);
    expect(load).not.toHaveBeenCalled();
  });

  it('shows deep research and event monitor fields in the agent category when available', () => {
    useSystemConfigMock.mockReturnValue(buildSystemConfigState({
      activeCategory: 'agent',
      itemsByCategory: {
        ...buildSystemConfigState().itemsByCategory,
        agent: [
          {
            key: 'AGENT_ORCHESTRATOR_TIMEOUT_S',
            value: '600',
            rawValueExists: true,
            isMasked: false,
            schema: {
              key: 'AGENT_ORCHESTRATOR_TIMEOUT_S',
              category: 'agent',
              dataType: 'integer',
              uiControl: 'number',
              isSensitive: false,
              isRequired: false,
              isEditable: true,
              options: [],
              validation: {},
              displayOrder: 1,
            },
          },
          {
            key: 'AGENT_DEEP_RESEARCH_BUDGET',
            value: '30000',
            rawValueExists: true,
            isMasked: false,
            schema: {
              key: 'AGENT_DEEP_RESEARCH_BUDGET',
              category: 'agent',
              dataType: 'integer',
              uiControl: 'number',
              isSensitive: false,
              isRequired: false,
              isEditable: true,
              options: [],
              validation: {},
              displayOrder: 2,
            },
          },
          {
            key: 'AGENT_EVENT_MONITOR_ENABLED',
            value: 'false',
            rawValueExists: true,
            isMasked: false,
            schema: {
              key: 'AGENT_EVENT_MONITOR_ENABLED',
              category: 'agent',
              dataType: 'boolean',
              uiControl: 'switch',
              isSensitive: false,
              isRequired: false,
              isEditable: true,
              options: [],
              validation: {},
              displayOrder: 3,
            },
          },
        ],
      },
    }));

    render(<SettingsPage />);

    expect(screen.getByText('AGENT_ORCHESTRATOR_TIMEOUT_S')).toBeInTheDocument();
    expect(screen.getByText('AGENT_DEEP_RESEARCH_BUDGET')).toBeInTheDocument();
    expect(screen.getByText('AGENT_EVENT_MONITOR_ENABLED')).toBeInTheDocument();
    expect(settingsPanelErrorBoundary).toHaveBeenCalledWith('Agent \u8bbe\u7f6e');
  });

  it('renders context compression profile labels and blank preset guidance in agent settings', () => {
    const configState = buildSystemConfigState();
    useSystemConfigMock.mockReturnValue(buildSystemConfigState({
      activeCategory: 'agent',
      itemsByCategory: {
        ...configState.itemsByCategory,
        agent: [
          {
            key: 'AGENT_CONTEXT_COMPRESSION_PROFILE',
            value: 'balanced',
            rawValueExists: true,
            isMasked: false,
            schema: {
              key: 'AGENT_CONTEXT_COMPRESSION_PROFILE',
              category: 'agent',
              dataType: 'string',
              uiControl: 'select',
              isSensitive: false,
              isRequired: false,
              isEditable: true,
              options: [
                { label: '\u6210\u672c\u4f18\u5148', value: 'cost' },
                { label: '\u5747\u8861\u63a8\u8350', value: 'balanced' },
                { label: '\u957f\u4e0a\u4e0b\u6587\u539f\u6587\u4f18\u5148', value: 'long_context_raw_first' },
              ],
              validation: {
                enum: ['cost', 'balanced', 'long_context_raw_first'],
              },
              displayOrder: 72,
            },
          },
          {
            key: 'AGENT_CONTEXT_COMPRESSION_TRIGGER_TOKENS',
            value: '',
            rawValueExists: false,
            isMasked: false,
            schema: {
              key: 'AGENT_CONTEXT_COMPRESSION_TRIGGER_TOKENS',
              category: 'agent',
              dataType: 'integer',
              uiControl: 'number',
              isSensitive: false,
              isRequired: false,
              isEditable: true,
              options: [],
              validation: { min: 1000 },
              displayOrder: 73,
              description: '\u4f30\u7b97\u5386\u53f2 token \u8d85\u8fc7\u8be5\u503c\u65f6\u89e6\u53d1\u6458\u8981；\u7559\u7a7a\u5219\u8ddf\u968f\u5f53\u524d\u4e0a\u4e0b\u6587\u538b\u7f29\u7b56\u7565 profile \u9ed8\u8ba4\u503c。',
            },
          },
          {
            key: 'AGENT_CONTEXT_PROTECTED_TURNS',
            value: '',
            rawValueExists: false,
            isMasked: false,
            schema: {
              key: 'AGENT_CONTEXT_PROTECTED_TURNS',
              category: 'agent',
              dataType: 'integer',
              uiControl: 'number',
              isSensitive: false,
              isRequired: false,
              isEditable: true,
              options: [],
              validation: { min: 1 },
              displayOrder: 74,
              description: '\u538b\u7f29\u65f6\u6700\u8fd1 N \u4e2a\u7528\u6237\u8f6e\u6b21\u53ca\u5176\u540e\u7684\u56de\u590d\u4fdd\u6301\u539f\u6587；\u7559\u7a7a\u5219\u8ddf\u968f\u5f53\u524d\u4e0a\u4e0b\u6587\u538b\u7f29\u7b56\u7565 profile \u9ed8\u8ba4\u503c。',
            },
          },
        ],
      },
    }));

    render(<SettingsPage />);

    expect(screen.getByText('AGENT_CONTEXT_COMPRESSION_PROFILE')).toBeInTheDocument();
    expect(screen.getByText('\u6210\u672c\u4f18\u5148')).toBeInTheDocument();
    expect(screen.getByText('\u5747\u8861\u63a8\u8350')).toBeInTheDocument();
    expect(screen.getByText('\u957f\u4e0a\u4e0b\u6587\u539f\u6587\u4f18\u5148')).toBeInTheDocument();
    expect(screen.getByText(/\u4f30\u7b97\u5386\u53f2 token \u8d85\u8fc7\u8be5\u503c\u65f6\u89e6\u53d1\u6458\u8981/)).toHaveTextContent('\u7559\u7a7a\u5219\u8ddf\u968f\u5f53\u524d\u4e0a\u4e0b\u6587\u538b\u7f29\u7b56\u7565 profile \u9ed8\u8ba4\u503c');
    expect(screen.getByText(/\u538b\u7f29\u65f6\u6700\u8fd1 N \u4e2a\u7528\u6237\u8f6e\u6b21\u53ca\u5176\u540e\u7684\u56de\u590d\u4fdd\u6301\u539f\u6587/)).toHaveTextContent('\u7559\u7a7a\u5219\u8ddf\u968f\u5f53\u524d\u4e0a\u4e0b\u6587\u538b\u7f29\u7b56\u7565 profile \u9ed8\u8ba4\u503c');
  });

  it('reset button semantic: discards local changes without network request', () => {
    // Simulate user has unsaved drafts
    const dirtyState = buildSystemConfigState({
      hasDirty: true,
      dirtyCount: 2,
    });

    useSystemConfigMock.mockReturnValue(dirtyState);

    render(<SettingsPage />);

    // Clear initial useEffect load call
    vi.clearAllMocks();

    // Click reset button
    fireEvent.click(screen.getByRole('button', { name: '\u91cd\u7f6e' }));

    // Verify semantic: reset should only discard local changes
    // It should NOT trigger a network load
    expect(resetDraft).toHaveBeenCalledTimes(1);
    expect(load).not.toHaveBeenCalled();
    expect(save).not.toHaveBeenCalled();
  });

  it('refreshes server state after intelligent import merges stock list', async () => {
    useSystemConfigMock.mockReturnValue(buildSystemConfigState({ activeCategory: 'base' }));

    render(<SettingsPage />);

    fireEvent.click(screen.getByRole('button', { name: 'merge stock list' }));

    expect(refreshAfterExternalSave).toHaveBeenCalledWith(['STOCK_LIST']);
    expect(load).toHaveBeenCalledTimes(1);
  });

  it('refreshes server state after llm channel editor saves', async () => {
    useSystemConfigMock.mockReturnValue(buildSystemConfigState({ activeCategory: 'ai_model' }));

    render(<SettingsPage />);

    fireEvent.click(screen.getByRole('button', { name: 'save llm channels' }));

    expect(refreshAfterExternalSave).toHaveBeenCalledWith(['LLM_CHANNELS']);
    expect(load).toHaveBeenCalledTimes(1);
  });

  it('passes merged generation backend draft items to the backend status panel', async () => {
    useSystemConfigMock.mockReturnValue(buildSystemConfigState({
      activeCategory: 'ai_model',
      getChangedItems: () => [
        { key: 'GENERATION_BACKEND', value: 'litellm' },
        { key: 'LLM_CHANNELS', value: 'saved' },
        { key: 'OPENAI_MODEL', value: 'gpt-draft' },
        { key: 'GEMINI_MODEL', value: 'gemini-draft' },
        { key: 'OLLAMA_API_BASE', value: 'http://localhost:11434' },
        { key: 'WECHAT_WEBHOOK_URL', value: 'not-a-url' },
      ],
    }));

    render(<SettingsPage />);

    fireEvent.click(screen.getByRole('button', { name: 'emit llm draft' }));

    const statusItems = await screen.findByTestId('generation-backend-status-items');
    await waitFor(() => {
      expect(statusItems).toHaveTextContent('GENERATION_BACKEND=litellm');
      expect(statusItems).toHaveTextContent('LLM_CHANNELS=draft,backup');
      expect(statusItems).toHaveTextContent('LITELLM_MODEL=openai/draft-model');
      expect(statusItems).toHaveTextContent('OPENAI_MODEL=gpt-draft');
      expect(statusItems).toHaveTextContent('GEMINI_MODEL=gemini-draft');
      expect(statusItems).toHaveTextContent('OLLAMA_API_BASE=http://localhost:11434');
      expect(statusItems).not.toHaveTextContent('GENERATION_BACKEND=codex_cli');
      expect(statusItems).not.toHaveTextContent('WECHAT_WEBHOOK_URL=not-a-url');
    });
  });

  it('clears llm channel draft items after llm channel editor saves', async () => {
    useSystemConfigMock.mockReturnValue(buildSystemConfigState({ activeCategory: 'ai_model' }));

    render(<SettingsPage />);

    fireEvent.click(screen.getByRole('button', { name: 'emit llm draft' }));
    expect(await screen.findByTestId('generation-backend-status-items')).toHaveTextContent('LLM_CHANNELS=draft,backup');

    fireEvent.click(screen.getByRole('button', { name: 'save llm channels' }));

    await waitFor(() => {
      expect(screen.getByTestId('generation-backend-status-items')).not.toHaveTextContent('LLM_CHANNELS=draft,backup');
    });
    expect(refreshAfterExternalSave).toHaveBeenCalledWith(['LLM_CHANNELS']);
  });

  it('keeps prompt cache settings collapsed and expandable at the bottom of AI model settings', () => {
    const aiField = (key: string, displayOrder: number, value = '') => ({
      key,
      value,
      rawValueExists: Boolean(value),
      isMasked: false,
      schema: {
        key,
        category: 'ai_model',
        dataType: 'string',
        uiControl: key === 'LLM_PROMPT_CACHE_DIAGNOSTICS_LEVEL' ? 'select' : 'text',
        isSensitive: false,
        isRequired: false,
        isEditable: true,
        options: key === 'LLM_PROMPT_CACHE_DIAGNOSTICS_LEVEL' ? ['off', 'basic', 'debug'] : [],
        validation: {},
        displayOrder,
      },
    });
    const configState = buildSystemConfigState();
    useSystemConfigMock.mockReturnValue(buildSystemConfigState({
      activeCategory: 'ai_model',
      itemsByCategory: {
        ...configState.itemsByCategory,
        ai_model: [
          aiField('LITELLM_CONFIG', 10, './litellm.yaml'),
          aiField('LLM_PROMPT_CACHE_TELEMETRY_ENABLED', 20, 'true'),
          aiField('LLM_PROMPT_CACHE_HINTS_ENABLED', 21, 'false'),
          aiField('LLM_PROMPT_CACHE_DIAGNOSTICS_LEVEL', 22, 'off'),
        ],
      },
    }));

    const { container } = render(<SettingsPage />);

    const promptCacheSummary = screen.getByText('Provider Prompt Cache \u9ad8\u7ea7\u8bbe\u7f6e').closest('summary');
    const promptCacheDetails = promptCacheSummary?.closest('details');
    const telemetryField = screen.getByTestId('settings-field-LLM_PROMPT_CACHE_TELEMETRY_ENABLED');
    const hintsField = screen.getByTestId('settings-field-LLM_PROMPT_CACHE_HINTS_ENABLED');
    const diagnosticsField = screen.getByTestId('settings-field-LLM_PROMPT_CACHE_DIAGNOSTICS_LEVEL');

    expect(promptCacheSummary).toBeInTheDocument();
    expect(promptCacheDetails).toBeInTheDocument();
    expect(promptCacheDetails).not.toHaveAttribute('open');
    expect(promptCacheDetails).toContainElement(telemetryField);
    expect(promptCacheDetails).toContainElement(hintsField);
    expect(promptCacheDetails).toContainElement(diagnosticsField);
    expect(telemetryField).not.toBeVisible();
    expect(hintsField).not.toBeVisible();
    expect(diagnosticsField).not.toBeVisible();

    fireEvent.click(promptCacheSummary as HTMLElement);

    expect(promptCacheDetails).toHaveAttribute('open');
    expect(telemetryField).toBeVisible();
    expect(hintsField).toBeVisible();
    expect(diagnosticsField).toBeVisible();

    expect(Array.from(container.querySelectorAll('[data-testid^="settings-field-"]')).map((node) => node.getAttribute('data-testid'))).toEqual([
      'settings-field-LITELLM_CONFIG',
      'settings-field-LLM_PROMPT_CACHE_TELEMETRY_ENABLED',
      'settings-field-LLM_PROMPT_CACHE_HINTS_ENABLED',
      'settings-field-LLM_PROMPT_CACHE_DIAGNOSTICS_LEVEL',
    ]);
  });

  it('notifies alphasift status update and skips install after generic save when ALPHASIFT_ENABLED is set false', async () => {
    save.mockResolvedValue({ success: true });
    getChangedItems.mockReturnValue([{ key: 'ALPHASIFT_ENABLED', value: 'false' }]);

    useSystemConfigMock.mockReturnValue(buildSystemConfigState({
      hasDirty: true,
      dirtyCount: 1,
      getChangedItems: () => [{ key: 'ALPHASIFT_ENABLED', value: 'false' }],
    }));

    render(<SettingsPage />);

    fireEvent.click(screen.getByRole('button', { name: /\u4fdd\u5b58\u914d\u7f6e/ }));

    await waitFor(() => expect(save).toHaveBeenCalledTimes(1));
    expect(notifyAlphaSiftConfigChanged).toHaveBeenCalledTimes(1);
    expect(notifySystemConfigChanged).toHaveBeenCalledTimes(1);
    expect(alphasiftEnable).not.toHaveBeenCalled();
    expect(alphasiftInstall).not.toHaveBeenCalled();
  });

  it('runs the AlphaSift enable flow after generic save when ALPHASIFT_ENABLED is set true', async () => {
    save.mockResolvedValue({ success: true });
    getChangedItems.mockReturnValue([{ key: 'ALPHASIFT_ENABLED', value: 'true' }]);

    useSystemConfigMock.mockReturnValue(buildSystemConfigState({
      hasDirty: true,
      dirtyCount: 1,
      getChangedItems: () => [{ key: 'ALPHASIFT_ENABLED', value: 'true' }],
    }));

    render(<SettingsPage />);

    fireEvent.click(screen.getByRole('button', { name: /\u4fdd\u5b58\u914d\u7f6e/ }));

    await waitFor(() => expect(save).toHaveBeenCalledTimes(1));
    expect(notifySystemConfigChanged).toHaveBeenCalledTimes(1);
    expect(alphasiftEnable).toHaveBeenCalledTimes(1);
    expect(alphasiftInstall).not.toHaveBeenCalled();
    expect(refreshAfterExternalSave).toHaveBeenCalledWith(['ALPHASIFT_ENABLED']);
  });

  it('does not notify alphasift status when generic save updates other fields', async () => {
    save.mockResolvedValue({ success: true });
    useSystemConfigMock.mockReturnValue(buildSystemConfigState({
      hasDirty: true,
      dirtyCount: 1,
      getChangedItems: () => [{ key: 'LLM_CHANNELS', value: 'primary,backup' }],
    }));

    render(<SettingsPage />);

    fireEvent.click(screen.getByRole('button', { name: /\u4fdd\u5b58\u914d\u7f6e/ }));

    await waitFor(() => expect(save).toHaveBeenCalledTimes(1));
    expect(notifySystemConfigChanged).toHaveBeenCalledTimes(1);
    expect(notifyAlphaSiftConfigChanged).not.toHaveBeenCalled();
  });

  it('runs AlphaSift enable flow from the settings card', async () => {
    const configState = buildSystemConfigState();
    useSystemConfigMock.mockReturnValue(buildSystemConfigState({
      activeCategory: 'data_source',
      itemsByCategory: {
        ...configState.itemsByCategory,
        data_source: [
          {
            key: 'ALPHASIFT_ENABLED',
            value: 'false',
            rawValueExists: true,
            isMasked: false,
            schema: {
              key: 'ALPHASIFT_ENABLED',
              category: 'data_source',
              dataType: 'boolean',
              uiControl: 'switch',
              isSensitive: false,
              isRequired: false,
              isEditable: true,
              options: [],
              validation: {},
              displayOrder: 16,
            },
          },
          {
            key: 'ALPHASIFT_INSTALL_SPEC',
            value: 'git+https://github.com/ZhuLinsen/alphasift.git@2c76b2b6074ae3bae01d52e5e830a4af3e3246b2',
            rawValueExists: true,
            isMasked: false,
            schema: {
              key: 'ALPHASIFT_INSTALL_SPEC',
              category: 'data_source',
              dataType: 'string',
              uiControl: 'password',
              isSensitive: true,
              isRequired: false,
              isEditable: true,
              options: [],
              validation: {},
              displayOrder: 17,
            },
          },
        ],
      },
    }));

    render(<SettingsPage />);

    fireEvent.click(screen.getByRole('button', { name: '\u5f00\u542f\u9009\u80a1' }));

    await waitFor(() => expect(alphasiftEnable).toHaveBeenCalledTimes(1));
    expect(updateSystemConfig).not.toHaveBeenCalled();
    expect(alphasiftInstall).not.toHaveBeenCalled();
    expect(refreshAfterExternalSave).toHaveBeenCalledWith(['ALPHASIFT_ENABLED']);
  });

  it('does not render raw AlphaSift install spec in the settings card', () => {
    const privateInstallSpec = 'git+https://user:token@example.com/internal/alphasift.git';
    const configState = buildSystemConfigState();
    useSystemConfigMock.mockReturnValue(buildSystemConfigState({
      activeCategory: 'data_source',
      itemsByCategory: {
        ...configState.itemsByCategory,
        data_source: [
          {
            key: 'ALPHASIFT_ENABLED',
            value: 'true',
            rawValueExists: true,
            isMasked: false,
            schema: {
              key: 'ALPHASIFT_ENABLED',
              category: 'data_source',
              dataType: 'boolean',
              uiControl: 'switch',
              isSensitive: false,
              isRequired: false,
              isEditable: true,
              options: [],
              validation: {},
              displayOrder: 16,
            },
          },
          {
            key: 'ALPHASIFT_INSTALL_SPEC',
            value: privateInstallSpec,
            rawValueExists: true,
            isMasked: true,
            schema: {
              key: 'ALPHASIFT_INSTALL_SPEC',
              category: 'data_source',
              dataType: 'string',
              uiControl: 'password',
              isSensitive: true,
              isRequired: false,
              isEditable: true,
              options: [],
              validation: {},
              displayOrder: 17,
            },
          },
        ],
      },
    }));

    render(<SettingsPage />);

    expect(screen.getByText('\u542f\u7528\u5185\u7f6e AlphaSift \u5b9e\u9a8c\u6027\u8d28\u9009\u80a1\u80fd\u529b。')).toBeInTheDocument();
    expect(screen.queryByText(privateInstallSpec)).not.toBeInTheDocument();
    expect(screen.queryByText(/\u5b89\u88c5\u6765\u6e90/)).not.toBeInTheDocument();
  });

  it('maps ALPHASIFT_ENABLED to the AlphaSift card instead of a generic settings field', () => {
    const configState = buildSystemConfigState();
    useSystemConfigMock.mockReturnValue(buildSystemConfigState({
      activeCategory: 'data_source',
      itemsByCategory: {
        ...configState.itemsByCategory,
        data_source: [
          {
            key: 'ALPHASIFT_ENABLED',
            value: 'false',
            rawValueExists: true,
            isMasked: false,
            schema: {
              key: 'ALPHASIFT_ENABLED',
              category: 'data_source',
              dataType: 'boolean',
              uiControl: 'switch',
              isSensitive: false,
              isRequired: false,
              isEditable: true,
              options: [],
              validation: {},
              displayOrder: 16,
            },
          },
          {
            key: 'ALPHASIFT_INSTALL_SPEC',
            value: '******',
            rawValueExists: true,
            isMasked: true,
            schema: {
              key: 'ALPHASIFT_INSTALL_SPEC',
              category: 'data_source',
              dataType: 'string',
              uiControl: 'password',
              isSensitive: true,
              isRequired: false,
              isEditable: true,
              options: [],
              validation: {},
              displayOrder: 17,
            },
          },
        ],
      },
    }));

    render(<SettingsPage />);

    expect(screen.getByRole('button', { name: '\u5f00\u542f\u9009\u80a1' })).toBeInTheDocument();
    expect(screen.queryByTestId('settings-field-ALPHASIFT_ENABLED')).not.toBeInTheDocument();
    expect(screen.getByTestId('settings-field-ALPHASIFT_INSTALL_SPEC')).toBeInTheDocument();
  });

  it('scopes setup and AlphaSift helper cards to their related categories', async () => {
    const configState = buildSystemConfigState();
    const dataSourceItems = [
      {
        key: 'ALPHASIFT_ENABLED',
        value: 'false',
        rawValueExists: true,
        isMasked: false,
        schema: {
          key: 'ALPHASIFT_ENABLED',
          category: 'data_source',
          dataType: 'boolean',
          uiControl: 'switch',
          isSensitive: false,
          isRequired: false,
          isEditable: true,
          options: [],
          validation: {},
          displayOrder: 16,
        },
      },
    ];

    useSystemConfigMock.mockReturnValue(buildSystemConfigState({
      activeCategory: 'base',
      itemsByCategory: {
        ...configState.itemsByCategory,
        data_source: dataSourceItems,
      },
    }));

    const { rerender } = render(<SettingsPage />);

    expect(await screen.findByRole('heading', { name: '\u9996\u6b21\u542f\u52a8\u914d\u7f6e\u68c0\u67e5' })).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: 'AlphaSift \u9009\u80a1' })).not.toBeInTheDocument();

    useSystemConfigMock.mockReturnValue(buildSystemConfigState({
      activeCategory: 'ai_model',
      itemsByCategory: {
        ...configState.itemsByCategory,
        data_source: dataSourceItems,
      },
    }));
    rerender(<SettingsPage />);

    expect(screen.queryByRole('heading', { name: '\u9996\u6b21\u542f\u52a8\u914d\u7f6e\u68c0\u67e5' })).not.toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: 'AlphaSift \u9009\u80a1' })).not.toBeInTheDocument();

    useSystemConfigMock.mockReturnValue(buildSystemConfigState({
      activeCategory: 'data_source',
      itemsByCategory: {
        ...configState.itemsByCategory,
        data_source: dataSourceItems,
      },
    }));
    rerender(<SettingsPage />);

    expect(await screen.findByRole('heading', { name: 'AlphaSift \u9009\u80a1' })).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: '\u9996\u6b21\u542f\u52a8\u914d\u7f6e\u68c0\u67e5' })).not.toBeInTheDocument();
  });

  it('maps schedule settings to the scheduler card instead of generic raw fields', async () => {
    const configState = buildSystemConfigState();
    useSystemConfigMock.mockReturnValue(buildSystemConfigState({
      activeCategory: 'system',
      itemsByCategory: {
        ...configState.itemsByCategory,
        system: [
          ...configState.itemsByCategory.system,
          {
            key: 'SCHEDULE_ENABLED',
            value: 'true',
            rawValueExists: true,
            isMasked: false,
            schema: {
              key: 'SCHEDULE_ENABLED',
              category: 'system',
              dataType: 'boolean',
              uiControl: 'switch',
              isSensitive: false,
              isRequired: false,
              isEditable: true,
              options: [],
              validation: {},
              displayOrder: 8,
            },
          },
          {
            key: 'SCHEDULE_TIME',
            value: '18:00',
            rawValueExists: true,
            isMasked: false,
            schema: {
              key: 'SCHEDULE_TIME',
              category: 'system',
              dataType: 'time',
              uiControl: 'time',
              isSensitive: false,
              isRequired: false,
              isEditable: true,
              options: [],
              validation: {},
              displayOrder: 10,
            },
          },
          {
            key: 'SCHEDULE_TIMES',
            value: '09:20,15:10',
            rawValueExists: true,
            isMasked: false,
            schema: {
              key: 'SCHEDULE_TIMES',
              category: 'system',
              dataType: 'string',
              uiControl: 'text',
              isSensitive: false,
              isRequired: false,
              isEditable: true,
              options: [],
              validation: {},
              displayOrder: 11,
            },
          },
          {
            key: 'SCHEDULE_RUN_IMMEDIATELY',
            value: 'false',
            rawValueExists: true,
            isMasked: false,
            schema: {
              key: 'SCHEDULE_RUN_IMMEDIATELY',
              category: 'system',
              dataType: 'boolean',
              uiControl: 'switch',
              isSensitive: false,
              isRequired: false,
              isEditable: true,
              options: [],
              validation: {},
              displayOrder: 12,
            },
          },
          {
            key: 'LOG_LEVEL',
            value: 'INFO',
            rawValueExists: true,
            isMasked: false,
            schema: {
              key: 'LOG_LEVEL',
              category: 'system',
              dataType: 'string',
              uiControl: 'select',
              isSensitive: false,
              isRequired: false,
              isEditable: true,
              options: ['INFO', 'DEBUG'],
              validation: {},
              displayOrder: 50,
            },
          },
        ],
      },
    }));

    render(<SettingsPage />);

    expect(await screen.findByTestId('scheduler-settings-card')).toBeInTheDocument();
    expect(screen.queryByTestId('settings-field-SCHEDULE_ENABLED')).not.toBeInTheDocument();
    expect(screen.queryByTestId('settings-field-SCHEDULE_TIME')).not.toBeInTheDocument();
    expect(screen.queryByTestId('settings-field-SCHEDULE_TIMES')).not.toBeInTheDocument();
    expect(screen.queryByTestId('settings-field-SCHEDULE_RUN_IMMEDIATELY')).not.toBeInTheDocument();
    expect(screen.getByTestId('settings-field-LOG_LEVEL')).toBeInTheDocument();

    fireEvent.change(screen.getByTestId('scheduler-time-input-0'), {
      target: { value: '10:30' },
    });

    expect(setDraftValue).toHaveBeenCalledWith('SCHEDULE_TIMES', '10:30,15:10');

    fireEvent.click(screen.getByTestId('scheduler-run-now-button'));

    await waitFor(() => expect(runSchedulerNow).toHaveBeenCalledTimes(1));
  });

  it('shows an error when run-now is rejected because analysis is already running', async () => {
    runSchedulerNow.mockRejectedValueOnce(new Error('A scheduled analysis is already running'));
    const configState = buildSystemConfigState();
    useSystemConfigMock.mockReturnValue(buildSystemConfigState({
      activeCategory: 'system',
      itemsByCategory: {
        ...configState.itemsByCategory,
        system: [
          ...configState.itemsByCategory.system,
          {
            key: 'SCHEDULE_ENABLED',
            value: 'true',
            rawValueExists: true,
            isMasked: false,
            schema: {
              key: 'SCHEDULE_ENABLED',
              category: 'system',
              dataType: 'boolean',
              uiControl: 'switch',
              isSensitive: false,
              isRequired: false,
              isEditable: true,
              options: [],
              validation: {},
              displayOrder: 8,
            },
          },
          {
            key: 'SCHEDULE_TIMES',
            value: '18:00',
            rawValueExists: true,
            isMasked: false,
            schema: {
              key: 'SCHEDULE_TIMES',
              category: 'system',
              dataType: 'string',
              uiControl: 'text',
              isSensitive: false,
              isEditable: true,
              options: [],
              validation: {},
              displayOrder: 11,
            },
          },
        ],
      },
    }));

    render(<SettingsPage />);

    fireEvent.click(await screen.findByTestId('scheduler-run-now-button'));

    await waitFor(() => expect(runSchedulerNow).toHaveBeenCalledTimes(1));
    expect(await screen.findByText(/A scheduled analysis is already running/)).toBeInTheDocument();
  });

  it('does not show a failed run as the last successful scheduler run', async () => {
    const configState = buildSystemConfigState();
    getSchedulerStatus.mockResolvedValueOnce({
      enabled: true,
      running: false,
      scheduleTimes: ['18:00'],
      nextRunAt: null,
      lastRunAt: '2026-06-21T17:00:00+08:00',
      lastSuccessAt: null,
      lastError: 'analysis failed',
    });
    useSystemConfigMock.mockReturnValue(buildSystemConfigState({
      activeCategory: 'system',
      itemsByCategory: {
        ...configState.itemsByCategory,
        system: [
          ...configState.itemsByCategory.system,
          {
            key: 'SCHEDULE_ENABLED',
            value: 'true',
            rawValueExists: true,
            isMasked: false,
            schema: {
              key: 'SCHEDULE_ENABLED',
              category: 'system',
              dataType: 'boolean',
              uiControl: 'switch',
              isSensitive: false,
              isRequired: false,
              isEditable: true,
              options: [],
              validation: {},
              displayOrder: 8,
            },
          },
          {
            key: 'SCHEDULE_TIMES',
            value: '18:00',
            rawValueExists: true,
            isMasked: false,
            schema: {
              key: 'SCHEDULE_TIMES',
              category: 'system',
              dataType: 'string',
              uiControl: 'text',
              isSensitive: false,
              isRequired: false,
              isEditable: true,
              options: [],
              validation: {},
              displayOrder: 11,
            },
          },
        ],
      },
    }));

    render(<SettingsPage />);

    expect(await screen.findByTestId('scheduler-last-success')).toHaveTextContent('-');
    expect(screen.getByTestId('scheduler-last-error')).toHaveTextContent('analysis failed');
  });

  it('shows active runtime scheduler state even when saved schedule flag is false', async () => {
    const configState = buildSystemConfigState();
    getSchedulerStatus.mockResolvedValueOnce({
      enabled: true,
      running: false,
      scheduleTimes: ['18:00'],
      nextRunAt: null,
      lastRunAt: null,
      lastSuccessAt: null,
      lastError: null,
    });
    useSystemConfigMock.mockReturnValue(buildSystemConfigState({
      activeCategory: 'system',
      itemsByCategory: {
        ...configState.itemsByCategory,
        system: [
          ...configState.itemsByCategory.system,
          {
            key: 'SCHEDULE_ENABLED',
            value: 'false',
            rawValueExists: true,
            isMasked: false,
            schema: {
              key: 'SCHEDULE_ENABLED',
              category: 'system',
              dataType: 'boolean',
              uiControl: 'switch',
              isSensitive: false,
              isRequired: false,
              isEditable: true,
              options: [],
              validation: {},
              displayOrder: 8,
            },
          },
          {
            key: 'SCHEDULE_TIMES',
            value: '18:00',
            rawValueExists: true,
            isMasked: false,
            schema: {
              key: 'SCHEDULE_TIMES',
              category: 'system',
              dataType: 'string',
              uiControl: 'text',
              isSensitive: false,
              isRequired: false,
              isEditable: true,
              options: [],
              validation: {},
              displayOrder: 11,
            },
          },
        ],
      },
    }));

    render(<SettingsPage />);

    const enabledCheckbox = await screen.findByTestId('scheduler-enabled-checkbox');
    expect(enabledCheckbox).toBeChecked();

    fireEvent.click(enabledCheckbox);

    expect(setDraftValue).toHaveBeenCalledWith('SCHEDULE_ENABLED', 'false');
    await waitFor(() => expect(enabledCheckbox).not.toBeChecked());
  });

  it('keeps local scheduler toggle edits when runtime and saved states are initially consistent', async () => {
    const configState = buildSystemConfigState();
    useSystemConfigMock.mockReturnValue(buildSystemConfigState({
      activeCategory: 'system',
      itemsByCategory: {
        ...configState.itemsByCategory,
        system: [
          ...configState.itemsByCategory.system,
          {
            key: 'SCHEDULE_ENABLED',
            value: 'true',
            rawValueExists: true,
            isMasked: false,
            schema: {
              key: 'SCHEDULE_ENABLED',
              category: 'system',
              dataType: 'boolean',
              uiControl: 'switch',
              isSensitive: false,
              isRequired: false,
              isEditable: true,
              options: [],
              validation: {},
              displayOrder: 8,
            },
          },
          {
            key: 'SCHEDULE_TIMES',
            value: '18:00',
            rawValueExists: true,
            isMasked: false,
            schema: {
              key: 'SCHEDULE_TIMES',
              category: 'system',
              dataType: 'string',
              uiControl: 'text',
              isSensitive: false,
              isRequired: false,
              isEditable: true,
              options: [],
              validation: {},
              displayOrder: 11,
            },
          },
        ],
      },
    }));
    render(<SettingsPage />);

    const enabledCheckbox = await screen.findByTestId('scheduler-enabled-checkbox');
    expect(enabledCheckbox).toBeChecked();

    fireEvent.click(enabledCheckbox);

    expect(setDraftValue).toHaveBeenCalledWith('SCHEDULE_ENABLED', 'false');
    await waitFor(() => expect(screen.getByTestId('scheduler-enabled-checkbox')).not.toBeChecked());

    const refreshButton = screen.getByTestId('scheduler-refresh-status-button');
    fireEvent.click(refreshButton);
    await waitFor(() => expect(screen.getByTestId('scheduler-enabled-checkbox')).not.toBeChecked());
  });

  it('can reconcile runtime scheduler state when runtime is enabled but saved value is disabled', async () => {
    save.mockResolvedValue({ success: true });
    getChangedItems.mockReturnValue([]);
    const configState = buildSystemConfigState();
    getSchedulerStatus.mockResolvedValueOnce({
      enabled: true,
      running: false,
      scheduleTimes: ['18:00'],
      nextRunAt: null,
      lastRunAt: null,
      lastSuccessAt: null,
      lastError: null,
    });
    useSystemConfigMock.mockReturnValue(buildSystemConfigState({
      activeCategory: 'system',
      hasDirty: false,
      dirtyCount: 0,
      getChangedItems: () => [],
      itemsByCategory: {
        ...configState.itemsByCategory,
        system: [
          ...configState.itemsByCategory.system,
          {
            key: 'SCHEDULE_ENABLED',
            value: 'false',
            rawValueExists: true,
            isMasked: false,
            schema: {
              key: 'SCHEDULE_ENABLED',
              category: 'system',
              dataType: 'boolean',
              uiControl: 'switch',
              isSensitive: false,
              isRequired: false,
              isEditable: true,
              options: [],
              validation: {},
              displayOrder: 8,
            },
          },
          {
            key: 'SCHEDULE_TIMES',
            value: '18:00',
            rawValueExists: true,
            isMasked: false,
            schema: {
              key: 'SCHEDULE_TIMES',
              category: 'system',
              dataType: 'string',
              uiControl: 'text',
              isSensitive: false,
              isEditable: true,
              options: [],
              validation: {},
              displayOrder: 11,
            },
          },
        ],
      },
    }));

    render(<SettingsPage />);

    const saveButton = screen.getByRole('button', { name: /\u4fdd\u5b58\u914d\u7f6e/ });
    expect(saveButton).toBeDisabled();

    const enabledCheckbox = await screen.findByTestId('scheduler-enabled-checkbox');
    expect(enabledCheckbox).toBeChecked();
    fireEvent.click(enabledCheckbox);

    await waitFor(() => expect(enabledCheckbox).not.toBeChecked());
    await waitFor(() => expect(saveButton).toBeEnabled());
    await waitFor(() => expect(saveButton).toHaveTextContent('\u4fdd\u5b58\u914d\u7f6e (1)'));

    fireEvent.click(saveButton);
    await waitFor(() => expect(save).toHaveBeenCalledWith([{ key: 'SCHEDULE_ENABLED', value: 'false' }]));
  });

  it('can reconcile runtime scheduler state when runtime is disabled but saved value is enabled', async () => {
    save.mockResolvedValue({ success: true });
    getChangedItems.mockReturnValue([]);
    const configState = buildSystemConfigState();
    getSchedulerStatus.mockResolvedValueOnce({
      enabled: false,
      running: false,
      scheduleTimes: ['18:00'],
      nextRunAt: null,
      lastRunAt: null,
      lastSuccessAt: null,
      lastError: null,
    });
    useSystemConfigMock.mockReturnValue(buildSystemConfigState({
      activeCategory: 'system',
      hasDirty: false,
      dirtyCount: 0,
      getChangedItems: () => [],
      itemsByCategory: {
        ...configState.itemsByCategory,
        system: [
          ...configState.itemsByCategory.system,
          {
            key: 'SCHEDULE_ENABLED',
            value: 'true',
            rawValueExists: true,
            isMasked: false,
            schema: {
              key: 'SCHEDULE_ENABLED',
              category: 'system',
              dataType: 'boolean',
              uiControl: 'switch',
              isSensitive: false,
              isRequired: false,
              isEditable: true,
              options: [],
              validation: {},
              displayOrder: 8,
            },
          },
          {
            key: 'SCHEDULE_TIMES',
            value: '18:00',
            rawValueExists: true,
            isMasked: false,
            schema: {
              key: 'SCHEDULE_TIMES',
              category: 'system',
              dataType: 'string',
              uiControl: 'text',
              isSensitive: false,
              isEditable: true,
              options: [],
              validation: {},
              displayOrder: 11,
            },
          },
        ],
      },
    }));

    render(<SettingsPage />);

    const saveButton = screen.getByRole('button', { name: /\u4fdd\u5b58\u914d\u7f6e/ });
    expect(saveButton).toBeDisabled();

    const enabledCheckbox = await screen.findByTestId('scheduler-enabled-checkbox');
    expect(enabledCheckbox).not.toBeChecked();
    fireEvent.click(enabledCheckbox);

    await waitFor(() => expect(enabledCheckbox).toBeChecked());
    await waitFor(() => expect(saveButton).toBeEnabled());
    await waitFor(() => expect(saveButton).toHaveTextContent('\u4fdd\u5b58\u914d\u7f6e (1)'));

    fireEvent.click(saveButton);
    await waitFor(() => expect(save).toHaveBeenCalledWith([{ key: 'SCHEDULE_ENABLED', value: 'true' }]));
  });

  it('refreshes scheduler status after saving scheduler settings', async () => {
    const configState = buildSystemConfigState();
    getSchedulerStatus
      .mockResolvedValueOnce({
        enabled: false,
        running: false,
        scheduleTimes: [],
        nextRunAt: null,
        lastRunAt: null,
        lastSuccessAt: null,
        lastError: null,
      })
      .mockResolvedValueOnce({
        enabled: true,
        running: false,
        scheduleTimes: ['09:20', '15:10'],
        nextRunAt: '2026-06-21T09:20:00+08:00',
        lastRunAt: null,
        lastSuccessAt: null,
        lastError: null,
      });
    save.mockResolvedValue({ success: true });
    useSystemConfigMock.mockReturnValue(buildSystemConfigState({
      activeCategory: 'system',
      hasDirty: true,
      dirtyCount: 1,
      getChangedItems: () => [{ key: 'SCHEDULE_ENABLED', value: 'true' }],
      itemsByCategory: {
        ...configState.itemsByCategory,
        system: [
          ...configState.itemsByCategory.system,
          {
            key: 'SCHEDULE_ENABLED',
            value: 'false',
            rawValueExists: true,
            isMasked: false,
            schema: {
              key: 'SCHEDULE_ENABLED',
              category: 'system',
              dataType: 'boolean',
              uiControl: 'switch',
              isSensitive: false,
              isRequired: false,
              isEditable: true,
              options: [],
              validation: {},
              displayOrder: 8,
            },
          },
          {
            key: 'SCHEDULE_TIMES',
            value: '09:20,15:10',
            rawValueExists: true,
            isMasked: false,
            schema: {
              key: 'SCHEDULE_TIMES',
              category: 'system',
              dataType: 'string',
              uiControl: 'text',
              isSensitive: false,
              isRequired: false,
              isEditable: true,
              options: [],
              validation: {},
              displayOrder: 11,
            },
          },
        ],
      },
    }));

    render(<SettingsPage />);

    expect(await screen.findByText('\u672a\u542f\u7528')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: '\u4fdd\u5b58\u914d\u7f6e (1)' }));

    await waitFor(() => expect(getSchedulerStatus).toHaveBeenCalledTimes(2));
    expect(await screen.findByText('\u5df2\u542f\u7528')).toBeInTheDocument();
  });

  it('refreshes AlphaSift state when the enable flow fails', async () => {
    const configState = buildSystemConfigState();
    alphasiftEnable.mockRejectedValueOnce(new Error('config update failed'));
    useSystemConfigMock.mockReturnValue(buildSystemConfigState({
      activeCategory: 'data_source',
      itemsByCategory: {
        ...configState.itemsByCategory,
        data_source: [
          {
            key: 'ALPHASIFT_ENABLED',
            value: 'false',
            rawValueExists: true,
            isMasked: false,
            schema: {
              key: 'ALPHASIFT_ENABLED',
              category: 'data_source',
              dataType: 'boolean',
              uiControl: 'switch',
              isSensitive: false,
              isRequired: false,
              isEditable: true,
              options: [],
              validation: {},
              displayOrder: 16,
            },
          },
        ],
      },
    }));

    render(<SettingsPage />);

    fireEvent.click(screen.getByRole('button', { name: '\u5f00\u542f\u9009\u80a1' }));

    await waitFor(() => expect(alphasiftEnable).toHaveBeenCalledTimes(1));
    expect(updateSystemConfig).not.toHaveBeenCalled();
    expect(alphasiftInstall).not.toHaveBeenCalled();
    expect(refreshAfterExternalSave).toHaveBeenCalledWith(['ALPHASIFT_ENABLED']);
  });

  it('passes LLM channel support keys to the channel editor without rendering them as generic fields', async () => {
    useSystemConfigMock.mockReturnValue(buildSystemConfigState({
      activeCategory: 'ai_model',
      itemsByCategory: {
        ...buildSystemConfigState().itemsByCategory,
        ai_model: [
          {
            key: 'LLM_CHANNELS',
            value: 'my_proxy',
            rawValueExists: true,
            isMasked: false,
            schema: {
              key: 'LLM_CHANNELS',
              category: 'ai_model',
              dataType: 'string',
              uiControl: 'textarea',
              isSensitive: false,
              isRequired: false,
              isEditable: true,
              options: [],
              validation: {},
              displayOrder: 1,
            },
          },
          {
            key: 'LITELLM_MODEL',
            value: 'gpt-5.0',
            rawValueExists: true,
            isMasked: false,
            schema: {
              key: 'LITELLM_MODEL',
              category: 'ai_model',
              dataType: 'string',
              uiControl: 'text',
              isSensitive: false,
              isRequired: false,
              isEditable: true,
              options: [],
              validation: {},
              displayOrder: 2,
            },
          },
          {
            key: 'OPENAI_BASE_URL',
            value: 'https://api.openai.com/v1',
            rawValueExists: true,
            isMasked: false,
            schema: {
              key: 'OPENAI_BASE_URL',
              category: 'ai_model',
              dataType: 'string',
              uiControl: 'text',
              isSensitive: false,
              isRequired: false,
              isEditable: true,
              options: [],
              validation: {},
              displayOrder: 3,
            },
          },
          {
            key: 'OPENAI_MODEL',
            value: 'gpt-5.0',
            rawValueExists: true,
            isMasked: false,
            schema: {
              key: 'OPENAI_MODEL',
              category: 'ai_model',
              isMasked: false,
              dataType: 'string',
              uiControl: 'text',
              isRequired: false,
              isEditable: true,
              options: [],
              validation: {},
              displayOrder: 4,
            },
          },
          {
            key: 'LLM_MY_PROXY_API_KEY',
            value: 'sk-test',
            rawValueExists: true,
            isMasked: false,
            schema: {
              key: 'LLM_MY_PROXY_API_KEY',
              category: 'ai_model',
              dataType: 'string',
              uiControl: 'password',
              isSensitive: true,
              isRequired: false,
              isEditable: true,
              options: [],
              validation: {},
              displayOrder: 9000,
            },
          },
          {
            key: 'LLM_MY_PROXY_MODELS',
            value: 'gpt-5.5',
            rawValueExists: true,
            isMasked: false,
            schema: {
              key: 'LLM_MY_PROXY_MODELS',
              category: 'ai_model',
              dataType: 'string',
              uiControl: 'text',
              isSensitive: false,
              isRequired: false,
              isEditable: true,
              options: [],
              validation: {},
              displayOrder: 9000,
            },
          },
        ],
      },
    }));

    render(<SettingsPage />);

    const llmEditorItems = await screen.findByTestId('llm-channel-editor-items');
    expect(llmEditorItems).toHaveTextContent('LLM_CHANNELS');
    expect(llmEditorItems).toHaveTextContent('LITELLM_MODEL');
    expect(llmEditorItems).toHaveTextContent('OPENAI_BASE_URL');
    expect(llmEditorItems).toHaveTextContent('OPENAI_MODEL');
    expect(llmEditorItems).toHaveTextContent('LLM_MY_PROXY_API_KEY');
    expect(llmEditorItems).toHaveTextContent('LLM_MY_PROXY_MODELS');
    expect(screen.queryByTestId('settings-field-LITELLM_MODEL')).not.toBeInTheDocument();
    expect(screen.queryByTestId('settings-field-OPENAI_BASE_URL')).not.toBeInTheDocument();
    expect(screen.queryByTestId('settings-field-OPENAI_MODEL')).not.toBeInTheDocument();
    expect(screen.queryByTestId('settings-field-LLM_MY_PROXY_API_KEY')).not.toBeInTheDocument();
    expect(screen.queryByTestId('settings-field-LLM_MY_PROXY_MODELS')).not.toBeInTheDocument();
  });

  it('renders notification test panel before notification fields', () => {
    useSystemConfigMock.mockReturnValue(buildSystemConfigState({ activeCategory: 'notification' }));

    render(<SettingsPage />);

    expect(screen.getByText('\u901a\u77e5\u6d4b\u8bd5\u9762\u677f:WECHAT_WEBHOOK_URL')).toBeInTheDocument();
    expect(screen.getByText('WECHAT_WEBHOOK_URL')).toBeInTheDocument();
    expect(settingsPanelErrorBoundary).toHaveBeenCalledWith('\u901a\u77e5\u6d4b\u8bd5');
    expect(settingsPanelErrorBoundary).toHaveBeenCalledWith('\u901a\u77e5\u8bbe\u7f6e');
  });

  it('uses browser and backend logs in settings panel diagnostic hints outside desktop runtime', () => {
    useSystemConfigMock.mockReturnValue(buildSystemConfigState({ activeCategory: 'notification' }));

    render(<SettingsPage />);

    expect(screen.getAllByText(/\u6d4f\u89c8\u5668\u5f00\u53d1\u8005\u5de5\u5177\u63a7\u5236\u53f0\u4e0e\u540e\u7aef\u65e5\u5fd7/)).toHaveLength(2);
    expect(screen.queryByText('desktop.log')).not.toBeInTheDocument();
  });

  it('uses desktop log in settings panel diagnostic hints during desktop runtime', () => {
    useSystemConfigMock.mockReturnValue(buildSystemConfigState({ activeCategory: 'notification' }));
    (window as { dsaDesktop?: unknown }).dsaDesktop = createDesktopRuntime();

    render(<SettingsPage />);

    expect(screen.getAllByText('desktop.log')).toHaveLength(2);
    expect(screen.queryByText(/\u6d4f\u89c8\u5668\u5f00\u53d1\u8005\u5de5\u5177\u63a7\u5236\u53f0\u4e0e\u540e\u7aef\u65e5\u5fd7/)).not.toBeInTheDocument();
  });

  it('renders env backup actions outside desktop runtime', () => {
    render(<SettingsPage />);

    expect(screen.getByRole('heading', { name: '\u914d\u7f6e\u5907\u4efd' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '\u5bfc\u51fa .env' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '\u5bfc\u5165 .env' })).toBeInTheDocument();
    expect(screen.getByText(/Docker \u90e8\u7f72\u4e2d/)).toHaveTextContent('ENV_FILE');
  });

  it('disables env backup actions when web auth is not enabled', () => {
    useAuthMock.mockReturnValue({
      authEnabled: false,
      passwordChangeable: false,
      refreshStatus,
    });

    render(<SettingsPage />);

    expect(screen.getByText(/\u5f53\u524d Web \u7aef\u672a\u5f00\u542f\u7ba1\u7406\u5458\u9274\u6743/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '\u5bfc\u51fa .env' })).toBeDisabled();
    expect(screen.getByRole('button', { name: '\u5bfc\u5165 .env' })).toBeDisabled();
  });

  it('uses live auth state for env backup availability instead of loaded config items', () => {
    const configState = buildSystemConfigState();
    useSystemConfigMock.mockReturnValue(buildSystemConfigState({
      itemsByCategory: {
        ...configState.itemsByCategory,
        system: configState.itemsByCategory.system.map((item) => (
          item.key === 'ADMIN_AUTH_ENABLED' ? { ...item, value: 'false' } : item
        )),
      },
    }));
    useAuthMock.mockReturnValue({
      authEnabled: true,
      passwordChangeable: true,
      refreshStatus,
    });

    render(<SettingsPage />);

    expect(screen.queryByText(/\u5f53\u524d Web \u7aef\u672a\u5f00\u542f\u7ba1\u7406\u5458\u9274\u6743/)).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: '\u5bfc\u51fa .env' })).not.toBeDisabled();
    expect(screen.getByRole('button', { name: '\u5bfc\u5165 .env' })).not.toBeDisabled();
  });

  it('exports saved env from config backup actions', async () => {
    (window as { dsaDesktop?: unknown }).dsaDesktop = { version: '3.12.0' };

    render(<SettingsPage />);

    vi.clearAllMocks();

    fireEvent.click(screen.getByRole('button', { name: '\u5bfc\u51fa .env' }));

    await waitFor(() => expect(exportEnv).toHaveBeenCalledTimes(1));
    expect(mockedAnchorClick).toHaveBeenCalledTimes(1);
    expect(load).not.toHaveBeenCalled();
  });

  it('asks for confirmation before importing when local drafts exist', async () => {
    (window as { dsaDesktop?: unknown }).dsaDesktop = { version: '3.12.0' };
    useSystemConfigMock.mockReturnValue(buildSystemConfigState({ hasDirty: true, dirtyCount: 2 }));

    render(<SettingsPage />);

    vi.clearAllMocks();

    fireEvent.click(screen.getByRole('button', { name: '\u5bfc\u5165 .env' }));

    expect(await screen.findByText('\u5bfc\u5165\u4f1a\u8986\u76d6\u5f53\u524d\u8349\u7a3f')).toBeInTheDocument();
    expect(importEnv).not.toHaveBeenCalled();
  });

  it('reloads config after successful env import', async () => {
    (window as { dsaDesktop?: unknown }).dsaDesktop = { version: '3.12.0' };

    const { container } = render(<SettingsPage />);

    vi.clearAllMocks();

    const input = container.querySelector('input[type="file"]');
    expect(input).not.toBeNull();

    fireEvent.change(input as HTMLInputElement, {
      target: {
        files: [new File(['STOCK_LIST=300750\n'], 'desktop-backup.env', { type: 'text/plain' })],
      },
    });

    await waitFor(() => expect(importEnv).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(load).toHaveBeenCalledTimes(1));
  });

  it('refreshes scheduler status after successful env import updates scheduler settings', async () => {
    (window as { dsaDesktop?: unknown }).dsaDesktop = { version: '3.12.0' };
    const configState = buildSystemConfigState();
    getSchedulerStatus
      .mockResolvedValueOnce({
        enabled: false,
        running: false,
        scheduleTimes: ['18:00'],
        nextRunAt: null,
        lastRunAt: null,
        lastSuccessAt: null,
        lastError: null,
      })
      .mockResolvedValueOnce({
        enabled: true,
        running: false,
        scheduleTimes: ['09:20', '15:10'],
        nextRunAt: '2026-06-21T09:20:00+08:00',
        lastRunAt: null,
        lastSuccessAt: null,
        lastError: null,
      });
    importEnv.mockResolvedValueOnce({
      success: true,
      configVersion: 'v2',
      appliedCount: 2,
      skippedMaskedCount: 0,
      reloadTriggered: true,
      updatedKeys: ['SCHEDULE_ENABLED', 'SCHEDULE_TIMES'],
      warnings: [],
    });
    useSystemConfigMock.mockReturnValue(buildSystemConfigState({
      activeCategory: 'system',
      itemsByCategory: {
        ...configState.itemsByCategory,
        system: [
          ...configState.itemsByCategory.system,
          {
            key: 'SCHEDULE_ENABLED',
            value: 'false',
            rawValueExists: true,
            isMasked: false,
            schema: {
              key: 'SCHEDULE_ENABLED',
              category: 'system',
              dataType: 'boolean',
              uiControl: 'switch',
              isSensitive: false,
              isRequired: false,
              isEditable: true,
              options: [],
              validation: {},
              displayOrder: 8,
            },
          },
          {
            key: 'SCHEDULE_TIMES',
            value: '18:00',
            rawValueExists: true,
            isMasked: false,
            schema: {
              key: 'SCHEDULE_TIMES',
              category: 'system',
              dataType: 'string',
              uiControl: 'text',
              isSensitive: false,
              isRequired: false,
              isEditable: true,
              options: [],
              validation: {},
              displayOrder: 11,
            },
          },
        ],
      },
    }));

    const { container } = render(<SettingsPage />);

    await waitFor(() => expect(getSchedulerStatus).toHaveBeenCalledTimes(1));
    expect(await screen.findByText('\u672a\u542f\u7528')).toBeInTheDocument();

    vi.clearAllMocks();

    const input = container.querySelector('input[type="file"]');
    expect(input).not.toBeNull();

    fireEvent.change(input as HTMLInputElement, {
      target: {
        files: [new File(['SCHEDULE_ENABLED=true\nSCHEDULE_TIMES=09:20,15:10\n'], 'desktop-backup.env', { type: 'text/plain' })],
      },
    });

    await waitFor(() => expect(importEnv).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(load).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(getSchedulerStatus).toHaveBeenCalledTimes(1));
    expect(await screen.findByText('\u5df2\u542f\u7528')).toBeInTheDocument();
  });

  it('shows an error when env import succeeds but reload fails', async () => {
    (window as { dsaDesktop?: unknown }).dsaDesktop = { version: '3.12.0' };
    load.mockResolvedValue(false);

    const { container } = render(<SettingsPage />);

    vi.clearAllMocks();
    load.mockResolvedValue(false);

    const input = container.querySelector('input[type="file"]');
    expect(input).not.toBeNull();

    fireEvent.change(input as HTMLInputElement, {
      target: {
        files: [new File(['STOCK_LIST=300750\n'], 'desktop-backup.env', { type: 'text/plain' })],
      },
    });

    await waitFor(() => expect(importEnv).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(load).toHaveBeenCalledTimes(1));
    expect(screen.getByText('\u914d\u7f6e\u5df2\u5bfc\u5165\u4f46\u5237\u65b0\u5931\u8d25')).toBeInTheDocument();
    expect(screen.getByText('\u5907\u4efd\u5df2\u5bfc\u5165，\u4f46\u91cd\u65b0\u52a0\u8f7d\u914d\u7f6e\u5931\u8d25，\u8bf7\u624b\u52a8\u91cd\u8f7d\u9875\u9762。')).toBeInTheDocument();
    expect(screen.queryByText('\u5df2\u5bfc\u5165 .env \u5907\u4efd\u5e76\u91cd\u65b0\u52a0\u8f7d\u914d\u7f6e。')).not.toBeInTheDocument();
  });

  it('renders desktop update notice when a newer release is available', async () => {
    desktopGetUpdateState.mockResolvedValue({
      status: 'update-available',
      currentVersion: '3.12.0',
      latestVersion: '3.13.0',
      releaseUrl: 'https://github.com/ZhuLinsen/daily_stock_analysis/releases/tag/v3.13.0',
      message: '\u53d1\u73b0\u65b0\u7248\u672c 3.13.0，\u53ef\u524d\u5f80 GitHub Releases \u4e0b\u8f7d\u66f4\u65b0。',
    });
    (window as { dsaDesktop?: unknown }).dsaDesktop = createDesktopRuntime();

    render(<SettingsPage />);

    expect(await screen.findByText(/\u53d1\u73b0\u65b0\u7248\u672c:\u5f53\u524d 3\.12\.0，\u6700\u65b0 3\.13\.0/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '\u524d\u5f80\u4e0b\u8f7d' })).toBeInTheDocument();
  });

  it('checks desktop updates on demand and renders the latest-version state', async () => {
    (window as { dsaDesktop?: unknown }).dsaDesktop = createDesktopRuntime();

    render(<SettingsPage />);

    fireEvent.click(await screen.findByRole('button', { name: '\u68c0\u67e5\u66f4\u65b0' }));

    await waitFor(() => expect(desktopCheckForUpdates).toHaveBeenCalledTimes(1));
    expect(await screen.findByText('\u5df2\u662f\u6700\u65b0\u7248\u672c:\u5f53\u524d\u684c\u9762\u7aef\u5df2\u662f\u6700\u65b0\u7248\u672c。')).toBeInTheDocument();
  });

  it('opens GitHub release page from desktop update notice', async () => {
    desktopGetUpdateState.mockResolvedValue({
      status: 'update-available',
      currentVersion: '3.12.0',
      latestVersion: '3.13.0',
      releaseUrl: 'https://github.com/ZhuLinsen/daily_stock_analysis/releases/tag/v3.13.0',
      message: '\u53d1\u73b0\u65b0\u7248\u672c 3.13.0，\u53ef\u524d\u5f80 GitHub Releases \u4e0b\u8f7d\u66f4\u65b0。',
    });
    (window as { dsaDesktop?: unknown }).dsaDesktop = createDesktopRuntime();

    render(<SettingsPage />);

    fireEvent.click(await screen.findByRole('button', { name: '\u524d\u5f80\u4e0b\u8f7d' }));

    await waitFor(() => {
      expect(desktopOpenReleasePage).toHaveBeenCalledWith(
        'https://github.com/ZhuLinsen/daily_stock_analysis/releases/tag/v3.13.0'
      );
    });
  });

  it('renders downloaded desktop update and starts install on demand', async () => {
    desktopGetUpdateState.mockResolvedValue({
      status: 'update-downloaded',
      updateMode: 'auto',
      currentVersion: '3.12.0',
      latestVersion: '3.13.0',
      releaseUrl: 'https://github.com/ZhuLinsen/daily_stock_analysis/releases/tag/v3.13.0',
      message: '\u65b0\u7248\u672c 3.13.0 \u5df2\u4e0b\u8f7d，\u53ef\u91cd\u542f\u5e94\u7528\u5b8c\u6210\u5b89\u88c5。',
      downloadPercent: 100,
    });
    (window as { dsaDesktop?: unknown }).dsaDesktop = createDesktopRuntime();

    render(<SettingsPage />);

    expect(await screen.findByText('\u66f4\u65b0\u5df2\u4e0b\u8f7d:\u65b0\u7248\u672c 3.13.0 \u5df2\u4e0b\u8f7d，\u53ef\u91cd\u542f\u5e94\u7528\u5b8c\u6210\u5b89\u88c5。')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: '\u91cd\u542f\u5b89\u88c5' }));

    await waitFor(() => expect(desktopInstallDownloadedUpdate).toHaveBeenCalledTimes(1));
  });
});
