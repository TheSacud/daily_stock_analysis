import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { DashboardStateBlock } from '../DashboardStateBlock';

describe('DashboardStateBlock', () => {
  it('renders the title as a paragraph by default', () => {
    const { container } = render(<DashboardStateBlock title="\u5f00\u59cb\u5206\u6790" description="\u67e5\u770b\u63d0\u793a\u6587\u6848" />);

    const title = screen.getByText('\u5f00\u59cb\u5206\u6790');
    expect(title.tagName).toBe('P');
    expect(container.querySelector('h3')).toBeNull();
  });

  it('renders the title with the requested heading level', () => {
    render(<DashboardStateBlock title="\u5f00\u59cb\u5206\u6790" titleAs="h3" description="\u67e5\u770b\u63d0\u793a\u6587\u6848" />);

    expect(screen.getByRole('heading', { name: '\u5f00\u59cb\u5206\u6790', level: 3 })).toBeInTheDocument();
  });

  it('keeps icon, description, action, and loading behaviors intact', () => {
    const { rerender } = render(
      <DashboardStateBlock
        title="\u5f00\u59cb\u5206\u6790"
        description="\u8f93\u5165\u80a1\u7968\u4ee3\u7801\u8fdb\u884c\u5206\u6790"
        icon={<span data-testid="icon">icon</span>}
        action={<button type="button">\u7acb\u5373\u5f00\u59cb</button>}
      />,
    );

    expect(screen.getByTestId('icon')).toBeInTheDocument();
    expect(screen.getByText('\u8f93\u5165\u80a1\u7968\u4ee3\u7801\u8fdb\u884c\u5206\u6790')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '\u7acb\u5373\u5f00\u59cb' })).toBeInTheDocument();

    rerender(
      <DashboardStateBlock
        title="\u5f00\u59cb\u5206\u6790"
        titleAs="h3"
        description="\u8f93\u5165\u80a1\u7968\u4ee3\u7801\u8fdb\u884c\u5206\u6790"
        loading
      />,
    );

    expect(screen.getByRole('heading', { name: '\u5f00\u59cb\u5206\u6790', level: 3 })).toBeInTheDocument();
    expect(screen.getByText('\u8f93\u5165\u80a1\u7968\u4ee3\u7801\u8fdb\u884c\u5206\u6790')).toBeInTheDocument();
    expect(document.querySelector('.home-spinner')).not.toBeNull();
    expect(screen.queryByTestId('icon')).not.toBeInTheDocument();
  });
});
