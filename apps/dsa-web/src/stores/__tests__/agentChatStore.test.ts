import { beforeEach, describe, expect, it, vi } from 'vitest';
import { useAgentChatStore } from '../agentChatStore';

vi.mock('../../api/agent', () => ({
  agentApi: {
    getChatSessions: vi.fn(async () => []),
    getChatSessionMessages: vi.fn(async () => []),
    chatStream: vi.fn(),
  },
}));

const { agentApi } = await import('../../api/agent');

const encoder = new TextEncoder();

function createStreamResponse(lines: string[]) {
  return new Response(
    new ReadableStream({
      start(controller) {
        controller.enqueue(encoder.encode(lines.join('\n')));
        controller.close();
      },
    }),
    {
      status: 200,
      headers: { 'Content-Type': 'text/event-stream' },
    },
  );
}

function createDeferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

beforeEach(() => {
  localStorage.clear();
  useAgentChatStore.setState({
    messages: [],
    loading: false,
    progressSteps: [],
    sessionId: 'session-test',
    sessions: [],
    sessionsLoading: false,
    chatError: null,
    currentRoute: '/chat',
    completionBadge: false,
    hasInitialLoad: true,
    abortController: null,
  });
  vi.clearAllMocks();
});

describe('agentChatStore.startStream', () => {
  it('appends the user message and final assistant message from the SSE stream', async () => {
    vi.mocked(agentApi.chatStream).mockResolvedValue(
      createStreamResponse([
        'data: {"type":"thinking","step":1,"message":"\u5206\u6790\u4e2d"}',
        'data: {"type":"tool_done","tool":"quote","display_name":"\u884c\u60c5","success":true,"duration":0.3}',
        'data: {"type":"done","success":true,"content":"\u6700\u7ec8\u5206\u6790\u7ed3\u679c"}',
      ]),
    );

    await useAgentChatStore
      .getState()
      .startStream({ message: '\u5206\u6790\u8305\u53f0', session_id: 'session-test' }, { skillName: '\u8d8b\u52bf\u6280\u80fd' });

    const state = useAgentChatStore.getState();
    expect(state.loading).toBe(false);
    expect(state.chatError).toBeNull();
    expect(state.messages).toHaveLength(2);
    expect(state.messages[0]).toMatchObject({
      role: 'user',
      content: '\u5206\u6790\u8305\u53f0',
      skillName: '\u8d8b\u52bf\u6280\u80fd',
    });
    expect(state.messages[1]).toMatchObject({
      role: 'assistant',
      content: '\u6700\u7ec8\u5206\u6790\u7ed3\u679c',
      skillName: '\u8d8b\u52bf\u6280\u80fd',
    });
    expect(state.messages[1].thinkingSteps).toHaveLength(2);
    expect(state.progressSteps).toEqual([]);
  });

  it('preserves multiple selected skills on streamed user and assistant messages', async () => {
    vi.mocked(agentApi.chatStream).mockResolvedValue(
      createStreamResponse([
        'data: {"type":"done","success":true,"content":"\u591a\u7b56\u7565\u5206\u6790\u7ed3\u679c"}',
      ]),
    );

    await useAgentChatStore
      .getState()
      .startStream(
        {
          message: '\u5206\u6790\u8305\u53f0',
          session_id: 'session-test',
          skills: ['bull_trend', 'ma_golden_cross'],
        },
        {
          skillNames: ['\u8d8b\u52bf\u5206\u6790', '\u5747\u7ebf\u91d1\u53c9'],
        },
      );

    const state = useAgentChatStore.getState();
    expect(state.messages).toHaveLength(2);
    expect(state.messages[0]).toMatchObject({
      role: 'user',
      skills: ['bull_trend', 'ma_golden_cross'],
      skill: 'bull_trend',
      skillNames: ['\u8d8b\u52bf\u5206\u6790', '\u5747\u7ebf\u91d1\u53c9'],
      skillName: '\u8d8b\u52bf\u5206\u6790、\u5747\u7ebf\u91d1\u53c9',
    });
    expect(state.messages[1]).toMatchObject({
      role: 'assistant',
      content: '\u591a\u7b56\u7565\u5206\u6790\u7ed3\u679c',
      skills: ['bull_trend', 'ma_golden_cross'],
      skill: 'bull_trend',
      skillNames: ['\u8d8b\u52bf\u5206\u6790', '\u5747\u7ebf\u91d1\u53c9'],
      skillName: '\u8d8b\u52bf\u5206\u6790、\u5747\u7ebf\u91d1\u53c9',
    });
  });

  it('reports an interrupted stream instead of appending an empty assistant message', async () => {
    vi.mocked(agentApi.chatStream).mockResolvedValue(
      createStreamResponse([
        'data: {"type":"thinking","step":1,"message":"\u5206\u6790\u4e2d"}',
      ]),
    );

    await useAgentChatStore
      .getState()
      .startStream({ message: '\u5206\u6790\u8305\u53f0', session_id: 'session-test' }, { skillName: '\u8d8b\u52bf\u6280\u80fd' });

    const state = useAgentChatStore.getState();
    expect(state.loading).toBe(false);
    expect(state.messages).toHaveLength(1);
    expect(state.messages[0]).toMatchObject({
      role: 'user',
      content: '\u5206\u6790\u8305\u53f0',
    });
    expect(state.chatError).toMatchObject({
      title: '\u56de\u590d\u672a\u5b8c\u6574\u8fd4\u56de',
      message: 'Agent \u6d41\u5f0f\u54cd\u5e94\u5728\u5b8c\u6210\u524d\u4e2d\u65ad，\u8bf7\u91cd\u8bd5。',
      category: 'upstream_network',
      rawMessage: 'Agent stream ended before a done event was received.',
    });
  });

  it('preserves parsed error details when done.success is false', async () => {
    vi.mocked(agentApi.chatStream).mockResolvedValue(
      createStreamResponse([
        'data: {"type":"done","success":false,"error":"Agent LLM: no effective primary model configured"}',
      ]),
    );

    await useAgentChatStore
      .getState()
      .startStream({ message: '\u5206\u6790\u8305\u53f0', session_id: 'session-test' }, { skillName: '\u8d8b\u52bf\u6280\u80fd' });

    const state = useAgentChatStore.getState();
    expect(state.loading).toBe(false);
    expect(state.messages).toHaveLength(1);
    expect(state.chatError).toMatchObject({
      title: '\u7cfb\u7edf\u6ca1\u6709\u914d\u7f6e\u53ef\u7528\u7684 LLM \u6a21\u578b',
      message: '\u8bf7\u5148\u5728\u7cfb\u7edf\u8bbe\u7f6e\u4e2d\u914d\u7f6e\u4e3b\u6a21\u578b、\u53ef\u7528\u6e20\u9053\u6216\u76f8\u5173 API Key \u540e\u518d\u91cd\u8bd5。',
      category: 'llm_not_configured',
      rawMessage: 'Agent LLM: no effective primary model configured',
    });
  });

  it('uses the same parser for SSE error events', async () => {
    vi.mocked(agentApi.chatStream).mockResolvedValue(
      createStreamResponse([
        'data: {"type":"error","message":"connect timeout while calling upstream provider"}',
      ]),
    );

    await useAgentChatStore
      .getState()
      .startStream({ message: '\u5206\u6790\u8305\u53f0', session_id: 'session-test' }, { skillName: '\u8d8b\u52bf\u6280\u80fd' });

    const state = useAgentChatStore.getState();
    expect(state.loading).toBe(false);
    expect(state.messages).toHaveLength(1);
    expect(state.chatError).toMatchObject({
      title: '\u8fde\u63a5\u4e0a\u6e38\u670d\u52a1\u8d85\u65f6',
      message: '\u670d\u52a1\u7aef\u8bbf\u95ee\u5916\u90e8\u4f9d\u8d56\u65f6\u8d85\u65f6，\u8bf7\u7a0d\u540e\u91cd\u8bd5，\u6216\u68c0\u67e5\u5f53\u524d\u7f51\u7edc\u4e0e\u4ee3\u7406\u8bbe\u7f6e。',
      category: 'upstream_timeout',
      rawMessage: 'connect timeout while calling upstream provider',
    });
  });

  it('falls back when SSE error fields are empty strings', async () => {
    vi.mocked(agentApi.chatStream).mockResolvedValue(
      createStreamResponse([
        'data: {"type":"error","error":"","message":"   ","content":""}',
      ]),
    );

    await useAgentChatStore
      .getState()
      .startStream({ message: '\u5206\u6790\u8305\u53f0', session_id: 'session-test' }, { skillName: '\u8d8b\u52bf\u6280\u80fd' });

    const state = useAgentChatStore.getState();
    expect(state.loading).toBe(false);
    expect(state.messages).toHaveLength(1);
    expect(state.chatError).toMatchObject({
      title: '\u8bf7\u6c42\u5931\u8d25',
      message: '\u5206\u6790\u51fa\u9519',
      category: 'unknown',
      rawMessage: '\u5206\u6790\u51fa\u9519',
    });
  });
});

describe('agentChatStore.switchSession', () => {

  it('clears transient loading state when switching sessions during a stream', async () => {
    const ac = new AbortController();
    vi.mocked(agentApi.getChatSessionMessages).mockResolvedValue([
      { id: 'msg-2', role: 'assistant', content: '\u5386\u53f2\u56de\u590d', created_at: null },
    ]);
    useAgentChatStore.setState({
      loading: true,
      progressSteps: [{ type: 'thinking', message: '\u6b63\u5728\u5236\u5b9a\u5206\u6790\u8def\u5f84...' }],
      abortController: ac,
      chatError: {
        title: '\u8bf7\u6c42\u5931\u8d25',
        message: '\u65e7\u9519\u8bef',
        category: 'unknown',
        rawMessage: '\u65e7\u9519\u8bef',
      },
    });

    await useAgentChatStore.getState().switchSession('session-2');

    const state = useAgentChatStore.getState();
    expect(ac.signal.aborted).toBe(true);
    expect(state.sessionId).toBe('session-2');
    expect(state.loading).toBe(false);
    expect(state.progressSteps).toEqual([]);
    expect(state.abortController).toBeNull();
    expect(state.chatError).toBeNull();
    expect(state.messages).toEqual([
      { id: 'msg-2', role: 'assistant', content: '\u5386\u53f2\u56de\u590d' },
    ]);
  });

  it('does not let a late session history response overwrite the current session', async () => {
    const sessionA = createDeferred<
      Array<{ id: string; role: 'user' | 'assistant'; content: string; created_at: string | null }>
    >();
    const sessionB = createDeferred<
      Array<{ id: string; role: 'user' | 'assistant'; content: string; created_at: string | null }>
    >();
    vi.mocked(agentApi.getChatSessionMessages).mockImplementation((targetSessionId: string) => {
      if (targetSessionId === 'session-a') return sessionA.promise;
      if (targetSessionId === 'session-b') return sessionB.promise;
      return Promise.resolve([]);
    });

    const switchToA = useAgentChatStore.getState().switchSession('session-a');
    const switchToB = useAgentChatStore.getState().switchSession('session-b');

    sessionB.resolve([{ id: 'msg-b', role: 'assistant', content: 'B \u56de\u590d', created_at: null }]);
    await switchToB;

    sessionA.resolve([{ id: 'msg-a', role: 'assistant', content: 'A \u56de\u590d', created_at: null }]);
    await switchToA;

    const state = useAgentChatStore.getState();
    expect(state.sessionId).toBe('session-b');
    expect(state.messages).toEqual([
      { id: 'msg-b', role: 'assistant', content: 'B \u56de\u590d' },
    ]);
  });
});
