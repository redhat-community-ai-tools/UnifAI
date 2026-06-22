/**
 * BlueprintVersionHistory — unit tests
 *
 * Tests are aligned to the actual component data-testid attributes,
 * public API shape (named export, correct type names), and behavioral
 * contract (useState/useEffect, NOT React Query).
 *
 * GENIE-1336
 */

import React from "react";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach, type Mock } from "vitest";

// Mock the API module — keep all types intact, replace functions with mocks.
vi.mock("@/api/blueprints", async (importOriginal) => {
  const mod = await importOriginal<typeof import("@/api/blueprints")>();
  return {
    ...mod,
    listBlueprintVersions: vi.fn(),
    getBlueprintVersion: vi.fn(),
    restoreBlueprintVersion: vi.fn(),
  };
});

import { BlueprintVersionHistory } from "../BlueprintVersionHistory";
import {
  listBlueprintVersions,
  getBlueprintVersion,
  restoreBlueprintVersion,
  BlueprintApiError,
} from "@/api/blueprints";
import type {
  PaginatedVersionsResponse,
  BlueprintVersionDetail,
  BlueprintVersionSummary,
} from "@/api/blueprints";

// ---------------------------------------------------------------------------
// Typed mock references
// ---------------------------------------------------------------------------

const mockListVersions = listBlueprintVersions as Mock;
const mockGetVersion = getBlueprintVersion as Mock;
const mockRestore = restoreBlueprintVersion as Mock;

// ---------------------------------------------------------------------------
// Factory helpers
// ---------------------------------------------------------------------------

function makeVersionSummary(overrides: Partial<BlueprintVersionSummary> = {}): BlueprintVersionSummary {
  return {
    version: 1,
    blueprint_id: "bp-test",
    created_by: "alice",
    created_at: "2025-06-01T12:00:00Z",
    change_summary: "Initial version",
    ...overrides,
  };
}

function makePageResponse(
  items: BlueprintVersionSummary[],
  overrides: Partial<PaginatedVersionsResponse> = {},
): PaginatedVersionsResponse {
  return {
    items,
    total: items.length,
    page: 1,
    page_size: 10,
    total_pages: 1,
    ...overrides,
  };
}

function makeVersionDetail(
  overrides: Partial<BlueprintVersionDetail> = {},
): BlueprintVersionDetail {
  return {
    version: 1,
    blueprint_id: "bp-test",
    created_by: "alice",
    created_at: "2025-06-01T12:00:00Z",
    change_summary: "Initial version",
    spec_dict_snapshot: { name: "test-spec", nodes: [] },
    ...overrides,
  };
}

// ---------------------------------------------------------------------------
// Render helper
// ---------------------------------------------------------------------------

function renderComponent(
  props: Partial<React.ComponentProps<typeof BlueprintVersionHistory>> = {},
) {
  const defaultProps = {
    blueprintId: "bp-test",
    ...props,
  };
  return render(<BlueprintVersionHistory {...defaultProps} />);
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("BlueprintVersionHistory", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  // ── Loading state ───────────────────────────────────────────────────

  it("shows loading indicator while fetching versions", () => {
    mockListVersions.mockReturnValue(new Promise(() => {})); // never resolves
    renderComponent();
    expect(screen.getByTestId("version-history-loading")).toBeInTheDocument();
  });

  // ── Error state ─────────────────────────────────────────────────────

  it("shows error message when fetching fails", async () => {
    mockListVersions.mockRejectedValueOnce(new Error("Network error"));
    renderComponent();

    await waitFor(() => {
      expect(screen.getByTestId("version-history-error")).toBeInTheDocument();
    });
    expect(screen.getByTestId("version-history-error")).toHaveTextContent(
      "Failed to load version history.",
    );
  });

  it("shows retry button on error and retries on click", async () => {
    const user = userEvent.setup();
    mockListVersions
      .mockRejectedValueOnce(new Error("fail"))
      .mockResolvedValueOnce(makePageResponse([makeVersionSummary()]));

    renderComponent();

    await waitFor(() => {
      expect(screen.getByTestId("retry-btn")).toBeInTheDocument();
    });

    await user.click(screen.getByTestId("retry-btn"));

    await waitFor(() => {
      expect(screen.getByTestId("version-history-table")).toBeInTheDocument();
    });
    expect(mockListVersions).toHaveBeenCalledTimes(2);
  });

  // ── Empty state ─────────────────────────────────────────────────────

  it("shows empty message when no versions exist", async () => {
    mockListVersions.mockResolvedValueOnce(makePageResponse([]));
    renderComponent();

    await waitFor(() => {
      expect(screen.getByTestId("no-versions-message")).toBeInTheDocument();
    });
    expect(screen.getByTestId("no-versions-message")).toHaveTextContent(
      "No version history available yet.",
    );
  });

  // ── Table rendering ─────────────────────────────────────────────────

  it("renders version table with correct rows", async () => {
    const items = [
      makeVersionSummary({ version: 2, created_by: "bob", change_summary: "Updated nodes" }),
      makeVersionSummary({ version: 1, created_by: "alice", change_summary: "Initial version" }),
    ];
    mockListVersions.mockResolvedValueOnce(makePageResponse(items));
    renderComponent();

    await waitFor(() => {
      expect(screen.getByTestId("version-history-table")).toBeInTheDocument();
    });

    // Root section
    expect(screen.getByTestId("blueprint-version-history")).toBeInTheDocument();

    // Row for each version
    expect(screen.getByTestId("version-row-2")).toBeInTheDocument();
    expect(screen.getByTestId("version-row-1")).toBeInTheDocument();

    // Author cells
    expect(screen.getByTestId("version-created-by-2")).toHaveTextContent("bob");
    expect(screen.getByTestId("version-created-by-1")).toHaveTextContent("alice");

    // Summary cells
    expect(screen.getByTestId("version-summary-2")).toHaveTextContent("Updated nodes");
    expect(screen.getByTestId("version-summary-1")).toHaveTextContent("Initial version");
  });

  it("renders em dash for null change_summary", async () => {
    const items = [makeVersionSummary({ version: 1, change_summary: null })];
    mockListVersions.mockResolvedValueOnce(makePageResponse(items));
    renderComponent();

    await waitFor(() => {
      expect(screen.getByTestId("version-summary-1")).toBeInTheDocument();
    });
    expect(screen.getByTestId("version-summary-1")).toHaveTextContent("—");
  });

  // ── Preview ─────────────────────────────────────────────────────────

  it("opens preview modal when Preview button is clicked", async () => {
    const user = userEvent.setup();
    const items = [makeVersionSummary({ version: 2 })];
    mockListVersions.mockResolvedValueOnce(makePageResponse(items));
    mockGetVersion.mockResolvedValueOnce(
      makeVersionDetail({ version: 2, spec_dict_snapshot: { graph: "data" } }),
    );

    renderComponent();

    await waitFor(() => {
      expect(screen.getByTestId("preview-btn-2")).toBeInTheDocument();
    });

    await user.click(screen.getByTestId("preview-btn-2"));

    await waitFor(() => {
      expect(screen.getByTestId("version-preview-modal")).toBeInTheDocument();
    });

    expect(screen.getByTestId("preview-spec-snapshot")).toHaveTextContent(
      JSON.stringify({ graph: "data" }, null, 2),
    );
    expect(mockGetVersion).toHaveBeenCalledWith("bp-test", 2);
  });

  it("shows preview error when getBlueprintVersion fails", async () => {
    const user = userEvent.setup();
    const items = [makeVersionSummary({ version: 3 })];
    mockListVersions.mockResolvedValueOnce(makePageResponse(items));
    mockGetVersion.mockRejectedValueOnce(new Error("Preview failed"));

    renderComponent();

    await waitFor(() => {
      expect(screen.getByTestId("preview-btn-3")).toBeInTheDocument();
    });

    await user.click(screen.getByTestId("preview-btn-3"));

    await waitFor(() => {
      expect(screen.getByTestId("preview-error")).toBeInTheDocument();
    });
    expect(screen.getByTestId("preview-error")).toHaveTextContent(
      "Failed to load version preview.",
    );
  });

  // ── Restore flow ────────────────────────────────────────────────────

  it("shows confirmation dialog when Restore button is clicked", async () => {
    const user = userEvent.setup();
    const items = [makeVersionSummary({ version: 2 })];
    mockListVersions.mockResolvedValueOnce(makePageResponse(items));
    renderComponent();

    await waitFor(() => {
      expect(screen.getByTestId("restore-btn-2")).toBeInTheDocument();
    });

    await user.click(screen.getByTestId("restore-btn-2"));

    expect(screen.getByTestId("restore-confirm-dialog")).toBeInTheDocument();
    expect(screen.getByTestId("restore-confirm-btn")).toBeInTheDocument();
    expect(screen.getByTestId("restore-cancel-btn")).toBeInTheDocument();
  });

  it("dismisses confirmation dialog on cancel", async () => {
    const user = userEvent.setup();
    const items = [makeVersionSummary({ version: 2 })];
    mockListVersions.mockResolvedValueOnce(makePageResponse(items));
    renderComponent();

    await waitFor(() => {
      expect(screen.getByTestId("restore-btn-2")).toBeInTheDocument();
    });

    await user.click(screen.getByTestId("restore-btn-2"));
    expect(screen.getByTestId("restore-confirm-dialog")).toBeInTheDocument();

    await user.click(screen.getByTestId("restore-cancel-btn"));
    expect(screen.queryByTestId("restore-confirm-dialog")).not.toBeInTheDocument();
  });

  it("calls restoreBlueprintVersion and refreshes list on confirm", async () => {
    const user = userEvent.setup();
    const items = [
      makeVersionSummary({ version: 2, change_summary: "Pre-restore" }),
      makeVersionSummary({ version: 1 }),
    ];
    mockListVersions.mockResolvedValue(makePageResponse(items));
    mockRestore.mockResolvedValueOnce({ success: true });

    renderComponent();

    await waitFor(() => {
      expect(screen.getByTestId("restore-btn-2")).toBeInTheDocument();
    });

    // Click restore → confirm
    await user.click(screen.getByTestId("restore-btn-2"));
    await user.click(screen.getByTestId("restore-confirm-btn"));

    await waitFor(() => {
      expect(mockRestore).toHaveBeenCalledWith("bp-test", 2);
    });

    // After successful restore, fetchVersions is called again.
    // Initial call + refresh = at least 2 calls.
    await waitFor(() => {
      expect(mockListVersions.mock.calls.length).toBeGreaterThanOrEqual(2);
    });
  });

  it("calls onRestoreSuccess with the target version number", async () => {
    const user = userEvent.setup();
    const onSuccess = vi.fn();
    const items = [makeVersionSummary({ version: 2 })];
    mockListVersions.mockResolvedValue(makePageResponse(items));
    mockRestore.mockResolvedValueOnce({ success: true });

    renderComponent({ onRestoreSuccess: onSuccess });

    await waitFor(() => {
      expect(screen.getByTestId("restore-btn-2")).toBeInTheDocument();
    });

    await user.click(screen.getByTestId("restore-btn-2"));
    await user.click(screen.getByTestId("restore-confirm-btn"));

    await waitFor(() => {
      // Component calls onRestoreSuccess(targetVersion) where targetVersion = 2
      expect(onSuccess).toHaveBeenCalledWith(2);
    });
  });

  it("shows restore error when restoreBlueprintVersion fails", async () => {
    const user = userEvent.setup();
    const items = [makeVersionSummary({ version: 2 })];
    mockListVersions.mockResolvedValueOnce(makePageResponse(items));
    mockRestore.mockRejectedValueOnce(new Error("Restore failed"));

    renderComponent();

    await waitFor(() => {
      expect(screen.getByTestId("restore-btn-2")).toBeInTheDocument();
    });

    await user.click(screen.getByTestId("restore-btn-2"));
    await user.click(screen.getByTestId("restore-confirm-btn"));

    await waitFor(() => {
      expect(screen.getByTestId("restore-error")).toBeInTheDocument();
    });
    // Generic Error (not BlueprintApiError) → fallback message
    expect(screen.getByTestId("restore-error")).toHaveTextContent(
      "Failed to restore version 2.",
    );
  });

  it("shows API error message for BlueprintApiError on restore", async () => {
    const user = userEvent.setup();
    const items = [makeVersionSummary({ version: 2 })];
    mockListVersions.mockResolvedValueOnce(makePageResponse(items));
    mockRestore.mockRejectedValueOnce(
      new BlueprintApiError(409, "Blueprint was modified by another user", "/blueprint.version.restore"),
    );

    renderComponent();

    await waitFor(() => {
      expect(screen.getByTestId("restore-btn-2")).toBeInTheDocument();
    });

    await user.click(screen.getByTestId("restore-btn-2"));
    await user.click(screen.getByTestId("restore-confirm-btn"));

    await waitFor(() => {
      expect(screen.getByTestId("restore-error")).toBeInTheDocument();
    });
    expect(screen.getByTestId("restore-error")).toHaveTextContent(
      "Blueprint was modified by another user",
    );
  });

  // ── Pagination ──────────────────────────────────────────────────────

  it("disables prev button on first page", async () => {
    const items = [makeVersionSummary({ version: 1 })];
    mockListVersions.mockResolvedValueOnce(
      makePageResponse(items, { page: 1, total_pages: 3, total: 25 }),
    );
    renderComponent();

    await waitFor(() => {
      expect(screen.getByTestId("pagination-prev")).toBeInTheDocument();
    });

    expect(screen.getByTestId("pagination-prev")).toBeDisabled();
    expect(screen.getByTestId("pagination-next")).toBeEnabled();
  });

  it("advances to page 2 when next is clicked", async () => {
    const user = userEvent.setup();
    const items = [makeVersionSummary({ version: 1 })];
    mockListVersions
      .mockResolvedValueOnce(makePageResponse(items, { page: 1, total_pages: 3, total: 25 }))
      .mockResolvedValueOnce(
        makePageResponse(
          [makeVersionSummary({ version: 11 })],
          { page: 2, total_pages: 3, total: 25 },
        ),
      );

    renderComponent();

    await waitFor(() => {
      expect(screen.getByTestId("pagination-next")).toBeInTheDocument();
    });

    await user.click(screen.getByTestId("pagination-next"));

    await waitFor(() => {
      expect(screen.getByTestId("pagination-info")).toHaveTextContent("Page 2 of 3");
    });

    // Second call should be page 2 with default pageSize 10
    expect(mockListVersions).toHaveBeenCalledWith("bp-test", 2, 10);
  });

  // ── API integration ─────────────────────────────────────────────────

  it("calls listBlueprintVersions with correct args on mount", async () => {
    mockListVersions.mockResolvedValueOnce(makePageResponse([]));
    renderComponent();

    await waitFor(() => {
      expect(mockListVersions).toHaveBeenCalledWith("bp-test", 1, 10);
    });
  });

  it("passes custom pageSize to API", async () => {
    mockListVersions.mockResolvedValueOnce(makePageResponse([]));
    renderComponent({ pageSize: 5 });

    await waitFor(() => {
      expect(mockListVersions).toHaveBeenCalledWith("bp-test", 1, 5);
    });
  });
});
