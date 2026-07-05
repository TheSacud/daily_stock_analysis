import { render, screen, waitFor } from '@testing-library/react';
import type { ReactElement } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { SettingsPanelErrorBoundary } from '../SettingsPanelErrorBoundary';

function ThrowingPanel({ message = 'mock settings panel crash' }: { message?: string }): ReactElement {
  throw new Error(message);
}

describe('SettingsPanelErrorBoundary', () => {
  beforeEach(() => {
    vi.spyOn(console, 'error').mockImplementation(() => undefined);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('renders a configurable desktop-log diagnostic fallback when a settings panel throws', () => {
    render(
      <SettingsPanelErrorBoundary
        title="\u901a\u77e5\u8bbe\u7f6e"
        resetKey="notification"
        diagnosticHint={(
          <>
            \u8bf7\u67e5\u770b\u5e76\u63d0\u4f9b\u684c\u9762\u7aef\u65e5\u5fd7
            <code>desktop.log</code>
            ，\u540c\u65f6\u8865\u5145 release \u7248\u672c、Windows \u7248\u672c\u548c\u89e6\u53d1\u5165\u53e3。
          </>
        )}
      >
        <ThrowingPanel />
      </SettingsPanelErrorBoundary>
    );

    expect(screen.getByRole('alert')).toBeInTheDocument();
    expect(screen.getByText('\u901a\u77e5\u8bbe\u7f6e\u52a0\u8f7d\u5931\u8d25')).toBeInTheDocument();
    expect(screen.getByText('desktop.log')).toBeInTheDocument();
    expect(screen.getByText(/release \u7248\u672c、Windows \u7248\u672c\u548c\u89e6\u53d1\u5165\u53e3/)).toBeInTheDocument();
    expect(screen.getByText(/\u9519\u8bef\u6458\u8981：mock settings panel crash/)).toBeInTheDocument();
  });

  it('redacts and truncates sensitive error summary text', () => {
    render(
      <SettingsPanelErrorBoundary title="\u901a\u77e5\u8bbe\u7f6e" resetKey="notification">
        <ThrowingPanel
          message={`Webhook failed: https://hooks.slack.com/services/T000/B000/path-secret?token=super-secret-token&foo=bar OPENAI_API_KEY=sk-supersecretvalue123456 ${'x'.repeat(220)}`}
        />
      </SettingsPanelErrorBoundary>
    );

    const summary = screen.getByText(/\u9519\u8bef\u6458\u8981：/).textContent ?? '';

    expect(summary).toContain('https://hooks.slack.com/[redacted]?[redacted]');
    expect(summary).toContain('?[redacted]');
    expect(summary).toContain('OPENAI_API_KEY=[redacted]');
    expect(summary).not.toContain('/services/T000/B000/path-secret');
    expect(summary).not.toContain('path-secret');
    expect(summary).not.toContain('super-secret-token');
    expect(summary).not.toContain('sk-supersecretvalue123456');
    expect(summary.length).toBeLessThanOrEqual('\u9519\u8bef\u6458\u8981：'.length + 183);
  });

  it('resets after resetKey changes so the panel can render again', async () => {
    const { rerender } = render(
      <SettingsPanelErrorBoundary title="Agent \u8bbe\u7f6e" resetKey="agent:v1">
        <ThrowingPanel />
      </SettingsPanelErrorBoundary>
    );

    expect(screen.getByText('Agent \u8bbe\u7f6e\u52a0\u8f7d\u5931\u8d25')).toBeInTheDocument();

    rerender(
      <SettingsPanelErrorBoundary title="Agent \u8bbe\u7f6e" resetKey="agent:v2">
        <div>Agent \u8bbe\u7f6e\u5df2\u6062\u590d</div>
      </SettingsPanelErrorBoundary>
    );

    await waitFor(() => {
      expect(screen.getByText('Agent \u8bbe\u7f6e\u5df2\u6062\u590d')).toBeInTheDocument();
    });
    expect(screen.queryByText('Agent \u8bbe\u7f6e\u52a0\u8f7d\u5931\u8d25')).not.toBeInTheDocument();
  });
});
