import { expect, test, type Page } from '@playwright/test';

const smokePassword = process.env.DSA_WEB_SMOKE_PASSWORD;

if (!smokePassword) {
  test.skip(true, 'Set DSA_WEB_SMOKE_PASSWORD to run authenticated smoke tests.');
}


async function captureSmokeScreenshot(page: Page, testInfo: { outputPath: (name: string) => string }, name: string, options: { fullPage?: boolean } = {}) {
  const path = testInfo.outputPath(`${name}.png`);
  await page.screenshot({
    path,
    fullPage: options.fullPage ?? true,
  });
  await testInfo.attach(name, {
    path,
    contentType: 'image/png',
  });
}

async function login(page: Page) {
  test.skip(!smokePassword, 'Set DSA_WEB_SMOKE_PASSWORD to run authenticated smoke tests.');

  await page.goto('/login');
  await page.waitForLoadState('domcontentloaded');

  const passwordInput = page.locator('#password');
  const submitButton = page.getByRole('button', { name: /\u6388\u6743\u8fdb\u5165\u5de5\u4f5c\u53f0|\u5b8c\u6210\u8bbe\u7f6e\u5e76\u767b\u5f55/ });
  const homeLink = page.getByRole('link', { name: '\u9996\u9875' });

  const isAlreadyAuthenticated =
    page.url().endsWith('/') ||
    await homeLink.isVisible({ timeout: 2_000 }).catch(() => false);

  if (isAlreadyAuthenticated) {
    await page.waitForLoadState('domcontentloaded');
    return;
  }

  await expect(passwordInput).toBeVisible({ timeout: 10_000 });
  await passwordInput.fill(smokePassword!);
  await expect(submitButton).toBeVisible();

  await Promise.all([
    page.waitForResponse(
      (response) => response.url().includes('/api/v1/auth/login') && response.status() === 200,
      { timeout: 15_000 }
    ),
    submitButton.click(),
  ]);

  await page.waitForURL('/', { timeout: 15_000 });
  await page.waitForLoadState('domcontentloaded');
  await page.waitForTimeout(1000);
}

test.describe('web smoke', () => {
  test.use({ locale: 'zh-CN' });

  test('login page renders password form', async ({ page }, testInfo) => {
    await page.goto('/login');
    await page.waitForLoadState('domcontentloaded');

    // Check for branding
    await expect(page.getByText('DAILY STOCK').first()).toBeVisible();
    await expect(page.getByText('Analysis Engine')).toBeVisible();

    // Check for password input
    await expect(page.locator('#password')).toBeVisible();

    // Check for submit button
    await expect(page.getByRole('button', { name: /\u6388\u6743\u8fdb\u5165\u5de5\u4f5c\u53f0|\u5b8c\u6210\u8bbe\u7f6e\u5e76\u767b\u5f55/ })).toBeVisible();

    await captureSmokeScreenshot(page, testInfo, 'smoke-login-page-zh');
  });

  test('home page shows analysis entry and history panel after login', async ({ page }, testInfo) => {
    await login(page);

    const stockInput = page.getByPlaceholder('\u8f93\u5165\u80a1\u7968\u4ee3\u7801\u6216\u540d\u79f0，\u5982 600519、\u8d35\u5dde\u8305\u53f0、AAPL');
    await expect(stockInput).toBeVisible({ timeout: 10_000 });
    await expect(page.getByRole('link', { name: '\u9996\u9875' })).toBeVisible();
    await expect(page.getByRole('link', { name: '\u95ee\u80a1' })).toBeVisible();
    await expect(page.getByText('\u5386\u53f2\u5206\u6790')).toBeVisible();

    await stockInput.fill('600519');
    const analyzeButton = page.getByRole('button', { name: '\u5206\u6790', exact: true });
    await expect(analyzeButton).toBeVisible();

    await captureSmokeScreenshot(page, testInfo, 'smoke-home-page-zh', { fullPage: true });
  });

  test('chat page allows entering a question and starts a request', async ({ page }) => {
    await login(page);

    // Navigate to chat page by clicking the link
    await page.getByRole('link', { name: '\u95ee\u80a1' }).click();
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(1000);

    await expect(page.getByTestId('chat-workspace')).toBeVisible({ timeout: 10_000 });
    await expect(page.getByTestId('chat-session-list-scroll')).toBeVisible();
    await expect(page.getByTestId('chat-message-scroll')).toBeVisible();

    const input = page.getByPlaceholder(/\u5206\u6790 600519/);
    await expect(input).toBeVisible({ timeout: 5000 });
    await expect(page.getByText('\u7b56\u7565', { exact: true })).toBeVisible();

    const prompt = '\u8bf7\u7b80\u8981\u5206\u6790 600519';
    await input.fill(prompt);
    await page.getByRole('button', { name: '\u53d1\u9001' }).click();

    await expect(page.locator('p').filter({ hasText: prompt }).last()).toBeVisible({ timeout: 5000 });
  });

  test('chat page uses accessible labels instead of native title attributes for key actions', async ({ page }) => {
    await login(page);

    await page.getByRole('link', { name: '\u95ee\u80a1' }).click();
    await page.waitForLoadState('domcontentloaded');

    const sendButton = page.getByRole('button', { name: '\u53d1\u9001' });
    const composer = page.getByPlaceholder(/\u5206\u6790 600519/);

    await expect(page.getByTestId('chat-workspace')).toBeVisible({ timeout: 10_000 });
    await expect(sendButton).toBeVisible({ timeout: 10_000 });
    await expect(composer).toBeVisible({ timeout: 10_000 });

    await expect(sendButton).not.toHaveAttribute('title', /.+/);
    await expect(composer).not.toHaveAttribute('title', /.+/);
  });

  test('mobile shell opens navigation drawer after login', async ({ page }, testInfo) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await login(page);

    // Try to open navigation menu
    const menuButton = page.getByRole('button', { name: /\u6253\u5f00\u5bfc\u822a|\u83dc\u5355/i });
    if (await menuButton.isVisible({ timeout: 2000 }).catch(() => false)) {
      await menuButton.click();
    }

    // Check if navigation is visible
    await expect(page.getByRole('link', { name: '\u56de\u6d4b' })).toBeVisible({ timeout: 5000 });

    await captureSmokeScreenshot(page, testInfo, 'smoke-mobile-shell-nav');
  });

  test('settings page renders title and save actions after login', async ({ page }, testInfo) => {
    await login(page);

    // Navigate to settings page by clicking the link
    await page.getByRole('link', { name: '\u8bbe\u7f6e' }).click();
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(1000);

    // Use heading role for more precise selection
    await expect(page.getByRole('heading', { name: '\u7cfb\u7edf\u8bbe\u7f6e' })).toBeVisible({ timeout: 10_000 });
    await expect(page.getByRole('button', { name: '\u91cd\u7f6e' })).toBeVisible();
    await expect(page.getByRole('button', { name: /\u4fdd\u5b58\u914d\u7f6e/ })).toBeVisible();

    await captureSmokeScreenshot(page, testInfo, 'smoke-settings-page-zh');
  });

  test('language switch updates UI copy and persists after page refresh', async ({ page }, testInfo) => {
    await login(page);

    const languageToggle = page.getByRole('button', { name: '\u5207\u6362\u754c\u9762\u8bed\u8a00' });
    await expect(languageToggle).toBeVisible();
    await expect(page.getByRole('link', { name: '\u8bbe\u7f6e' })).toBeVisible();
    await expect(page.getByRole('link', { name: '\u9996\u9875' })).toBeVisible();

    await languageToggle.click();

    const englishLanguageToggle = page.getByRole('button', { name: 'Switch UI language' });
    await expect(englishLanguageToggle).toBeVisible();
    await expect(page.getByRole('link', { name: 'Settings' })).toBeVisible();
    await expect(page.getByRole('link', { name: 'Home' })).toBeVisible();
    await captureSmokeScreenshot(page, testInfo, 'smoke-home-page-en');

    expect(await page.evaluate(() => localStorage.getItem('dsa.uiLanguage'))).toBe('en');

    await page.reload();
    await page.waitForLoadState('domcontentloaded');

    await expect(englishLanguageToggle).toBeVisible();
    await expect(page.getByRole('link', { name: 'Settings' })).toBeVisible();
    await expect(page.getByRole('link', { name: 'Home' })).toBeVisible();

    await page.getByRole('link', { name: 'Settings' }).click();
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(1000);

    await expect(page.getByRole('heading', { name: 'System settings' })).toBeVisible({ timeout: 10_000 });
    await expect(page.getByRole('button', { name: 'Send test' })).toBeVisible();
    await expect(page.getByRole('textbox', { name: 'Title' })).toHaveValue('DSA notification test');

    await captureSmokeScreenshot(page, testInfo, 'smoke-settings-page-en');
  });

  test('backtest page renders filter controls after login', async ({ page }, testInfo) => {
    await login(page);

    // Navigate to backtest page by clicking the link
    await page.getByRole('link', { name: '\u56de\u6d4b' }).click();
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(1000);

    // Check for filter controls
    const filterInput = page.getByPlaceholder('\u6309\u80a1\u7968\u4ee3\u7801\u7b5b\u9009（\u7559\u7a7a\u8868\u793a\u5168\u90e8）');
    await expect(filterInput).toBeVisible({ timeout: 10_000 });
    await expect(page.getByRole('button', { name: '\u7b5b\u9009' })).toBeVisible();
    await expect(page.getByRole('button', { name: '\u8fd0\u884c\u56de\u6d4b' })).toBeVisible();

    await captureSmokeScreenshot(page, testInfo, 'smoke-backtest-page-zh', { fullPage: true });
  });
});
