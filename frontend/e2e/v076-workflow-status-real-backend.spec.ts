import { test, expect } from '@playwright/test';

const RIS = `TY  - JOUR
TI  - V076 Real Backend Workflow Status
AU  - Author One
PY  - 2024
DO  - 10.1234/v076.e2e
ER  -${' '}
`;

test.describe('v0.7.6 real-backend workflow status', () => {
  test.skip(process.env.REAL_BACKEND !== '1', 'Set REAL_BACKEND=1 with the API on :8000 to run.');

  test('accept updates sidebar and dashboard without route interception', async ({ page, request }) => {
    const created = await request.post('/api/v1/projects', {
      data: { title: `V076 E2E ${Date.now()}`, description: '', protocol_version: '1.0' },
    });
    expect(created.ok()).toBeTruthy();
    const project = await created.json();
    const projectId = project.project_id ?? project.id;

    const upload = async (name: string) => {
      const res = await request.post(`/api/v1/projects/${projectId}/imports`, {
        multipart: {
          file: { name, mimeType: 'application/x-research-info-systems', buffer: Buffer.from(RIS) },
        },
      });
      expect(res.ok()).toBeTruthy();
      return res.json();
    };

    const first = await upload('first.ris');
    expect(first.status).toBe('success');
    const second = await upload('second.ris');
    expect(second.status).toBe('warning');

    await page.goto(`/projects/${projectId}/sources`);
    await expect(page.getByText('Ostrzeżenie')).toBeVisible();
    await page.getByText('Ostrzeżenie').click();
    await page.getByRole('button', { name: 'Akceptuję' }).click();
    await expect(page.getByRole('button', { name: 'Akceptuję' })).not.toBeVisible();

    // Sidebar reflects the resolved warnings without waiting for a full reload.
    await expect(page.locator('[data-stage-id="sources"]')).toHaveAttribute('data-stage-state', 'completed', { timeout: 10000 });

    const documentToken = await page.evaluate(() => {
      const token = crypto.randomUUID();
      (window as Window & { navigationToken?: string }).navigationToken = token;
      return token;
    });
    await page.locator('a[href="/projects/' + projectId + '/dashboard"]').click();
    expect(await page.evaluate(() => (window as Window & { navigationToken?: string }).navigationToken)).toBe(documentToken);
    await expect(page.locator('#stage-card-sources')).toHaveAttribute('data-state', 'completed', { timeout: 10000 });
    await expect(page.locator('#stage-card-sources')).toContainText('2 importy');
  });
});
