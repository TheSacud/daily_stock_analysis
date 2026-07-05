import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { createMemoryRouter, MemoryRouter, RouterProvider } from 'react-router-dom';
import { beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';
import { createParsedApiError } from '../../api/error';
import { historyApi } from '../../api/history';
import type { Message, ProgressStep } from '../../stores/agentChatStore';
import ChatPage from '../ChatPage';
import { extractStockCodeFromMessage, extractStockCodesFromMessage } from '../../utils/chatStockCode';

function createDeferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

const {
  mockGetSkills,
  mockDeleteChatSession,
  mockSendChat,
  mockGetSystemConfig,
  mockUpdateSystemConfig,
  mockGetWatchlist,
  mockAddToWatchlist,
  mockRemoveFromWatchlist,
  mockDownloadSession,
  mockFormatSessionAsMarkdown,
} = vi.hoisted(() => ({
  mockGetSkills: vi.fn(),
  mockDeleteChatSession: vi.fn(),
  mockSendChat: vi.fn(),
  mockGetSystemConfig: vi.fn(),
  mockUpdateSystemConfig: vi.fn(),
  mockGetWatchlist: vi.fn(),
  mockAddToWatchlist: vi.fn(),
  mockRemoveFromWatchlist: vi.fn(),
  mockDownloadSession: vi.fn(),
  mockFormatSessionAsMarkdown: vi.fn(),
}));

const mockLoadSessions = vi.fn();
const mockLoadInitialSession = vi.fn();
const mockSwitchSession = vi.fn();
const mockStartStream = vi.fn();
const mockClearCompletionBadge = vi.fn();
const mockStartNewChat = vi.fn();

const mockStoreState = {
  messages: [] as Message[],
  loading: false,
  progressSteps: [] as ProgressStep[],
  sessionId: 'session-1',
  sessions: [
    {
      session_id: 'session-1',
      title: '\u8bf7\u7b80\u8981\u5206\u6790 600519',
      message_count: 2,
      created_at: '2026-03-15T09:00:00Z',
      last_active: '2026-03-15T09:05:00Z',
    },
  ],
  sessionsLoading: false,
  chatError: null,
  loadSessions: mockLoadSessions,
  loadInitialSession: mockLoadInitialSession,
  switchSession: mockSwitchSession,
  startStream: mockStartStream,
  clearCompletionBadge: mockClearCompletionBadge,
};

vi.mock('../../api/agent', () => ({
  agentApi: {
    getSkills: mockGetSkills,
    deleteChatSession: mockDeleteChatSession,
    sendChat: mockSendChat,
  },
}));

vi.mock('../../api/systemConfig', () => ({
  systemConfigApi: {
    getConfig: mockGetSystemConfig,
    update: mockUpdateSystemConfig,
    getWatchlist: mockGetWatchlist,
    addToWatchlist: mockAddToWatchlist,
    removeFromWatchlist: mockRemoveFromWatchlist,
  },
}));

vi.mock('../../utils/chatExport', () => ({
  downloadSession: mockDownloadSession,
  formatSessionAsMarkdown: mockFormatSessionAsMarkdown,
}));

vi.mock('../../api/history', () => ({
  historyApi: {
    getDetail: vi.fn().mockResolvedValue({}),
  },
}));

vi.mock('../../stores/agentChatStore', () => {
  const useAgentChatStore = (
    selector?: (state: typeof mockStoreState) => unknown
  ) => (typeof selector === 'function' ? selector(mockStoreState) : mockStoreState);

  useAgentChatStore.getState = () => ({
    startNewChat: mockStartNewChat,
  });

  return { useAgentChatStore };
});

beforeAll(() => {
  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    value: vi.fn().mockImplementation((query: string) => ({
      matches: query === '(prefers-color-scheme: dark)',
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  });

  Object.defineProperty(window, 'requestAnimationFrame', {
    writable: true,
    value: (callback: FrameRequestCallback) => window.setTimeout(() => callback(0), 0),
  });

  Object.defineProperty(window, 'cancelAnimationFrame', {
    writable: true,
    value: (handle: number) => window.clearTimeout(handle),
  });

  Object.defineProperty(HTMLElement.prototype, 'scrollIntoView', {
    writable: true,
    value: vi.fn(),
  });
});

beforeEach(() => {
  vi.clearAllMocks();
  mockStoreState.messages = [];
  mockStoreState.loading = false;
  mockStoreState.progressSteps = [];
  mockStoreState.chatError = null;
  mockStoreState.sessionsLoading = false;
  mockStoreState.sessionId = 'session-1';
  mockStoreState.sessions = [
    {
      session_id: 'session-1',
      title: '\u8bf7\u7b80\u8981\u5206\u6790 600519',
      message_count: 2,
      created_at: '2026-03-15T09:00:00Z',
      last_active: '2026-03-15T09:05:00Z',
    },
  ];
  mockGetSkills.mockResolvedValue({
    skills: [
      { id: 'bull_trend', name: '\u8d8b\u52bf\u5206\u6790', description: '\u6d4b\u8bd5\u6280\u80fd' },
    ],
    default_skill_id: 'bull_trend',
  });
  mockDeleteChatSession.mockResolvedValue(undefined);
  mockSendChat.mockResolvedValue({ success: true });
  mockGetWatchlist.mockResolvedValue([]);
  mockGetSystemConfig.mockResolvedValue({
    configVersion: 'cfg-v1',
    maskToken: 'mask-token',
    items: [
      {
        key: 'AGENT_CONTEXT_COMPRESSION_ENABLED',
        value: 'false',
        rawValueExists: true,
        isMasked: false,
      },
    ],
  });
  mockUpdateSystemConfig.mockResolvedValue({
    success: true,
    configVersion: 'cfg-v2',
    appliedCount: 1,
    skippedMaskedCount: 0,
    reloadTriggered: true,
    updatedKeys: ['AGENT_CONTEXT_COMPRESSION_ENABLED'],
    warnings: [],
  });
  mockDownloadSession.mockImplementation(() => {});
  mockFormatSessionAsMarkdown.mockReturnValue('# exported session');
});

describe('ChatPage', () => {
  it('renders a fixed workspace shell with independent session and message viewports', async () => {
    render(
      <MemoryRouter initialEntries={['/chat']}>
        <ChatPage />
      </MemoryRouter>
    );

    expect(await screen.findByTestId('chat-workspace')).toBeInTheDocument();
    expect(screen.getByTestId('chat-session-list-scroll')).toBeInTheDocument();
    expect(screen.getByTestId('chat-message-scroll')).toBeInTheDocument();
    expect(mockLoadInitialSession).toHaveBeenCalled();
    expect(mockClearCompletionBadge).toHaveBeenCalled();
  });

  it('loads and saves the global context compression setting from the chat input area', async () => {
    render(
      <MemoryRouter initialEntries={['/chat']}>
        <ChatPage />
      </MemoryRouter>
    );

    const compressionToggle = await screen.findByRole('checkbox', { name: /\u4e0a\u4e0b\u6587\u538b\u7f29/ });

    await waitFor(() => {
      expect(compressionToggle).not.toBeDisabled();
    });

    expect(compressionToggle).not.toBeChecked();

    fireEvent.click(compressionToggle);

    await waitFor(() => {
      expect(mockUpdateSystemConfig).toHaveBeenCalledWith({
        configVersion: 'cfg-v1',
        maskToken: 'mask-token',
        reloadNow: true,
        items: [
          {
            key: 'AGENT_CONTEXT_COMPRESSION_ENABLED',
            value: 'true',
          },
        ],
      });
    });

    expect(compressionToggle).toBeChecked();
    expect(screen.getByText('\u5df2\u542f\u7528')).toBeInTheDocument();
  });

  it('rolls back the context compression switch when saving fails', async () => {
    mockGetSystemConfig.mockResolvedValue({
      configVersion: 'cfg-v1',
      maskToken: 'mask-token',
      items: [
        {
          key: 'AGENT_CONTEXT_COMPRESSION_ENABLED',
          value: 'true',
          rawValueExists: true,
          isMasked: false,
        },
      ],
    });
    mockUpdateSystemConfig.mockRejectedValue(
      createParsedApiError({
        title: '\u4fdd\u5b58\u5931\u8d25',
        message: '\u914d\u7f6e\u670d\u52a1\u4e0d\u53ef\u7528',
        category: 'unknown',
      }),
    );

    render(
      <MemoryRouter initialEntries={['/chat']}>
        <ChatPage />
      </MemoryRouter>
    );

    const compressionToggle = await screen.findByRole('checkbox', { name: /\u4e0a\u4e0b\u6587\u538b\u7f29/ });

    await waitFor(() => {
      expect(compressionToggle).toBeChecked();
      expect(compressionToggle).not.toBeDisabled();
    });

    fireEvent.click(compressionToggle);

    await waitFor(() => {
      expect(mockUpdateSystemConfig).toHaveBeenCalledWith(expect.objectContaining({
        items: [
          {
            key: 'AGENT_CONTEXT_COMPRESSION_ENABLED',
            value: 'false',
          },
        ],
      }));
      expect(compressionToggle).toBeChecked();
    });
    expect(screen.getByText('\u914d\u7f6e\u670d\u52a1\u4e0d\u53ef\u7528')).toBeInTheDocument();
  });

  it('does not switch when clicking the current session card', async () => {
    render(
      <MemoryRouter initialEntries={['/chat']}>
        <ChatPage />
      </MemoryRouter>
    );

    const sessionCard = await screen.findByRole('button', {
      name: /\u5207\u6362\u5230\u5bf9\u8bdd \u8bf7\u7b80\u8981\u5206\u6790 600519/,
    });

    fireEvent.click(sessionCard);
    expect(mockSwitchSession).not.toHaveBeenCalled();
    expect(sessionCard).toHaveAttribute('aria-current', 'page');
  });

  it('renders a separate delete button for each session and opens confirmation without switching', async () => {
    render(
      <MemoryRouter initialEntries={['/chat']}>
        <ChatPage />
      </MemoryRouter>
    );

    const deleteButton = await screen.findByRole('button', {
      name: /\u5220\u9664\u5bf9\u8bdd \u8bf7\u7b80\u8981\u5206\u6790 600519/,
    });

    fireEvent.click(deleteButton);

    expect(mockSwitchSession).not.toHaveBeenCalled();
    expect(await screen.findByText('\u5220\u9664\u540e，\u8be5\u5bf9\u8bdd\u5c06\u4e0d\u53ef\u6062\u590d，\u786e\u8ba4\u5220\u9664\u5417？')).toBeInTheDocument();
  });

  it('hides header actions when there are no messages', async () => {
    render(
      <MemoryRouter initialEntries={['/chat']}>
        <ChatPage />
      </MemoryRouter>
    );

    expect(await screen.findByRole('heading', { name: '\u95ee\u80a1' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '\u5bfc\u51fa\u4f1a\u8bdd' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '\u53d1\u9001\u5230\u5df2\u914d\u7f6e\u7684\u901a\u77e5\u673a\u5668\u4eba/\u90ae\u7bb1' })).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: '\u5386\u53f2\u5bf9\u8bdd' })).toBeInTheDocument();
  });

  it('exports the current session from the header action', async () => {
    mockStoreState.messages = [
      { id: 'user-1', role: 'user', content: '\u8bf7\u5206\u6790 600519' },
      { id: 'assistant-1', role: 'assistant', content: '\u8d8b\u52bf\u504f\u5f3a', skillName: '\u8d8b\u52bf\u5206\u6790' },
    ];

    render(
      <MemoryRouter initialEntries={['/chat']}>
        <ChatPage />
      </MemoryRouter>
    );

    fireEvent.click(await screen.findByRole('button', { name: '\u5bfc\u51fa\u4f1a\u8bdd\u4e3a Markdown \u6587\u4ef6' }));

    expect(mockDownloadSession).toHaveBeenCalledWith(mockStoreState.messages);
    expect(mockFormatSessionAsMarkdown).not.toHaveBeenCalled();
  });

  it('renders assistant skill labels with shared badge semantics', async () => {
    mockStoreState.messages = [
      { id: 'assistant-1', role: 'assistant', content: '\u8d8b\u52bf\u504f\u5f3a', skillName: '\u8d8b\u52bf\u5206\u6790' },
    ];

    render(
      <MemoryRouter initialEntries={['/chat']}>
        <ChatPage />
      </MemoryRouter>
    );

    const skillBadge = await screen.findByLabelText('\u6280\u80fd \u8d8b\u52bf\u5206\u6790');
    expect(skillBadge).toBeInTheDocument();
    expect(skillBadge).toHaveTextContent('\u8d8b\u52bf\u5206\u6790');
  });

  it('renders assistant multi-skill labels with shared badge semantics', async () => {
    mockStoreState.messages = [
      {
        id: 'assistant-1',
        role: 'assistant',
        content: '\u8d8b\u52bf\u504f\u5f3a',
        skills: ['bull_trend', 'ma_golden_cross'],
        skillNames: ['\u8d8b\u52bf\u5206\u6790', '\u5747\u7ebf\u91d1\u53c9'],
      },
    ];

    render(
      <MemoryRouter initialEntries={['/chat']}>
        <ChatPage />
      </MemoryRouter>
    );

    const skillBadge = await screen.findByLabelText('\u6280\u80fd \u8d8b\u52bf\u5206\u6790、\u5747\u7ebf\u91d1\u53c9');
    expect(skillBadge).toBeInTheDocument();
    expect(skillBadge).toHaveTextContent('\u8d8b\u52bf\u5206\u6790、\u5747\u7ebf\u91d1\u53c9');
  });

  it('renders failed stage_done progress as a non-success state', async () => {
    mockStoreState.loading = true;
    mockStoreState.progressSteps = [
      { type: 'stage_done', stage: 'risk', status: 'failed' },
    ];
    mockStoreState.messages = [
      {
        id: 'assistant-1',
        role: 'assistant',
        content: 'Partial answer',
        thinkingSteps: [
          { type: 'stage_done', stage: 'risk', status: 'failed' },
        ],
      },
    ];

    const { container } = render(
      <MemoryRouter initialEntries={['/chat']}>
        <ChatPage />
      </MemoryRouter>
    );

    expect(await screen.findAllByText('risk failed')).toHaveLength(1);

    const thinkingToggle = container.querySelector('button[class*="mb-2"][class*="w-full"]') as HTMLButtonElement;
    fireEvent.click(thinkingToggle);

    const failedStage = screen.getAllByText('risk failed').find((node) =>
      node.closest('.chat-progress-item'),
    );
    expect(failedStage).toBeDefined();
    expect(failedStage?.closest('.chat-progress-item')).toHaveClass('chat-progress-item-danger');
    expect(failedStage?.closest('.chat-progress-item')).not.toHaveClass('chat-progress-item-success');
  });

  it('renders pipeline budget skip progress without timeout severity', async () => {
    mockStoreState.loading = true;
    mockStoreState.progressSteps = [
      { type: 'pipeline_budget_skipped', stage: 'decision' },
    ];
    mockStoreState.messages = [
      {
        id: 'assistant-1',
        role: 'assistant',
        content: 'Partial answer',
        thinkingSteps: [
          { type: 'pipeline_budget_skipped', stage: 'decision' },
        ],
      },
    ];

    const { container } = render(
      <MemoryRouter initialEntries={['/chat']}>
        <ChatPage />
      </MemoryRouter>
    );

    expect(await screen.findAllByText('decision skipped: insufficient budget')).toHaveLength(1);
    expect(screen.queryByText('decision timed out')).not.toBeInTheDocument();

    const thinkingToggle = container.querySelector('button[class*="mb-2"][class*="w-full"]') as HTMLButtonElement;
    fireEvent.click(thinkingToggle);

    const budgetSkipped = screen.getAllByText('decision skipped: insufficient budget').find((node) =>
      node.closest('.chat-progress-item'),
    );
    expect(budgetSkipped).toBeDefined();
    expect(budgetSkipped?.closest('.chat-progress-item')).toHaveClass('chat-progress-item-muted');
    expect(budgetSkipped?.closest('.chat-progress-item')).not.toHaveClass('chat-progress-item-danger');
  });

  it('selects the default skill after loading skills', async () => {
    render(
      <MemoryRouter initialEntries={['/chat']}>
        <ChatPage />
      </MemoryRouter>
    );

    expect(await screen.findByRole('checkbox', { name: '\u8d8b\u52bf\u5206\u6790' })).toBeChecked();
    expect(screen.getByRole('checkbox', { name: '\u901a\u7528\u5206\u6790' })).not.toBeChecked();
  });

  it('sends multiple selected skills in order', async () => {
    mockGetSkills.mockResolvedValue({
      skills: [
        { id: 'bull_trend', name: '\u8d8b\u52bf\u5206\u6790', description: '\u9ed8\u8ba4\u8d8b\u52bf' },
        { id: 'ma_golden_cross', name: '\u5747\u7ebf\u91d1\u53c9', description: '\u5747\u7ebf\u4ea4\u53c9' },
      ],
      default_skill_id: 'bull_trend',
    });

    render(
      <MemoryRouter initialEntries={['/chat']}>
        <ChatPage />
      </MemoryRouter>
    );

    fireEvent.click(await screen.findByRole('checkbox', { name: '\u5747\u7ebf\u91d1\u53c9' }));
    fireEvent.change(screen.getByPlaceholderText(/\u5206\u6790 600519/), {
      target: { value: '\u5206\u6790 600519' },
    });
    fireEvent.click(screen.getByRole('button', { name: '\u53d1\u9001' }));

    await waitFor(() => {
      expect(mockStartStream).toHaveBeenCalledWith(
        expect.objectContaining({
          message: '\u5206\u6790 600519',
          skills: ['bull_trend', 'ma_golden_cross'],
        }),
        expect.objectContaining({
          skillNames: ['\u8d8b\u52bf\u5206\u6790', '\u5747\u7ebf\u91d1\u53c9'],
          skillName: '\u8d8b\u52bf\u5206\u6790、\u5747\u7ebf\u91d1\u53c9',
        }),
      );
    });
  });

  it('collapses the mobile skill picker by default and keeps selected skills when sending', async () => {
    mockGetSkills.mockResolvedValue({
      skills: [
        { id: 'bull_trend', name: '\u8d8b\u52bf\u5206\u6790', description: '\u9ed8\u8ba4\u8d8b\u52bf' },
        { id: 'ma_golden_cross', name: '\u5747\u7ebf\u91d1\u53c9', description: '\u5747\u7ebf\u4ea4\u53c9' },
      ],
      default_skill_id: 'bull_trend',
    });

    render(
      <MemoryRouter initialEntries={['/chat']}>
        <ChatPage />
      </MemoryRouter>
    );

    const mobileToggle = await screen.findByRole('button', { name: '\u5c55\u5f00\u7b56\u7565\u9009\u62e9' });
    const skillPanel = screen.getByTestId('chat-skill-picker-panel');
    expect(mobileToggle).toHaveAttribute('aria-expanded', 'false');
    expect(skillPanel).toHaveClass('hidden');

    fireEvent.click(mobileToggle);

    expect(screen.getByRole('button', { name: '\u6536\u8d77\u7b56\u7565\u9009\u62e9' })).toHaveAttribute('aria-expanded', 'true');
    expect(skillPanel).not.toHaveClass('hidden');
    expect(skillPanel).toHaveClass('flex');

    fireEvent.click(screen.getByRole('checkbox', { name: '\u5747\u7ebf\u91d1\u53c9' }));
    fireEvent.change(screen.getByPlaceholderText(/\u5206\u6790 600519/), {
      target: { value: '\u5206\u6790 600519' },
    });
    fireEvent.click(screen.getByRole('button', { name: '\u53d1\u9001' }));

    await waitFor(() => {
      expect(mockStartStream).toHaveBeenCalledWith(
        expect.objectContaining({
          message: '\u5206\u6790 600519',
          skills: ['bull_trend', 'ma_golden_cross'],
        }),
        expect.objectContaining({
          skillName: '\u8d8b\u52bf\u5206\u6790、\u5747\u7ebf\u91d1\u53c9',
        }),
      );
    });

    expect(screen.getByRole('button', { name: '\u5c55\u5f00\u7b56\u7565\u9009\u62e9' })).toHaveAttribute('aria-expanded', 'false');
    expect(skillPanel).toHaveClass('hidden');
  });

  it('omits skills when all concrete skills are cleared', async () => {
    render(
      <MemoryRouter initialEntries={['/chat']}>
        <ChatPage />
      </MemoryRouter>
    );

    fireEvent.click(await screen.findByRole('checkbox', { name: '\u8d8b\u52bf\u5206\u6790' }));
    expect(screen.getByRole('checkbox', { name: '\u901a\u7528\u5206\u6790' })).toBeChecked();

    fireEvent.change(screen.getByPlaceholderText(/\u5206\u6790 600519/), {
      target: { value: '\u5206\u6790 AAPL' },
    });
    fireEvent.click(screen.getByRole('button', { name: '\u53d1\u9001' }));

    await waitFor(() => {
      expect(mockStartStream).toHaveBeenCalled();
    });
    const lastCall = mockStartStream.mock.calls[mockStartStream.mock.calls.length - 1];
    expect(lastCall[0]).toEqual(expect.objectContaining({ message: '\u5206\u6790 AAPL' }));
    expect(lastCall[0]).not.toHaveProperty('skills');
    expect(lastCall[1]).toEqual(expect.objectContaining({
      skillNames: ['\u901a\u7528'],
      skillName: '\u901a\u7528',
    }));
  });

  it('caps concrete skill selection at three and re-enables choices after unselecting', async () => {
    mockGetSkills.mockResolvedValue({
      skills: [
        { id: 'bull_trend', name: '\u8d8b\u52bf\u5206\u6790', description: '\u9ed8\u8ba4\u8d8b\u52bf' },
        { id: 'ma_golden_cross', name: '\u5747\u7ebf\u91d1\u53c9', description: '\u5747\u7ebf\u4ea4\u53c9' },
        { id: 'chan_theory', name: '\u7f20\u8bba', description: '\u7ed3\u6784\u5206\u6790' },
        { id: 'wave_theory', name: '\u6ce2\u6d6a\u7406\u8bba', description: '\u6ce2\u6d6a\u5206\u6790' },
      ],
      default_skill_id: 'bull_trend',
    });

    render(
      <MemoryRouter initialEntries={['/chat']}>
        <ChatPage />
      </MemoryRouter>
    );

    fireEvent.click(await screen.findByRole('checkbox', { name: '\u5747\u7ebf\u91d1\u53c9' }));
    fireEvent.click(screen.getByRole('checkbox', { name: '\u7f20\u8bba' }));

    const wave = screen.getByRole('checkbox', { name: '\u6ce2\u6d6a\u7406\u8bba' });
    expect(wave).toBeDisabled();

    fireEvent.click(screen.getByRole('checkbox', { name: '\u5747\u7ebf\u91d1\u53c9' }));
    expect(wave).not.toBeDisabled();
  });

  it('quick questions override the current multi-skill selection', async () => {
    mockGetSkills.mockResolvedValue({
      skills: [
        { id: 'bull_trend', name: '\u8d8b\u52bf\u5206\u6790', description: '\u9ed8\u8ba4\u8d8b\u52bf' },
        { id: 'ma_golden_cross', name: '\u5747\u7ebf\u91d1\u53c9', description: '\u5747\u7ebf\u4ea4\u53c9' },
        { id: 'chan_theory', name: '\u7f20\u8bba', description: '\u7ed3\u6784\u5206\u6790' },
      ],
      default_skill_id: 'bull_trend',
    });

    render(
      <MemoryRouter initialEntries={['/chat']}>
        <ChatPage />
      </MemoryRouter>
    );

    fireEvent.click(await screen.findByRole('checkbox', { name: '\u5747\u7ebf\u91d1\u53c9' }));
    fireEvent.click(screen.getByRole('button', { name: '\u7528\u7f20\u8bba\u5206\u6790\u8305\u53f0' }));

    await waitFor(() => {
      expect(mockStartStream).toHaveBeenCalledWith(
        expect.objectContaining({
          message: '\u7528\u7f20\u8bba\u5206\u6790\u8305\u53f0',
          skills: ['chan_theory'],
        }),
        expect.objectContaining({
          skillNames: ['\u7f20\u8bba'],
          skillName: '\u7f20\u8bba',
        }),
      );
    });
  });

  it('keeps assistant message actions directly activatable in the DOM', async () => {
    mockStoreState.messages = [
      { id: 'assistant-1', role: 'assistant', content: '\u8d8b\u52bf\u504f\u5f3a', skillName: '\u8d8b\u52bf\u5206\u6790' },
    ];

    render(
      <MemoryRouter initialEntries={['/chat']}>
        <ChatPage />
      </MemoryRouter>
    );

    const exportButton = await screen.findByRole('button', { name: '\u5bfc\u51fa\u6b64\u6761\u6d88\u606f\u4e3a Markdown' });
    const actionGroup = exportButton.parentElement;

    expect(actionGroup).toHaveClass('chat-message-actions');
    expect(actionGroup?.className).not.toMatch(/pointer-events-none|opacity-0/);
  });

  it('sends exported markdown to notification channel and shows success feedback', async () => {
    mockStoreState.messages = [
      { id: 'user-1', role: 'user', content: '\u8bf7\u5206\u6790 600519' },
      { id: 'assistant-1', role: 'assistant', content: '\u8d8b\u52bf\u504f\u5f3a', skillName: '\u8d8b\u52bf\u5206\u6790' },
    ];
    mockFormatSessionAsMarkdown.mockReturnValue('# exported markdown');

    render(
      <MemoryRouter initialEntries={['/chat']}>
        <ChatPage />
      </MemoryRouter>
    );

    fireEvent.click(await screen.findByRole('button', { name: '\u53d1\u9001\u5230\u5df2\u914d\u7f6e\u7684\u901a\u77e5\u673a\u5668\u4eba/\u90ae\u7bb1' }));

    await waitFor(() => {
      expect(mockFormatSessionAsMarkdown).toHaveBeenCalledWith(mockStoreState.messages);
      expect(mockSendChat).toHaveBeenCalledWith('# exported markdown');
    });

    expect(await screen.findByText('\u5df2\u53d1\u9001\u5230\u901a\u77e5\u6e20\u9053')).toBeInTheDocument();
  });

  it('shows parsed error feedback when notification delivery fails', async () => {
    mockStoreState.messages = [
      { id: 'user-1', role: 'user', content: '\u8bf7\u5206\u6790 AAPL' },
      { id: 'assistant-1', role: 'assistant', content: '\u77ed\u7ebf\u9707\u8361', skillName: '\u8d8b\u52bf\u5206\u6790' },
    ];
    mockSendChat.mockRejectedValue(
      createParsedApiError({
        title: '\u53d1\u9001\u5931\u8d25',
        message: '\u901a\u77e5\u6e20\u9053\u4e0d\u53ef\u7528',
        category: 'unknown',
      }),
    );

    render(
      <MemoryRouter initialEntries={['/chat']}>
        <ChatPage />
      </MemoryRouter>
    );

    fireEvent.click(await screen.findByRole('button', { name: '\u53d1\u9001\u5230\u5df2\u914d\u7f6e\u7684\u901a\u77e5\u673a\u5668\u4eba/\u90ae\u7bb1' }));

    expect(await screen.findByText('\u901a\u77e5\u6e20\u9053\u4e0d\u53ef\u7528')).toBeInTheDocument();
  });

  it('prevents duplicate notification sends while the request is in flight', async () => {
    mockStoreState.messages = [
      { id: 'user-1', role: 'user', content: '\u8bf7\u5206\u6790 TSLA' },
      { id: 'assistant-1', role: 'assistant', content: '\u6ce2\u52a8\u8f83\u5927', skillName: '\u8d8b\u52bf\u5206\u6790' },
    ];
    const deferred = createDeferred<{ success: boolean }>();
    mockSendChat.mockImplementation(() => deferred.promise);

    render(
      <MemoryRouter initialEntries={['/chat']}>
        <ChatPage />
      </MemoryRouter>
    );

    const sendButton = await screen.findByRole('button', { name: '\u53d1\u9001\u5230\u5df2\u914d\u7f6e\u7684\u901a\u77e5\u673a\u5668\u4eba/\u90ae\u7bb1' });
    fireEvent.click(sendButton);

    await waitFor(() => {
      expect(mockSendChat).toHaveBeenCalledTimes(1);
      expect(sendButton).toBeDisabled();
    });

    fireEvent.click(sendButton);
    expect(mockSendChat).toHaveBeenCalledTimes(1);

    deferred.resolve({ success: true });

    await waitFor(() => {
      expect(sendButton).not.toBeDisabled();
    });
  });

  it('allows sending with base follow-up context before report hydration completes', async () => {
    const deferred = createDeferred<Awaited<ReturnType<typeof historyApi.getDetail>>>();

    vi.mocked(historyApi.getDetail).mockImplementation(() => deferred.promise);

    render(
      <MemoryRouter initialEntries={['/chat?stock=600519&name=%E8%B4%B5%E5%B7%9E%E8%8C%85%E5%8F%B0&recordId=1']}>
        <ChatPage />
      </MemoryRouter>
    );

    expect(await screen.findByDisplayValue('\u8bf7\u6df1\u5165\u5206\u6790 \u8d35\u5dde\u8305\u53f0(600519)')).toBeInTheDocument();

    const sendButton = screen.getByRole('button', { name: /\u53d1\u9001|\u5904\u7406\u4e2d\.\.\./ });
    expect(sendButton).not.toBeDisabled();
    expect(screen.getByText('\u6b63\u5728\u52a0\u8f7d\u5386\u53f2\u5206\u6790\u4e0a\u4e0b\u6587；\u73b0\u5728\u53ef\u76f4\u63a5\u53d1\u9001\u8ffd\u95ee。')).toBeInTheDocument();

    fireEvent.click(sendButton);

    await waitFor(() => {
      expect(mockStartStream).toHaveBeenCalledWith(
        expect.objectContaining({
          message: '\u8bf7\u6df1\u5165\u5206\u6790 \u8d35\u5dde\u8305\u53f0(600519)',
          context: {
            stock_code: '600519',
            stock_name: '\u8d35\u5dde\u8305\u53f0',
          },
        }),
        expect.objectContaining({
          skillName: '\u8d8b\u52bf\u5206\u6790',
        }),
      );
    });

    deferred.resolve({
      meta: {
        id: 1,
        queryId: 'q-1',
        stockCode: '600519',
        stockName: '\u8d35\u5dde\u8305\u53f0',
        reportType: 'detailed',
        createdAt: '2026-03-18T08:00:00Z',
        currentPrice: 1523.6,
        changePct: 1.8,
      },
      summary: {
        analysisSummary: '\u8d8b\u52bf\u5ef6\u7eed',
        operationAdvice: '\u7ee7\u7eed\u89c2\u5bdf',
        trendPrediction: '\u9ad8\u4f4d\u9707\u8361',
        sentimentScore: 78,
      },
      strategy: {
        stopLoss: '1450',
      },
    });

    await waitFor(() => {
      expect(screen.queryByText('\u6b63\u5728\u52a0\u8f7d\u5386\u53f2\u5206\u6790\u4e0a\u4e0b\u6587；\u73b0\u5728\u53ef\u76f4\u63a5\u53d1\u9001\u8ffd\u95ee。')).not.toBeInTheDocument();
    });

    fireEvent.change(screen.getByPlaceholderText(/\u5206\u6790 600519/), {
      target: { value: '\u7ee7\u7eed\u5206\u6790\u6210\u4ea4\u91cf' },
    });
    fireEvent.click(screen.getByRole('button', { name: '\u53d1\u9001' }));

    await waitFor(() => {
      expect(mockStartStream).toHaveBeenLastCalledWith(
        expect.objectContaining({
          message: '\u7ee7\u7eed\u5206\u6790\u6210\u4ea4\u91cf',
          context: expect.objectContaining({
            stock_code: '600519',
            stock_name: '\u8d35\u5dde\u8305\u53f0',
          }),
        }),
        expect.objectContaining({
          skillName: '\u8d8b\u52bf\u5206\u6790',
        }),
      );
    });

    fireEvent.change(screen.getByPlaceholderText(/\u5206\u6790 600519/), {
      target: { value: '\u5982\u679c\u4e0d\u8003\u8651 TTM \u5462' },
    });
    fireEvent.click(screen.getByRole('button', { name: '\u53d1\u9001' }));

    await waitFor(() => {
      expect(mockStartStream).toHaveBeenLastCalledWith(
        expect.objectContaining({
          message: '\u5982\u679c\u4e0d\u8003\u8651 TTM \u5462',
          context: expect.objectContaining({
            stock_code: '600519',
            stock_name: '\u8d35\u5dde\u8305\u53f0',
          }),
        }),
        expect.objectContaining({
          skillName: '\u8d8b\u52bf\u5206\u6790',
        }),
      );
    });
  });

  it('uses hydrated report context when it finishes before sending', async () => {
    vi.mocked(historyApi.getDetail).mockResolvedValue({
      meta: {
        id: 1,
        queryId: 'q-1',
        stockCode: '600519',
        stockName: '\u8d35\u5dde\u8305\u53f0',
        reportType: 'detailed',
        createdAt: '2026-03-18T08:00:00Z',
        currentPrice: 1523.6,
        changePct: 1.8,
      },
      summary: {
        analysisSummary: '\u8d8b\u52bf\u5ef6\u7eed',
        operationAdvice: '\u7ee7\u7eed\u89c2\u5bdf',
        trendPrediction: '\u9ad8\u4f4d\u9707\u8361',
        sentimentScore: 78,
      },
      strategy: {
        stopLoss: '1450',
      },
    });

    render(
      <MemoryRouter initialEntries={['/chat?stock=600519&name=%E8%B4%B5%E5%B7%9E%E8%8C%85%E5%8F%B0&recordId=1']}>
        <ChatPage />
      </MemoryRouter>
    );

    expect(await screen.findByDisplayValue('\u8bf7\u6df1\u5165\u5206\u6790 \u8d35\u5dde\u8305\u53f0(600519)')).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.queryByText('\u6b63\u5728\u52a0\u8f7d\u5386\u53f2\u5206\u6790\u4e0a\u4e0b\u6587；\u73b0\u5728\u53ef\u76f4\u63a5\u53d1\u9001\u8ffd\u95ee。')).not.toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: '\u53d1\u9001' }));

    await waitFor(() => {
      expect(mockStartStream).toHaveBeenCalledWith(
        expect.objectContaining({
          message: '\u8bf7\u6df1\u5165\u5206\u6790 \u8d35\u5dde\u8305\u53f0(600519)',
          context: expect.objectContaining({
            stock_code: '600519',
            stock_name: '\u8d35\u5dde\u8305\u53f0',
            previous_price: 1523.6,
            previous_change_pct: 1.8,
            previous_strategy: expect.objectContaining({
              stopLoss: '1450',
            }),
          }),
        }),
        expect.objectContaining({
          skillName: '\u8d8b\u52bf\u5206\u6790',
        }),
      );
    });
  });

  it('falls back to base stock context when recordId is missing', async () => {
    render(
      <MemoryRouter initialEntries={['/chat?stock=AAPL']}>
        <ChatPage />
      </MemoryRouter>
    );

    expect(await screen.findByDisplayValue('\u8bf7\u6df1\u5165\u5206\u6790 AAPL')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: '\u53d1\u9001' }));

    await waitFor(() => {
      expect(mockStartStream).toHaveBeenCalledWith(
        expect.objectContaining({
          message: '\u8bf7\u6df1\u5165\u5206\u6790 AAPL',
          context: {
            stock_code: 'AAPL',
            stock_name: null,
          },
        }),
        expect.objectContaining({
          skillName: '\u8d8b\u52bf\u5206\u6790',
        }),
      );
    });
    expect(historyApi.getDetail).not.toHaveBeenCalled();

    fireEvent.change(screen.getByPlaceholderText(/\u5206\u6790 600519/), {
      target: { value: '\u7ee7\u7eed\u770b\u4f30\u503c' },
    });
    fireEvent.click(screen.getByRole('button', { name: '\u53d1\u9001' }));

    await waitFor(() => {
      expect(mockStartStream).toHaveBeenLastCalledWith(
        expect.objectContaining({
          message: '\u7ee7\u7eed\u770b\u4f30\u503c',
          context: {
            stock_code: 'AAPL',
            stock_name: null,
          },
        }),
        expect.objectContaining({
          skillName: '\u8d8b\u52bf\u5206\u6790',
        }),
      );
    });
  });

  it('switches active stock context for explicit switch messages', async () => {
    render(
      <MemoryRouter initialEntries={['/chat?stock=600519&name=%E8%B4%B5%E5%B7%9E%E8%8C%85%E5%8F%B0']}>
        <ChatPage />
      </MemoryRouter>
    );

    expect(await screen.findByDisplayValue('\u8bf7\u6df1\u5165\u5206\u6790 \u8d35\u5dde\u8305\u53f0(600519)')).toBeInTheDocument();

    fireEvent.change(screen.getByPlaceholderText(/\u5206\u6790 600519/), {
      target: { value: '\u6362\u6210 AAPL \u770b\u770b' },
    });
    fireEvent.click(screen.getByRole('button', { name: '\u53d1\u9001' }));

    await waitFor(() => {
      expect(mockStartStream).toHaveBeenLastCalledWith(
        expect.objectContaining({
          message: '\u6362\u6210 AAPL \u770b\u770b',
          context: {
            stock_code: 'AAPL',
            stock_name: null,
          },
        }),
        expect.objectContaining({
          skillName: '\u8d8b\u52bf\u5206\u6790',
        }),
      );
    });
  });

  it('switches to the single new stock when the current stock appears first', async () => {
    render(
      <MemoryRouter initialEntries={['/chat?stock=600519&name=%E8%B4%B5%E5%B7%9E%E8%8C%85%E5%8F%B0']}>
        <ChatPage />
      </MemoryRouter>
    );

    expect(await screen.findByDisplayValue('\u8bf7\u6df1\u5165\u5206\u6790 \u8d35\u5dde\u8305\u53f0(600519)')).toBeInTheDocument();

    fireEvent.change(screen.getByPlaceholderText(/\u5206\u6790 600519/), {
      target: { value: '\u5148\u4e0d\u770b 600519，\u6362\u6210 AAPL \u770b\u770b' },
    });
    fireEvent.click(screen.getByRole('button', { name: '\u53d1\u9001' }));

    await waitFor(() => {
      expect(mockStartStream).toHaveBeenLastCalledWith(
        expect.objectContaining({
          message: '\u5148\u4e0d\u770b 600519，\u6362\u6210 AAPL \u770b\u770b',
          context: {
            stock_code: 'AAPL',
            stock_name: null,
          },
        }),
        expect.objectContaining({
          skillName: '\u8d8b\u52bf\u5206\u6790',
        }),
      );
    });

    fireEvent.change(screen.getByPlaceholderText(/\u5206\u6790 600519/), {
      target: { value: '\u7ee7\u7eed\u770b\u652f\u6491\u4f4d' },
    });
    fireEvent.click(screen.getByRole('button', { name: '\u53d1\u9001' }));

    await waitFor(() => {
      expect(mockStartStream).toHaveBeenLastCalledWith(
        expect.objectContaining({
          message: '\u7ee7\u7eed\u770b\u652f\u6491\u4f4d',
          context: {
            stock_code: 'AAPL',
            stock_name: null,
          },
        }),
        expect.objectContaining({
          skillName: '\u8d8b\u52bf\u5206\u6790',
        }),
      );
    });
  });

  it('keeps active stock context for compare messages', async () => {
    render(
      <MemoryRouter initialEntries={['/chat?stock=600519&name=%E8%B4%B5%E5%B7%9E%E8%8C%85%E5%8F%B0']}>
        <ChatPage />
      </MemoryRouter>
    );

    expect(await screen.findByDisplayValue('\u8bf7\u6df1\u5165\u5206\u6790 \u8d35\u5dde\u8305\u53f0(600519)')).toBeInTheDocument();

    fireEvent.change(screen.getByPlaceholderText(/\u5206\u6790 600519/), {
      target: { value: '\u6bd4\u8f83 600519 \u548c AAPL' },
    });
    fireEvent.click(screen.getByRole('button', { name: '\u53d1\u9001' }));

    await waitFor(() => {
      expect(mockStartStream).toHaveBeenLastCalledWith(
        expect.objectContaining({
          message: '\u6bd4\u8f83 600519 \u548c AAPL',
          context: {
            stock_code: '600519',
            stock_name: '\u8d35\u5dde\u8305\u53f0',
          },
        }),
        expect.objectContaining({
          skillName: '\u8d8b\u52bf\u5206\u6790',
        }),
      );
    });
  });

  it('keeps active stock context for difference-style compare messages', async () => {
    render(
      <MemoryRouter initialEntries={['/chat?stock=600519&name=%E8%B4%B5%E5%B7%9E%E8%8C%85%E5%8F%B0']}>
        <ChatPage />
      </MemoryRouter>
    );

    expect(await screen.findByDisplayValue('\u8bf7\u6df1\u5165\u5206\u6790 \u8d35\u5dde\u8305\u53f0(600519)')).toBeInTheDocument();

    fireEvent.change(screen.getByPlaceholderText(/\u5206\u6790 600519/), {
      target: { value: '\u5206\u6790 600519 \u548c AAPL \u7684\u5dee\u5f02' },
    });
    fireEvent.click(screen.getByRole('button', { name: '\u53d1\u9001' }));

    await waitFor(() => {
      expect(mockStartStream).toHaveBeenLastCalledWith(
        expect.objectContaining({
          message: '\u5206\u6790 600519 \u548c AAPL \u7684\u5dee\u5f02',
          context: {
            stock_code: '600519',
            stock_name: '\u8d35\u5dde\u8305\u53f0',
          },
        }),
        expect.objectContaining({
          skillName: '\u8d8b\u52bf\u5206\u6790',
        }),
      );
    });
  });

  it('keeps active stock context when the compared stock appears first', async () => {
    render(
      <MemoryRouter initialEntries={['/chat?stock=600519&name=%E8%B4%B5%E5%B7%9E%E8%8C%85%E5%8F%B0']}>
        <ChatPage />
      </MemoryRouter>
    );

    expect(await screen.findByDisplayValue('\u8bf7\u6df1\u5165\u5206\u6790 \u8d35\u5dde\u8305\u53f0(600519)')).toBeInTheDocument();

    fireEvent.change(screen.getByPlaceholderText(/\u5206\u6790 600519/), {
      target: { value: '\u5206\u6790 AAPL \u548c 600519 \u7684\u5dee\u5f02' },
    });
    fireEvent.click(screen.getByRole('button', { name: '\u53d1\u9001' }));

    await waitFor(() => {
      expect(mockStartStream).toHaveBeenLastCalledWith(
        expect.objectContaining({
          message: '\u5206\u6790 AAPL \u548c 600519 \u7684\u5dee\u5f02',
          context: {
            stock_code: '600519',
            stock_name: '\u8d35\u5dde\u8305\u53f0',
          },
        }),
        expect.objectContaining({
          skillName: '\u8d8b\u52bf\u5206\u6790',
        }),
      );
    });
  });

  it('keeps active stock context for choice-style multi-stock messages', async () => {
    render(
      <MemoryRouter initialEntries={['/chat?stock=600519&name=%E8%B4%B5%E5%B7%9E%E8%8C%85%E5%8F%B0']}>
        <ChatPage />
      </MemoryRouter>
    );

    expect(await screen.findByDisplayValue('\u8bf7\u6df1\u5165\u5206\u6790 \u8d35\u5dde\u8305\u53f0(600519)')).toBeInTheDocument();

    fireEvent.change(screen.getByPlaceholderText(/\u5206\u6790 600519/), {
      target: { value: 'AAPL \u548c TSLA \u54ea\u4e2a\u66f4\u503c\u5f97\u4e70' },
    });
    fireEvent.click(screen.getByRole('button', { name: '\u53d1\u9001' }));

    await waitFor(() => {
      expect(mockStartStream).toHaveBeenLastCalledWith(
        expect.objectContaining({
          message: 'AAPL \u548c TSLA \u54ea\u4e2a\u66f4\u503c\u5f97\u4e70',
          context: {
            stock_code: '600519',
            stock_name: '\u8d35\u5dde\u8305\u53f0',
          },
        }),
        expect.objectContaining({
          skillName: '\u8d8b\u52bf\u5206\u6790',
        }),
      );
    });
  });

  it('switches active stock context for single-stock difference phrasing', async () => {
    render(
      <MemoryRouter initialEntries={['/chat?stock=600519&name=%E8%B4%B5%E5%B7%9E%E8%8C%85%E5%8F%B0']}>
        <ChatPage />
      </MemoryRouter>
    );

    expect(await screen.findByDisplayValue('\u8bf7\u6df1\u5165\u5206\u6790 \u8d35\u5dde\u8305\u53f0(600519)')).toBeInTheDocument();

    fireEvent.change(screen.getByPlaceholderText(/\u5206\u6790 600519/), {
      target: { value: '\u5206\u6790 AAPL \u7684\u5dee\u5f02\u5316\u4f18\u52bf' },
    });
    fireEvent.click(screen.getByRole('button', { name: '\u53d1\u9001' }));

    await waitFor(() => {
      expect(mockStartStream).toHaveBeenLastCalledWith(
        expect.objectContaining({
          message: '\u5206\u6790 AAPL \u7684\u5dee\u5f02\u5316\u4f18\u52bf',
          context: {
            stock_code: 'AAPL',
            stock_name: null,
          },
        }),
        expect.objectContaining({
          skillName: '\u8d8b\u52bf\u5206\u6790',
        }),
      );
    });
  });

  it('switches active stock context for lowercase US ticker switch messages', async () => {
    render(
      <MemoryRouter initialEntries={['/chat?stock=600519&name=%E8%B4%B5%E5%B7%9E%E8%8C%85%E5%8F%B0']}>
        <ChatPage />
      </MemoryRouter>
    );

    expect(await screen.findByDisplayValue('\u8bf7\u6df1\u5165\u5206\u6790 \u8d35\u5dde\u8305\u53f0(600519)')).toBeInTheDocument();

    fireEvent.change(screen.getByPlaceholderText(/\u5206\u6790 600519/), {
      target: { value: '\u5206\u6790tsla' },
    });
    fireEvent.click(screen.getByRole('button', { name: '\u53d1\u9001' }));

    await waitFor(() => {
      expect(mockStartStream).toHaveBeenLastCalledWith(
        expect.objectContaining({
          message: '\u5206\u6790tsla',
          context: {
            stock_code: 'TSLA',
            stock_name: null,
          },
        }),
        expect.objectContaining({
          skillName: '\u8d8b\u52bf\u5206\u6790',
        }),
      );
    });
  });

  it('keeps active stock context when clicking the current session', async () => {
    render(
      <MemoryRouter initialEntries={['/chat?stock=600519&name=%E8%B4%B5%E5%B7%9E%E8%8C%85%E5%8F%B0']}>
        <ChatPage />
      </MemoryRouter>
    );

    expect(await screen.findByDisplayValue('\u8bf7\u6df1\u5165\u5206\u6790 \u8d35\u5dde\u8305\u53f0(600519)')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '\u5207\u6362\u5230\u5bf9\u8bdd \u8bf7\u7b80\u8981\u5206\u6790 600519' }));
    expect(mockSwitchSession).not.toHaveBeenCalled();

    fireEvent.change(screen.getByPlaceholderText(/\u5206\u6790 600519/), {
      target: { value: '\u7ee7\u7eed\u770b\u6210\u4ea4\u91cf' },
    });
    fireEvent.click(screen.getByRole('button', { name: '\u53d1\u9001' }));

    await waitFor(() => {
      expect(mockStartStream).toHaveBeenLastCalledWith(
        expect.objectContaining({
          message: '\u7ee7\u7eed\u770b\u6210\u4ea4\u91cf',
          context: {
            stock_code: '600519',
            stock_name: '\u8d35\u5dde\u8305\u53f0',
          },
        }),
        expect.objectContaining({
          skillName: '\u8d8b\u52bf\u5206\u6790',
        }),
      );
    });
  });

  it('restores active stock context from loaded session messages', async () => {
    mockStoreState.messages = [
      { id: 'm-1', role: 'user', content: '\u8bf7\u5206\u6790 600519' },
      { id: 'm-2', role: 'assistant', content: '600519 \u5206\u6790\u7ed3\u679c' },
      { id: 'm-3', role: 'user', content: '\u5148\u4e0d\u770b 600519，\u6362\u6210 AAPL \u770b\u770b' },
      { id: 'm-4', role: 'assistant', content: 'AAPL \u5206\u6790\u7ed3\u679c' },
    ];

    render(
      <MemoryRouter initialEntries={['/chat']}>
        <ChatPage />
      </MemoryRouter>
    );

    expect(await screen.findByTestId('chat-workspace')).toBeInTheDocument();

    fireEvent.change(screen.getByPlaceholderText(/\u5206\u6790 600519/), {
      target: { value: '\u7ee7\u7eed\u770b\u652f\u6491\u4f4d' },
    });
    fireEvent.click(screen.getByRole('button', { name: '\u53d1\u9001' }));

    await waitFor(() => {
      expect(mockStartStream).toHaveBeenLastCalledWith(
        expect.objectContaining({
          message: '\u7ee7\u7eed\u770b\u652f\u6491\u4f4d',
          context: {
            stock_code: 'AAPL',
            stock_name: null,
          },
        }),
        expect.objectContaining({
          skillName: '\u8d8b\u52bf\u5206\u6790',
        }),
      );
    });
  });

  it('clears active stock context when starting a new chat or switching sessions', async () => {
    mockStoreState.sessions = [
      ...mockStoreState.sessions,
      {
        session_id: 'session-2',
        title: '\u65e7\u4f1a\u8bdd',
        message_count: 1,
        created_at: '2026-03-16T09:00:00Z',
        last_active: '2026-03-16T09:05:00Z',
      },
    ];

    const { unmount } = render(
      <MemoryRouter initialEntries={['/chat?stock=600519&name=%E8%B4%B5%E5%B7%9E%E8%8C%85%E5%8F%B0']}>
        <ChatPage />
      </MemoryRouter>
    );

    expect(await screen.findByDisplayValue('\u8bf7\u6df1\u5165\u5206\u6790 \u8d35\u5dde\u8305\u53f0(600519)')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '\u5f00\u542f\u65b0\u5bf9\u8bdd' }));
    expect(mockStartNewChat).toHaveBeenCalled();

    fireEvent.change(screen.getByPlaceholderText(/\u5206\u6790 600519/), {
      target: { value: '\u7ee7\u7eed\u770b\u6210\u4ea4\u91cf' },
    });
    fireEvent.click(screen.getByRole('button', { name: '\u53d1\u9001' }));

    await waitFor(() => {
      expect(mockStartStream).toHaveBeenLastCalledWith(
        expect.objectContaining({
          message: '\u7ee7\u7eed\u770b\u6210\u4ea4\u91cf',
          context: undefined,
        }),
        expect.objectContaining({
          skillName: '\u8d8b\u52bf\u5206\u6790',
        }),
      );
    });

    unmount();
    mockStartStream.mockClear();

    render(
      <MemoryRouter initialEntries={['/chat?stock=600519&name=%E8%B4%B5%E5%B7%9E%E8%8C%85%E5%8F%B0']}>
        <ChatPage />
      </MemoryRouter>
    );

    expect(await screen.findByDisplayValue('\u8bf7\u6df1\u5165\u5206\u6790 \u8d35\u5dde\u8305\u53f0(600519)')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '\u5207\u6362\u5230\u5bf9\u8bdd \u65e7\u4f1a\u8bdd' }));
    expect(mockSwitchSession).toHaveBeenCalledWith('session-2');

    fireEvent.change(screen.getByPlaceholderText(/\u5206\u6790 600519/), {
      target: { value: '\u7ee7\u7eed\u770b\u6210\u4ea4\u91cf' },
    });
    fireEvent.click(screen.getByRole('button', { name: '\u53d1\u9001' }));

    await waitFor(() => {
      expect(mockStartStream).toHaveBeenLastCalledWith(
        expect.objectContaining({
          message: '\u7ee7\u7eed\u770b\u6210\u4ea4\u91cf',
          context: undefined,
        }),
        expect.objectContaining({
          skillName: '\u8d8b\u52bf\u5206\u6790',
        }),
      );
    });
  });

  it('clears active stock context when deleting the current session', async () => {
    render(
      <MemoryRouter initialEntries={['/chat?stock=600519&name=%E8%B4%B5%E5%B7%9E%E8%8C%85%E5%8F%B0']}>
        <ChatPage />
      </MemoryRouter>
    );

    expect(await screen.findByDisplayValue('\u8bf7\u6df1\u5165\u5206\u6790 \u8d35\u5dde\u8305\u53f0(600519)')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '\u5220\u9664\u5bf9\u8bdd \u8bf7\u7b80\u8981\u5206\u6790 600519' }));
    fireEvent.click(screen.getByRole('button', { name: '\u5220\u9664' }));

    await waitFor(() => {
      expect(mockDeleteChatSession).toHaveBeenCalledWith('session-1');
    });
    expect(mockStartNewChat).toHaveBeenCalled();

    fireEvent.change(screen.getByPlaceholderText(/\u5206\u6790 600519/), {
      target: { value: '\u7ee7\u7eed\u770b\u6210\u4ea4\u91cf' },
    });
    fireEvent.click(screen.getByRole('button', { name: '\u53d1\u9001' }));

    await waitFor(() => {
      expect(mockStartStream).toHaveBeenLastCalledWith(
        expect.objectContaining({
          message: '\u7ee7\u7eed\u770b\u6210\u4ea4\u91cf',
          context: undefined,
        }),
        expect.objectContaining({
          skillName: '\u8d8b\u52bf\u5206\u6790',
        }),
      );
    });
  });

  it('ignores malformed follow-up query params', async () => {
    render(
      <MemoryRouter initialEntries={['/chat?stock=%3Cscript%3E&name=Bad%0AName&recordId=abc']}>
        <ChatPage />
      </MemoryRouter>
    );

    expect(await screen.findByRole('heading', { name: '\u95ee\u80a1' })).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/\u5206\u6790 600519/)).toHaveValue('');
    expect(historyApi.getDetail).not.toHaveBeenCalled();
  });

  it('reprocesses follow-up query params when navigating to the same chat route again', async () => {
    const firstDeferred = createDeferred<Awaited<ReturnType<typeof historyApi.getDetail>>>();
    const secondDeferred = createDeferred<Awaited<ReturnType<typeof historyApi.getDetail>>>();

    vi.mocked(historyApi.getDetail)
      .mockImplementationOnce(() => firstDeferred.promise)
      .mockImplementationOnce(() => secondDeferred.promise);

    const router = createMemoryRouter(
      [{ path: '/chat', element: <ChatPage /> }],
      {
        initialEntries: ['/chat?stock=600519&name=%E8%B4%B5%E5%B7%9E%E8%8C%85%E5%8F%B0&recordId=1'],
      },
    );

    render(<RouterProvider router={router} />);

    expect(await screen.findByDisplayValue('\u8bf7\u6df1\u5165\u5206\u6790 \u8d35\u5dde\u8305\u53f0(600519)')).toBeInTheDocument();
    expect(screen.getByText('\u6b63\u5728\u52a0\u8f7d\u5386\u53f2\u5206\u6790\u4e0a\u4e0b\u6587；\u73b0\u5728\u53ef\u76f4\u63a5\u53d1\u9001\u8ffd\u95ee。')).toBeInTheDocument();

    await router.navigate('/chat?stock=AAPL&name=Apple&recordId=2');

    expect(await screen.findByDisplayValue('\u8bf7\u6df1\u5165\u5206\u6790 Apple(AAPL)')).toBeInTheDocument();

    firstDeferred.resolve({
      meta: {
        id: 1,
        queryId: 'q-1',
        stockCode: '600519',
        stockName: '\u8d35\u5dde\u8305\u53f0',
        reportType: 'detailed',
        createdAt: '2026-03-18T08:00:00Z',
        currentPrice: 1523.6,
        changePct: 1.8,
      },
      summary: {
        analysisSummary: '\u8d8b\u52bf\u5ef6\u7eed',
        operationAdvice: '\u7ee7\u7eed\u89c2\u5bdf',
        trendPrediction: '\u9ad8\u4f4d\u9707\u8361',
        sentimentScore: 78,
      },
      strategy: {
        stopLoss: '1450',
      },
    });

    secondDeferred.resolve({
      meta: {
        id: 2,
        queryId: 'q-2',
        stockCode: 'AAPL',
        stockName: 'Apple',
        reportType: 'detailed',
        createdAt: '2026-03-18T09:00:00Z',
        currentPrice: 211.5,
        changePct: 2.4,
      },
      summary: {
        analysisSummary: '\u8d8b\u52bf\u8d70\u5f3a',
        operationAdvice: '\u7ee7\u7eed\u6301\u6709',
        trendPrediction: '\u77ed\u7ebf\u504f\u5f3a',
        sentimentScore: 81,
      },
      strategy: {
        stopLoss: '205',
      },
    });

    await waitFor(() => {
      expect(screen.queryByText('\u6b63\u5728\u52a0\u8f7d\u5386\u53f2\u5206\u6790\u4e0a\u4e0b\u6587；\u73b0\u5728\u53ef\u76f4\u63a5\u53d1\u9001\u8ffd\u95ee。')).not.toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: '\u53d1\u9001' }));

    await waitFor(() => {
      expect(mockStartStream).toHaveBeenCalledWith(
        expect.objectContaining({
          message: '\u8bf7\u6df1\u5165\u5206\u6790 Apple(AAPL)',
          context: expect.objectContaining({
            stock_code: 'AAPL',
            stock_name: 'Apple',
            previous_price: 211.5,
            previous_change_pct: 2.4,
            previous_strategy: expect.objectContaining({
              stopLoss: '205',
            }),
          }),
        }),
        expect.objectContaining({
          skillName: '\u8d8b\u52bf\u5206\u6790',
        }),
      );
    });
  });

  it('shows a jump-to-latest action when new content arrives while the user is away from bottom', async () => {
    mockStoreState.messages = [
      { id: 'user-1', role: 'user', content: '\u8bf7\u5206\u6790 600519' },
      { id: 'assistant-1', role: 'assistant', content: '\u8d8b\u52bf\u504f\u5f3a', skillName: '\u8d8b\u52bf\u5206\u6790' },
    ];

    const { rerender } = render(
      <MemoryRouter initialEntries={['/chat']}>
        <ChatPage />
      </MemoryRouter>
    );

    const viewport = await screen.findByTestId('chat-message-scroll');
    Object.defineProperty(viewport, 'scrollTop', { configurable: true, value: 0 });
    Object.defineProperty(viewport, 'clientHeight', { configurable: true, value: 400 });
    Object.defineProperty(viewport, 'scrollHeight', { configurable: true, value: 1200 });

    fireEvent.scroll(viewport);

    mockStoreState.messages = [
      ...mockStoreState.messages,
      { id: 'assistant-2', role: 'assistant', content: '\u65b0\u7684\u8865\u5145\u5206\u6790', skillName: '\u8d8b\u52bf\u5206\u6790' },
    ];

    rerender(
      <MemoryRouter initialEntries={['/chat']}>
        <ChatPage />
      </MemoryRouter>
    );

    const jumpButton = await screen.findByRole('button', { name: '\u67e5\u770b\u6700\u65b0\u6d88\u606f' });
    expect(jumpButton).toBeInTheDocument();

    fireEvent.click(jumpButton);

    expect(HTMLElement.prototype.scrollIntoView).toHaveBeenCalled();
  });
});

describe('extractStockCodeFromMessage', () => {
  it('returns 6-digit A-share code', () => {
    expect(extractStockCodeFromMessage('\u5206\u6790 600519 \u8d8b\u52bf')).toBe('600519');
    expect(extractStockCodeFromMessage('002460')).toBe('002460');
  });

  it('returns HK prefixed code (normalized)', () => {
    expect(extractStockCodeFromMessage('\u5206\u6790 hk00700')).toBe('HK00700');
  });

  it('returns .HK suffix code (normalized to canonical)', () => {
    expect(extractStockCodeFromMessage('00700.HK')).toBe('HK00700');
    expect(extractStockCodeFromMessage('1810.HK')).toBe('HK01810');
  });

  it('returns code with .SH/.SZ suffix (normalized)', () => {
    expect(extractStockCodeFromMessage('\u770b 600519.SH')).toBe('600519');
    expect(extractStockCodeFromMessage('000001.SZ')).toBe('000001');
  });

  it('returns US ticker like AAPL', () => {
    expect(extractStockCodeFromMessage('\u5206\u6790 AAPL \u8d70\u52bf')).toBe('AAPL');
    expect(extractStockCodeFromMessage('TSLA')).toBe('TSLA');
    expect(extractStockCodeFromMessage('\u5206\u6790 BRK.B')).toBe('BRK.B');
  });

  it('does NOT return finance abbreviations as tickers', () => {
    expect(extractStockCodeFromMessage('\u5982\u679c\u4e0d\u8003\u8651 TTM \u5462')).toBeNull();
    expect(extractStockCodeFromMessage('\u5e02\u76c8\u7387 TTM \u600e\u4e48\u770b')).toBeNull();
    expect(extractStockCodeFromMessage('PE \u600e\u4e48\u770b')).toBeNull();
    expect(extractStockCodeFromMessage('MACD \u8fd8\u6ca1\u91d1\u53c9\u5417')).toBeNull();
    expect(extractStockCodeFromMessage('RSI \u600e\u4e48\u770b')).toBeNull();
    expect(extractStockCodeFromMessage('WHAT IS PE')).toBeNull();
    expect(extractStockCodeFromMessage('PE IS HIGH')).toBeNull();
    expect(extractStockCodeFromMessage('WHAT IS TTM')).toBeNull();
  });

  it('does NOT return contextual moving-average MA as a ticker', () => {
    expect(extractStockCodeFromMessage('\u5206\u6790 MA \u5747\u7ebf')).toBeNull();
    expect(extractStockCodeFromMessage('\u770b\u770b MA \u600e\u4e48\u6392\u5217')).toBeNull();
    expect(extractStockCodesFromMessage('MA \u548c RSI \u7684\u6307\u6807\u600e\u4e48\u770b')).toEqual([]);
    expect(extractStockCodeFromMessage('\u5206\u6790 KDJ \u6307\u6807')).toBeNull();
    expect(extractStockCodeFromMessage('KDJ \u600e\u4e48\u770b')).toBeNull();
  });

  it('skips finance abbreviations before a real ticker', () => {
    expect(extractStockCodeFromMessage('PE AAPL \u600e\u4e48\u770b')).toBe('AAPL');
    expect(extractStockCodeFromMessage('TTM AAPL \u600e\u4e48\u770b')).toBe('AAPL');
    expect(extractStockCodeFromMessage('MACD AAPL \u600e\u4e48\u770b')).toBe('AAPL');
    expect(extractStockCodeFromMessage('WHAT IS PE AAPL')).toBe('AAPL');
  });

  it('does NOT return exchange prefixes as tickers', () => {
    expect(extractStockCodeFromMessage('\u5206\u6790 SH \u8d70\u52bf')).toBeNull();
    expect(extractStockCodeFromMessage('\u770b\u770b BJ')).toBeNull();
    expect(extractStockCodeFromMessage('HK')).toBeNull();
    expect(extractStockCodeFromMessage('\u4e70\u5165 SZ')).toBeNull();
    expect(extractStockCodeFromMessage('US \u5e02\u573a')).toBeNull();
    expect(extractStockCodeFromMessage('SS')).toBeNull();
  });

  it('returns null for messages without stock codes', () => {
    expect(extractStockCodeFromMessage('\u8305\u53f0\u73b0\u5728\u9002\u5408\u4e70\u5165\u5417')).toBeNull();
    expect(extractStockCodeFromMessage('\u5927\u76d8\u8d70\u52bf\u5982\u4f55')).toBeNull();
  });

  it('matches prefixed code like SH600519 (normalized)', () => {
    expect(extractStockCodeFromMessage('\u5206\u6790 SH600519')).toBe('600519');
  });

  it('returns SZ-prefixed code when standalone (normalized)', () => {
    expect(extractStockCodeFromMessage('SZ000001')).toBe('000001');
  });

  it('returns all stock codes in message order', () => {
    expect(extractStockCodesFromMessage('\u5206\u6790 600519 \u548c AAPL \u7684\u5dee\u5f02')).toEqual(['600519', 'AAPL']);
    expect(extractStockCodesFromMessage('\u5206\u6790 AAPL \u548c 600519 \u7684\u5dee\u5f02')).toEqual(['AAPL', '600519']);
    expect(extractStockCodesFromMessage('AAPL \u548c TSLA \u54ea\u4e2a\u66f4\u503c\u5f97\u4e70')).toEqual(['AAPL', 'TSLA']);
    expect(extractStockCodesFromMessage('\u6bd4\u8f83 BRK.B \u548c AAPL')).toEqual(['BRK.B', 'AAPL']);
  });

  it('extracts lowercase tickers only with explicit stock intent hints', () => {
    expect(extractStockCodesFromMessage('\u5206\u6790tsla')).toEqual(['TSLA']);
    expect(extractStockCodesFromMessage('\u770b\u770b tsla')).toEqual(['TSLA']);
    expect(extractStockCodesFromMessage('aapl \u548c tsla \u54ea\u4e2a\u66f4\u503c\u5f97\u4e70')).toEqual(['AAPL', 'TSLA']);
    expect(extractStockCodesFromMessage('hello tsla')).toEqual([]);
  });

  it('returns all HK and A-share variants without exchange affix tokens', () => {
    expect(extractStockCodesFromMessage('\u6bd4\u8f83 01810 \u548c AAPL')).toEqual(['HK01810', 'AAPL']);
    expect(extractStockCodesFromMessage('\u6bd4\u8f83 1810.HK \u548c AAPL')).toEqual(['HK01810', 'AAPL']);
    expect(extractStockCodesFromMessage('\u6bd4\u8f83 600519.SH \u548c AAPL')).toEqual(['600519', 'AAPL']);
    expect(extractStockCodesFromMessage('\u6bd4\u8f83 000001.SZ \u548c SS')).toEqual(['000001']);
    expect(extractStockCodesFromMessage('\u6bd4\u8f83 SH600519 \u548c AAPL')).toEqual(['600519', 'AAPL']);
    expect(extractStockCodesFromMessage('\u6bd4\u8f83 SZ000001 \u548c AAPL')).toEqual(['000001', 'AAPL']);
    expect(extractStockCodesFromMessage('\u6bd4\u8f83 BJ920748 \u548c AAPL')).toEqual(['920748', 'AAPL']);
    expect(extractStockCodesFromMessage('\u6bd4\u8f83 HK01810 \u548c AAPL')).toEqual(['HK01810', 'AAPL']);
  });

  it('does not return denied abbreviations in multi-code extraction', () => {
    expect(extractStockCodesFromMessage('\u5982\u679c\u4e0d\u8003\u8651 TTM \u548c PE')).toEqual([]);
    expect(extractStockCodesFromMessage('MACD AAPL \u548c RSI')).toEqual(['AAPL']);
    expect(extractStockCodesFromMessage('KDJ AAPL \u600e\u4e48\u770b')).toEqual(['AAPL']);
  });
});

describe('watchlist button with code variants', () => {
  it('shows "\u4ece\u81ea\u9009\u5220\u9664" when canonical code is in watchlist and user inputs variant', async () => {
    mockGetWatchlist.mockResolvedValue(['600519', 'HK01810']);

    render(
      <MemoryRouter>
        <ChatPage />
      </MemoryRouter>,
    );

    const textarea = await screen.findByPlaceholderText(/\u4f8b\u5982/);
    fireEvent.change(textarea, { target: { value: '\u5206\u6790 600519.SH' } });
    fireEvent.keyDown(textarea, { key: 'Enter' });

    expect(await screen.findByText('\u4ece\u81ea\u9009\u5220\u9664')).toBeInTheDocument();
  });

  it('shows "\u4ece\u81ea\u9009\u5220\u9664" for HK variant codes', async () => {
    mockGetWatchlist.mockResolvedValue(['HK01810']);

    render(
      <MemoryRouter>
        <ChatPage />
      </MemoryRouter>,
    );

    const textarea = await screen.findByPlaceholderText(/\u4f8b\u5982/);
    fireEvent.change(textarea, { target: { value: '\u5206\u6790 1810.HK' } });
    fireEvent.keyDown(textarea, { key: 'Enter' });

    expect(await screen.findByText('\u4ece\u81ea\u9009\u5220\u9664')).toBeInTheDocument();
  });

  it('matches raw HK watchlist entries before rendering the watchlist action', async () => {
    mockGetWatchlist.mockResolvedValue(['01810']);

    render(
      <MemoryRouter>
        <ChatPage />
      </MemoryRouter>,
    );

    const textarea = await screen.findByPlaceholderText(/\u4f8b\u5982/);
    fireEvent.change(textarea, { target: { value: '\u5206\u6790 1810.HK' } });
    fireEvent.keyDown(textarea, { key: 'Enter' });

    expect(await screen.findByText('\u4ece\u81ea\u9009\u5220\u9664')).toBeInTheDocument();
  });

  it('removes the matched raw HK watchlist entry instead of adding a duplicate variant', async () => {
    mockGetWatchlist.mockResolvedValue(['00700']);
    mockRemoveFromWatchlist.mockResolvedValue([]);

    render(
      <MemoryRouter>
        <ChatPage />
      </MemoryRouter>,
    );

    const textarea = await screen.findByPlaceholderText(/\u4f8b\u5982/);
    fireEvent.change(textarea, { target: { value: '\u5206\u6790 00700.HK' } });
    fireEvent.keyDown(textarea, { key: 'Enter' });
    fireEvent.click(await screen.findByText('\u4ece\u81ea\u9009\u5220\u9664'));

    await waitFor(() => {
      expect(mockRemoveFromWatchlist).toHaveBeenCalledWith('00700');
    });
    expect(mockAddToWatchlist).not.toHaveBeenCalled();
  });
});
