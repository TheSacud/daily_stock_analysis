import { useState } from 'react';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { LLMChannelEditor } from '../LLMChannelEditor';

const {
  update,
  testLLMChannel,
  discoverLLMChannelModels,
} = vi.hoisted(() => ({
  update: vi.fn(),
  testLLMChannel: vi.fn(),
  discoverLLMChannelModels: vi.fn(),
}));

vi.mock('../../../api/systemConfig', () => ({
  systemConfigApi: {
    update: (...args: unknown[]) => update(...args),
    testLLMChannel: (...args: unknown[]) => testLLMChannel(...args),
    discoverLLMChannelModels: (...args: unknown[]) => discoverLLMChannelModels(...args),
  },
}));

describe('LLMChannelEditor', () => {
  beforeEach(() => {
    update.mockReset();
    testLLMChannel.mockReset();
    discoverLLMChannelModels.mockReset();
  });

  function selectOptionValues(label: string): string[] {
    const select = screen.getByLabelText(label) as HTMLSelectElement;
    return Array.from(select.options).map((option) => option.value);
  }

  const openAiItems = [
    { key: 'LLM_CHANNELS', value: 'openai' },
    { key: 'LLM_OPENAI_PROTOCOL', value: 'openai' },
    { key: 'LLM_OPENAI_BASE_URL', value: 'https://api.openai.com/v1' },
    { key: 'LLM_OPENAI_ENABLED', value: 'true' },
    { key: 'LLM_OPENAI_API_KEY', value: 'secret-key' },
    { key: 'LLM_OPENAI_MODELS', value: 'gpt-4o-mini' },
    { key: 'LITELLM_MODEL', value: 'openai/gpt-4o-mini' },
  ];

  function lastDraftCall(onDraftItemsChange: ReturnType<typeof vi.fn>) {
    const calls = onDraftItemsChange.mock.calls;
    return calls[calls.length - 1]?.[0] || [];
  }

  it('reports an empty generation backend draft when channel settings are unchanged', async () => {
    const onDraftItemsChange = vi.fn();
    const { rerender } = render(
      <LLMChannelEditor
        items={openAiItems}
        configVersion="v1"
        maskToken="******"
        onSaved={() => {}}
        onDraftItemsChange={onDraftItemsChange}
      />
    );

    await waitFor(() => expect(onDraftItemsChange).toHaveBeenCalledWith([]));
    expect(onDraftItemsChange).toHaveBeenCalledTimes(1);

    rerender(
      <LLMChannelEditor
        items={openAiItems}
        configVersion="v1"
        maskToken="******"
        onSaved={() => {}}
        onDraftItemsChange={onDraftItemsChange}
      />
    );

    expect(onDraftItemsChange).toHaveBeenCalledTimes(1);
  });

  it('reports unsaved channel edits as generation backend draft items', async () => {
    const onDraftItemsChange = vi.fn();
    render(
      <LLMChannelEditor
        items={openAiItems}
        configVersion="v1"
        maskToken="******"
        onSaved={() => {}}
        onDraftItemsChange={onDraftItemsChange}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: /OpenAI \u5b98\u65b9/i }));
    fireEvent.change(await screen.findByLabelText('Base URL'), {
      target: { value: 'https://proxy.example.com/v1' },
    });
    fireEvent.change(screen.getByLabelText('API Key'), {
      target: { value: 'sk-draft' },
    });
    fireEvent.change(screen.getByLabelText('\u6a21\u578b（\u9017\u53f7\u5206\u9694）'), {
      target: { value: 'gpt-4o-mini,gpt-4o' },
    });

    await waitFor(() => {
      const draft = lastDraftCall(onDraftItemsChange);
      expect(draft).toContainEqual({ key: 'LLM_OPENAI_BASE_URL', value: 'https://proxy.example.com/v1' });
      expect(draft).toContainEqual({ key: 'LLM_OPENAI_API_KEY', value: 'sk-draft' });
      expect(draft).toContainEqual({ key: 'LLM_OPENAI_MODELS', value: 'gpt-4o-mini,gpt-4o' });
    });
  });

  it('returns to an empty generation backend draft after channel edits are restored', async () => {
    const onDraftItemsChange = vi.fn();
    render(
      <LLMChannelEditor
        items={openAiItems}
        configVersion="v1"
        maskToken="******"
        onSaved={() => {}}
        onDraftItemsChange={onDraftItemsChange}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: /OpenAI \u5b98\u65b9/i }));
    const baseUrlInput = await screen.findByLabelText('Base URL');
    fireEvent.change(baseUrlInput, { target: { value: 'https://proxy.example.com/v1' } });
    await waitFor(() => expect(lastDraftCall(onDraftItemsChange)).toContainEqual({
      key: 'LLM_OPENAI_BASE_URL',
      value: 'https://proxy.example.com/v1',
    }));

    fireEvent.change(baseUrlInput, { target: { value: 'https://api.openai.com/v1' } });

    await waitFor(() => {
      expect(lastDraftCall(onDraftItemsChange)).toEqual([]);
    });
  });

  it('does not emit invalid channel env keys while the channel name is empty', async () => {
    const onDraftItemsChange = vi.fn();
    render(
      <LLMChannelEditor
        items={openAiItems}
        configVersion="v1"
        maskToken="******"
        onSaved={() => {}}
        onDraftItemsChange={onDraftItemsChange}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: /OpenAI \u5b98\u65b9/i }));
    fireEvent.change(await screen.findByLabelText('\u6e20\u9053\u540d\u79f0'), { target: { value: '' } });

    await waitFor(() => {
      expect(lastDraftCall(onDraftItemsChange)).toEqual([]);
    });
    expect(onDraftItemsChange.mock.calls.flatMap((call) => call[0]).some((item) => item.key.startsWith('LLM__'))).toBe(false);
  });

  it('renders API Key input with controlled visibility', async () => {
    render(
      <LLMChannelEditor
        items={[
          { key: 'LLM_CHANNELS', value: 'openai' },
          { key: 'LLM_OPENAI_PROTOCOL', value: 'openai' },
          { key: 'LLM_OPENAI_BASE_URL', value: 'https://api.openai.com/v1' },
          { key: 'LLM_OPENAI_ENABLED', value: 'true' },
          { key: 'LLM_OPENAI_API_KEY', value: 'secret-key' },
          { key: 'LLM_OPENAI_MODELS', value: 'gpt-4o-mini' },
        ]}
        configVersion="v1"
        maskToken="******"
        onSaved={() => {}}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: /OpenAI \u5b98\u65b9/i }));

    const input = await screen.findByLabelText('API Key');
    expect(input).toHaveAttribute('type', 'password');

    fireEvent.click(screen.getByRole('button', { name: '\u663e\u793a\u5185\u5bb9' }));
    expect(input).toHaveAttribute('type', 'text');
  });

  it('shows help dialogs for channel editor fields', async () => {
    render(
      <LLMChannelEditor
        items={[
          { key: 'LLM_CHANNELS', value: 'deepseek' },
          { key: 'LLM_DEEPSEEK_PROTOCOL', value: 'deepseek' },
          { key: 'LLM_DEEPSEEK_BASE_URL', value: 'https://api.deepseek.com' },
          { key: 'LLM_DEEPSEEK_ENABLED', value: 'true' },
          { key: 'LLM_DEEPSEEK_API_KEY', value: 'sk-test' },
          { key: 'LLM_DEEPSEEK_MODELS', value: 'deepseek-v4-flash' },
        ]}
        configVersion="v1"
        maskToken="******"
        onSaved={() => {}}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: /DeepSeek \u5b98\u65b9/i }));
    fireEvent.click(await screen.findByRole('button', { name: '\u67e5\u770b Base URL \u914d\u7f6e\u8bf4\u660e' }));

    expect(screen.getByRole('dialog', { name: 'Base URL' })).toBeInTheDocument();
    expect(screen.getByText('\u8be5\u6e20\u9053\u7684\u63a5\u53e3\u6839\u5730\u5740。')).toBeInTheDocument();
    expect(screen.getByText('LLM_DEEPSEEK_BASE_URL=https://api.deepseek.com')).toBeInTheDocument();

    fireEvent.keyDown(document, { key: 'Escape' });
    fireEvent.click(await screen.findByRole('button', { name: '\u67e5\u770b Temperature \u914d\u7f6e\u8bf4\u660e' }));

    expect(screen.getByRole('dialog', { name: 'Temperature' })).toBeInTheDocument();
    expect(screen.getByText('\u8fd0\u884c\u65f6\u7edf\u4e00\u91c7\u6837\u6e29\u5ea6。')).toBeInTheDocument();

    fireEvent.keyDown(document, { key: 'Escape' });
    fireEvent.click(await screen.findByRole('button', { name: '\u67e5\u770b \u8fd0\u884c\u65f6\u80fd\u529b\u68c0\u6d4b \u914d\u7f6e\u8bf4\u660e' }));

    expect(screen.getByRole('dialog', { name: '\u8fd0\u884c\u65f6\u80fd\u529b\u68c0\u6d4b' })).toBeInTheDocument();
    expect(screen.getByText('\u9009\u62e9\u80fd\u529b\u540e\u70b9\u51fb\u68c0\u6d4b；\u68c0\u6d4b\u4f1a\u53d1\u8d77\u771f\u5b9e LLM \u8bf7\u6c42。')).toBeInTheDocument();
  });

  it('hides LiteLLM wording when advanced YAML routing is enabled', () => {
    render(
      <LLMChannelEditor
        items={[
          { key: 'LLM_CHANNELS', value: 'openai' },
          { key: 'LITELLM_CONFIG', value: './litellm_config.yaml' },
          { key: 'LLM_OPENAI_PROTOCOL', value: 'openai' },
          { key: 'LLM_OPENAI_BASE_URL', value: 'https://api.openai.com/v1' },
          { key: 'LLM_OPENAI_ENABLED', value: 'true' },
          { key: 'LLM_OPENAI_API_KEY', value: 'secret-key' },
          { key: 'LLM_OPENAI_MODELS', value: 'gpt-4o-mini' },
        ]}
        configVersion="v1"
        maskToken="******"
        onSaved={() => {}}
      />
    );

    expect(screen.getByText(/\u68c0\u6d4b\u5230\u5df2\u914d\u7f6e\u9ad8\u7ea7\u6a21\u578b\u8def\u7531 YAML/i)).toBeInTheDocument();
    expect(screen.getByText(/\u8fd0\u884c\u65f6\u4e3b\u6a21\u578b \/ \u5907\u9009\u6a21\u578b \/ Vision \/ Temperature \u4ecd\u7531\u4e0b\u65b9\u901a\u7528\u5b57\u6bb5\u51b3\u5b9a/i)).toBeInTheDocument();
    expect(screen.queryByText(/LiteLLM/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/LITELLM_CONFIG/i)).not.toBeInTheDocument();
  });

  it('excludes Hermes-only route from Agent and Vision runtime selects', () => {
    render(
      <LLMChannelEditor
        items={[
          { key: 'LLM_CHANNELS', value: 'hermes' },
          { key: 'LLM_HERMES_PROTOCOL', value: 'openai' },
          { key: 'LLM_HERMES_BASE_URL', value: 'http://127.0.0.1:8642/v1' },
          { key: 'LLM_HERMES_ENABLED', value: 'true' },
          { key: 'LLM_HERMES_API_KEY', value: '******' },
          { key: 'LLM_HERMES_MODELS', value: 'hermes-agent' },
        ]}
        configVersion="v1"
        maskToken="******"
        onSaved={() => {}}
      />
    );

    expect(selectOptionValues('\u4e3b\u6a21\u578b')).toContain('openai/hermes-agent');
    expect(selectOptionValues('Agent \u4e3b\u6a21\u578b')).not.toContain('openai/hermes-agent');
    expect(selectOptionValues('Vision \u6a21\u578b')).not.toContain('openai/hermes-agent');
  });

  it('keeps mixed Hermes route for Agent but excludes it from Vision', () => {
    render(
      <LLMChannelEditor
        items={[
          { key: 'LLM_CHANNELS', value: 'hermes,remote,pure' },
          { key: 'LLM_HERMES_PROTOCOL', value: 'openai' },
          { key: 'LLM_HERMES_BASE_URL', value: 'http://127.0.0.1:8642/v1' },
          { key: 'LLM_HERMES_ENABLED', value: 'true' },
          { key: 'LLM_HERMES_API_KEY', value: '******' },
          { key: 'LLM_HERMES_MODELS', value: 'shared-route' },
          { key: 'LLM_REMOTE_PROTOCOL', value: 'openai' },
          { key: 'LLM_REMOTE_BASE_URL', value: 'https://api.example.com/v1' },
          { key: 'LLM_REMOTE_ENABLED', value: 'true' },
          { key: 'LLM_REMOTE_API_KEY', value: 'sk-remote' },
          { key: 'LLM_REMOTE_MODELS', value: 'shared-route' },
          { key: 'LLM_PURE_PROTOCOL', value: 'openai' },
          { key: 'LLM_PURE_BASE_URL', value: 'https://api.example.com/v1' },
          { key: 'LLM_PURE_ENABLED', value: 'true' },
          { key: 'LLM_PURE_API_KEY', value: 'sk-pure' },
          { key: 'LLM_PURE_MODELS', value: 'pure-route' },
        ]}
        configVersion="v1"
        maskToken="******"
        onSaved={() => {}}
      />
    );

    expect(selectOptionValues('\u4e3b\u6a21\u578b')).not.toContain('openai/shared-route');
    expect(selectOptionValues('\u4e3b\u6a21\u578b')).toContain('openai/pure-route');
    expect(selectOptionValues('Agent \u4e3b\u6a21\u578b')).toContain('openai/shared-route');
    expect(selectOptionValues('Vision \u6a21\u578b')).not.toContain('openai/shared-route');
  });

  it('rejects bare mixed Hermes route before saving runtime generation config', async () => {
    render(
      <LLMChannelEditor
        items={[
          { key: 'LLM_CHANNELS', value: 'hermes,remote' },
          { key: 'LITELLM_MODEL', value: 'shared-route' },
          { key: 'LLM_HERMES_PROTOCOL', value: 'openai' },
          { key: 'LLM_HERMES_BASE_URL', value: 'http://127.0.0.1:8642/v1' },
          { key: 'LLM_HERMES_ENABLED', value: 'true' },
          { key: 'LLM_HERMES_API_KEY', value: 'sk-hermes' },
          { key: 'LLM_HERMES_MODELS', value: 'shared-route' },
          { key: 'LLM_REMOTE_PROTOCOL', value: 'openai' },
          { key: 'LLM_REMOTE_BASE_URL', value: 'https://api.example.com/v1' },
          { key: 'LLM_REMOTE_ENABLED', value: 'true' },
          { key: 'LLM_REMOTE_API_KEY', value: 'sk-remote' },
          { key: 'LLM_REMOTE_MODELS', value: 'shared-route' },
        ]}
        configVersion="v1"
        maskToken="******"
        onSaved={() => {}}
      />
    );

    fireEvent.change(screen.getByRole('slider'), { target: { value: '0.2' } });
    fireEvent.click(screen.getByRole('button', { name: '\u4fdd\u5b58 AI \u914d\u7f6e' }));

    expect(await screen.findByText(/Mixed Hermes\/non-Hermes route \u6682\u4e0d\u652f\u6301\u4f5c\u4e3a\u4e3b\u751f\u6210\u6216\u5907\u9009\u6a21\u578b/i)).toBeInTheDocument();
    expect(update).not.toHaveBeenCalled();
  });

  it('does not test runtime-only masked Hermes secrets from the settings UI', async () => {
    render(
      <LLMChannelEditor
        items={[
          { key: 'LLM_CHANNELS', value: 'hermes' },
          { key: 'LLM_HERMES_PROTOCOL', value: 'openai' },
          { key: 'LLM_HERMES_BASE_URL', value: 'http://127.0.0.1:8642/v1' },
          { key: 'LLM_HERMES_ENABLED', value: 'true' },
          { key: 'LLM_HERMES_API_KEY', value: '******', rawValueExists: false },
          { key: 'LLM_HERMES_MODELS', value: 'hermes-agent' },
        ]}
        configVersion="v1"
        maskToken="******"
        onSaved={() => {}}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: /Hermes/i }));
    fireEvent.click(screen.getByRole('button', { name: '\u6d4b\u8bd5\u8fde\u63a5' }));
    fireEvent.click(screen.getByRole('button', { name: '\u83b7\u53d6\u6a21\u578b' }));
    fireEvent.click(screen.getByLabelText('JSON'));
    fireEvent.click(screen.getByRole('button', { name: '\u68c0\u6d4b\u80fd\u529b' }));

    const messages = await screen.findAllByText(/\u8fd0\u884c\u65f6\u6ce8\u5165\u7684 Hermes Key \u4e0d\u4f1a\u56de\u4f20/i);
    expect(messages.length).toBeGreaterThanOrEqual(3);
    expect(testLLMChannel).not.toHaveBeenCalled();
    expect(discoverLLMChannelModels).not.toHaveBeenCalled();
  });

  it('keeps pure non-Hermes route in Agent and Vision runtime selects', () => {
    render(
      <LLMChannelEditor
        items={[
          { key: 'LLM_CHANNELS', value: 'remote' },
          { key: 'LLM_REMOTE_PROTOCOL', value: 'openai' },
          { key: 'LLM_REMOTE_BASE_URL', value: 'https://api.example.com/v1' },
          { key: 'LLM_REMOTE_ENABLED', value: 'true' },
          { key: 'LLM_REMOTE_API_KEY', value: 'sk-remote' },
          { key: 'LLM_REMOTE_MODELS', value: 'gpt-4o-mini' },
        ]}
        configVersion="v1"
        maskToken="******"
        onSaved={() => {}}
      />
    );

    expect(selectOptionValues('\u4e3b\u6a21\u578b')).toContain('openai/gpt-4o-mini');
    expect(selectOptionValues('Agent \u4e3b\u6a21\u578b')).toContain('openai/gpt-4o-mini');
    expect(selectOptionValues('Vision \u6a21\u578b')).toContain('openai/gpt-4o-mini');
  });

  it('keeps minimax-prefixed models in runtime selections', () => {
    render(
      <LLMChannelEditor
        items={[
          { key: 'LLM_CHANNELS', value: 'openai' },
          { key: 'LLM_OPENAI_PROTOCOL', value: 'openai' },
          { key: 'LLM_OPENAI_BASE_URL', value: 'https://api.example.com/v1' },
          { key: 'LLM_OPENAI_ENABLED', value: 'true' },
          { key: 'LLM_OPENAI_API_KEY', value: 'secret-key' },
          { key: 'LLM_OPENAI_MODELS', value: 'minimax/MiniMax-M1' },
        ]}
        configVersion="v1"
        maskToken="******"
        onSaved={() => {}}
      />
    );

    const primaryModelSelect = screen.getByRole('combobox', { name: '\u4e3b\u6a21\u578b' });
    const agentModelSelect = screen.getByRole('combobox', { name: 'Agent \u4e3b\u6a21\u578b' });
    const visionModelSelect = screen.getByRole('combobox', { name: 'Vision \u6a21\u578b' });

    expect(within(primaryModelSelect).getByRole('option', { name: 'minimax/MiniMax-M1' })).toBeInTheDocument();
    expect(within(agentModelSelect).getByRole('option', { name: 'minimax/MiniMax-M1' })).toBeInTheDocument();
    expect(within(visionModelSelect).getByRole('option', { name: 'minimax/MiniMax-M1' })).toBeInTheDocument();
  });

  it('uses DeepSeek V4 defaults when adding the official preset', async () => {
    render(
      <LLMChannelEditor
        items={[]}
        configVersion="v1"
        maskToken="******"
        onSaved={() => {}}
      />
    );

    fireEvent.change(screen.getByRole('combobox'), { target: { value: 'deepseek' } });
    fireEvent.click(screen.getByRole('button', { name: '+ \u6dfb\u52a0\u6e20\u9053' }));

    await screen.findByRole('button', { name: /DeepSeek \u5b98\u65b9/i });
    expect(screen.getByLabelText('Base URL')).toHaveValue('https://api.deepseek.com');
    expect(screen.getByLabelText('\u6a21\u578b（\u9017\u53f7\u5206\u9694）')).toHaveValue('deepseek-v4-flash,deepseek-v4-pro');
  });

  it.each([
    ['minimax', /MiniMax \u5b98\u65b9/i, 'https://api.minimax.io/v1', 'MiniMax-M3,MiniMax-M2.7,MiniMax-M2.7-highspeed'],
    ['volcengine', /\u706b\u5c71\u65b9\u821f/i, 'https://ark.cn-beijing.volces.com/api/v3', 'doubao-seed-1-6-251015,doubao-seed-1-6-thinking-251015'],
  ])('uses %s OpenAI-compatible defaults when adding the official preset', async (preset, buttonName, baseUrl, models) => {
    render(
      <LLMChannelEditor
        items={[]}
        configVersion="v1"
        maskToken="******"
        onSaved={() => {}}
      />
    );

    fireEvent.change(screen.getByRole('combobox'), { target: { value: preset } });
    fireEvent.click(screen.getByRole('button', { name: '+ \u6dfb\u52a0\u6e20\u9053' }));

    await screen.findByRole('button', { name: buttonName });
    expect(screen.getAllByRole('combobox').some((select) => (
      select instanceof HTMLSelectElement && select.value === 'openai'
    ))).toBe(true);
    expect(screen.getByLabelText('Base URL')).toHaveValue(baseUrl);
    expect(screen.getByLabelText('\u6a21\u578b（\u9017\u53f7\u5206\u9694）')).toHaveValue(models);
  });

  it('shows provider capability badges, official sources, and config hints', async () => {
    render(
      <LLMChannelEditor
        items={[
          { key: 'LLM_CHANNELS', value: 'openrouter' },
          { key: 'LLM_OPENROUTER_PROTOCOL', value: 'openai' },
          { key: 'LLM_OPENROUTER_BASE_URL', value: 'https://openrouter.ai/api/v1' },
          { key: 'LLM_OPENROUTER_ENABLED', value: 'true' },
          { key: 'LLM_OPENROUTER_API_KEY', value: 'sk-or-test' },
          { key: 'LLM_OPENROUTER_MODELS', value: '~anthropic/claude-sonnet-latest' },
        ]}
        configVersion="v1"
        maskToken="******"
        onSaved={() => {}}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: /OpenRouter/i }));

    expect(await screen.findByText('\u914d\u7f6e\u53c2\u8003')).toBeInTheDocument();
    expect(screen.getByText('OpenAI \u517c\u5bb9')).toBeInTheDocument();
    expect(screen.getByText('\u805a\u5408\u5e73\u53f0')).toBeInTheDocument();
    expect(screen.getByText('\u53ef\u83b7\u53d6\u6a21\u578b')).toBeInTheDocument();
    expect(screen.getByText(/\u6a21\u578b\u5217\u8868\u548c\u6a21\u578b\u53ef\u89c1\u6027\u4f9d\u8d56\u8d26\u53f7\u6743\u9650\u4e0e API Key/i)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'OpenRouter Models API' })).toHaveAttribute(
      'href',
      'https://openrouter.ai/docs/api/api-reference/models/get-models',
    );
    expect(screen.getByText(/\u80fd\u529b\u6807\u7b7e\u4ec5\u7528\u4e8e\u914d\u7f6e\u53c2\u8003，\u4e0d\u4ee3\u8868\u8fd0\u884c\u65f6\u80fd\u529b\u5df2\u9a8c\u8bc1\u901a\u8fc7/i)).toBeInTheDocument();
  });

  it('shows model-discovery capability for SiliconFlow provider hints', async () => {
    render(
      <LLMChannelEditor
        items={[
          { key: 'LLM_CHANNELS', value: 'siliconflow' },
          { key: 'LLM_SILICONFLOW_PROTOCOL', value: 'openai' },
          { key: 'LLM_SILICONFLOW_BASE_URL', value: 'https://api.siliconflow.cn/v1' },
          { key: 'LLM_SILICONFLOW_ENABLED', value: 'true' },
          { key: 'LLM_SILICONFLOW_API_KEY', value: 'sk-test' },
          { key: 'LLM_SILICONFLOW_MODELS', value: 'deepseek-ai/DeepSeek-V3.2' },
        ]}
        configVersion="v1"
        maskToken="******"
        onSaved={() => {}}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: /SiliconFlow/i }));

    expect(await screen.findByText('\u53ef\u83b7\u53d6\u6a21\u578b')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'SiliconFlow Models' })).toBeInTheDocument();
  });

  it('does not show provider metadata for custom or unknown channels', async () => {
    render(
      <LLMChannelEditor
        items={[
          { key: 'LLM_CHANNELS', value: 'my_proxy' },
          { key: 'LLM_MY_PROXY_PROTOCOL', value: 'openai' },
          { key: 'LLM_MY_PROXY_BASE_URL', value: 'https://proxy.example.com/v1' },
          { key: 'LLM_MY_PROXY_ENABLED', value: 'true' },
          { key: 'LLM_MY_PROXY_API_KEY', value: 'sk-test' },
          { key: 'LLM_MY_PROXY_MODELS', value: 'custom-model' },
        ]}
        configVersion="v1"
        maskToken="******"
        onSaved={() => {}}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: /my_proxy/i }));

    expect(screen.queryByText('\u914d\u7f6e\u53c2\u8003')).not.toBeInTheDocument();
    expect(screen.queryByText(/\u5b98\u65b9\u6765\u6e90/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/\u80fd\u529b\u6807\u7b7e\u4ec5\u7528\u4e8e\u914d\u7f6e\u53c2\u8003/i)).not.toBeInTheDocument();
  });

  it('preserves manually edited base URL and models when switching preset names', async () => {
    render(
      <LLMChannelEditor
        items={[]}
        configVersion="v1"
        maskToken="******"
        onSaved={() => {}}
      />
    );

    fireEvent.change(screen.getByRole('combobox'), { target: { value: 'deepseek' } });
    fireEvent.click(screen.getByRole('button', { name: '+ \u6dfb\u52a0\u6e20\u9053' }));

    await screen.findByRole('button', { name: /DeepSeek \u5b98\u65b9/i });
    fireEvent.change(screen.getByLabelText('Base URL'), {
      target: { value: 'https://proxy.example.com/v1' },
    });
    fireEvent.change(screen.getByLabelText('\u6a21\u578b（\u9017\u53f7\u5206\u9694）'), {
      target: { value: 'custom-model-a,custom-model-b' },
    });
    fireEvent.change(screen.getByLabelText('\u6e20\u9053\u540d\u79f0'), {
      target: { value: 'minimax' },
    });

    await screen.findByRole('button', { name: /MiniMax \u5b98\u65b9/i });
    expect(screen.getByLabelText('Base URL')).toHaveValue('https://proxy.example.com/v1');
    expect(screen.getByLabelText('\u6a21\u578b（\u9017\u53f7\u5206\u9694）')).toHaveValue('custom-model-a,custom-model-b');
  });

  it('uses the selected preset defaults when adding a duplicate provider channel', async () => {
    render(
      <LLMChannelEditor
        items={[]}
        configVersion="v1"
        maskToken="******"
        onSaved={() => {}}
      />
    );

    fireEvent.change(screen.getByRole('combobox'), { target: { value: 'minimax' } });
    fireEvent.click(screen.getByRole('button', { name: '+ \u6dfb\u52a0\u6e20\u9053' }));
    await screen.findByRole('button', { name: /MiniMax \u5b98\u65b9/i });
    fireEvent.click(screen.getByRole('button', { name: '+ \u6dfb\u52a0\u6e20\u9053' }));

    await screen.findByRole('button', { name: /minimax2/i });
    expect(screen.getAllByLabelText('\u6e20\u9053\u540d\u79f0').map((input) => (input as HTMLInputElement).value)).toEqual([
      'minimax',
      'minimax2',
    ]);
    expect(screen.getAllByLabelText('Base URL').map((input) => (input as HTMLInputElement).value)).toEqual([
      'https://api.minimax.io/v1',
      'https://api.minimax.io/v1',
    ]);
    expect(screen.getAllByLabelText('\u6a21\u578b（\u9017\u53f7\u5206\u9694）').map((input) => (input as HTMLInputElement).value)).toEqual([
      'MiniMax-M3,MiniMax-M2.7,MiniMax-M2.7-highspeed',
      'MiniMax-M3,MiniMax-M2.7,MiniMax-M2.7-highspeed',
    ]);
    expect(screen.getAllByRole('link', { name: 'MiniMax OpenAI API' })).toHaveLength(1);
  });

  it('saves the MiniMax preset into LLM channel env keys', async () => {
    update.mockResolvedValue({
      success: true,
      configVersion: 'v2',
      appliedCount: 1,
      skippedMaskedCount: 0,
      reloadTriggered: true,
      updatedKeys: ['LLM_CHANNELS', 'LLM_MINIMAX_PROTOCOL', 'LLM_MINIMAX_BASE_URL', 'LLM_MINIMAX_MODELS'],
      warnings: [],
    });

    render(
      <LLMChannelEditor
        items={[]}
        configVersion="v1"
        maskToken="******"
        onSaved={() => {}}
      />
    );

    fireEvent.change(screen.getByRole('combobox'), { target: { value: 'minimax' } });
    fireEvent.click(screen.getByRole('button', { name: '+ \u6dfb\u52a0\u6e20\u9053' }));
    await screen.findByRole('button', { name: /MiniMax \u5b98\u65b9/i });
    fireEvent.click(screen.getByRole('button', { name: '\u4fdd\u5b58 AI \u914d\u7f6e' }));

    await waitFor(() => {
      expect(update).toHaveBeenCalled();
    });

    const updatePayload = update.mock.calls[0][0];
    expect(updatePayload.items).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ key: 'LLM_CHANNELS', value: 'minimax' }),
        expect.objectContaining({ key: 'LLM_MINIMAX_PROTOCOL', value: 'openai' }),
        expect.objectContaining({ key: 'LLM_MINIMAX_BASE_URL', value: 'https://api.minimax.io/v1' }),
        expect.objectContaining({ key: 'LLM_MINIMAX_MODELS', value: 'MiniMax-M3,MiniMax-M2.7,MiniMax-M2.7-highspeed' }),
      ]),
    );
  });

  it('clears active Hermes unsupported multi-key and extra-header env keys on save', async () => {
    update.mockResolvedValue({
      success: true,
      configVersion: 'v2',
      appliedCount: 1,
      skippedMaskedCount: 0,
      reloadTriggered: true,
      updatedKeys: ['LLM_HERMES_API_KEYS', 'LLM_HERMES_EXTRA_HEADERS'],
      warnings: [
        '\u68c0\u6d4b\u5230\u5df2\u6e05\u7406 Hermes Phase 3 \u4e0d\u652f\u6301\u7684\u914d\u7f6e\u9879：LLM_HERMES_API_KEYS, LLM_HERMES_EXTRA_HEADERS。Hermes reserved channel \u53ea\u652f\u6301\u5355\u4e2a LLM_HERMES_API_KEY，\u4e0d\u652f\u6301\u591a Key \u6216\u989d\u5916 Header；\u5982\u9700\u6062\u590d\u65e7\u503c，\u8bf7\u4ece .env \u5907\u4efd、Git \u5386\u53f2\u6216\u684c\u9762\u7aef\u5bfc\u51fa\u5907\u4efd\u624b\u52a8\u8fd8\u539f，\u4f46\u975e\u7a7a LLM_HERMES_API_KEYS / LLM_HERMES_EXTRA_HEADERS \u4ecd\u4f1a\u88ab\u540e\u7aef\u6821\u9a8c\u62d2\u7edd。',
      ],
    });

    render(
      <LLMChannelEditor
        items={[
          { key: 'LLM_CHANNELS', value: 'hermes' },
          { key: 'LLM_HERMES_PROTOCOL', value: 'openai' },
          { key: 'LLM_HERMES_BASE_URL', value: 'http://127.0.0.1:8642/v1' },
          { key: 'LLM_HERMES_ENABLED', value: 'true' },
          { key: 'LLM_HERMES_API_KEY', value: 'sk-hermes-test-value' },
          { key: 'LLM_HERMES_API_KEYS', value: 'sk-old-a,sk-old-b' },
          { key: 'LLM_HERMES_EXTRA_HEADERS', value: '{"X":"Y"}' },
          { key: 'LLM_HERMES_MODELS', value: 'hermes-agent' },
        ]}
        configVersion="v1"
        maskToken="******"
        onSaved={() => {}}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: /Hermes/i }));
    fireEvent.change(screen.getByLabelText('\u6a21\u578b（\u9017\u53f7\u5206\u9694）'), { target: { value: 'hermes-agent,hermes-agent-2' } });
    fireEvent.click(screen.getByRole('button', { name: '\u4fdd\u5b58 AI \u914d\u7f6e' }));

    await waitFor(() => {
      expect(update).toHaveBeenCalled();
    });

    const updatePayload = update.mock.calls[0][0];
    const updateItemMap = new Map(updatePayload.items.map((item: { key: string; value: string }) => [item.key, item.value]));

    expect(updateItemMap.get('LLM_HERMES_API_KEY')).toBe('sk-hermes-test-value');
    expect(updateItemMap.get('LLM_HERMES_API_KEYS')).toBe('');
    expect(updateItemMap.get('LLM_HERMES_EXTRA_HEADERS')).toBe('');
    expect(await screen.findByText(/\u5df2\u6e05\u7406 Hermes Phase 3 \u4e0d\u652f\u6301\u7684\u914d\u7f6e\u9879/i)).toBeInTheDocument();
    expect(screen.getByText(/\u5982\u9700\u6062\u590d\u65e7\u503c，\u8bf7\u4ece \.env \u5907\u4efd/i)).toBeInTheDocument();
  });

  it('only persists edited values for runtime-only channel keys', async () => {
    update.mockResolvedValue({
      success: true,
      configVersion: 'v2',
      appliedCount: 1,
      skippedMaskedCount: 0,
      reloadTriggered: true,
      updatedKeys: ['LLM_CHANNELS', 'LLM_MY_PROXY_MODELS'],
      warnings: [],
    });

    render(
      <LLMChannelEditor
        items={[
          { key: 'LLM_CHANNELS', value: 'my_proxy', rawValueExists: false },
          { key: 'LITELLM_MODEL', value: 'openai/gpt-4o', rawValueExists: false },
          { key: 'LLM_MY_PROXY_PROTOCOL', value: 'openai', rawValueExists: false },
          { key: 'LLM_MY_PROXY_BASE_URL', value: 'https://proxy.example.com/v1', rawValueExists: false },
          { key: 'LLM_MY_PROXY_ENABLED', value: 'true', rawValueExists: false },
          { key: 'LLM_MY_PROXY_API_KEYS', value: 'sk-runtime-only', rawValueExists: false },
          { key: 'LLM_MY_PROXY_MODELS', value: 'gpt-4o-mini', rawValueExists: false },
        ]}
        configVersion="v1"
        maskToken="******"
        onSaved={() => {}}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: /my_proxy/i }));
    fireEvent.change(screen.getByLabelText('\u6a21\u578b（\u9017\u53f7\u5206\u9694）'), { target: { value: 'gpt-4o-mini,gpt-4o' } });
    fireEvent.click(screen.getByRole('button', { name: '\u4fdd\u5b58 AI \u914d\u7f6e' }));

    await waitFor(() => {
      expect(update).toHaveBeenCalled();
    });

    const updatePayload = update.mock.calls[0][0];
    const updateItemMap = new Map(updatePayload.items.map((item: { key: string; value: string }) => [item.key, item.value]));

    expect(updateItemMap.get('LLM_MY_PROXY_MODELS')).toBe('gpt-4o-mini,gpt-4o');
    expect(updateItemMap.has('LITELLM_MODEL')).toBe(false);
    expect(updateItemMap.has('LLM_MY_PROXY_PROTOCOL')).toBe(false);
    expect(updateItemMap.has('LLM_MY_PROXY_BASE_URL')).toBe(false);
    expect(updateItemMap.has('LLM_MY_PROXY_API_KEY')).toBe(false);
    expect(updateItemMap.has('LLM_MY_PROXY_API_KEYS')).toBe(false);
  });

  it('renames a mixed raw/runtime channel and clears persisted API key field', async () => {
    update.mockResolvedValue({
      success: true,
      configVersion: 'v2',
      appliedCount: 1,
      skippedMaskedCount: 0,
      reloadTriggered: true,
      updatedKeys: ['LLM_MY_PROXY_API_KEY', 'LLM_MY_PROXY2_API_KEY', 'LLM_MY_PROXY2_BASE_URL', 'LLM_MY_PROXY2_MODELS'],
      warnings: [],
    });

    render(
      <LLMChannelEditor
        items={[
          { key: 'LLM_CHANNELS', value: 'my_proxy' },
          { key: 'LLM_MY_PROXY_PROTOCOL', value: 'openai', rawValueExists: false },
          { key: 'LLM_MY_PROXY_BASE_URL', value: 'https://proxy.example.com/v1', rawValueExists: false },
          { key: 'LLM_MY_PROXY_ENABLED', value: 'true', rawValueExists: false },
          { key: 'LLM_MY_PROXY_API_KEY', value: 'sk-saved' },
          { key: 'LLM_MY_PROXY_MODELS', value: 'gpt-4o-mini', rawValueExists: false },
        ]}
        configVersion="v1"
        maskToken="******"
        onSaved={() => {}}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: /my_proxy/i }));
    fireEvent.change(screen.getByLabelText('\u6e20\u9053\u540d\u79f0'), { target: { value: 'my_proxy2' } });
    fireEvent.click(screen.getByRole('button', { name: '\u4fdd\u5b58 AI \u914d\u7f6e' }));

    await waitFor(() => {
      expect(update).toHaveBeenCalled();
    });

    const updatePayload = update.mock.calls[0][0];
    const updateItemMap = new Map(updatePayload.items.map((item: { key: string; value: string }) => [item.key, item.value]));

    expect(updateItemMap.get('LLM_MY_PROXY_API_KEY')).toBe('');
    expect(updateItemMap.has('LLM_MY_PROXY_API_KEYS')).toBe(false);
    expect(updateItemMap.has('LLM_MY_PROXY_PROTOCOL')).toBe(false);
    expect(updateItemMap.has('LLM_MY_PROXY_BASE_URL')).toBe(false);
    expect(updateItemMap.has('LLM_MY_PROXY_MODELS')).toBe(false);
    expect(updateItemMap.get('LLM_MY_PROXY2_API_KEY')).toBe('sk-saved');
    expect(updateItemMap.get('LLM_MY_PROXY2_BASE_URL')).toBe('https://proxy.example.com/v1');
    expect(updateItemMap.get('LLM_MY_PROXY2_MODELS')).toBe('gpt-4o-mini');
  });

  it('uses runtime API_KEYS when both API_KEY and API_KEYS coexist', async () => {
    render(
      <LLMChannelEditor
        items={[
          { key: 'LLM_CHANNELS', value: 'my_proxy', rawValueExists: false },
          { key: 'LLM_MY_PROXY_PROTOCOL', value: 'openai', rawValueExists: false },
          { key: 'LLM_MY_PROXY_BASE_URL', value: 'https://proxy.example.com/v1', rawValueExists: false },
          { key: 'LLM_MY_PROXY_ENABLED', value: 'true', rawValueExists: false },
          { key: 'LLM_MY_PROXY_API_KEY', value: 'sk-saved' },
          { key: 'LLM_MY_PROXY_API_KEYS', value: 'sk-runtime-only', rawValueExists: false },
          { key: 'LLM_MY_PROXY_MODELS', value: 'gpt-4o-mini', rawValueExists: false },
        ]}
        configVersion="v1"
        maskToken="******"
        onSaved={() => {}}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: /my_proxy/i }));
    expect(screen.getByLabelText('API Key')).toHaveValue('sk-runtime-only');
  });

  it('does not migrate conflicted API key data as API_KEY when renaming a channel', async () => {
    update.mockResolvedValue({
      success: true,
      configVersion: 'v2',
      appliedCount: 1,
      skippedMaskedCount: 0,
      reloadTriggered: true,
      updatedKeys: ['LLM_CHANNELS', 'LLM_MY_PROXY_API_KEY', 'LLM_MY_PROXY2_PROTOCOL', 'LLM_MY_PROXY2_BASE_URL', 'LLM_MY_PROXY2_MODELS'],
      warnings: [],
    });

    render(
      <LLMChannelEditor
        items={[
          { key: 'LLM_CHANNELS', value: 'my_proxy', rawValueExists: false },
          { key: 'LLM_MY_PROXY_PROTOCOL', value: 'openai', rawValueExists: false },
          { key: 'LLM_MY_PROXY_BASE_URL', value: 'https://proxy.example.com/v1', rawValueExists: false },
          { key: 'LLM_MY_PROXY_ENABLED', value: 'true', rawValueExists: false },
          { key: 'LLM_MY_PROXY_API_KEY', value: 'sk-saved' },
          { key: 'LLM_MY_PROXY_API_KEYS', value: 'sk-runtime-only', rawValueExists: false },
          { key: 'LLM_MY_PROXY_MODELS', value: 'gpt-4o-mini', rawValueExists: false },
        ]}
        configVersion="v1"
        maskToken="******"
        onSaved={() => {}}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: /my_proxy/i }));
    fireEvent.change(screen.getByLabelText('\u6e20\u9053\u540d\u79f0'), { target: { value: 'my_proxy2' } });
    fireEvent.click(screen.getByRole('button', { name: '\u4fdd\u5b58 AI \u914d\u7f6e' }));

    await waitFor(() => {
      expect(update).toHaveBeenCalled();
    });

    const updatePayload = update.mock.calls[0][0];
    const updateItemMap = new Map(updatePayload.items.map((item: { key: string; value: string }) => [item.key, item.value]));

    expect(updateItemMap.get('LLM_CHANNELS')).toBe('my_proxy2');
    expect(updateItemMap.has('LLM_MY_PROXY2_API_KEY')).toBe(false);
    expect(updateItemMap.has('LLM_MY_PROXY2_API_KEYS')).toBe(false);
    expect([...updateItemMap.values()]).not.toContain('sk-runtime-only');
    expect([...updateItemMap.values()]).not.toContain('sk-saved');
    expect(updateItemMap.get('LLM_MY_PROXY_API_KEY')).toBe('');
    expect(updateItemMap.get('LLM_MY_PROXY2_BASE_URL')).toBe('https://proxy.example.com/v1');
    expect(updateItemMap.get('LLM_MY_PROXY2_MODELS')).toBe('gpt-4o-mini');
  });

  it('does not migrate runtime-only API keys when renaming a startup-env channel', async () => {
    update.mockResolvedValue({
      success: true,
      configVersion: 'v2',
      appliedCount: 1,
      skippedMaskedCount: 0,
      reloadTriggered: true,
      updatedKeys: ['LLM_CHANNELS', 'LLM_MY_PROXY2_BASE_URL', 'LLM_MY_PROXY2_MODELS'],
      warnings: [],
    });

    render(
      <LLMChannelEditor
        items={[
          { key: 'LLM_CHANNELS', value: 'my_proxy', rawValueExists: false },
          { key: 'LLM_MY_PROXY_PROTOCOL', value: 'openai', rawValueExists: false },
          { key: 'LLM_MY_PROXY_BASE_URL', value: 'https://proxy.example.com/v1', rawValueExists: false },
          { key: 'LLM_MY_PROXY_ENABLED', value: 'true', rawValueExists: false },
          { key: 'LLM_MY_PROXY_API_KEYS', value: 'sk-runtime-only', rawValueExists: false },
          { key: 'LLM_MY_PROXY_MODELS', value: 'gpt-4o-mini', rawValueExists: false },
        ]}
        configVersion="v1"
        maskToken="******"
        onSaved={() => {}}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: /my_proxy/i }));
    fireEvent.change(screen.getByLabelText('\u6e20\u9053\u540d\u79f0'), { target: { value: 'my_proxy2' } });
    fireEvent.click(screen.getByRole('button', { name: '\u4fdd\u5b58 AI \u914d\u7f6e' }));

    await waitFor(() => {
      expect(update).toHaveBeenCalled();
    });

    const updatePayload = update.mock.calls[0][0];
    const updateItemMap = new Map(updatePayload.items.map((item: { key: string; value: string }) => [item.key, item.value]));

    expect(updateItemMap.get('LLM_CHANNELS')).toBe('my_proxy2');
    expect(updateItemMap.has('LLM_MY_PROXY_API_KEY')).toBe(false);
    expect(updateItemMap.has('LLM_MY_PROXY_API_KEYS')).toBe(false);
    expect(updateItemMap.has('LLM_MY_PROXY2_API_KEY')).toBe(false);
    expect(updateItemMap.has('LLM_MY_PROXY2_API_KEYS')).toBe(false);
    expect([...updateItemMap.values()]).not.toContain('sk-runtime-only');
  });

  it('sanitizes stale runtime models before saving DeepSeek V4 channel changes', async () => {
    update.mockResolvedValue({
      success: true,
      configVersion: 'v2',
      appliedCount: 1,
      skippedMaskedCount: 0,
      reloadTriggered: true,
      updatedKeys: ['LLM_DEEPSEEK_MODELS', 'LITELLM_MODEL'],
      warnings: [],
    });

    render(
      <LLMChannelEditor
        items={[
          { key: 'LLM_CHANNELS', value: 'deepseek' },
          { key: 'LLM_DEEPSEEK_PROTOCOL', value: 'deepseek' },
          { key: 'LLM_DEEPSEEK_BASE_URL', value: 'https://api.deepseek.com' },
          { key: 'LLM_DEEPSEEK_ENABLED', value: 'true' },
          { key: 'LLM_DEEPSEEK_API_KEY', value: 'sk-test' },
          { key: 'LLM_DEEPSEEK_MODELS', value: 'deepseek-chat,deepseek-reasoner' },
          { key: 'LITELLM_MODEL', value: 'deepseek/deepseek-chat' },
          { key: 'AGENT_LITELLM_MODEL', value: 'deepseek/deepseek-reasoner' },
          { key: 'LITELLM_FALLBACK_MODELS', value: 'deepseek/deepseek-v4-pro,deepseek/deepseek-chat,cohere/command-r-plus' },
          { key: 'VISION_MODEL', value: 'deepseek/deepseek-reasoner' },
        ]}
        configVersion="v1"
        maskToken="******"
        onSaved={() => {}}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: /DeepSeek \u5b98\u65b9/i }));
    fireEvent.change(screen.getByLabelText('\u6a21\u578b（\u9017\u53f7\u5206\u9694）'), {
      target: { value: 'deepseek-v4-flash,deepseek-v4-pro' },
    });
    fireEvent.click(screen.getByRole('button', { name: '\u4fdd\u5b58 AI \u914d\u7f6e' }));

    await waitFor(() => {
      expect(update).toHaveBeenCalled();
    });

    const updatePayload = update.mock.calls[0][0];
    expect(updatePayload.items).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ key: 'LITELLM_MODEL', value: '' }),
        expect.objectContaining({ key: 'AGENT_LITELLM_MODEL', value: '' }),
        expect.objectContaining({ key: 'LITELLM_FALLBACK_MODELS', value: 'deepseek/deepseek-v4-pro,cohere/command-r-plus' }),
        expect.objectContaining({ key: 'VISION_MODEL', value: '' }),
        expect.objectContaining({ key: 'LLM_DEEPSEEK_MODELS', value: 'deepseek-v4-flash,deepseek-v4-pro' }),
      ]),
    );
  });

  it('prompts when bare runtime models loosely match canonical OpenAI route aliases', async () => {
    update.mockResolvedValue({
      success: true,
      configVersion: 'v2',
      appliedCount: 1,
      skippedMaskedCount: 0,
      reloadTriggered: true,
      updatedKeys: ['LLM_PRIMARY_BASE_URL', 'LITELLM_MODEL', 'LITELLM_FALLBACK_MODELS'],
      warnings: [],
    });

    render(
      <LLMChannelEditor
        items={[
          { key: 'LLM_CHANNELS', value: 'primary' },
          { key: 'LLM_PRIMARY_PROTOCOL', value: 'openai' },
          { key: 'LLM_PRIMARY_BASE_URL', value: 'https://api.example.com/v1' },
          { key: 'LLM_PRIMARY_ENABLED', value: 'true' },
          { key: 'LLM_PRIMARY_API_KEY', value: 'sk-test' },
          { key: 'LLM_PRIMARY_MODELS', value: 'gpt-4o-mini' },
          { key: 'LITELLM_MODEL', value: 'gpt-4o-mini' },
          { key: 'LITELLM_FALLBACK_MODELS', value: 'gpt-4o-mini' },
          { key: 'AGENT_LITELLM_MODEL', value: '' },
          { key: 'VISION_MODEL', value: '' },
        ]}
        configVersion="v1"
        maskToken="******"
        onSaved={() => {}}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: /primary/i }));
    fireEvent.change(screen.getByLabelText('Base URL'), {
      target: { value: 'https://api.example.com/compatible/v1' },
    });
    fireEvent.click(screen.getByRole('button', { name: '\u4fdd\u5b58 AI \u914d\u7f6e' }));

    await waitFor(() => {
      expect(screen.getByText('\u5f53\u524d\u8fd0\u884c\u65f6\u6a21\u578b\u4f7f\u7528\u975e\u89c4\u8303 route alias，\u8bf7\u4ece\u4e0b\u62c9\u6846\u91cd\u65b0\u9009\u62e9\u89c4\u8303\u6a21\u578b。')).toBeInTheDocument();
    });

    expect(update).not.toHaveBeenCalled();
  });

  it('does not treat direct-env provider models as non-canonical route aliases', async () => {
    update.mockResolvedValue({
      success: true,
      configVersion: 'v2',
      appliedCount: 1,
      skippedMaskedCount: 0,
      reloadTriggered: true,
      updatedKeys: ['LLM_PRIMARY_BASE_URL', 'LITELLM_MODEL'],
      warnings: [],
    });

    render(
      <LLMChannelEditor
        items={[
          { key: 'LLM_CHANNELS', value: 'primary' },
          { key: 'LLM_PRIMARY_PROTOCOL', value: 'openai' },
          { key: 'LLM_PRIMARY_BASE_URL', value: 'https://api.example.com/v1' },
          { key: 'LLM_PRIMARY_ENABLED', value: 'true' },
          { key: 'LLM_PRIMARY_API_KEY', value: 'sk-test' },
          { key: 'LLM_PRIMARY_MODELS', value: 'cohere/command-r-plus' },
          { key: 'LITELLM_MODEL', value: 'cohere/command-r-plus' },
          { key: 'AGENT_LITELLM_MODEL', value: '' },
          { key: 'LITELLM_FALLBACK_MODELS', value: '' },
          { key: 'VISION_MODEL', value: '' },
        ]}
        configVersion="v1"
        maskToken="******"
        onSaved={() => {}}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: /primary/i }));
    fireEvent.change(screen.getByLabelText('Base URL'), {
      target: { value: 'https://api.example.com/compatible/v1' },
    });
    fireEvent.click(screen.getByRole('button', { name: '\u4fdd\u5b58 AI \u914d\u7f6e' }));

    await waitFor(() => {
      expect(update).toHaveBeenCalled();
    });

    const updatePayload = update.mock.calls[0][0];
    expect(updatePayload.items).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ key: 'LITELLM_MODEL', value: 'cohere/command-r-plus' }),
      ]),
    );
  });

  it('sanitizes stale runtime models when enabled channels have no available models', async () => {
    update.mockResolvedValue({
      success: true,
      configVersion: 'v2',
      appliedCount: 1,
      skippedMaskedCount: 0,
      reloadTriggered: true,
      updatedKeys: ['LLM_DEEPSEEK_BASE_URL', 'LITELLM_MODEL', 'AGENT_LITELLM_MODEL', 'LITELLM_FALLBACK_MODELS', 'VISION_MODEL'],
      warnings: [],
    });

    render(
      <LLMChannelEditor
        items={[
          { key: 'LLM_CHANNELS', value: 'deepseek' },
          { key: 'LLM_DEEPSEEK_PROTOCOL', value: 'deepseek' },
          { key: 'LLM_DEEPSEEK_BASE_URL', value: 'https://api.deepseek.com' },
          { key: 'LLM_DEEPSEEK_ENABLED', value: 'false' },
          { key: 'LLM_DEEPSEEK_API_KEY', value: 'sk-test' },
          { key: 'LLM_DEEPSEEK_MODELS', value: 'deepseek-chat,deepseek-v4-pro' },
          { key: 'LITELLM_MODEL', value: 'deepseek/deepseek-chat' },
          { key: 'AGENT_LITELLM_MODEL', value: 'deepseek/deepseek-chat' },
          { key: 'LITELLM_FALLBACK_MODELS', value: 'deepseek/deepseek-v4-pro' },
          { key: 'VISION_MODEL', value: 'deepseek/deepseek-chat' },
        ]}
        configVersion="v1"
        maskToken="******"
        onSaved={() => {}}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: /DeepSeek \u5b98\u65b9/i }));
    fireEvent.change(screen.getByLabelText('Base URL'), {
      target: { value: 'https://api.deepseek.com/v1' },
    });
    fireEvent.click(screen.getByRole('button', { name: '\u4fdd\u5b58 AI \u914d\u7f6e' }));

    await waitFor(() => {
      expect(update).toHaveBeenCalled();
    });

    const updatePayload = update.mock.calls[0][0];
    expect(updatePayload.items).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ key: 'LITELLM_MODEL', value: '' }),
        expect.objectContaining({ key: 'AGENT_LITELLM_MODEL', value: '' }),
        expect.objectContaining({ key: 'LITELLM_FALLBACK_MODELS', value: '' }),
        expect.objectContaining({ key: 'VISION_MODEL', value: '' }),
      ]),
    );
  });

  it('keeps legacy-key-backed runtime models when enabled channels have no available models', async () => {
    update.mockResolvedValue({
      success: true,
      configVersion: 'v2',
      appliedCount: 1,
      skippedMaskedCount: 0,
      reloadTriggered: true,
      updatedKeys: ['LLM_PRIMARY_BASE_URL', 'LITELLM_MODEL', 'LITELLM_FALLBACK_MODELS'],
      warnings: [],
    });

    render(
      <LLMChannelEditor
        items={[
          { key: 'LLM_CHANNELS', value: 'primary' },
          { key: 'LLM_PRIMARY_PROTOCOL', value: 'openai' },
          { key: 'LLM_PRIMARY_BASE_URL', value: 'https://api.example.com/v1' },
          { key: 'LLM_PRIMARY_ENABLED', value: 'false' },
          { key: 'LLM_PRIMARY_API_KEY', value: 'sk-test' },
          { key: 'LLM_PRIMARY_MODELS', value: 'gpt-4o-mini' },
          { key: 'OPENAI_API_KEY', value: 'sk-legacy-value' },
          { key: 'LITELLM_MODEL', value: 'openai/gpt-4o-mini' },
          { key: 'LITELLM_FALLBACK_MODELS', value: 'openai/gpt-4o' },
          { key: 'AGENT_LITELLM_MODEL', value: '' },
          { key: 'VISION_MODEL', value: '' },
        ]}
        configVersion="v1"
        maskToken="******"
        onSaved={() => {}}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: /primary/i }));
    fireEvent.change(screen.getByLabelText('Base URL'), {
      target: { value: 'https://api.example.com/compatible/v1' },
    });
    fireEvent.click(screen.getByRole('button', { name: '\u4fdd\u5b58 AI \u914d\u7f6e' }));

    await waitFor(() => {
      expect(update).toHaveBeenCalled();
    });

    const updatePayload = update.mock.calls[0][0];
    expect(updatePayload.items).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ key: 'LITELLM_MODEL', value: 'openai/gpt-4o-mini' }),
        expect.objectContaining({ key: 'LITELLM_FALLBACK_MODELS', value: 'openai/gpt-4o' }),
      ]),
    );
  });

  it('shows cleanup warning and restore path after stale runtime models are removed on save', async () => {
    update.mockResolvedValue({
      success: true,
      configVersion: 'v2',
      appliedCount: 1,
      skippedMaskedCount: 0,
      reloadTriggered: true,
      updatedKeys: ['LLM_DEEPSEEK_MODELS', 'LITELLM_MODEL'],
      warnings: [
        '\u68c0\u6d4b\u5230\u5df2\u540c\u6b65\u6e05\u7406\u5931\u6548\u7684\u8fd0\u884c\u65f6\u6a21\u578b\u5f15\u7528：\u4e3b\u6a21\u578b / Agent \u4e3b\u6a21\u578b / Vision \u6a21\u578b / \u5907\u9009\u6a21\u578b\u4e2d\u7684\u5931\u6548\u9879。\u5982\u9700\u6062\u590d，\u8bf7\u5148\u8865\u56de\u5bf9\u5e94\u6e20\u9053\u6a21\u578b\u5217\u8868\u540e\u91cd\u65b0\u9009\u62e9；\u4e5f\u53ef\u7528\u684c\u9762\u7aef\u5bfc\u51fa\u5907\u4efd\u6216\u624b\u52a8 .env \u8fd8\u539f\u4e4b\u524d\u7684 LLM_* / LITELLM_MODEL / AGENT_LITELLM_MODEL / VISION_MODEL / LLM_TEMPERATURE。',
      ],
    });

    render(
      <LLMChannelEditor
        items={[
          { key: 'LLM_CHANNELS', value: 'deepseek' },
          { key: 'LLM_DEEPSEEK_PROTOCOL', value: 'deepseek' },
          { key: 'LLM_DEEPSEEK_BASE_URL', value: 'https://api.deepseek.com' },
          { key: 'LLM_DEEPSEEK_ENABLED', value: 'true' },
          { key: 'LLM_DEEPSEEK_API_KEY', value: 'sk-test' },
          { key: 'LLM_DEEPSEEK_MODELS', value: 'deepseek-chat,deepseek-reasoner' },
          { key: 'LITELLM_MODEL', value: 'deepseek/deepseek-chat' },
          { key: 'AGENT_LITELLM_MODEL', value: 'deepseek/deepseek-reasoner' },
          { key: 'LITELLM_FALLBACK_MODELS', value: 'deepseek/deepseek-v4-pro,deepseek/deepseek-chat' },
          { key: 'VISION_MODEL', value: 'deepseek/deepseek-reasoner' },
        ]}
        configVersion="v1"
        maskToken="******"
        onSaved={() => {}}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: /DeepSeek \u5b98\u65b9/i }));
    fireEvent.change(screen.getByLabelText('\u6a21\u578b（\u9017\u53f7\u5206\u9694）'), {
      target: { value: 'deepseek-v4-flash,deepseek-v4-pro' },
    });
    fireEvent.click(screen.getByRole('button', { name: '\u4fdd\u5b58 AI \u914d\u7f6e' }));

    expect(await screen.findByText('\u4fdd\u5b58\u540e\u63d0\u793a')).toBeInTheDocument();
    expect(screen.getByText(/\u5df2\u540c\u6b65\u6e05\u7406\u5931\u6548\u7684\u8fd0\u884c\u65f6\u6a21\u578b\u5f15\u7528/i)).toBeInTheDocument();
    expect(screen.getByText(/\u684c\u9762\u7aef\u5bfc\u51fa\u5907\u4efd\u6216\u624b\u52a8 \.env \u8fd8\u539f/i)).toBeInTheDocument();
  });

  it('keeps save warnings visible after onSaved-driven refresh', async () => {
    const warningMessage = '\u68c0\u6d4b\u5230\u5df2\u540c\u6b65\u6e05\u7406\u5931\u6548\u7684\u8fd0\u884c\u65f6\u6a21\u578b\u5f15\u7528：\u4e3b\u6a21\u578b / Agent \u4e3b\u6a21\u578b / Vision \u6a21\u578b / \u5907\u9009\u6a21\u578b\u4e2d\u7684\u5931\u6548\u9879。';
    const initialItems = [
      { key: 'LLM_CHANNELS', value: 'deepseek' },
      { key: 'LLM_DEEPSEEK_PROTOCOL', value: 'deepseek' },
      { key: 'LLM_DEEPSEEK_BASE_URL', value: 'https://api.deepseek.com' },
      { key: 'LLM_DEEPSEEK_ENABLED', value: 'true' },
      { key: 'LLM_DEEPSEEK_API_KEY', value: 'sk-test' },
      { key: 'LLM_DEEPSEEK_MODELS', value: 'deepseek-chat,deepseek-reasoner' },
      { key: 'LITELLM_MODEL', value: 'deepseek/deepseek-chat' },
      { key: 'AGENT_LITELLM_MODEL', value: 'deepseek/deepseek-reasoner' },
      { key: 'LITELLM_FALLBACK_MODELS', value: 'deepseek/deepseek-v4-pro,cohere/command-r-plus' },
      { key: 'VISION_MODEL', value: 'deepseek/deepseek-reasoner' },
    ];
    const Component = () => {
      const [items, setItems] = useState(initialItems);

      return (
        <LLMChannelEditor
          items={items}
          configVersion="v1"
          maskToken="******"
          onSaved={async (updatedItems) => {
            setItems(updatedItems);
          }}
        />
      );
    };

    update.mockResolvedValue({
      success: true,
      configVersion: 'v2',
      appliedCount: 1,
      skippedMaskedCount: 0,
      reloadTriggered: true,
      updatedKeys: ['LLM_DEEPSEEK_MODELS', 'LITELLM_MODEL'],
      warnings: [warningMessage],
    });

    render(<Component />);

    fireEvent.click(screen.getByRole('button', { name: /DeepSeek \u5b98\u65b9/i }));
    fireEvent.change(screen.getByLabelText('\u6a21\u578b（\u9017\u53f7\u5206\u9694）'), {
      target: { value: 'deepseek-v4-flash,deepseek-v4-pro' },
    });
    fireEvent.click(screen.getByRole('button', { name: '\u4fdd\u5b58 AI \u914d\u7f6e' }));

    expect(await screen.findByText('\u4fdd\u5b58\u540e\u63d0\u793a')).toBeInTheDocument();
    expect(screen.getByText(warningMessage)).toBeInTheDocument();
  });

  it('clears failed-save feedback after saved props refresh', async () => {
    const initialItems = [
      { key: 'LLM_CHANNELS', value: 'openai' },
      { key: 'LLM_OPENAI_PROTOCOL', value: 'openai' },
      { key: 'LLM_OPENAI_BASE_URL', value: 'https://api.openai.com/v1' },
      { key: 'LLM_OPENAI_ENABLED', value: 'true' },
      { key: 'LLM_OPENAI_API_KEY', value: 'secret-key' },
      { key: 'LLM_OPENAI_MODELS', value: 'gpt-4o-mini' },
    ];
    const onSaved = vi.fn(async () => {
      throw new Error('refresh failed');
    });

    update.mockResolvedValue({
      success: true,
      configVersion: 'v2',
      appliedCount: 1,
      skippedMaskedCount: 0,
      reloadTriggered: true,
      updatedKeys: ['LLM_OPENAI_BASE_URL'],
      warnings: [],
    });

    const renderResult = render(
      <LLMChannelEditor
        items={initialItems}
        configVersion="v1"
        maskToken="******"
        onSaved={onSaved}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: /OpenAI \u5b98\u65b9/i }));
    fireEvent.change(screen.getByLabelText('Base URL'), {
      target: { value: 'https://api.openai.com/v1/test' },
    });
    fireEvent.click(screen.getByRole('button', { name: '\u4fdd\u5b58 AI \u914d\u7f6e' }));

    expect(await screen.findByText('refresh failed')).toBeInTheDocument();

    const savedItems = update.mock.calls[0][0].items;
    renderResult.rerender(
      <LLMChannelEditor
        items={savedItems}
        configVersion="v2"
        maskToken="******"
        onSaved={onSaved}
      />,
    );

    await waitFor(() => {
      expect(screen.queryByText('refresh failed')).not.toBeInTheDocument();
    });
  });

  it('keeps stale runtime fallback model available when user restores it in channel models', async () => {
    update.mockResolvedValue({
      success: true,
      configVersion: 'v2',
      appliedCount: 1,
      skippedMaskedCount: 0,
      reloadTriggered: true,
      updatedKeys: ['LLM_DEEPSEEK_MODELS', 'LITELLM_MODEL', 'LITELLM_FALLBACK_MODELS'],
      warnings: [],
    });

    render(
      <LLMChannelEditor
        items={[
          { key: 'LLM_CHANNELS', value: 'deepseek' },
          { key: 'LLM_DEEPSEEK_PROTOCOL', value: 'deepseek' },
          { key: 'LLM_DEEPSEEK_BASE_URL', value: 'https://api.deepseek.com' },
          { key: 'LLM_DEEPSEEK_ENABLED', value: 'true' },
          { key: 'LLM_DEEPSEEK_API_KEY', value: 'sk-test' },
          { key: 'LLM_DEEPSEEK_MODELS', value: 'deepseek-chat' },
          { key: 'LITELLM_MODEL', value: 'deepseek/deepseek-chat' },
          { key: 'AGENT_LITELLM_MODEL', value: '' },
          { key: 'LITELLM_FALLBACK_MODELS', value: 'deepseek/deepseek-old' },
          { key: 'VISION_MODEL', value: '' },
        ]}
        configVersion="v1"
        maskToken="******"
        onSaved={() => {}}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: /DeepSeek \u5b98\u65b9/i }));
    fireEvent.change(screen.getByLabelText('\u6a21\u578b（\u9017\u53f7\u5206\u9694）'), {
      target: { value: 'deepseek-chat,deepseek-old' },
    });

    expect(await screen.findByLabelText('deepseek/deepseek-old')).toBeChecked();

    fireEvent.click(screen.getByRole('button', { name: '\u4fdd\u5b58 AI \u914d\u7f6e' }));
    await waitFor(() => {
      expect(update).toHaveBeenCalled();
    });

    const updatePayload = update.mock.calls[0][0];
    expect(updatePayload.items).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ key: 'LITELLM_FALLBACK_MODELS', value: 'deepseek/deepseek-old' }),
      ]),
    );
  });

  it('keeps runtime selections while channel models are edited temporarily', async () => {
    render(
      <LLMChannelEditor
        items={[
          { key: 'LLM_CHANNELS', value: 'deepseek' },
          { key: 'LLM_DEEPSEEK_PROTOCOL', value: 'deepseek' },
          { key: 'LLM_DEEPSEEK_BASE_URL', value: 'https://api.deepseek.com' },
          { key: 'LLM_DEEPSEEK_ENABLED', value: 'true' },
          { key: 'LLM_DEEPSEEK_API_KEY', value: 'sk-test' },
          { key: 'LLM_DEEPSEEK_MODELS', value: 'deepseek-chat,deepseek-reasoner,deepseek-v4-pro' },
          { key: 'LITELLM_MODEL', value: 'deepseek/deepseek-chat' },
          { key: 'AGENT_LITELLM_MODEL', value: 'deepseek/deepseek-reasoner' },
          { key: 'LITELLM_FALLBACK_MODELS', value: 'deepseek/deepseek-v4-pro' },
          { key: 'VISION_MODEL', value: 'deepseek/deepseek-reasoner' },
        ]}
        configVersion="v1"
        maskToken="******"
        onSaved={() => {}}
      />
    );

    const primaryModelSelect = screen.getByRole('combobox', { name: '\u4e3b\u6a21\u578b' });
    const agentModelSelect = screen.getByRole('combobox', { name: 'Agent \u4e3b\u6a21\u578b' });
    const visionModelSelect = screen.getByRole('combobox', { name: 'Vision \u6a21\u578b' });

    fireEvent.click(screen.getByRole('button', { name: /DeepSeek \u5b98\u65b9/i }));
    const modelInput = screen.getByLabelText('\u6a21\u578b（\u9017\u53f7\u5206\u9694）');
    fireEvent.change(modelInput, {
      target: { value: 'deepseek-v4-flash' },
    });

    await waitFor(() => {
      expect(primaryModelSelect).toHaveValue('deepseek/deepseek-chat');
      expect(agentModelSelect).toHaveValue('deepseek/deepseek-reasoner');
      expect(visionModelSelect).toHaveValue('deepseek/deepseek-reasoner');
    });

    fireEvent.change(modelInput, {
      target: { value: 'deepseek-chat,deepseek-reasoner,deepseek-v4-pro' },
    });

    await waitFor(() => {
      expect(primaryModelSelect).toHaveValue('deepseek/deepseek-chat');
      expect(agentModelSelect).toHaveValue('deepseek/deepseek-reasoner');
      expect(visionModelSelect).toHaveValue('deepseek/deepseek-reasoner');
      expect(screen.getByLabelText('deepseek/deepseek-v4-pro')).toBeChecked();
    });
  });

  it('keeps direct-env provider runtime models (cohere / google / xai) while saving channel changes', async () => {
    update.mockResolvedValue({
      success: true,
      configVersion: 'v2',
      appliedCount: 1,
      skippedMaskedCount: 0,
      reloadTriggered: true,
      updatedKeys: ['LLM_DEEPSEEK_BASE_URL', 'LITELLM_MODEL', 'AGENT_LITELLM_MODEL', 'LITELLM_FALLBACK_MODELS', 'VISION_MODEL'],
      warnings: [],
    });

    render(
      <LLMChannelEditor
        items={[
          { key: 'LLM_CHANNELS', value: 'deepseek' },
          { key: 'LLM_DEEPSEEK_PROTOCOL', value: 'deepseek' },
          { key: 'LLM_DEEPSEEK_BASE_URL', value: 'https://api.deepseek.com/v1' },
          { key: 'LLM_DEEPSEEK_ENABLED', value: 'true' },
          { key: 'LLM_DEEPSEEK_API_KEY', value: 'sk-test' },
          { key: 'LLM_DEEPSEEK_MODELS', value: 'deepseek-v4-flash' },
          { key: 'LITELLM_MODEL', value: 'cohere/command-r-plus' },
          { key: 'AGENT_LITELLM_MODEL', value: 'google/gemini-2.5-flash' },
          { key: 'LITELLM_FALLBACK_MODELS', value: 'cohere/command-r-plus,google/gemini-2.5-flash,xai/grok-beta' },
          { key: 'VISION_MODEL', value: 'xai/grok-vision-beta' },
        ]}
        configVersion="v1"
        maskToken="******"
        onSaved={() => {}}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: /DeepSeek \u5b98\u65b9/i }));
    fireEvent.change(screen.getByLabelText('Base URL'), {
      target: { value: 'https://api.deepseek.com' },
    });
    fireEvent.click(screen.getByRole('button', { name: '\u4fdd\u5b58 AI \u914d\u7f6e' }));

    await waitFor(() => {
      expect(update).toHaveBeenCalled();
    });

    const updatePayload = update.mock.calls[0][0];
    expect(updatePayload.items).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ key: 'LITELLM_MODEL', value: 'cohere/command-r-plus' }),
        expect.objectContaining({ key: 'AGENT_LITELLM_MODEL', value: 'google/gemini-2.5-flash' }),
        expect.objectContaining({ key: 'LITELLM_FALLBACK_MODELS', value: 'cohere/command-r-plus,google/gemini-2.5-flash,xai/grok-beta' }),
        expect.objectContaining({ key: 'VISION_MODEL', value: 'xai/grok-vision-beta' }),
      ]),
    );
  });

  it('checks protocol-prefixed selected model when discovery returns bare id', async () => {
    discoverLLMChannelModels.mockResolvedValue({
      success: true,
      message: 'LLM channel model discovery succeeded',
      error: null,
      resolvedProtocol: 'openai',
      models: ['MiniMax-M1'],
      latencyMs: 80,
    });

    render(
      <LLMChannelEditor
        items={[
          { key: 'LLM_CHANNELS', value: 'dashscope' },
          { key: 'LLM_DASHSCOPE_PROTOCOL', value: 'openai' },
          { key: 'LLM_DASHSCOPE_BASE_URL', value: 'https://dashscope.aliyuncs.com/compatible-mode/v1' },
          { key: 'LLM_DASHSCOPE_ENABLED', value: 'true' },
          { key: 'LLM_DASHSCOPE_API_KEY', value: 'sk-test' },
          { key: 'LLM_DASHSCOPE_MODELS', value: 'openai/MiniMax-M1' },
        ]}
        configVersion="v1"
        maskToken="******"
        onSaved={() => {}}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: /\u901a\u4e49\u5343\u95ee/i }));
    fireEvent.click(screen.getByRole('button', { name: '\u83b7\u53d6\u6a21\u578b' }));

    const checkbox = await screen.findByLabelText('MiniMax-M1');
    expect(checkbox).toBeChecked();

    fireEvent.click(checkbox);
    await waitFor(() => {
      expect(screen.getByLabelText('\u624b\u52a8\u6a21\u578b（\u9017\u53f7\u5206\u9694）')).toHaveValue('');
    });
  });

  it('does not treat unknown-prefixed selected model as equivalent to bare discovered id', async () => {
    discoverLLMChannelModels.mockResolvedValue({
      success: true,
      message: 'LLM channel model discovery succeeded',
      error: null,
      resolvedProtocol: 'openai',
      models: ['MiniMax-M1'],
      latencyMs: 80,
    });

    render(
      <LLMChannelEditor
        items={[
          { key: 'LLM_CHANNELS', value: 'dashscope' },
          { key: 'LLM_DASHSCOPE_PROTOCOL', value: 'openai' },
          { key: 'LLM_DASHSCOPE_BASE_URL', value: 'https://dashscope.aliyuncs.com/compatible-mode/v1' },
          { key: 'LLM_DASHSCOPE_ENABLED', value: 'true' },
          { key: 'LLM_DASHSCOPE_API_KEY', value: 'sk-test' },
          { key: 'LLM_DASHSCOPE_MODELS', value: 'minimax/MiniMax-M1' },
        ]}
        configVersion="v1"
        maskToken="******"
        onSaved={() => {}}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: /\u901a\u4e49\u5343\u95ee/i }));
    fireEvent.click(screen.getByRole('button', { name: '\u83b7\u53d6\u6a21\u578b' }));

    const checkbox = await screen.findByLabelText('MiniMax-M1');
    expect(checkbox).not.toBeChecked();
    expect(screen.getByLabelText('\u624b\u52a8\u6a21\u578b（\u9017\u53f7\u5206\u9694）')).toHaveValue('minimax/MiniMax-M1');
  });

  it('discovers models and writes selected values back to channel config', async () => {
    discoverLLMChannelModels.mockResolvedValue({
      success: true,
      message: 'LLM channel model discovery succeeded',
      error: null,
      resolvedProtocol: 'openai',
      models: ['qwen-plus', 'qwen-turbo'],
      latencyMs: 88,
    });
    update.mockResolvedValue({
      success: true,
      configVersion: 'v2',
      appliedCount: 1,
      skippedMaskedCount: 0,
      reloadTriggered: true,
      updatedKeys: ['LLM_DASHSCOPE_MODELS'],
      warnings: [],
    });

    render(
      <LLMChannelEditor
        items={[
          { key: 'LLM_CHANNELS', value: 'dashscope' },
          { key: 'LLM_DASHSCOPE_PROTOCOL', value: 'openai' },
          { key: 'LLM_DASHSCOPE_BASE_URL', value: 'https://dashscope.aliyuncs.com/compatible-mode/v1' },
          { key: 'LLM_DASHSCOPE_ENABLED', value: 'true' },
          { key: 'LLM_DASHSCOPE_API_KEY', value: 'sk-test' },
          { key: 'LLM_DASHSCOPE_MODELS', value: 'qwen-old' },
        ]}
        configVersion="v1"
        maskToken="******"
        onSaved={() => {}}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: /Dashscope/i }));
    fireEvent.click(screen.getByRole('button', { name: '\u83b7\u53d6\u6a21\u578b' }));

    const qwenPlusCheckbox = await screen.findByLabelText('qwen-plus');
    fireEvent.click(qwenPlusCheckbox);

    await waitFor(() => {
      expect(screen.getByLabelText('\u624b\u52a8\u6a21\u578b（\u9017\u53f7\u5206\u9694）')).toHaveValue('qwen-old,qwen-plus');
    });

    expect(discoverLLMChannelModels).toHaveBeenCalledWith(
      expect.objectContaining({
        name: 'dashscope',
        protocol: 'openai',
        baseUrl: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
        apiKey: 'sk-test',
        models: ['qwen-old'],
      }),
    );

    fireEvent.click(screen.getByRole('button', { name: '\u4fdd\u5b58 AI \u914d\u7f6e' }));

    await waitFor(() => {
      expect(update).toHaveBeenCalled();
    });

    const updatePayload = update.mock.calls[0][0];
    expect(updatePayload.items).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ key: 'LLM_DASHSCOPE_MODELS', value: 'qwen-old,qwen-plus' }),
      ]),
    );
  });

  it('shows structured troubleshooting hint when channel auth fails', async () => {
    testLLMChannel.mockResolvedValue({ success: false, message: 'LLM authentication failed', error: '401 Unauthorized · Bearer [REDACTED]', errorCode: 'auth', stage: 'chat_completion', retryable: false, details: {}, resolvedProtocol: 'openai', resolvedModel: 'openai/gpt-4o-mini', latencyMs: null });

    render(
      <LLMChannelEditor
        items={[{ key: 'LLM_CHANNELS', value: 'openai' }, { key: 'LLM_OPENAI_PROTOCOL', value: 'openai' }, { key: 'LLM_OPENAI_BASE_URL', value: 'https://api.openai.com/v1' }, { key: 'LLM_OPENAI_ENABLED', value: 'true' }, { key: 'LLM_OPENAI_API_KEY', value: 'secret-key' }, { key: 'LLM_OPENAI_MODELS', value: 'gpt-4o-mini' }]}
        configVersion="v1"
        maskToken="******"
        onSaved={() => {}}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: /OpenAI \u5b98\u65b9/i }));
    fireEvent.click(screen.getByRole('button', { name: '\u6d4b\u8bd5\u8fde\u63a5' }));

    expect(await screen.findByText(/\u804a\u5929\u8c03\u7528 · \u9274\u6743\u5931\u8d25：LLM authentication failed/i)).toBeInTheDocument();
    expect(screen.getByText(/\u8bf7\u68c0\u67e5 API Key \u662f\u5426\u6b63\u786e/i)).toBeInTheDocument();
    expect(screen.queryByText(/\u8c03\u6574\u6a21\u578b\u987a\u5e8f\u6216\u79fb\u9664\u4e0d\u53ef\u7528\u6a21\u578b/i)).not.toBeInTheDocument();
  });

  it('shows tested model and model-availability hints when a model is disabled', async () => {
    testLLMChannel.mockResolvedValue({
      success: false,
      message: 'LLM channel test failed',
      error: 'litellm.APIError: APIError: OpenAIException - Model disabled.',
      errorCode: 'model_not_found',
      stage: 'chat_completion',
      retryable: false,
      details: { reason: 'model_access_denied', model: 'openai/deepseek-ai/DeepSeek-V3' },
      resolvedProtocol: 'openai',
      resolvedModel: 'openai/deepseek-ai/DeepSeek-V3',
      latencyMs: null,
    });

    render(
      <LLMChannelEditor
        items={[
          { key: 'LLM_CHANNELS', value: 'siliconflow' },
          { key: 'LLM_SILICONFLOW_PROTOCOL', value: 'openai' },
          { key: 'LLM_SILICONFLOW_BASE_URL', value: 'https://api.siliconflow.cn/v1' },
          { key: 'LLM_SILICONFLOW_ENABLED', value: 'true' },
          { key: 'LLM_SILICONFLOW_API_KEY', value: 'secret-key' },
          { key: 'LLM_SILICONFLOW_MODELS', value: 'deepseek-ai/DeepSeek-V3,Qwen/Qwen3-Coder' },
        ]}
        configVersion="v1"
        maskToken="******"
        onSaved={() => {}}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: /SiliconFlow/i }));
    fireEvent.click(screen.getByRole('button', { name: '\u6d4b\u8bd5\u8fde\u63a5' }));

    expect(await screen.findByText(/\u804a\u5929\u8c03\u7528 · \u6a21\u578b\u4e0d\u53ef\u7528：LLM channel test failed/i)).toBeInTheDocument();
    expect(screen.getByText(/\u672c\u6b21\u6d4b\u8bd5\u6a21\u578b：openai\/deepseek-ai\/DeepSeek-V3/i)).toBeInTheDocument();
    expect(screen.getByText(/\u57fa\u7840\u8fde\u63a5\u6d4b\u8bd5\u9ed8\u8ba4\u4f7f\u7528\u6a21\u578b\u5217\u8868\u9996\u9879：deepseek-ai\/DeepSeek-V3/i)).toBeInTheDocument();
    expect(screen.getByText(/\u57fa\u7840\u8fde\u63a5\u6d4b\u8bd5\u9ed8\u8ba4\u53ea\u6d4b\u8bd5\u6a21\u578b\u5217\u8868\u4e2d\u7684\u7b2c\u4e00\u4e2a\u6a21\u578b/i)).toBeInTheDocument();
    expect(screen.getByText(/\u8c03\u6574\u6a21\u578b\u987a\u5e8f\u6216\u79fb\u9664\u4e0d\u53ef\u7528\u6a21\u578b/i)).toBeInTheDocument();
    expect(screen.getByText(/\u6a21\u578b\u662f\u5426\u5df2\u5f00\u901a、\u8d26\u53f7\u662f\u5426\u53ef\u89c1/i)).toBeInTheDocument();
    expect(screen.queryByText(/Base URL、\u4ee3\u7406、TLS/i)).not.toBeInTheDocument();
    expect(testLLMChannel).toHaveBeenCalledWith(expect.objectContaining({
      models: ['deepseek-ai/DeepSeek-V3', 'Qwen/Qwen3-Coder'],
    }));
  });

  it('shows provider blocked troubleshooting without network or model-list hints', async () => {
    testLLMChannel.mockResolvedValue({
      success: false,
      message: 'LLM request was blocked by provider or gateway policy',
      error: 'litellm.APIError: APIError: OpenAIException - Your request was blocked.',
      errorCode: 'request_blocked',
      stage: 'chat_completion',
      retryable: false,
      details: { reason: 'provider_blocked', model: 'openai/gpt-5.5' },
      resolvedProtocol: 'openai',
      resolvedModel: 'openai/gpt-5.5',
      latencyMs: null,
    });

    render(
      <LLMChannelEditor
        items={[
          { key: 'LLM_CHANNELS', value: 'proxy' },
          { key: 'LLM_PROXY_PROTOCOL', value: 'openai' },
          { key: 'LLM_PROXY_BASE_URL', value: 'https://gateway.example.com/v1' },
          { key: 'LLM_PROXY_ENABLED', value: 'true' },
          { key: 'LLM_PROXY_API_KEY', value: 'secret-key' },
          { key: 'LLM_PROXY_MODELS', value: 'gpt-5.5,gpt-4o-mini' },
        ]}
        configVersion="v1"
        maskToken="******"
        onSaved={() => {}}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: /proxy/i }));
    fireEvent.click(screen.getByRole('button', { name: '\u6d4b\u8bd5\u8fde\u63a5' }));

    expect(await screen.findByText(/\u804a\u5929\u8c03\u7528 · \u8bf7\u6c42\u88ab\u62e6\u622a/i)).toBeInTheDocument();
    expect(screen.getByText(/\u672c\u6b21\u6d4b\u8bd5\u6a21\u578b：openai\/gpt-5\.5/i)).toBeInTheDocument();
    expect(screen.getByText(/\u8d26\u53f7\u98ce\u63a7、\u5730\u57df\u9650\u5236、\u6a21\u578b\u6743\u9650/i)).toBeInTheDocument();
    expect(screen.queryByText(/Base URL、\u4ee3\u7406、TLS/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/\u8c03\u6574\u6a21\u578b\u987a\u5e8f\u6216\u79fb\u9664\u4e0d\u53ef\u7528\u6a21\u578b/i)).not.toBeInTheDocument();
  });

  it('shows focused quota exceeded troubleshooting hints', async () => {
    testLLMChannel.mockResolvedValue({
      success: false,
      message: 'LLM request was rejected by quota or rate limiting',
      error: 'quota exceeded',
      errorCode: 'quota',
      stage: 'chat_completion',
      retryable: true,
      details: { reason: 'quota_exceeded' },
      resolvedProtocol: 'openai',
      resolvedModel: 'openai/gpt-4o-mini',
      latencyMs: null,
    });

    render(
      <LLMChannelEditor
        items={[{ key: 'LLM_CHANNELS', value: 'openai' }, { key: 'LLM_OPENAI_PROTOCOL', value: 'openai' }, { key: 'LLM_OPENAI_BASE_URL', value: 'https://api.openai.com/v1' }, { key: 'LLM_OPENAI_ENABLED', value: 'true' }, { key: 'LLM_OPENAI_API_KEY', value: 'secret-key' }, { key: 'LLM_OPENAI_MODELS', value: 'gpt-4o-mini' }]}
        configVersion="v1"
        maskToken="******"
        onSaved={() => {}}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: /OpenAI \u5b98\u65b9/i }));
    fireEvent.click(screen.getByRole('button', { name: '\u6d4b\u8bd5\u8fde\u63a5' }));

    expect(await screen.findByText(/\u670d\u52a1\u5546\u8fd4\u56de\u914d\u989d\u5df2\u8017\u5c3d/i)).toBeInTheDocument();
    expect(screen.queryByText(/\u8c03\u6574\u6a21\u578b\u987a\u5e8f\u6216\u79fb\u9664\u4e0d\u53ef\u7528\u6a21\u578b/i)).not.toBeInTheDocument();
  });

  it('does not show model-list action hints for network failures', async () => {
    testLLMChannel.mockResolvedValue({
      success: false,
      message: 'LLM request failed before a valid response was returned',
      error: 'DNS lookup failed',
      errorCode: 'network_error',
      stage: 'chat_completion',
      retryable: true,
      details: { reason: 'dns_error' },
      resolvedProtocol: 'openai',
      resolvedModel: 'openai/gpt-4o-mini',
      latencyMs: null,
    });

    render(
      <LLMChannelEditor
        items={[{ key: 'LLM_CHANNELS', value: 'openai' }, { key: 'LLM_OPENAI_PROTOCOL', value: 'openai' }, { key: 'LLM_OPENAI_BASE_URL', value: 'https://api.openai.com/v1' }, { key: 'LLM_OPENAI_ENABLED', value: 'true' }, { key: 'LLM_OPENAI_API_KEY', value: 'secret-key' }, { key: 'LLM_OPENAI_MODELS', value: 'gpt-4o-mini' }]}
        configVersion="v1"
        maskToken="******"
        onSaved={() => {}}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: /OpenAI \u5b98\u65b9/i }));
    fireEvent.click(screen.getByRole('button', { name: '\u6d4b\u8bd5\u8fde\u63a5' }));

    expect(await screen.findByText(/\u57df\u540d\u89e3\u6790\u5931\u8d25/i)).toBeInTheDocument();
    expect(screen.queryByText(/\u8c03\u6574\u6a21\u578b\u987a\u5e8f\u6216\u79fb\u9664\u4e0d\u53ef\u7528\u6a21\u578b/i)).not.toBeInTheDocument();
  });

  it('does not request runtime capabilities during the basic connection test', async () => {
    testLLMChannel.mockResolvedValue({
      success: true,
      message: 'LLM channel test succeeded',
      error: null,
      errorCode: null,
      stage: 'chat_completion',
      retryable: false,
      details: {},
      resolvedProtocol: 'openai',
      resolvedModel: 'openai/gpt-4o-mini',
      latencyMs: 80,
      capabilityResults: {},
    });

    render(
      <LLMChannelEditor
        items={[{ key: 'LLM_CHANNELS', value: 'openai' }, { key: 'LLM_OPENAI_PROTOCOL', value: 'openai' }, { key: 'LLM_OPENAI_BASE_URL', value: 'https://api.openai.com/v1' }, { key: 'LLM_OPENAI_ENABLED', value: 'true' }, { key: 'LLM_OPENAI_API_KEY', value: 'secret-key' }, { key: 'LLM_OPENAI_MODELS', value: 'gpt-4o-mini' }]}
        configVersion="v1"
        maskToken="******"
        onSaved={() => {}}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: /OpenAI \u5b98\u65b9/i }));
    fireEvent.click(screen.getByRole('button', { name: '\u6d4b\u8bd5\u8fde\u63a5' }));

    await screen.findByText(/\u8fde\u63a5\u6210\u529f · openai\/gpt-4o-mini/i);
    expect(testLLMChannel).toHaveBeenCalledWith(expect.not.objectContaining({ capabilityChecks: expect.anything() }));
  });

  it('runs explicit runtime capability checks and shows detailed hints', async () => {
    testLLMChannel.mockResolvedValue({
      success: true,
      message: 'LLM channel test succeeded',
      error: null,
      errorCode: null,
      stage: 'chat_completion',
      retryable: false,
      details: {},
      resolvedProtocol: 'openai',
      resolvedModel: 'openai/gpt-4o-mini',
      latencyMs: 80,
      capabilityResults: {
        json: {
          status: 'passed',
          message: 'JSON output capability check passed',
          errorCode: null,
          stage: 'capability_json',
          retryable: false,
          details: { reason: 'json_valid' },
        },
        tools: {
          status: 'failed',
          message: 'LLM channel does not support tools capability',
          errorCode: 'capability_unsupported',
          stage: 'capability_tools',
          retryable: false,
          details: { reason: 'capability_unsupported' },
        },
      },
    });

    render(
      <LLMChannelEditor
        items={[{ key: 'LLM_CHANNELS', value: 'openai' }, { key: 'LLM_OPENAI_PROTOCOL', value: 'openai' }, { key: 'LLM_OPENAI_BASE_URL', value: 'https://api.openai.com/v1' }, { key: 'LLM_OPENAI_ENABLED', value: 'true' }, { key: 'LLM_OPENAI_API_KEY', value: 'secret-key' }, { key: 'LLM_OPENAI_MODELS', value: 'gpt-4o-mini' }]}
        configVersion="v1"
        maskToken="******"
        onSaved={() => {}}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: /OpenAI \u5b98\u65b9/i }));
    fireEvent.click(screen.getByLabelText('JSON'));
    fireEvent.click(screen.getByLabelText('Tools'));
    fireEvent.click(screen.getByRole('button', { name: '\u68c0\u6d4b\u80fd\u529b' }));

    expect(await screen.findByText(/\u80fd\u529b\u68c0\u6d4b\u5b8c\u6210：1 \u901a\u8fc7 \/ 1 \u5931\u8d25 \/ 0 \u8df3\u8fc7/i)).toBeInTheDocument();
    expect(screen.getByText('JSON \u901a\u8fc7')).toBeInTheDocument();
    expect(screen.getByText('Tools \u5931\u8d25')).toBeInTheDocument();
    expect(screen.getByText(/\u5f53\u524d\u6a21\u578b\u6216\u517c\u5bb9\u5c42\u4e0d\u652f\u6301\u8be5\u80fd\u529b/i)).toBeInTheDocument();
    expect(testLLMChannel).toHaveBeenCalledWith(expect.objectContaining({ capabilityChecks: ['json', 'tools'] }));
  });

  it('shows skipped runtime capabilities when the base test fails', async () => {
    testLLMChannel.mockResolvedValue({
      success: false,
      message: 'LLM authentication failed',
      error: '401 Unauthorized',
      errorCode: 'auth',
      stage: 'chat_completion',
      retryable: false,
      details: { reason: 'api_key_rejected' },
      resolvedProtocol: 'openai',
      resolvedModel: 'openai/gpt-4o-mini',
      latencyMs: null,
      capabilityResults: {
        json: {
          status: 'skipped',
          message: 'Skipped because the base channel test did not pass',
          errorCode: 'skipped',
          stage: 'capability_json',
          retryable: false,
          details: { reason: 'base_test_failed' },
        },
      },
    });

    render(
      <LLMChannelEditor
        items={[{ key: 'LLM_CHANNELS', value: 'openai' }, { key: 'LLM_OPENAI_PROTOCOL', value: 'openai' }, { key: 'LLM_OPENAI_BASE_URL', value: 'https://api.openai.com/v1' }, { key: 'LLM_OPENAI_ENABLED', value: 'true' }, { key: 'LLM_OPENAI_API_KEY', value: 'bad-key' }, { key: 'LLM_OPENAI_MODELS', value: 'gpt-4o-mini' }]}
        configVersion="v1"
        maskToken="******"
        onSaved={() => {}}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: /OpenAI \u5b98\u65b9/i }));
    fireEvent.click(screen.getByLabelText('JSON'));
    fireEvent.click(screen.getByRole('button', { name: '\u68c0\u6d4b\u80fd\u529b' }));

    expect(await screen.findByText(/\u80fd\u529b\u68c0\u6d4b\u5b8c\u6210：0 \u901a\u8fc7 \/ 0 \u5931\u8d25 \/ 1 \u8df3\u8fc7/i)).toBeInTheDocument();
    expect(screen.getByText('JSON \u8df3\u8fc7')).toBeInTheDocument();
    expect(screen.getByText(/\u670d\u52a1\u5546\u62d2\u7edd\u4e86\u5f53\u524d API Key/i)).toBeInTheDocument();
    expect(screen.getByLabelText('\u6a21\u578b（\u9017\u53f7\u5206\u9694）')).toBeEnabled();
  });

  it('keeps manual model input available when discovery fails', async () => {
    discoverLLMChannelModels.mockResolvedValue({
      success: false,
      message: 'Model discovery is not supported for this protocol',
      error: 'LLM channel does not support /models discovery yet',
      errorCode: 'unsupported_protocol',
      stage: 'model_discovery',
      retryable: false,
      details: {},
      resolvedProtocol: 'gemini',
      models: [],
      latencyMs: null,
    });

    render(
      <LLMChannelEditor
        items={[
          { key: 'LLM_CHANNELS', value: 'gemini' },
          { key: 'LLM_GEMINI_PROTOCOL', value: 'gemini' },
          { key: 'LLM_GEMINI_BASE_URL', value: '' },
          { key: 'LLM_GEMINI_ENABLED', value: 'true' },
          { key: 'LLM_GEMINI_API_KEY', value: 'sk-test' },
          { key: 'LLM_GEMINI_MODELS', value: '' },
        ]}
        configVersion="v1"
        maskToken="******"
        onSaved={() => {}}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: /Gemini \u5b98\u65b9/i }));
    fireEvent.click(screen.getByRole('button', { name: '\u83b7\u53d6\u6a21\u578b' }));

    await screen.findByText(/\u6a21\u578b\u53d1\u73b0 · \u534f\u8bae\u6682\u4e0d\u652f\u6301：Model discovery is not supported for this protocol/i);
    expect(screen.getByText(/\u5f53\u524d\u4ec5\u5bf9 OpenAI Compatible \/ DeepSeek \u6e20\u9053\u63d0\u4f9b\u81ea\u52a8\u6a21\u578b\u53d1\u73b0/i)).toBeInTheDocument();

    const manualInput = screen.getByLabelText('\u6a21\u578b（\u9017\u53f7\u5206\u9694）');
    fireEvent.change(manualInput, { target: { value: 'gemini-2.5-flash' } });
    expect(manualInput).toHaveValue('gemini-2.5-flash');
  });

  it('maps discovery format errors to the /models troubleshooting hint', async () => {
    discoverLLMChannelModels.mockResolvedValue({
      success: false,
      message: 'Failed to parse /models response',
      error: 'Unexpected discovery payload',
      errorCode: 'format_error',
      stage: 'response_parse',
      retryable: false,
      details: {},
      resolvedProtocol: 'openai',
      models: [],
      latencyMs: null,
    });

    render(
      <LLMChannelEditor
        items={[
          { key: 'LLM_CHANNELS', value: 'openai' },
          { key: 'LLM_OPENAI_PROTOCOL', value: 'openai' },
          { key: 'LLM_OPENAI_BASE_URL', value: 'https://api.openai.com/v1' },
          { key: 'LLM_OPENAI_ENABLED', value: 'true' },
          { key: 'LLM_OPENAI_API_KEY', value: 'secret-key' },
          { key: 'LLM_OPENAI_MODELS', value: '' },
        ]}
        configVersion="v1"
        maskToken="******"
        onSaved={() => {}}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: /OpenAI \u5b98\u65b9/i }));
    fireEvent.click(screen.getByRole('button', { name: '\u83b7\u53d6\u6a21\u578b' }));

    expect(await screen.findByText(/\u54cd\u5e94\u89e3\u6790 · \u683c\u5f0f\u5f02\u5e38：Failed to parse \/models response/i)).toBeInTheDocument();
    expect(screen.getByText(/\u8be5\u6e20\u9053\u8fd4\u56de\u7684 \/models \u54cd\u5e94\u683c\u5f0f\u4e0d\u517c\u5bb9，\u8bf7\u6539\u4e3a\u624b\u52a8\u586b\u5199\u6a21\u578b\u5217\u8868。/i)).toBeInTheDocument();
  });

  it('maps discovery empty responses to the /models troubleshooting hint', async () => {
    discoverLLMChannelModels.mockResolvedValue({
      success: false,
      message: 'No model IDs returned from /models response',
      error: 'Empty model discovery response',
      errorCode: 'empty_response',
      stage: 'model_discovery',
      retryable: false,
      details: {},
      resolvedProtocol: 'openai',
      models: [],
      latencyMs: null,
    });

    render(
      <LLMChannelEditor
        items={[
          { key: 'LLM_CHANNELS', value: 'openai' },
          { key: 'LLM_OPENAI_PROTOCOL', value: 'openai' },
          { key: 'LLM_OPENAI_BASE_URL', value: 'https://api.openai.com/v1' },
          { key: 'LLM_OPENAI_ENABLED', value: 'true' },
          { key: 'LLM_OPENAI_API_KEY', value: 'secret-key' },
          { key: 'LLM_OPENAI_MODELS', value: '' },
        ]}
        configVersion="v1"
        maskToken="******"
        onSaved={() => {}}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: /OpenAI \u5b98\u65b9/i }));
    fireEvent.click(screen.getByRole('button', { name: '\u83b7\u53d6\u6a21\u578b' }));

    expect(await screen.findByText(/\u6a21\u578b\u53d1\u73b0 · \u7a7a\u54cd\u5e94：No model IDs returned from \/models response/i)).toBeInTheDocument();
    expect(screen.getByText(/\u8be5\u6e20\u9053\u7684 \/models \u63a5\u53e3\u672a\u8fd4\u56de\u53ef\u7528\u6a21\u578b ID/i)).toBeInTheDocument();
    expect(screen.queryByText(/\u5207\u6362\u517c\u5bb9\u6a21\u578b、\u5173\u95ed\u989d\u5916\u54cd\u5e94\u6a21\u5f0f/i)).not.toBeInTheDocument();
  });

  it('does not apply stale discovery response after channel list re-sync', async () => {
    let resolvePendingFirst!: (value: unknown) => void;
    const pendingFirst = new Promise((resolve) => {
      resolvePendingFirst = resolve;
    });

    discoverLLMChannelModels
      .mockImplementationOnce(() => pendingFirst)
      .mockResolvedValueOnce({
        success: true,
        message: 'LLM channel model discovery succeeded',
        error: null,
        resolvedProtocol: 'openai',
        models: ['dashscope-plus'],
        latencyMs: 30,
      });

    const renderResult = render(
      <LLMChannelEditor
        items={[
          { key: 'LLM_CHANNELS', value: 'openai' },
          { key: 'LLM_OPENAI_PROTOCOL', value: 'openai' },
          { key: 'LLM_OPENAI_BASE_URL', value: 'https://api.openai.com/v1' },
          { key: 'LLM_OPENAI_ENABLED', value: 'true' },
          { key: 'LLM_OPENAI_API_KEY', value: 'open-key' },
          { key: 'LLM_OPENAI_MODELS', value: 'gpt-old' },
          { key: 'LLM_DASHSCOPE_PROTOCOL', value: 'openai' },
          { key: 'LLM_DASHSCOPE_BASE_URL', value: 'https://dashscope.aliyuncs.com/compatible-mode/v1' },
          { key: 'LLM_DASHSCOPE_ENABLED', value: 'true' },
          { key: 'LLM_DASHSCOPE_API_KEY', value: 'dash-key' },
          { key: 'LLM_DASHSCOPE_MODELS', value: 'dash-old' },
        ]}
        configVersion="v1"
        maskToken="******"
        onSaved={() => {}}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: /OpenAI \u5b98\u65b9/i }));
    fireEvent.click(screen.getByRole('button', { name: '\u83b7\u53d6\u6a21\u578b' }));

    renderResult.rerender(
      <LLMChannelEditor
        items={[
          { key: 'LLM_CHANNELS', value: 'dashscope' },
          { key: 'LLM_DASHSCOPE_PROTOCOL', value: 'openai' },
          { key: 'LLM_DASHSCOPE_BASE_URL', value: 'https://dashscope.aliyuncs.com/compatible-mode/v1' },
          { key: 'LLM_DASHSCOPE_ENABLED', value: 'true' },
          { key: 'LLM_DASHSCOPE_API_KEY', value: 'dash-key' },
          { key: 'LLM_DASHSCOPE_MODELS', value: 'dash-old' },
        ]}
        configVersion="v1"
        maskToken="******"
        onSaved={() => {}}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: /\u901a\u4e49\u5343\u95ee/i }));
    fireEvent.click(screen.getByRole('button', { name: '\u83b7\u53d6\u6a21\u578b' }));

    const dashModelCheckbox = await screen.findByLabelText('dashscope-plus');
    fireEvent.click(dashModelCheckbox);

    expect(screen.getByLabelText('\u624b\u52a8\u6a21\u578b（\u9017\u53f7\u5206\u9694）')).toHaveValue('dash-old,dashscope-plus');

    resolvePendingFirst({
      success: true,
      message: 'LLM channel model discovery succeeded',
      error: null,
      resolvedProtocol: 'openai',
      models: ['stale-openai'],
      latencyMs: 20,
    });

    await waitFor(() => {
      expect(screen.getByLabelText('\u624b\u52a8\u6a21\u578b（\u9017\u53f7\u5206\u9694）')).toHaveValue('dash-old,dashscope-plus');
    });
    expect(screen.queryByLabelText('stale-openai')).not.toBeInTheDocument();
  });

  it('does not apply stale discovery response after inline channel edit', async () => {
    let resolvePendingFirst!: (value: unknown) => void;
    const pendingFirst = new Promise((resolve) => {
      resolvePendingFirst = resolve;
    });

    discoverLLMChannelModels.mockImplementationOnce(() => pendingFirst);

    render(
      <LLMChannelEditor
        items={[
          { key: 'LLM_CHANNELS', value: 'dashscope' },
          { key: 'LLM_DASHSCOPE_PROTOCOL', value: 'openai' },
          { key: 'LLM_DASHSCOPE_BASE_URL', value: 'https://dashscope.aliyuncs.com/compatible-mode/v1' },
          { key: 'LLM_DASHSCOPE_ENABLED', value: 'true' },
          { key: 'LLM_DASHSCOPE_API_KEY', value: 'dash-key' },
          { key: 'LLM_DASHSCOPE_MODELS', value: 'qwen-old' },
        ]}
        configVersion="v1"
        maskToken="******"
        onSaved={() => {}}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: /Dashscope/i }));
    fireEvent.click(screen.getByRole('button', { name: '\u83b7\u53d6\u6a21\u578b' }));

    const baseUrlInput = screen.getByLabelText('Base URL');
    fireEvent.change(baseUrlInput, {
      target: { value: 'https://dashscope.aliyuncs.com/compatible-mode/v2' },
    });

    resolvePendingFirst({
      success: true,
      message: 'LLM channel model discovery succeeded',
      error: null,
      resolvedProtocol: 'openai',
      models: ['stale-openai'],
      latencyMs: 20,
    });

    await waitFor(() => {
      expect(screen.getByLabelText('\u6a21\u578b（\u9017\u53f7\u5206\u9694）')).toHaveValue('qwen-old');
      expect(screen.queryByLabelText('stale-openai')).not.toBeInTheDocument();
    });
  });
});
