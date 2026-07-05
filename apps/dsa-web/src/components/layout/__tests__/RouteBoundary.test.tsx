import { fireEvent, render, screen } from '@testing-library/react';
import { lazy } from 'react';
import type React from 'react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';
import { RouteOutletBoundary } from '../RouteBoundary';
import { Shell } from '../Shell';

vi.mock('../../../contexts/AuthContext', () => ({
  useAuth: () => ({
    authEnabled: false,
    logout: vi.fn().mockResolvedValue(undefined),
  }),
}));

vi.mock('../../../stores/agentChatStore', () => {
  const state = { completionBadge: false };

  return {
    useAgentChatStore: (selector?: (value: typeof state) => unknown) => (
      selector ? selector(state) : state
    ),
  };
});

describe('RouteOutletBoundary', () => {
  it('catches rejected lazy route imports inside the shell and resets on navigation', async () => {
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => undefined);
    const BrokenLazyRoute = lazy(() => (
      Promise.reject(new Error('chunk load failed')) as Promise<{ default: React.ComponentType }>
    ));

    try {
      render(
        <MemoryRouter initialEntries={['/chat']}>
          <Routes>
            <Route
              element={(
                <Shell>
                  <RouteOutletBoundary />
                </Shell>
              )}
            >
              <Route path="/chat" element={<BrokenLazyRoute />} />
              <Route path="/portfolio" element={<div data-testid="portfolio-page">Portfolio</div>} />
            </Route>
          </Routes>
        </MemoryRouter>,
      );

      expect(screen.getByRole('navigation', { name: '\u4e3b\u5bfc\u822a' })).toBeInTheDocument();
      expect(await screen.findByRole('heading', { name: '\u9875\u9762\u52a0\u8f7d\u5931\u8d25' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: '\u91cd\u65b0\u52a0\u8f7d\u9875\u9762' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: '\u8fd4\u56de\u9996\u9875' })).toBeInTheDocument();

      fireEvent.click(screen.getByRole('link', { name: '\u6301\u4ed3' }));

      expect(await screen.findByTestId('portfolio-page')).toBeInTheDocument();
      expect(screen.queryByRole('heading', { name: '\u9875\u9762\u52a0\u8f7d\u5931\u8d25' })).not.toBeInTheDocument();
    } finally {
      consoleError.mockRestore();
    }
  });
});
