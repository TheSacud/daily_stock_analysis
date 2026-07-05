import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import type { ReactNode } from 'react';
import { UiLanguageProvider, useUiLanguage } from '../../../contexts/UiLanguageContext';
import { getFieldDescriptionZh, getFieldTitleZh } from '../../../utils/systemConfigI18n';
import { UI_LANGUAGE_STORAGE_KEY } from '../../../utils/uiLanguage';
import { SettingsField } from '../SettingsField';

describe('SettingsField', () => {
  it('prefers localized Chinese field titles over backend schema titles', () => {
    render(
      <SettingsField
        item={{
          key: 'STOCK_LIST',
          value: '600519',
          rawValueExists: true,
          isMasked: false,
          schema: {
            key: 'STOCK_LIST',
            title: 'Stock List',
            category: 'base',
            dataType: 'string',
            uiControl: 'text',
            isSensitive: false,
            isRequired: false,
            isEditable: true,
            options: [],
            validation: {},
            displayOrder: 1,
          },
        }}
        value="600519"
        onChange={vi.fn()}
      />
    );

    expect(screen.getByLabelText('\u81ea\u9009\u80a1\u5217\u8868')).toBeInTheDocument();
    expect(screen.queryByLabelText('Stock List')).not.toBeInTheDocument();
  });

  it('localizes TickFlow field descriptions instead of falling back to backend English schema', () => {
    render(
      <SettingsField
        item={{
          key: 'TICKFLOW_PRIORITY',
          value: '2',
          rawValueExists: false,
          isMasked: false,
          schema: {
            key: 'TICKFLOW_PRIORITY',
            title: 'TickFlow Priority',
            description: 'Priority for TickFlow daily K-line fetcher. Lower numbers are tried earlier.',
            category: 'data_source',
            dataType: 'integer',
            uiControl: 'number',
            isSensitive: false,
            isRequired: false,
            isEditable: true,
            options: [],
            validation: { min: 0, max: 99 },
            displayOrder: 16,
            helpKey: 'settings.data_source.TICKFLOW_PRIORITY',
          },
        }}
        value="2"
        onChange={vi.fn()}
      />
    );

    expect(screen.getByLabelText('TickFlow \u65e5 K \u4f18\u5148\u7ea7')).toBeInTheDocument();
    expect(screen.getByText(/\u63a7\u5236 TickFlow \u5728 A \u80a1\u65e5 K \u6570\u636e\u6e90\u56de\u9000\u94fe\u4e2d\u7684\u5c1d\u8bd5\u987a\u5e8f/)).toBeInTheDocument();
    expect(screen.queryByText(/Priority for TickFlow daily K-line fetcher/)).not.toBeInTheDocument();
  });
  it('uses schema key for TickFlow localization when the runtime item key differs', () => {
    render(
      <SettingsField
        item={{
          key: 'runtime.tickflow.priority',
          value: '2',
          rawValueExists: false,
          isMasked: false,
          schema: {
            key: 'TICKFLOW_PRIORITY',
            title: 'TickFlow Priority',
            description: 'Priority for TickFlow daily K-line fetcher. Lower numbers are tried earlier.',
            category: 'data_source',
            dataType: 'integer',
            uiControl: 'number',
            isSensitive: false,
            isRequired: false,
            isEditable: true,
            options: [],
            validation: { min: 0, max: 99 },
            displayOrder: 16,
            helpKey: 'settings.data_source.TICKFLOW_PRIORITY',
          },
        }}
        value="2"
        onChange={vi.fn()}
      />
    );

    expect(screen.getByLabelText(getFieldTitleZh('TICKFLOW_PRIORITY', ''))).toBeInTheDocument();
    expect(screen.getByText(getFieldDescriptionZh('TICKFLOW_PRIORITY', ''))).toBeInTheDocument();
    expect(screen.queryByLabelText('TickFlow Priority')).not.toBeInTheDocument();
    expect(screen.queryByText(/Priority for TickFlow daily K-line fetcher/)).not.toBeInTheDocument();
  });
  it('renders sensitive field metadata and validation errors', () => {
    const onChange = vi.fn();

    render(
      <SettingsField
        item={{
          key: 'OPENAI_API_KEY',
          value: 'secret',
          rawValueExists: true,
          isMasked: false,
          schema: {
            key: 'OPENAI_API_KEY',
            category: 'ai_model',
            dataType: 'string',
            uiControl: 'password',
            isSensitive: true,
            isRequired: true,
            isEditable: true,
            options: [],
            validation: {},
            displayOrder: 1,
          },
        }}
        value="secret"
        onChange={onChange}
        issues={[
          {
            key: 'OPENAI_API_KEY',
            code: 'required',
            message: 'API Key \u5fc5\u586b',
            severity: 'error',
          },
        ]}
      />
    );

    expect(screen.getByText('\u654f\u611f')).toBeInTheDocument();
    expect(screen.getByText('API Key \u5fc5\u586b')).toBeInTheDocument();

    const input = screen.getByLabelText('OpenAI API Key');
    fireEvent.focus(input);
    fireEvent.change(input, {
      target: { value: 'updated-secret' },
    });

    expect(onChange).toHaveBeenCalledWith('OPENAI_API_KEY', 'updated-secret');
  });

  it('renders multi-value sensitive fields with external delete actions', () => {
    const onChange = vi.fn();

    render(
      <SettingsField
        item={{
          key: 'OPENAI_API_KEYS',
          value: 'secret-a,secret-b',
          rawValueExists: true,
          isMasked: false,
          schema: {
            key: 'OPENAI_API_KEYS',
            category: 'ai_model',
            dataType: 'string',
            uiControl: 'password',
            isSensitive: true,
            isRequired: false,
            isEditable: true,
            options: [],
            validation: { multiValue: true },
            displayOrder: 1,
          },
        }}
        value="secret-a,secret-b"
        onChange={onChange}
      />
    );

    expect(screen.getAllByRole('button', { name: '\u663e\u793a\u5185\u5bb9' })).toHaveLength(2);
    expect(screen.getAllByRole('button', { name: '\u5220\u9664' })).toHaveLength(2);
  });

  it('allows optional select fields to be cleared when schema provides an empty option', () => {
    const onChange = vi.fn();

    render(
      <SettingsField
        item={{
          key: 'NOTIFICATION_MIN_SEVERITY',
          value: 'warning',
          rawValueExists: true,
          isMasked: false,
          schema: {
            key: 'NOTIFICATION_MIN_SEVERITY',
            title: 'Notification Minimum Severity',
            category: 'notification',
            dataType: 'string',
            uiControl: 'select',
            isSensitive: false,
            isRequired: false,
            isEditable: true,
            options: [
              { label: 'Not set', value: '' },
              { label: 'info', value: 'info' },
              { label: 'warning', value: 'warning' },
              { label: 'error', value: 'error' },
              { label: 'critical', value: 'critical' },
            ],
            validation: { enum: ['', 'info', 'warning', 'error', 'critical'] },
            displayOrder: 69,
          },
        }}
        value="warning"
        onChange={onChange}
      />
    );

    const select = screen.getByLabelText('\u6700\u5c0f\u901a\u77e5\u7ea7\u522b');
    expect(screen.getByRole('option', { name: '\u672a\u8bbe\u7f6e' })).not.toBeDisabled();
    expect(screen.queryByRole('option', { name: '\u8bf7\u9009\u62e9' })).not.toBeInTheDocument();

    fireEvent.change(select, { target: { value: '' } });

    expect(onChange).toHaveBeenCalledWith('NOTIFICATION_MIN_SEVERITY', '');
  });

  it('shows the schema default for select fields when no explicit env value exists', () => {
    const onChange = vi.fn();

    render(
      <SettingsField
        item={{
          key: 'GENERATION_BACKEND',
          value: '',
          rawValueExists: false,
          isMasked: false,
          schema: {
            key: 'GENERATION_BACKEND',
            title: 'Generation Backend',
            category: 'ai_model',
            dataType: 'string',
            uiControl: 'select',
            isSensitive: false,
            isRequired: false,
            isEditable: true,
            defaultValue: 'litellm',
            options: [{ label: 'Default model settings', value: 'litellm' }],
            validation: { enum: ['litellm'] },
            displayOrder: 1,
          },
        }}
        value=""
        onChange={onChange}
      />
    );

    expect(screen.getByLabelText('\u5206\u6790\u751f\u6210\u65b9\u5f0f')).toHaveValue('litellm');
    expect(onChange).not.toHaveBeenCalled();
  });

  it('renders localized labels for real system config select options', () => {
    const selectCases = [
      {
        key: 'NEWS_STRATEGY_PROFILE',
        category: 'data_source',
        options: ['ultra_short', 'short', 'medium', 'long'],
        expectedLabels: ['\u8d85\u77ed\u7ebf（1\u5929）', '\u77ed\u671f（3\u5929）', '\u4e2d\u671f（7\u5929）', '\u957f\u671f（30\u5929）'],
      },
      {
        key: 'REPORT_TYPE',
        category: 'notification',
        options: ['simple', 'full', 'brief'],
        expectedLabels: ['\u7b80\u6d01', '\u5b8c\u6574', '\u7b80\u62a5'],
      },
      {
        key: 'LOG_LEVEL',
        category: 'system',
        options: ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
        expectedLabels: ['\u8c03\u8bd5', '\u4fe1\u606f', '\u8b66\u544a', '\u9519\u8bef', '\u4e25\u91cd'],
      },
    ] as const;

    selectCases.forEach(({ key, category, options, expectedLabels }) => {
      const { unmount } = render(
        <SettingsField
          item={{
            key,
            value: options[0],
            rawValueExists: true,
            isMasked: false,
            schema: {
              key,
              title: key,
              category,
              dataType: 'string',
              uiControl: 'select',
              isSensitive: false,
              isRequired: false,
              isEditable: true,
              options: [...options],
              validation: {},
              displayOrder: 1,
            },
          }}
          value={options[0]}
          onChange={() => undefined}
        />
      );

      expectedLabels.forEach((label) => {
        expect(screen.getByRole('option', { name: label })).toBeInTheDocument();
      });

      options.forEach((rawOption) => {
        expect(screen.queryByRole('option', { name: rawOption })).not.toBeInTheDocument();
      });

      unmount();
    });
  });

  it('renders MARKET_REVIEW_REGION as free-text field with comma-separated defaults', () => {
    const onChange = vi.fn();

    render(
      <SettingsField
        item={{
          key: 'MARKET_REVIEW_REGION',
          value: 'cn,jp',
          rawValueExists: true,
          isMasked: false,
          schema: {
            key: 'MARKET_REVIEW_REGION',
            category: 'system',
            dataType: 'string',
            uiControl: 'text',
            isSensitive: false,
            isRequired: false,
            isEditable: true,
            options: [],
            validation: {},
            displayOrder: 1,
          },
        }}
        value="cn,jp"
        onChange={onChange}
      />
    );

    const input = screen.getByLabelText('\u5927\u76d8\u590d\u76d8\u5e02\u573a') as HTMLInputElement;
    expect(input).toHaveValue('cn,jp');
    expect(screen.queryByRole('combobox')).not.toBeInTheDocument();

    fireEvent.change(input, {
      target: { value: 'cn,jp,kr' },
    });

    expect(onChange).toHaveBeenCalledWith('MARKET_REVIEW_REGION', 'cn,jp,kr');
  });

  it('renders context compression profile options with Chinese labels', () => {
    const onChange = vi.fn();

    render(
      <SettingsField
        item={{
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
        }}
        value="balanced"
        onChange={onChange}
      />
    );

    expect(screen.getByLabelText('\u4e0a\u4e0b\u6587\u538b\u7f29\u7b56\u7565')).toBeInTheDocument();
    expect(screen.getByRole('option', { name: '\u6210\u672c\u4f18\u5148' })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: '\u5747\u8861\u63a8\u8350' })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: '\u957f\u4e0a\u4e0b\u6587\u539f\u6587\u4f18\u5148' })).toBeInTheDocument();
  });

  it('renders blank-value preset guidance for context compression numeric fields', () => {
    const onChange = vi.fn();

    render(
      <>
        <SettingsField
          item={{
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
            },
          }}
          value=""
          onChange={onChange}
        />
        <SettingsField
          item={{
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
            },
          }}
          value=""
          onChange={onChange}
        />
      </>
    );

    expect(screen.getByLabelText('\u538b\u7f29\u89e6\u53d1\u9608\u503c（tokens）')).toBeInTheDocument();
    expect(screen.getByLabelText('\u539f\u6587\u4fdd\u62a4\u8f6e\u6b21')).toBeInTheDocument();
    expect(screen.getByText(/\u4f30\u7b97\u5386\u53f2 token \u8d85\u8fc7\u8be5\u503c\u65f6\u89e6\u53d1\u6458\u8981/)).toHaveTextContent('\u7559\u7a7a\u5219\u8ddf\u968f\u5f53\u524d\u4e0a\u4e0b\u6587\u538b\u7f29\u7b56\u7565 profile \u9ed8\u8ba4\u503c');
    expect(screen.getByText(/\u538b\u7f29\u65f6\u6700\u8fd1 N \u4e2a\u7528\u6237\u8f6e\u6b21\u53ca\u5176\u540e\u7684\u56de\u590d\u4fdd\u6301\u539f\u6587/)).toHaveTextContent('\u7559\u7a7a\u5219\u8ddf\u968f\u5f53\u524d\u4e0a\u4e0b\u6587\u538b\u7f29\u7b56\u7565 profile \u9ed8\u8ba4\u503c');
  });

  it('renders localized custom webhook body template guidance', () => {
    const onChange = vi.fn();

    render(
      <SettingsField
        item={{
          key: 'CUSTOM_WEBHOOK_BODY_TEMPLATE',
          value: '',
          rawValueExists: false,
          isMasked: false,
          schema: {
            key: 'CUSTOM_WEBHOOK_BODY_TEMPLATE',
            category: 'notification',
            dataType: 'string',
            uiControl: 'textarea',
            isSensitive: false,
            isRequired: false,
            isEditable: true,
            options: [],
            validation: {},
            displayOrder: 52,
          },
        }}
        value=""
        onChange={onChange}
      />
    );

    expect(screen.getByLabelText('\u81ea\u5b9a\u4e49 Webhook Body \u6a21\u677f')).toBeInTheDocument();
    expect(screen.getByText(/\u4f1a\u5148\u4e8e Bark、Slack、Discord \u7b49\u81ea\u52a8 payload \u751f\u6548/)).toBeInTheDocument();
    expect(screen.getByText(/\u88f8 \$content \/ \$title \u4e0d\u505a JSON \u8f6c\u4e49/)).toBeInTheDocument();
  });

  it('opens detailed field help when help metadata is available', () => {
    render(
      <SettingsField
        item={{
          key: 'STOCK_LIST',
          value: '600519,300750',
          rawValueExists: true,
          isMasked: false,
          schema: {
            key: 'STOCK_LIST',
            category: 'base',
            dataType: 'array',
            uiControl: 'textarea',
            isSensitive: false,
            isRequired: false,
            isEditable: true,
            options: [],
            validation: {},
            displayOrder: 1,
            helpKey: 'settings.base.STOCK_LIST',
            examples: ['STOCK_LIST=600519,300750,002594'],
            docs: [
              {
                label: '\u5b8c\u6574\u6307\u5357',
                href: 'https://example.com/full-guide',
              },
            ],
            warningCodes: [],
          },
        }}
        value="600519,300750"
        onChange={() => undefined}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: '\u67e5\u770b \u81ea\u9009\u80a1\u5217\u8868 \u914d\u7f6e\u8bf4\u660e' }));

    expect(screen.getByRole('dialog', { name: '\u81ea\u9009\u80a1\u5217\u8868' })).toBeInTheDocument();
    expect(screen.getByText('STOCK_LIST=600519,300750,002594')).toBeInTheDocument();
    const docLink = screen.getByRole('link', { name: /\u5b8c\u6574\u6307\u5357/ });
    expect(docLink).toHaveAttribute('href', 'https://example.com/full-guide');

    const closeButtons = screen.getAllByRole('button', { name: '\u5173\u95ed\u914d\u7f6e\u8bf4\u660e' });
    expect(closeButtons[0].tabIndex).toBe(-1);
    const closeButton = closeButtons.find((button) => button.tabIndex !== -1);
    expect(closeButton).toBeDefined();

    closeButton?.focus();
    fireEvent.keyDown(document, { key: 'Tab', shiftKey: true });
    expect(docLink).toHaveFocus();

    fireEvent.keyDown(document, { key: 'Tab' });
    expect(closeButton).toHaveFocus();

    fireEvent.keyDown(document, { key: 'Escape' });
    expect(screen.queryByRole('dialog', { name: '\u81ea\u9009\u80a1\u5217\u8868' })).not.toBeInTheDocument();
  });

  it('keeps generation channel help user-facing without env key or examples', () => {
    render(
      <SettingsField
        item={{
          key: 'GENERATION_BACKEND',
          value: 'litellm',
          rawValueExists: true,
          isMasked: false,
          schema: {
            key: 'GENERATION_BACKEND',
            title: 'Generation Backend',
            category: 'ai_model',
            dataType: 'string',
            uiControl: 'select',
            isSensitive: false,
            isRequired: false,
            isEditable: true,
            options: [{ label: 'Default model settings', value: 'litellm' }],
            validation: { enum: ['litellm'] },
            displayOrder: 1,
            helpKey: 'settings.ai_model.GENERATION_BACKEND',
            examples: ['GENERATION_BACKEND=litellm'],
            warningCodes: [],
          },
        }}
        value="litellm"
        onChange={() => undefined}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: '\u67e5\u770b \u5206\u6790\u751f\u6210\u65b9\u5f0f \u914d\u7f6e\u8bf4\u660e' }));

    const dialog = screen.getByRole('dialog', { name: '\u5206\u6790\u751f\u6210\u65b9\u5f0f' });
    expect(dialog).toHaveTextContent('\u51b3\u5b9a\u7cfb\u7edf\u7528\u54ea\u79cd\u65b9\u5f0f\u751f\u6210');
    expect(dialog).not.toHaveTextContent('GENERATION_BACKEND');
    expect(dialog).not.toHaveTextContent('\u914d\u7f6e\u6837\u4f8b');
    expect(dialog).not.toHaveTextContent('Phase 1');
    expect(dialog).toHaveTextContent('\u672c\u673a\u5df2\u5b89\u88c5\u5e76\u767b\u5f55\u5bf9\u5e94 CLI');
    expect(dialog).toHaveTextContent('\u9ed8\u8ba4\u6a21\u578b\u914d\u7f6e\u4f1a\u7ee7\u7eed\u4f7f\u7528\u73b0\u6709 API Key');
    expect(dialog).not.toHaveTextContent('\u9ad8\u7ea7\u8bf4\u660e');
    expect(dialog).not.toHaveTextContent('LiteLLM');
  });

  it('describes agent auto generation without exposing implementation labels as the primary UI copy', () => {
    render(
      <SettingsField
        item={{
          key: 'AGENT_GENERATION_BACKEND',
          value: 'auto',
          rawValueExists: true,
          isMasked: false,
          schema: {
            key: 'AGENT_GENERATION_BACKEND',
            title: 'Agent Generation Backend',
            category: 'agent',
            dataType: 'string',
            uiControl: 'select',
            isSensitive: false,
            isRequired: false,
            isEditable: true,
            options: [
              { label: 'Auto', value: 'auto' },
              { label: 'Default model settings', value: 'litellm' },
            ],
            validation: { enum: ['auto', 'litellm'] },
            displayOrder: 1,
            helpKey: 'settings.agent.AGENT_GENERATION_BACKEND',
            examples: [],
            warningCodes: [],
          },
        }}
        value="auto"
        onChange={() => undefined}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: '\u67e5\u770b \u95ee\u80a1\u751f\u6210\u65b9\u5f0f \u914d\u7f6e\u8bf4\u660e' }));

    const dialog = screen.getByRole('dialog', { name: '\u95ee\u80a1\u751f\u6210\u65b9\u5f0f' });
    expect(dialog).toHaveTextContent('\u7cfb\u7edf\u4f1a\u9009\u62e9\u5f53\u524d\u53ef\u7528\u7684\u65b9\u5f0f');
    expect(dialog).toHaveTextContent('\u5982\u679c\u4e0d\u786e\u5b9a，\u9009\u62e9“\u81ea\u52a8”\u5373\u53ef');
    expect(dialog).toHaveTextContent('\u8fd9\u9879\u8bbe\u7f6e\u53ea\u5f71\u54cd\u95ee\u80a1\u52a9\u624b');
    expect(dialog).not.toHaveTextContent('\u9ad8\u7ea7\u8bf4\u660e');
    expect(dialog).not.toHaveTextContent('LiteLLM');
    expect(dialog).not.toHaveTextContent('\u4f18\u5148\u9009\u62e9\u5f53\u524d\u53ef\u7528');
  });

  it('uses per-field schema titles even when helpKey is shared by multiple fields', () => {
    const restoreLanguage = localStorage.getItem(UI_LANGUAGE_STORAGE_KEY);
    localStorage.setItem(UI_LANGUAGE_STORAGE_KEY, 'en');

    try {
      const SchemaTitleSwitcher = ({ children }: { children: ReactNode }) => {
        const { setLanguage } = useUiLanguage();
        return (
          <div>
            <button type="button" onClick={() => setLanguage('en')}>
              switch-en
            </button>
            {children}
          </div>
        );
      };

      render(
        <UiLanguageProvider>
          <SchemaTitleSwitcher>
            <SettingsField
              item={{
                key: 'OPENAI_MODEL',
                value: 'gemini/gemini-3.1-pro-preview',
                rawValueExists: true,
                isMasked: false,
                schema: {
                  key: 'OPENAI_MODEL',
                  category: 'ai_model',
                  dataType: 'string',
                  uiControl: 'text',
                  isSensitive: false,
                  isRequired: false,
                  isEditable: true,
                  options: [],
                  validation: {},
                  displayOrder: 10,
                  title: 'Primary model',
                  helpKey: 'settings.llm_channel.primary_model',
                  description: 'Primary model description',
                },
              }}
              value="gemini/gemini-3.1-pro-preview"
              onChange={vi.fn()}
            />
            <SettingsField
              item={{
                key: 'OPENAI_VISION_MODEL',
                value: 'gemini/gemini-2.0-flash',
                rawValueExists: true,
                isMasked: false,
                schema: {
                  key: 'OPENAI_VISION_MODEL',
                  category: 'ai_model',
                  dataType: 'string',
                  uiControl: 'text',
                  isSensitive: false,
                  isRequired: false,
                  isEditable: true,
                  options: [],
                  validation: {},
                  displayOrder: 11,
                  title: 'Vision model',
                  helpKey: 'settings.llm_channel.primary_model',
                  description: 'Vision model description',
                },
              }}
              value="gemini/gemini-2.0-flash"
              onChange={vi.fn()}
            />
          </SchemaTitleSwitcher>
        </UiLanguageProvider>
      );

      fireEvent.click(screen.getByRole('button', { name: 'switch-en' }));

      expect(screen.getByLabelText('Primary model')).toBeInTheDocument();
      expect(screen.getByLabelText('Vision model')).toBeInTheDocument();
    } finally {
      if (restoreLanguage) {
        localStorage.setItem(UI_LANGUAGE_STORAGE_KEY, restoreLanguage);
      } else {
        localStorage.removeItem(UI_LANGUAGE_STORAGE_KEY);
      }
    }
  });
});
