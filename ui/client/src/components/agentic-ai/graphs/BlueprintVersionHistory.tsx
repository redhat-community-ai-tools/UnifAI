/**
 * BlueprintVersionHistory
 *
 * Displays the version history of a single blueprint with "Preview" and
 * "Restore" actions on each row.
 *
 * Accessibility & testability
 * ---------------------------
 * Every interactive element carries a ``data-testid`` attribute so the
 * QE automation suite can reliably locate them without relying on fragile
 * CSS selectors or text content.
 *
 * GENIE-1336
 */

import React, { useCallback, useEffect, useState } from "react";
import {
  BlueprintApiError,
  BlueprintVersionDetail,
  BlueprintVersionSummary,
  PaginatedVersionsResponse,
  getBlueprintVersion,
  listBlueprintVersions,
  restoreBlueprintVersion,
} from "../api/blueprints";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type Status = "idle" | "loading" | "error";

interface Props {
  /** The blueprint whose version history is displayed. */
  blueprintId: string;
  /**
   * Called after a successful restore so the parent can refresh its state
   * (e.g. reload the live spec into the editor).
   */
  onRestoreSuccess?: (restoredFromVersion: number) => void;
  /** Number of items per page (default 10). */
  pageSize?: number;
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

/** Displays the spec_dict_snapshot of a single version in a read-only modal. */
function VersionPreviewModal({
  detail,
  onClose,
}: {
  detail: BlueprintVersionDetail;
  onClose: () => void;
}) {
  const formatted = JSON.stringify(detail.spec_dict_snapshot, null, 2);

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={`Preview of version ${detail.version}`}
      data-testid="version-preview-modal"
      style={overlayStyle}
      onClick={onClose}
    >
      <div
        style={modalStyle}
        onClick={(e) => e.stopPropagation()} // prevent closing on inner click
      >
        <header style={modalHeaderStyle}>
          <h2 style={{ margin: 0 }} data-testid="preview-modal-title">
            Version {detail.version} Preview
          </h2>
          <button
            aria-label="Close preview"
            data-testid="preview-modal-close"
            onClick={onClose}
            style={closeButtonStyle}
          >
            ✕
          </button>
        </header>

        <dl style={metaListStyle}>
          <dt>Created by</dt>
          <dd data-testid="preview-created-by">{detail.created_by || "—"}</dd>
          <dt>Created at</dt>
          <dd data-testid="preview-created-at">{formatDate(detail.created_at)}</dd>
          {detail.change_summary && (
            <>
              <dt>Change summary</dt>
              <dd data-testid="preview-change-summary">{detail.change_summary}</dd>
            </>
          )}
        </dl>

        <pre
          data-testid="preview-spec-snapshot"
          style={preStyle}
          aria-label="Spec dict snapshot"
        >
          {formatted}
        </pre>
      </div>
    </div>
  );
}

/** A single row in the version-history table. */
function VersionRow({
  item,
  onPreview,
  onRestore,
  isRestoring,
}: {
  item: BlueprintVersionSummary;
  onPreview: (version: number) => void;
  onRestore: (version: number) => void;
  isRestoring: boolean;
}) {
  return (
    <tr data-testid={`version-row-${item.version}`}>
      <td data-testid={`version-number-${item.version}`}>{item.version}</td>
      <td data-testid={`version-created-at-${item.version}`}>{formatDate(item.created_at)}</td>
      <td data-testid={`version-created-by-${item.version}`}>{item.created_by || "—"}</td>
      <td data-testid={`version-summary-${item.version}`}>{item.change_summary || "—"}</td>
      <td>
        <button
          data-testid={`preview-btn-${item.version}`}
          aria-label={`Preview version ${item.version}`}
          onClick={() => onPreview(item.version)}
          style={actionButtonStyle}
          disabled={isRestoring}
        >
          Preview
        </button>
        <button
          data-testid={`restore-btn-${item.version}`}
          aria-label={`Restore to version ${item.version}`}
          onClick={() => onRestore(item.version)}
          style={{ ...actionButtonStyle, ...restoreButtonExtraStyle }}
          disabled={isRestoring}
        >
          {isRestoring ? "Restoring…" : "Restore"}
        </button>
      </td>
    </tr>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export function BlueprintVersionHistory({
  blueprintId,
  onRestoreSuccess,
  pageSize = 10,
}: Props) {
  const [page, setPage] = useState(1);
  const [response, setResponse] = useState<PaginatedVersionsResponse | null>(null);
  const [status, setStatus] = useState<Status>("idle");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Preview state
  const [previewDetail, setPreviewDetail] = useState<BlueprintVersionDetail | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewError, setPreviewError] = useState<string | null>(null);

  // Restore state
  const [restoringVersion, setRestoringVersion] = useState<number | null>(null);
  const [restoreConfirm, setRestoreConfirm] = useState<number | null>(null);
  const [restoreError, setRestoreError] = useState<string | null>(null);

  // ------------------------------------------------------------------
  // Data fetching
  // ------------------------------------------------------------------

  const fetchVersions = useCallback(async () => {
    setStatus("loading");
    setErrorMessage(null);
    try {
      const data = await listBlueprintVersions(blueprintId, page, pageSize);
      setResponse(data);
      setStatus("idle");
    } catch (err) {
      const message =
        err instanceof BlueprintApiError ? err.message : "Failed to load version history.";
      setErrorMessage(message);
      setStatus("error");
    }
  }, [blueprintId, page, pageSize]);

  useEffect(() => {
    fetchVersions();
  }, [fetchVersions]);

  // ------------------------------------------------------------------
  // Preview handlers
  // ------------------------------------------------------------------

  const handlePreview = useCallback(
    async (version: number) => {
      setPreviewLoading(true);
      setPreviewError(null);
      setPreviewDetail(null);
      try {
        const detail = await getBlueprintVersion(blueprintId, version);
        setPreviewDetail(detail);
      } catch (err) {
        const message =
          err instanceof BlueprintApiError ? err.message : "Failed to load version preview.";
        setPreviewError(message);
      } finally {
        setPreviewLoading(false);
      }
    },
    [blueprintId],
  );

  const handleClosePreview = useCallback(() => {
    setPreviewDetail(null);
    setPreviewError(null);
  }, []);

  // ------------------------------------------------------------------
  // Restore handlers
  // ------------------------------------------------------------------

  const handleRestoreClick = useCallback((version: number) => {
    setRestoreConfirm(version);
    setRestoreError(null);
  }, []);

  const handleRestoreConfirm = useCallback(async () => {
    if (restoreConfirm === null) return;
    const targetVersion = restoreConfirm;
    setRestoreConfirm(null);
    setRestoringVersion(targetVersion);
    setRestoreError(null);

    try {
      await restoreBlueprintVersion(blueprintId, targetVersion);
      onRestoreSuccess?.(targetVersion);
      // Refresh the list after restore — a new snapshot was created
      await fetchVersions();
    } catch (err) {
      const message =
        err instanceof BlueprintApiError
          ? err.message
          : `Failed to restore version ${targetVersion}.`;
      setRestoreError(message);
    } finally {
      setRestoringVersion(null);
    }
  }, [blueprintId, restoreConfirm, onRestoreSuccess, fetchVersions]);

  const handleRestoreCancel = useCallback(() => {
    setRestoreConfirm(null);
  }, []);

  // ------------------------------------------------------------------
  // Pagination
  // ------------------------------------------------------------------

  const totalPages = response?.total_pages ?? 1;
  const hasPrev = page > 1;
  const hasNext = page < totalPages;

  // ------------------------------------------------------------------
  // Render
  // ------------------------------------------------------------------

  return (
    <section
      data-testid="blueprint-version-history"
      aria-label="Blueprint version history"
      style={sectionStyle}
    >
      <h2 style={{ marginTop: 0 }}>Version History</h2>

      {/* ---- Global errors ---- */}
      {status === "error" && errorMessage && (
        <div role="alert" data-testid="version-history-error" style={errorBoxStyle}>
          {errorMessage}
          <button
            data-testid="retry-btn"
            onClick={fetchVersions}
            style={{ marginLeft: 12 }}
          >
            Retry
          </button>
        </div>
      )}

      {restoreError && (
        <div role="alert" data-testid="restore-error" style={errorBoxStyle}>
          {restoreError}
        </div>
      )}

      {previewError && (
        <div role="alert" data-testid="preview-error" style={errorBoxStyle}>
          {previewError}
        </div>
      )}

      {/* ---- Restore confirmation dialog ---- */}
      {restoreConfirm !== null && (
        <div role="alertdialog" aria-modal="true" data-testid="restore-confirm-dialog" style={confirmBoxStyle}>
          <p>
            Restore blueprint to <strong>version {restoreConfirm}</strong>? The current state
            will be saved as a new snapshot first.
          </p>
          <button
            data-testid="restore-confirm-btn"
            onClick={handleRestoreConfirm}
            style={{ ...actionButtonStyle, ...restoreButtonExtraStyle, marginRight: 8 }}
          >
            Confirm Restore
          </button>
          <button
            data-testid="restore-cancel-btn"
            onClick={handleRestoreCancel}
            style={actionButtonStyle}
          >
            Cancel
          </button>
        </div>
      )}

      {/* ---- Loading indicator ---- */}
      {status === "loading" && (
        <p data-testid="version-history-loading" aria-live="polite">
          Loading version history…
        </p>
      )}

      {previewLoading && (
        <p data-testid="preview-loading" aria-live="polite">
          Loading preview…
        </p>
      )}

      {/* ---- Version table ---- */}
      {response && response.items.length === 0 && status !== "loading" && (
        <p data-testid="no-versions-message">No version history available yet.</p>
      )}

      {response && response.items.length > 0 && (
        <>
          <table
            data-testid="version-history-table"
            style={tableStyle}
            aria-label="Blueprint versions"
          >
            <thead>
              <tr>
                <th scope="col">Version</th>
                <th scope="col">Date</th>
                <th scope="col">Author</th>
                <th scope="col">Summary</th>
                <th scope="col">Actions</th>
              </tr>
            </thead>
            <tbody>
              {response.items.map((item) => (
                <VersionRow
                  key={item.version}
                  item={item}
                  onPreview={handlePreview}
                  onRestore={handleRestoreClick}
                  isRestoring={restoringVersion === item.version}
                />
              ))}
            </tbody>
          </table>

          {/* ---- Pagination controls ---- */}
          <nav aria-label="Version history pagination" style={paginationStyle}>
            <button
              data-testid="pagination-prev"
              aria-label="Previous page"
              onClick={() => setPage((p) => p - 1)}
              disabled={!hasPrev || status === "loading"}
              style={pageButtonStyle}
            >
              ‹ Prev
            </button>

            <span data-testid="pagination-info" style={{ padding: "0 12px" }}>
              Page {response.page} of {response.total_pages} ({response.total} version
              {response.total !== 1 ? "s" : ""})
            </span>

            <button
              data-testid="pagination-next"
              aria-label="Next page"
              onClick={() => setPage((p) => p + 1)}
              disabled={!hasNext || status === "loading"}
              style={pageButtonStyle}
            >
              Next ›
            </button>
          </nav>
        </>
      )}

      {/* ---- Preview modal ---- */}
      {previewDetail && (
        <VersionPreviewModal detail={previewDetail} onClose={handleClosePreview} />
      )}
    </section>
  );
}

// ---------------------------------------------------------------------------
// Utilities
// ---------------------------------------------------------------------------

function formatDate(iso: string): string {
  try {
    return new Intl.DateTimeFormat(undefined, {
      year: "numeric",
      month: "short",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    }).format(new Date(iso));
  } catch {
    return iso;
  }
}

// ---------------------------------------------------------------------------
// Inline styles (kept minimal; replace with CSS modules/Tailwind as needed)
// ---------------------------------------------------------------------------

const sectionStyle: React.CSSProperties = {
  fontFamily: "system-ui, sans-serif",
  padding: "16px",
  maxWidth: 900,
};

const tableStyle: React.CSSProperties = {
  width: "100%",
  borderCollapse: "collapse",
  marginTop: 12,
  fontSize: 14,
};

const errorBoxStyle: React.CSSProperties = {
  background: "#fff0f0",
  border: "1px solid #f5a5a5",
  borderRadius: 4,
  padding: "10px 14px",
  marginBottom: 12,
  color: "#c00",
};

const confirmBoxStyle: React.CSSProperties = {
  background: "#fff8e1",
  border: "1px solid #ffe082",
  borderRadius: 4,
  padding: "12px 16px",
  marginBottom: 12,
};

const actionButtonStyle: React.CSSProperties = {
  cursor: "pointer",
  padding: "4px 10px",
  border: "1px solid #ccc",
  borderRadius: 4,
  background: "#f5f5f5",
  marginRight: 6,
  fontSize: 13,
};

const restoreButtonExtraStyle: React.CSSProperties = {
  background: "#e3f2fd",
  borderColor: "#90caf9",
  color: "#0d47a1",
};

const paginationStyle: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  marginTop: 12,
};

const pageButtonStyle: React.CSSProperties = {
  cursor: "pointer",
  padding: "4px 12px",
  border: "1px solid #ccc",
  borderRadius: 4,
  background: "#f5f5f5",
};

const overlayStyle: React.CSSProperties = {
  position: "fixed",
  inset: 0,
  background: "rgba(0,0,0,0.45)",
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  zIndex: 1000,
};

const modalStyle: React.CSSProperties = {
  background: "#fff",
  borderRadius: 8,
  padding: 24,
  maxWidth: 720,
  width: "90%",
  maxHeight: "80vh",
  overflowY: "auto",
  boxShadow: "0 8px 32px rgba(0,0,0,0.2)",
};

const modalHeaderStyle: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  justifyContent: "space-between",
  marginBottom: 16,
};

const closeButtonStyle: React.CSSProperties = {
  background: "none",
  border: "none",
  fontSize: 18,
  cursor: "pointer",
  color: "#555",
};

const metaListStyle: React.CSSProperties = {
  display: "grid",
  gridTemplateColumns: "max-content 1fr",
  gap: "4px 16px",
  fontSize: 13,
  color: "#555",
  marginBottom: 12,
};

const preStyle: React.CSSProperties = {
  background: "#f8f8f8",
  border: "1px solid #e0e0e0",
  borderRadius: 4,
  padding: 12,
  overflowX: "auto",
  fontSize: 12,
  lineHeight: 1.6,
  maxHeight: 400,
  overflowY: "auto",
};
