import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { AuthSettingsCard } from '../AuthSettingsCard';

const { refreshStatus, updateSettings, useAuthMock } = vi.hoisted(() => ({
  refreshStatus: vi.fn(),
  updateSettings: vi.fn(),
  useAuthMock: vi.fn(),
}));

vi.mock('../../../hooks', () => ({
  useAuth: () => useAuthMock(),
}));

vi.mock('../../../api/auth', () => ({
  authApi: {
    updateSettings,
  },
}));

describe('AuthSettingsCard', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useAuthMock.mockReturnValue({
      authEnabled: false,
      setupState: 'no_password',
      refreshStatus,
    });
  });

  it('enables auth with a new password and refreshes status', async () => {
    updateSettings.mockResolvedValue(undefined);
    refreshStatus.mockResolvedValue(undefined);

    render(<AuthSettingsCard />);

    fireEvent.click(screen.getByRole('checkbox'));
    fireEvent.change(screen.getByLabelText('\u8bbe\u7f6e\u7ba1\u7406\u5458\u5bc6\u7801'), { target: { value: 'passwd6' } });
    fireEvent.change(screen.getByLabelText('\u786e\u8ba4\u65b0\u5bc6\u7801'), { target: { value: 'passwd6' } });
    fireEvent.click(screen.getByRole('button', { name: '\u5f00\u542f\u8ba4\u8bc1' }));

    await waitFor(() => {
      expect(updateSettings).toHaveBeenCalledWith(true, 'passwd6', 'passwd6', undefined);
    });
    expect(refreshStatus).toHaveBeenCalled();
    expect(await screen.findByText('\u8ba4\u8bc1\u8bbe\u7f6e\u5df2\u66f4\u65b0')).toBeInTheDocument();
  });

  it('allows disabling auth without current password when the session is still valid', async () => {
    useAuthMock.mockReturnValue({
      authEnabled: true,
      setupState: 'enabled',
      refreshStatus,
    });
    updateSettings.mockResolvedValue(undefined);
    refreshStatus.mockResolvedValue(undefined);

    render(<AuthSettingsCard />);

    fireEvent.click(screen.getByRole('checkbox'));
    fireEvent.click(screen.getByRole('button', { name: '\u5173\u95ed\u8ba4\u8bc1' }));

    await waitFor(() => {
      expect(updateSettings).toHaveBeenCalledWith(false, undefined, undefined, undefined);
    });
    expect(refreshStatus).toHaveBeenCalled();
    expect(await screen.findByText('\u8ba4\u8bc1\u5df2\u5173\u95ed')).toBeInTheDocument();
  });

  it('shows only current password when re-enabling with a retained password', () => {
    useAuthMock.mockReturnValue({
      authEnabled: false,
      setupState: 'password_retained',
      refreshStatus,
    });

    render(<AuthSettingsCard />);

    fireEvent.click(screen.getByRole('checkbox'));

    expect(screen.getByLabelText('\u5f53\u524d\u7ba1\u7406\u5458\u5bc6\u7801')).toBeInTheDocument();
    expect(screen.queryByLabelText('\u8bbe\u7f6e\u7ba1\u7406\u5458\u5bc6\u7801')).not.toBeInTheDocument();
    expect(screen.queryByLabelText('\u786e\u8ba4\u65b0\u5bc6\u7801')).not.toBeInTheDocument();
  });

  it('does not show new password fields while auth is already enabled', () => {
    useAuthMock.mockReturnValue({
      authEnabled: true,
      setupState: 'enabled',
      refreshStatus,
    });

    render(<AuthSettingsCard />);

    expect(screen.queryByLabelText('\u8bbe\u7f6e\u7ba1\u7406\u5458\u5bc6\u7801')).not.toBeInTheDocument();
    expect(screen.queryByLabelText('\u786e\u8ba4\u65b0\u5bc6\u7801')).not.toBeInTheDocument();
  });

  it('blocks initial enable when the new password is missing', async () => {
    render(<AuthSettingsCard />);

    fireEvent.click(screen.getByRole('checkbox'));
    fireEvent.click(screen.getByRole('button', { name: '\u5f00\u542f\u8ba4\u8bc1' }));

    expect(await screen.findByText('\u8bbe\u7f6e\u65b0\u5bc6\u7801\u662f\u5fc5\u586b\u9879')).toBeInTheDocument();
    expect(updateSettings).not.toHaveBeenCalled();
  });
});
