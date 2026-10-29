import { test, expect, type Route } from '@playwright/test';

const project = {
  project_id: 'lean_energy',
  title: 'Lean Energy Project',
  description: '',
  protocol_version: '1.0',
  status: 'active',
  created_at: '',
  updated_at: '',
};

const reviewDetail = {
  project_id: 'lean_energy',
  import_id: 'import-gs01',
  source_type: 'file',
  filename: 'GS01.ris',
  format: 'RIS',
  provider: null,
  query: null,
  records_count: 378,
  status: 'warning',
  effective_status: 'warning',
  review_status: 'pending',
  warnings: ['Skipped 2 exact DOI duplicate record(s) already in the project.'],
  created_at: '2026-10-26T17:39:34Z',
  source_record_count: 380,
  canonical_publication_count: 378,
  exact_doi_match_count: 2,
  repeated_source_count: 3,
  title_candidate_count: 4,
  similar_title_candidate_count: 1,
  skipped_canonical_count: 5,
  invalid_doi_count: 2,
  validation_error_count: 0,
  audit_available: true,
  can_accept: true,
  can_reject: false,
  warning_categories: [{ code: 'exact_doi', label: 'Dokładne duplikaty DOI', count: 2 }],
  blockers: [],
  decision: null,
};

const acceptedDecision = {
  project_id: 'lean_energy',
  import_id: 'import-gs01',
  decision: {
    decision_id: 'decision-1',
    decision: 'accepted',
    reviewer_id: 'reviewer-a',
    rationale: null,
    decided_at: '2026-10-27T11:00:00Z',
    deleted_publication_count: 0,
    retained_source_record_count: 380,
    prisma_treatment: 'not_applicable',
  },
  effective_status: 'success',
  review_status: 'accepted',
};

function summary(accepted: boolean) {
  return {
    project_id: 'lean_energy',
    working_collection: { total_records: 446 },
    source_summaries: [
      {
        source: 'ris',
        source_kind: 'file',
        successful_imports_count: accepted ? 1 : 0,
        warning_imports_count: accepted ? 0 : 1,
        failed_imports_count: 0,
        records_added_count: 378,
        last_import_at: '2026-10-26T17:39:34Z',
        last_import_status: accepted ? 'success' : 'warning',
      },
    ],
    import_history: [
      {
        import_id: 'import-gs01',
        source_type: 'file',
        filename: 'GS01.ris',
        format: 'RIS',
        provider: null,
        query: null,
        records_count: 378,
        status: 'warning',
        warnings: ['Skipped 2 exact DOI duplicate record(s) already in the project.'],
        created_at: '2026-10-26T17:39:34Z',
        effective_status: accepted ? 'success' : 'warning',
        review_status: accepted ? 'accepted' : 'pending',
        can_accept: !accepted,
        can_reject: false,
      },
    ],
  };
}

test.describe('Import review decision (browser)', () => {
  test('accept updates row to Zaimportowano and closes modal', async ({ page }) => {
    let accepted = false;
    let summaryCalls = 0;

    await page.route('**/api/v1/projects?include_archived=*', (route: Route) =>
      route.fulfill({ json: { items: [project], total: 1 } }),
    );
    await page.route('**/api/v1/projects/lean_energy/sources-summary', (route: Route) => {
      summaryCalls += 1;
      route.fulfill({ json: summary(accepted) });
    });
    await page.route('**/api/v1/projects/lean_energy/imports/import-gs01/review', (route: Route) => {
      if (route.request().method() === 'GET') {
        route.fulfill({ json: reviewDetail });
      } else {
        accepted = true;
        route.fulfill({ json: acceptedDecision });
      }
    });

    await page.goto('/projects/lean_energy/sources');
    await expect(page.getByText('Ostrzeżenie')).toBeVisible();
    await page.getByText('Ostrzeżenie').click();
    await expect(page.getByRole('button', { name: 'Akceptuję' })).toBeVisible();
    await page.getByRole('button', { name: 'Akceptuję' }).click();

    await expect(page.getByRole('button', { name: 'Akceptuję' })).not.toBeVisible();
    await expect(page.getByText('Zaimportowano')).toBeVisible();
    await expect(page.getByText('Ostrzeżenie')).not.toBeVisible();
  });

  test('accept shows spinner only on accept and closes after settle', async ({ page }) => {
    let accepted = false;

    await page.route('**/api/v1/projects?include_archived=*', (route: Route) =>
      route.fulfill({ json: { items: [project], total: 1 } }),
    );
    await page.route('**/api/v1/projects/lean_energy/sources-summary', (route: Route) =>
      route.fulfill({ json: summary(accepted) }),
    );
    await page.route('**/api/v1/projects/lean_energy/imports/import-gs01/review', async (route: Route) => {
      if (route.request().method() === 'GET') {
        route.fulfill({ json: reviewDetail });
      } else {
        await new Promise((r) => setTimeout(r, 600));
        accepted = true;
        route.fulfill({ json: acceptedDecision });
      }
    });

    await page.goto('/projects/lean_energy/sources');
    await page.getByText('Ostrzeżenie').click();
    await page.getByRole('button', { name: 'Akceptuję' }).click();

    await expect(page.getByRole('button', { name: 'Odrzucam' })).toBeDisabled();
    await expect(page.getByRole('button', { name: 'Zamknij' })).toBeDisabled();
    // spinner (lucide Loader2) rendered inside the accept button while pending
    await expect(page.locator('button:has-text("Akceptuję") svg.lucide-loader-circle')).toBeVisible();

    await expect(page.getByText('Zaimportowano')).toBeVisible({ timeout: 5000 });
    await expect(page.getByRole('button', { name: 'Akceptuję' })).not.toBeVisible();
  });

  test('refresh failure keeps modal closed and shows retry', async ({ page }) => {
    let accepted = false;
    let summaryCalls = 0;

    await page.route('**/api/v1/projects?include_archived=*', (route: Route) =>
      route.fulfill({ json: { items: [project], total: 1 } }),
    );
    await page.route('**/api/v1/projects/lean_energy/sources-summary', (route: Route) => {
      summaryCalls += 1;
      if (summaryCalls === 1) {
        route.fulfill({ json: summary(false) });
      } else if (accepted && summaryCalls === 2) {
        route.fulfill({ status: 500, json: { detail: 'Nie udało się odświeżyć podsumowania źródeł' } });
      } else {
        route.fulfill({ json: summary(true) });
      }
    });
    await page.route('**/api/v1/projects/lean_energy/imports/import-gs01/review', (route: Route) => {
      if (route.request().method() === 'GET') {
        route.fulfill({ json: reviewDetail });
      } else {
        accepted = true;
        route.fulfill({ json: acceptedDecision });
      }
    });

    await page.goto('/projects/lean_energy/sources');
    await page.getByText('Ostrzeżenie').click();
    await page.getByRole('button', { name: 'Akceptuję' }).click();

    await expect(page.getByRole('button', { name: 'Akceptuję' })).not.toBeVisible();
    await expect(page.getByRole('alert')).toContainText('Nie udało się odświeżyć podsumowania źródeł');
    await expect(page.getByRole('button', { name: 'Ponów' })).toBeVisible();
  });
});