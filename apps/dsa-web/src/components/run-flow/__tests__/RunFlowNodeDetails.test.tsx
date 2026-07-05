import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import type { RunFlowNode } from '../../../types/runFlow';
import { RunFlowNodeDetails } from '../RunFlowNodeDetails';

describe('RunFlowNodeDetails', () => {
  it('hides provider metrics that do not apply to queue nodes', () => {
    const node: RunFlowNode = {
      id: 'task_queue',
      lane: 'entry',
      kind: 'queue',
      label: '\u4efb\u52a1\u961f\u5217',
      status: 'success',
      startedAt: '2026-06-08T22:14:25',
      message: '\u4efb\u52a1\u8fdb\u5165\u8fd0\u884c\u961f\u5217',
    };

    render(<RunFlowNodeDetails node={node} />);

    expect(screen.getByText('\u4efb\u52a1\u961f\u5217')).toBeInTheDocument();
    expect(screen.getByText('\u7c7b\u578b')).toBeInTheDocument();
    expect(screen.getByText('\u961f\u5217')).toBeInTheDocument();
    expect(screen.getByText('\u5f00\u59cb\u65f6\u95f4')).toBeInTheDocument();
    expect(screen.queryByText('\u63d0\u4f9b\u65b9')).not.toBeInTheDocument();
    expect(screen.queryByText('\u8017\u65f6')).not.toBeInTheDocument();
    expect(screen.queryByText('\u5c1d\u8bd5\u6b21\u6570')).not.toBeInTheDocument();
    expect(screen.queryByText('\u8bb0\u5f55\u6570')).not.toBeInTheDocument();
  });

  it('renders ContextPack quality metadata as structured details instead of raw JSON', () => {
    const node: RunFlowNode = {
      id: 'context_pack',
      lane: 'analysis',
      kind: 'analysis',
      label: 'ContextPack',
      status: 'degraded',
      metadata: {
        topologyGroup: 'context_pack',
        packVersion: '1.0',
        counts: {
          available: 4,
          missing: 1,
          partial: 1,
          fallback: 0,
        },
        dataQuality: {
          overallScore: 91,
          level: 'good',
          blockScores: {
            quote: 100,
            dailyBars: 100,
            technical: 100,
            news: 35,
          },
        },
        context_status_counts: {
          success: 4,
          degraded: 1,
          skipped: 1,
        },
      },
    };

    render(<RunFlowNodeDetails node={node} />);

    expect(screen.getByText('\u4e0a\u4e0b\u6587\u8d28\u91cf')).toBeInTheDocument();
    expect(screen.getByText('\u7efc\u5408\u8bc4\u5206')).toBeInTheDocument();
    expect(screen.getByText('91')).toBeInTheDocument();
    expect(screen.getByText('\u6570\u636e\u5757\u8bc4\u5206')).toBeInTheDocument();
    expect(screen.getByText('news')).toBeInTheDocument();
    expect(screen.getByText('35')).toBeInTheDocument();
    expect(screen.getByText('\u7248\u672c')).toBeInTheDocument();
    expect(screen.getByText('1.0')).toBeInTheDocument();
    expect(screen.queryByText('\u63d0\u4f9b\u65b9')).not.toBeInTheDocument();
    expect(screen.queryByText('\u8017\u65f6')).not.toBeInTheDocument();
    expect(screen.queryByText('\u5c1d\u8bd5\u6b21\u6570')).not.toBeInTheDocument();
    expect(screen.queryByText('\u8bb0\u5f55\u6570')).not.toBeInTheDocument();
    expect(screen.queryByText('counts')).not.toBeInTheDocument();
    expect(screen.queryByText('dataQuality')).not.toBeInTheDocument();
    expect(screen.queryByText('context_status_counts')).not.toBeInTheDocument();
    expect(screen.queryByText(/overallScore/)).not.toBeInTheDocument();
  });

  it('keeps provider metrics visible for data source nodes', () => {
    const node: RunFlowNode = {
      id: 'topology_data_realtime_quote',
      lane: 'data_source',
      kind: 'data_source',
      label: '\u5b9e\u65f6\u884c\u60c5',
      provider: 'TushareFetcher -> AkshareFetcher',
      status: 'fallback',
      durationMs: 750,
      attempts: 2,
      recordCount: 39,
    };

    render(<RunFlowNodeDetails node={node} />);

    expect(screen.getByText('\u63d0\u4f9b\u65b9')).toBeInTheDocument();
    expect(screen.getByText('TushareFetcher -> AkshareFetcher')).toBeInTheDocument();
    expect(screen.getByText('\u8017\u65f6')).toBeInTheDocument();
    expect(screen.getByText('750 ms')).toBeInTheDocument();
    expect(screen.getByText('\u5c1d\u8bd5\u6b21\u6570')).toBeInTheDocument();
    expect(screen.getByText('2')).toBeInTheDocument();
    expect(screen.getByText('\u8bb0\u5f55\u6570')).toBeInTheDocument();
    expect(screen.getByText('39')).toBeInTheDocument();
  });
});
