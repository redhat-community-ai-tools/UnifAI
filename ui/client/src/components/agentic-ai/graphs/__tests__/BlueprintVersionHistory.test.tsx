/**
 * BlueprintVersionHistory.test.tsx — GENIE-1336
 *
 * Test runner: Vitest + @testing-library/react + @testing-library/user-event
 *
 * Install (once, from ui/ root):
 *   pnpm add -D vitest @vitest/coverage-v8 jsdom \
 *              @testing-library/react @testing-library/user-event \
 *              @testing-library/jest-dom msw
 *
 * Add to vite.config.ts (or a dedicated vitest.config.ts):
 *   import { defineConfig } from 'vitest/config';
 *   export default defineConfig({
 *     test: {
 *       environment: 'jsdom',
 *       globals: true,
 *       setupFiles: ['src/setupTests.ts'],
 *     },
 *     resolve: { alias: { '@': path.resolve(__dirname, 'src') } },
 *   });
 *
 * Add src/setupTests.ts:
 *   import '@testing-library/jest-dom';
 *
 * Run:
 *   pnpm vitest run src/components/agentic-ai/graphs/__tests__/BlueprintVersionHistory.test.tsx
 */

import React from 'react';
import {
  describe,
  it,
  expect,
  vi,
  beforeEach,
  afterEach,
  type Mock,
} from 'vitest';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

import BlueprintVersionHistory from '../BlueprintVersionHistory';
import type {
  VersionListResponse,
  VersionDetail,
} from '@/api/blueprints';

// ── Mock the API module ────────────────────────────────────────────────────────
vi.mock('@/api/blueprints', () => ({
  listBlueprintVersions: vi.fn(),
  loadBlueprintVersion: vi.fn(),
  restoreBlueprintVersion: vi.fn(),
}));

// Import the mock functions with correct types after mocking.
import {
  listBlueprintVersions,
  loadBlueprintVersion,
  restoreBlueprintVersion,
} from '@/api/blueprints';

const mockListVersions = listBlueprintVersions as Mock;
const mockLoadVersion = loadBlueprintVersion as Mock;
const mockRestoreVersion = restoreBlueprintVersion as Mock;

// ── Test data factories ────────────────────────────────────────────────────────

function makeVersionList(
  overrides: Partial<VersionListResponse> = {},
): VersionListResponse {
  return {
    items: [
      {
        version: 3,
        created_by: 'alice',
        created_at: '2025-06-10T09:00:00.000Z',
        change_summary: 'Third version',
      },
      {
        version: 2,
        created_by: 'bob',
        created_at: '2025-06-09T08:00:00.000Z',
        change_summary: 'Second version',
      },
      {
        version: 1,
        created_by: 'carol',
        created_at: '2025-06-08T07:00:00.000Z',
        change_summary: null,
      },
    ],
    total: 3,
    page: 1,
    page_size: 20,
    total_pages: 1,
    ...overrides,
  };
}

function makeVersionDetail(version: number = 2): VersionDetail {
  return {
    blueprint_id: 'bp-test',
    version,
    created_by: 'bob',
    created_at: '2025-06-09T08:00:00.000Z',
    change_summary: 'Second version',
    spec_dict_snapshot: { name: 'My Blueprint', nodes: [] },
  };
}

// ── Render helper ──────────────────────────────────────────────────────────────

function renderComponent(
  blueprintId = 'bp-test',
  onRestoreSuccess?: Mock,
) {
  const client = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,           // Don't retry in tests
        staleTime: 0,
      },
    },
  });
  return render(
    <QueryClientProvider client={client}>
      <BlueprintVersionHistory
        blueprintId={blueprintId}
        onRestoreSuccess={onRestoreSuccess}
      />
    </QueryClientProvider>,
  );
}

// ── Test suites ────────────────────────────────────────────────────────────────

describe('BlueprintVersionHistory', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  // ── Loading state ──────────────────────────────────────────────────────────

  describe('Loading state', () => {
    it('shows a loading indicator while fetching', async () => {
      // Never resolve so the loading state persists for the assertion
      mockListVersions.mockReturnValue(new Promise(() => {}));

      renderComponent();

      expect(
        screen.getByTestId('blueprint-version-history-loading'),
      ).toBeInTheDocument();
    });
  });

  // ── Error state ────────────────────────────────────────────────────────────

  describe('Error state', () => {
    it('shows an error message when the API call fails', async () => {
      mockListVersions.mockRejectedValue(new Error('Network error'));

      renderComponent();

      await waitFor(() => {
        expect(
          screen.getByTestId('blueprint-version-history-error'),
        ).toBeInTheDocument();
      });
    });
  });

  // ── Empty state ────────────────────────────────────────────────────────────

  describe('Empty state', () => {
    it('shows an empty state when there are no versions', async () => {
      mockListVersions.mockResolvedValue(
        makeVersionList({ items: [], total: 0, total_pages: 1 }),
      );

      renderComponent();

      await waitFor(() => {
        expect(
          screen.getByTestId('blueprint-version-history-empty'),
        ).toBeInTheDocument();
      });
    });
  });

  // ── Version table ──────────────────────────────────────────────────────────

  describe('Version table', () => {
    beforeEach(() => {
      mockListVersions.mockResolvedValue(makeVersionList());
    });

    it('renders the version history root element', async () => {
      renderComponent();
      await waitFor(() => {
        expect(
          screen.getByTestId('blueprint-version-history'),
        ).toBeInTheDocument();
      });
    });

    it('renders the table element', async () => {
      renderComponent();
      await waitFor(() => {
        expect(
          screen.getByTestId('blueprint-version-history-table'),
        ).toBeInTheDocument();
      });
    });

    it('renders a row for each version', async () => {
      renderComponent();
      await waitFor(() => {
        expect(
          screen.getByTestId('blueprint-version-history-row-3'),
        ).toBeInTheDocument();
        expect(
          screen.getByTestId('blueprint-version-history-row-2'),
        ).toBeInTheDocument();
        expect(
          screen.getByTestId('blueprint-version-history-row-1'),
        ).toBeInTheDocument();
      });
    });

    it('displays the total version count badge', async () => {
      renderComponent();
      await waitFor(() => {
        expect(
          screen.getByTestId('blueprint-version-history-total-badge'),
        ).toHaveTextContent('3');
      });
    });

    it('renders created_by for each row', async () => {
      renderComponent();
      await waitFor(() => {
        expect(
          screen.getByTestId('blueprint-version-history-row-3-created-by'),
        ).toHaveTextContent('alice');
        expect(
          screen.getByTestId('blueprint-version-history-row-2-created-by'),
        ).toHaveTextContent('bob');
      });
    });

    it('renders change_summary or "No summary" placeholder', async () => {
      renderComponent();
      await waitFor(() => {
        // Version 3 has a summary
        expect(
          screen.getByTestId('blueprint-version-history-row-3-summary'),
        ).toHaveTextContent('Third version');
        // Version 1 has null summary → shows placeholder text
        expect(
          screen.getByTestId('blueprint-version-history-row-1-summary'),
        ).toHaveTextContent('No summary');
      });
    });

    it('renders preview button for each row', async () => {
      renderComponent();
      await waitFor(() => {
        expect(
          screen.getByTestId('blueprint-version-history-preview-btn-2'),
        ).toBeInTheDocument();
      });
    });

    it('renders restore button for each row', async () => {
      renderComponent();
      await waitFor(() => {
        expect(
          screen.getByTestId('blueprint-version-history-restore-btn-2'),
        ).toBeInTheDocument();
      });
    });
  });

  // ── Preview drawer ─────────────────────────────────────────────────────────

  describe('Preview drawer', () => {
    beforeEach(() => {
      mockListVersions.mockResolvedValue(makeVersionList());
      mockLoadVersion.mockResolvedValue(makeVersionDetail(2));
    });

    it('opens the preview drawer when a preview button is clicked', async () => {
      const user = userEvent.setup();
      renderComponent();

      // Wait for table to load
      const previewBtn = await screen.findByTestId(
        'blueprint-version-history-preview-btn-2',
      );
      await user.click(previewBtn);

      await waitFor(() => {
        expect(
          screen.getByTestId('blueprint-version-preview-drawer'),
        ).toBeInTheDocument();
      });
    });

    it('displays the spec snapshot JSON in the preview content', async () => {
      const user = userEvent.setup();
      renderComponent();

      const previewBtn = await screen.findByTestId(
        'blueprint-version-history-preview-btn-2',
      );
      await user.click(previewBtn);

      await waitFor(() => {
        const content = screen.getByTestId(
          'blueprint-version-preview-content',
        );
        expect(content.textContent).toContain('"My Blueprint"');
      });
    });

    it('calls loadBlueprintVersion with the correct arguments', async () => {
      const user = userEvent.setup();
      renderComponent();

      const previewBtn = await screen.findByTestId(
        'blueprint-version-history-preview-btn-2',
      );
      await user.click(previewBtn);

      await waitFor(() => {
        expect(mockLoadVersion).toHaveBeenCalledWith('bp-test', 2);
      });
    });
  });

  // ── Restore dialog ─────────────────────────────────────────────────────────

  describe('Restore dialog', () => {
    beforeEach(() => {
      mockListVersions.mockResolvedValue(makeVersionList());
    });

    it('opens the restore dialog when a restore button is clicked', async () => {
      const user = userEvent.setup();
      renderComponent();

      const restoreBtn = await screen.findByTestId(
        'blueprint-version-history-restore-btn-2',
      );
      await user.click(restoreBtn);

      await waitFor(() => {
        expect(
          screen.getByTestId('blueprint-version-restore-dialog'),
        ).toBeInTheDocument();
      });
    });

    it('closes the dialog when Cancel is clicked', async () => {
      const user = userEvent.setup();
      renderComponent();

      const restoreBtn = await screen.findByTestId(
        'blueprint-version-history-restore-btn-2',
      );
      await user.click(restoreBtn);

      // Dialog should now be visible
      const cancelBtn = await screen.findByTestId(
        'blueprint-version-restore-cancel-btn',
      );
      await user.click(cancelBtn);

      // Dialog should be closed — element is gone or not visible
      await waitFor(() => {
        expect(
          screen.queryByTestId('blueprint-version-restore-dialog'),
        ).not.toBeVisible();
      });
    });

    it('calls restoreBlueprintVersion with the correct args on confirm', async () => {
      mockRestoreVersion.mockResolvedValue({
        status: 'restored',
        blueprint_id: 'bp-test',
        restored_to_version: 4,
      });
      // Re-fetch after restore
      mockListVersions.mockResolvedValue(makeVersionList());

      const user = userEvent.setup();
      renderComponent();

      const restoreBtn = await screen.findByTestId(
        'blueprint-version-history-restore-btn-2',
      );
      await user.click(restoreBtn);

      const confirmBtn = await screen.findByTestId(
        'blueprint-version-restore-confirm-btn',
      );
      await user.click(confirmBtn);

      await waitFor(() => {
        expect(mockRestoreVersion).toHaveBeenCalledWith('bp-test', 2);
      });
    });

    it('shows a success status message after a successful restore', async () => {
      mockRestoreVersion.mockResolvedValue({
        status: 'restored',
        blueprint_id: 'bp-test',
        restored_to_version: 4,
      });
      mockListVersions.mockResolvedValue(makeVersionList());

      const user = userEvent.setup();
      renderComponent();

      const restoreBtn = await screen.findByTestId(
        'blueprint-version-history-restore-btn-2',
      );
      await user.click(restoreBtn);

      const confirmBtn = await screen.findByTestId(
        'blueprint-version-restore-confirm-btn',
      );
      await user.click(confirmBtn);

      await waitFor(() => {
        expect(
          screen.getByTestId('blueprint-version-history-status-success'),
        ).toBeInTheDocument();
      });
    });

    it('fires onRestoreSuccess callback with the new version number', async () => {
      mockRestoreVersion.mockResolvedValue({
        status: 'restored',
        blueprint_id: 'bp-test',
        restored_to_version: 4,
      });
      mockListVersions.mockResolvedValue(makeVersionList());

      const onSuccess = vi.fn();
      const user = userEvent.setup();
      renderComponent('bp-test', onSuccess);

      const restoreBtn = await screen.findByTestId(
        'blueprint-version-history-restore-btn-2',
      );
      await user.click(restoreBtn);

      const confirmBtn = await screen.findByTestId(
        'blueprint-version-restore-confirm-btn',
      );
      await user.click(confirmBtn);

      await waitFor(() => {
        expect(onSuccess).toHaveBeenCalledWith(4);
      });
    });

    it('shows an error status message when restore fails', async () => {
      mockRestoreVersion.mockRejectedValue(new Error('Internal Server Error'));
      mockListVersions.mockResolvedValue(makeVersionList());

      const user = userEvent.setup();
      renderComponent();

      const restoreBtn = await screen.findByTestId(
        'blueprint-version-history-restore-btn-3',
      );
      await user.click(restoreBtn);

      const confirmBtn = await screen.findByTestId(
        'blueprint-version-restore-confirm-btn',
      );
      await user.click(confirmBtn);

      await waitFor(() => {
        expect(
          screen.getByTestId('blueprint-version-history-status-error'),
        ).toBeInTheDocument();
      });
    });

    it('shows a user-friendly 409 conflict message when restore conflicts', async () => {
      mockRestoreVersion.mockRejectedValue(
        new Error('Request failed with status code 409'),
      );
      mockListVersions.mockResolvedValue(makeVersionList());

      const user = userEvent.setup();
      renderComponent();

      const restoreBtn = await screen.findByTestId(
        'blueprint-version-history-restore-btn-3',
      );
      await user.click(restoreBtn);

      const confirmBtn = await screen.findByTestId(
        'blueprint-version-restore-confirm-btn',
      );
      await user.click(confirmBtn);

      await waitFor(() => {
        const errorEl = screen.getByTestId(
          'blueprint-version-history-status-error',
        );
        expect(errorEl).toHaveTextContent(/modified by another user/i);
      });
    });
  });

  // ── Pagination ─────────────────────────────────────────────────────────────

  describe('Pagination', () => {
    it('does not render pagination controls when there is only one page', async () => {
      mockListVersions.mockResolvedValue(makeVersionList({ total_pages: 1 }));

      renderComponent();

      await waitFor(() => {
        expect(
          screen.queryByTestId('blueprint-version-history-pagination'),
        ).not.toBeInTheDocument();
      });
    });

    it('renders pagination controls when there are multiple pages', async () => {
      mockListVersions.mockResolvedValue(
        makeVersionList({ total: 50, total_pages: 3 }),
      );

      renderComponent();

      await waitFor(() => {
        expect(
          screen.getByTestId('blueprint-version-history-pagination'),
        ).toBeInTheDocument();
      });
    });

    it('disables the Prev button on the first page', async () => {
      mockListVersions.mockResolvedValue(
        makeVersionList({ total: 50, total_pages: 3, page: 1 }),
      );

      renderComponent();

      await waitFor(() => {
        expect(
          screen.getByTestId('blueprint-version-history-pagination-prev'),
        ).toBeDisabled();
      });
    });

    it('enables the Next button when there are more pages', async () => {
      mockListVersions.mockResolvedValue(
        makeVersionList({ total: 50, total_pages: 3, page: 1 }),
      );

      renderComponent();

      await waitFor(() => {
        expect(
          screen.getByTestId('blueprint-version-history-pagination-next'),
        ).not.toBeDisabled();
      });
    });

    it('advances to page 2 when Next is clicked', async () => {
      const user = userEvent.setup();
      // Page 1 response
      mockListVersions.mockResolvedValueOnce(
        makeVersionList({ total: 50, total_pages: 3, page: 1 }),
      );
      // Page 2 response
      mockListVersions.mockResolvedValueOnce(
        makeVersionList({ total: 50, total_pages: 3, page: 2 }),
      );

      renderComponent();

      const nextBtn = await screen.findByTestId(
        'blueprint-version-history-pagination-next',
      );
      await user.click(nextBtn);

      await waitFor(() => {
        // listBlueprintVersions should have been called with page=2
        expect(mockListVersions).toHaveBeenCalledWith('bp-test', 2, 20);
      });
    });
  });

  // ── API integration ────────────────────────────────────────────────────────

  describe('API integration', () => {
    it('calls listBlueprintVersions with the blueprintId prop', async () => {
      mockListVersions.mockResolvedValue(makeVersionList());

      renderComponent('my-specific-bp');

      await waitFor(() => {
        expect(mockListVersions).toHaveBeenCalledWith('my-specific-bp', 1, 20);
      });
    });
  });
});
