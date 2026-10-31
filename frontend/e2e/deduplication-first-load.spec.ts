import { expect, test } from '@playwright/test';

const RIS = (title: string) => `TY  - JOUR\nTI  - ${title}\nAU  - Synthetic Author\nPY  - 2024\nER  - \n`;

async function createEmptyProject(request: import('@playwright/test').APIRequestContext): Promise<string> {
  const created = await request.post('/api/v1/projects', {
    data: { title: `Synthetic dedup E2E ${Date.now()}`, description: '', protocol_version: '1.0' },
  });
  expect(created.ok()).toBeTruthy();
  const project = await created.json();
  return project.project_id ?? project.id;
}

test.describe('deduplication first load with the real API', () => {
  test('shows real backend groups on the first deduplication page load', async ({ page, request }) => {
    const projectId = await createEmptyProject(request);
    for (const [index, title] of [
      'Energy efficiency in manufacturing systems',
      'Energy efficiency in manufacturing system',
    ].entries()) {
      const imported = await request.post(`/api/v1/projects/${projectId}/imports`, {
        multipart: { file: {
          name: `dedup-page-${index}.ris`,
          mimeType: 'application/x-research-info-systems',
          buffer: Buffer.from(RIS(title)),
        } },
      });
      expect(imported.ok()).toBeTruthy();
    }
    const responsePromise = page.waitForResponse((response) =>
      response.url().includes(`/api/v1/projects/${projectId}/duplicate-groups`) && response.status() === 200,
    );
    await page.goto(`/projects/${projectId}/dedup`);
    const payload = await (await responsePromise).json();
    expect(payload.total_groups_count).toBe(1);
    expect(payload.readiness.pending_review_groups).toBe(1);
    expect(payload.readiness.screening_ready).toBe(false);
    expect(payload.groups[0].records_count).toBe(2);
    expect(payload.groups[0].records.map((record: { title: string }) => record.title).sort()).toEqual([
      'Energy efficiency in manufacturing system',
      'Energy efficiency in manufacturing systems',
    ]);
    await expect(page.getByText('Oczekujące grupy duplikatów (1)', { exact: true })).toBeVisible();
    for (const record of payload.groups[0].records) {
      await expect(page.getByText(record.title, { exact: true }).first()).toBeVisible();
    }
    await expect(page.getByRole('heading', { name: 'Duplicate Groups Awaiting Human Review (1)' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Zatwierdź tę grupę jako potwierdzony duplikat' })).toBeVisible();
    await expect(page.getByText('Błąd połączenia z API Deduplikacji', { exact: true })).toHaveCount(0);
  });

  test('renders candidate status on first dashboard navigation', async ({ page, request }) => {
    const projectId = await createEmptyProject(request);

    for (const [index, title] of [
      'Energy efficiency in manufacturing systems',
      'Energy efficiency in manufacturing system',
    ].entries()) {
      const imported = await request.post(`/api/v1/projects/${projectId}/imports`, {
        multipart: {
          file: {
            name: `synthetic-${index}.ris`,
            mimeType: 'application/x-research-info-systems',
            buffer: Buffer.from(RIS(title)),
          },
        },
      });
      expect(imported.ok()).toBeTruthy();
    }

    const dedupRequest = page.waitForResponse((response) =>
      response.url().includes(`/api/v1/projects/${projectId}/duplicate-groups`) && response.status() === 200,
    );
    await page.goto(`/projects/${projectId}/dashboard`);
    await dedupRequest;
    await expect(page.locator('[data-stage-id="dedup"]')).not.toHaveAttribute('data-stage-state', 'error');
    await expect(page.locator('[data-stage-id="dedup"]')).toBeVisible();
    const firstVisibleSamples: number[] = [];
    for (let sample = 0; sample < 20; sample += 1) {
      if (sample > 0) await page.reload();
      const dedupCard = page.locator('#stage-card-deduplication');
      await expect(dedupCard).toHaveAttribute('data-loading', 'false');
      await expect(dedupCard).not.toHaveAttribute('data-state', 'error');
      await expect.poll(() => page.evaluate(() =>
        performance.getEntriesByName('slr:duplicate-groups-render').length,
      )).toBeGreaterThan(0);
      const firstVisibleMs = await page.evaluate(() =>
        performance.getEntriesByName('slr:duplicate-groups-render').at(-1)?.duration,
      );
      expect(firstVisibleMs).toBeGreaterThan(0);
      firstVisibleSamples.push(firstVisibleMs!);
    }
    const sorted = [...firstVisibleSamples].sort((left, right) => left - right);
    const percentile = (fraction: number) => sorted[Math.ceil(sorted.length * fraction) - 1];
    console.info(JSON.stringify({
      synthetic_dedup_first_visible_samples: sorted.length,
      p50_ms: percentile(0.50),
      p95_ms: percentile(0.95),
      p99_ms: percentile(0.99),
    }));
  });

  test('reports a backend HTTP failure separately from a network failure', async ({ page, request }) => {
    const projectId = await createEmptyProject(request);
    const dedupUrl = `**/api/v1/projects/${projectId}/duplicate-groups`;
    await page.route(dedupUrl, (route) => route.fulfill({ status: 503, body: '{"detail":"temporary backend error"}' }));
    await page.goto(`/projects/${projectId}/dashboard`);
    await expect(page.locator('#stage-card-deduplication')).toHaveAttribute('data-state', 'error');
    await expect.poll(() => page.evaluate(() =>
      (performance.getEntriesByName('slr:duplicate-groups-api').at(-1) as PerformanceMeasure | undefined)?.detail?.outcome
    )).toBe('http_503');

    await page.unroute(dedupUrl);
    await page.route(dedupUrl, (route) => route.abort('failed'));
    await page.reload();
    await expect(page.locator('#stage-card-deduplication')).toHaveAttribute('data-state', 'error');
    await expect.poll(() => page.evaluate(() =>
      (performance.getEntriesByName('slr:duplicate-groups-api').at(-1) as PerformanceMeasure | undefined)?.detail?.outcome
    )).toBe('network_or_parse_error');
  });

  test('keeps a slow first request in loading state until the configured timeout', async ({ page, request }) => {
    const projectId = await createEmptyProject(request);
    const dedupUrl = `**/api/v1/projects/${projectId}/duplicate-groups`;
    await page.route(dedupUrl, async (route) => {
      await new Promise((resolve) => setTimeout(resolve, 8_500));
      await route.continue().catch(() => undefined);
    });
    await page.goto(`/projects/${projectId}/dashboard`);
    const dedupCard = page.locator('#stage-card-deduplication');
    await expect(dedupCard).toHaveAttribute('data-loading', 'true');
    await expect(dedupCard).toHaveAttribute('data-state', 'error', { timeout: 12_000 });
    await expect.poll(() => page.evaluate(() =>
      (performance.getEntriesByName('slr:duplicate-groups-timeout').at(-1) as PerformanceMeasure | undefined)?.detail?.outcome
    )).toBe('timeout');
  });
});
