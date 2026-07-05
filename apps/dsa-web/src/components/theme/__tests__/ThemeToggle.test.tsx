import { fireEvent, render, screen } from '@testing-library/react';
import { beforeAll, describe, expect, it, vi } from 'vitest';
import { ThemeProvider } from '../ThemeProvider';
import { ThemeToggle } from '../ThemeToggle';

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
});

describe('ThemeToggle', () => {
  it('opens the theme menu and shows all theme modes', async () => {
    render(
      <ThemeProvider>
        <ThemeToggle />
      </ThemeProvider>
    );

    fireEvent.click(screen.getByRole('button', { name: '\u5207\u6362\u4e3b\u9898' }));

    expect(await screen.findByRole('menu', { name: '\u4e3b\u9898\u6a21\u5f0f' })).toBeInTheDocument();
    expect(screen.getByRole('menuitemradio', { name: '\u6d45\u8272' })).toBeInTheDocument();
    expect(screen.getByRole('menuitemradio', { name: '\u6df1\u8272' })).toBeInTheDocument();
    expect(screen.getByRole('menuitemradio', { name: '\u8ddf\u968f\u7cfb\u7edf' })).toBeInTheDocument();
  });
});
