/**
 * BlueprintVersionHistory — GENIE-1336
 *
 * Renders the full version history for a single blueprint:
 *  - Paginated table of version summaries (newest first)
 *  - Drawer for previewing a specific version's spec snapshot
 *  - AlertDialog for confirming a rollback / restore
 *
 * All interactive elements have `data-testid` attributes so QE automation
 * can target them without relying on CSS class names or text content.
 */

import React, { useState, useCallback } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { History, Eye, RotateCcw, ChevronLeft, ChevronRight, AlertCircle, Loader2 } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  Drawer,
  DrawerClose,
  DrawerContent,
  DrawerDescription,
  DrawerFooter,
  DrawerHeader,
  DrawerTitle,
} from '@/components/ui/drawer';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { ScrollArea } from '@/components/ui/scroll-area';

import {
  listBlueprintVersions,
  loadBlueprintVersion,
  restoreBlueprintVersion,
  VersionSummary,
  VersionDetail,
} from '@/api/blueprints';

// ── Constants ──────────────────────────────────────────────────────────────────

const DEFAULT_PAGE_SIZE = 20;

// ── Helper functions ───────────────────────────────────────────────────────────

/**
 * Format an ISO-8601 timestamp as a locale-aware short date+time string.
 * Falls back gracefully if the input is invalid.
 */
function formatTimestamp(iso: string): string {
  try {
    return new Intl.DateTimeFormat(undefined, {
      year: 'numeric',
      month: 'short',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    }).format(new Date(iso));
  } catch {
    return iso;
  }
}

// ── Sub-components ─────────────────────────────────────────────────────────────

interface EmptyStateProps {
  message: string;
}

const EmptyState: React.FC<EmptyStateProps> = ({ message }) => (
  <div
    data-testid="blueprint-version-history-empty"
    className="flex flex-col items-center justify-center py-16 text-muted-foreground gap-2"
  >
    <History className="w-10 h-10 opacity-30" />
    <p className="text-sm">{message}</p>
  </div>
);

interface ErrorStateProps {
  message: string;
}

const ErrorState: React.FC<ErrorStateProps> = ({ message }) => (
  <div
    data-testid="blueprint-version-history-error"
    className="flex items-center gap-2 p-4 rounded-md border border-destructive/50 text-destructive text-sm"
  >
    <AlertCircle className="w-4 h-4 shrink-0" />
    <span>{message}</span>
  </div>
);

// ── Preview Drawer ─────────────────────────────────────────────────────────────

interface PreviewDrawerProps {
  blueprintId: string;
  versionNumber: number | null;
  open: boolean;
  onClose: () => void;
}

const PreviewDrawer: React.FC<PreviewDrawerProps> = ({
  blueprintId,
  versionNumber,
  open,
  onClose,
}) => {
  const { data, isLoading, isError } = useQuery<VersionDetail>({
    queryKey: ['blueprint-version-detail', blueprintId, versionNumber],
    queryFn: () => loadBlueprintVersion(blueprintId, versionNumber!),
    enabled: open && versionNumber !== null,
    staleTime: 5 * 60_000,
  });

  return (
    <Drawer open={open} onOpenChange={(isOpen) => !isOpen && onClose()}>
      <DrawerContent
        data-testid="blueprint-version-preview-drawer"
        className="max-h-[90vh]"
      >
        <DrawerHeader>
          <DrawerTitle data-testid="blueprint-version-preview-title">
            Version {versionNumber} — Spec Preview
          </DrawerTitle>
          {data && (
            <DrawerDescription data-testid="blueprint-version-preview-meta">
              Created by <strong>{data.created_by || 'Unknown'}</strong> on{' '}
              {formatTimestamp(data.created_at)}
              {data.change_summary && (
                <> &mdash; {data.change_summary}</>
              )}
            </DrawerDescription>
          )}
        </DrawerHeader>

        <div className="px-4 pb-4 flex-1 overflow-hidden">
          {isLoading && (
            <div
              data-testid="blueprint-version-preview-loading"
              className="flex items-center justify-center py-12"
            >
              <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
            </div>
          )}

          {isError && (
            <ErrorState message="Failed to load version snapshot. Please try again." />
          )}

          {data && !isLoading && (
            <ScrollArea
              data-testid="blueprint-version-preview-scroll"
              className="h-[55vh] rounded-md border"
            >
              <pre
                data-testid="blueprint-version-preview-content"
                className="p-4 text-xs font-mono leading-relaxed whitespace-pre-wrap break-all"
              >
                {JSON.stringify(data.spec_dict_snapshot, null, 2)}
              </pre>
            </ScrollArea>
          )}
        </div>

        <DrawerFooter>
          <DrawerClose asChild>
            <Button
              variant="outline"
              data-testid="blueprint-version-preview-close-btn"
              onClick={onClose}
            >
              Close
            </Button>
          </DrawerClose>
        </DrawerFooter>
      </DrawerContent>
    </Drawer>
  );
};

// ── Restore Confirmation Dialog ────────────────────────────────────────────────

interface RestoreDialogProps {
  versionNumber: number | null;
  open: boolean;
  isPending: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

const RestoreDialog: React.FC<RestoreDialogProps> = ({
  versionNumber,
  open,
  isPending,
  onConfirm,
  onCancel,
}) => (
  <AlertDialog open={open}>
    <AlertDialogContent data-testid="blueprint-version-restore-dialog">
      <AlertDialogHeader>
        <AlertDialogTitle data-testid="blueprint-version-restore-dialog-title">
          Restore to Version {versionNumber}?
        </AlertDialogTitle>
        <AlertDialogDescription data-testid="blueprint-version-restore-dialog-description">
          This will replace the current live blueprint spec with the content
          from version {versionNumber}. The current state will be saved as a new
          version so you can always roll back again. This action cannot be
          undone in a single click.
        </AlertDialogDescription>
      </AlertDialogHeader>
      <AlertDialogFooter>
        <AlertDialogCancel
          data-testid="blueprint-version-restore-cancel-btn"
          onClick={onCancel}
          disabled={isPending}
        >
          Cancel
        </AlertDialogCancel>
        <AlertDialogAction
          data-testid="blueprint-version-restore-confirm-btn"
          onClick={onConfirm}
          disabled={isPending}
          className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
        >
          {isPending ? (
            <>
              <Loader2 className="w-4 h-4 mr-2 animate-spin" />
              Restoring…
            </>
          ) : (
            <>
              <RotateCcw className="w-4 h-4 mr-2" />
              Restore
            </>
          )}
        </AlertDialogAction>
      </AlertDialogFooter>
    </AlertDialogContent>
  </AlertDialog>
);

// ── Main Component ─────────────────────────────────────────────────────────────

export interface BlueprintVersionHistoryProps {
  /** The blueprint whose version history to display. */
  blueprintId: string;
  /**
   * Optional callback fired after a successful restore so the parent can
   * refresh its own blueprint data.
   */
  onRestoreSuccess?: (restoredToVersion: number) => void;
}

/**
 * Full-featured version history panel for a single blueprint.
 *
 * @example
 * ```tsx
 * <BlueprintVersionHistory
 *   blueprintId="abc-123"
 *   onRestoreSuccess={(v) => console.log('Restored to', v)}
 * />
 * ```
 */
const BlueprintVersionHistory: React.FC<BlueprintVersionHistoryProps> = ({
  blueprintId,
  onRestoreSuccess,
}) => {
  const queryClient = useQueryClient();

  // ── Pagination state ──────────────────────────────────────────────────────
  const [page, setPage] = useState(1);

  // ── Preview drawer state ──────────────────────────────────────────────────
  const [previewVersion, setPreviewVersion] = useState<number | null>(null);
  const [previewOpen, setPreviewOpen] = useState(false);

  // ── Restore dialog state ──────────────────────────────────────────────────
  const [restoreVersion, setRestoreVersion] = useState<number | null>(null);
  const [restoreOpen, setRestoreOpen] = useState(false);

  // ── Success / error toast state ───────────────────────────────────────────
  const [statusMessage, setStatusMessage] = useState<{
    type: 'success' | 'error';
    text: string;
  } | null>(null);

  // ── Data fetching ─────────────────────────────────────────────────────────

  const {
    data: versionList,
    isLoading,
    isError,
    error,
  } = useQuery({
    queryKey: ['blueprint-versions', blueprintId, page, DEFAULT_PAGE_SIZE],
    queryFn: () => listBlueprintVersions(blueprintId, page, DEFAULT_PAGE_SIZE),
    staleTime: 30_000,
    enabled: Boolean(blueprintId),
  });

  // ── Restore mutation ──────────────────────────────────────────────────────

  const restoreMutation = useMutation({
    mutationFn: (versionNumber: number) =>
      restoreBlueprintVersion(blueprintId, versionNumber),
    onSuccess: (data) => {
      setRestoreOpen(false);
      setRestoreVersion(null);
      setStatusMessage({
        type: 'success',
        text: `Blueprint successfully restored to version ${data.restored_to_version}.`,
      });
      // Invalidate the version list so the new version snapshot appears.
      queryClient.invalidateQueries({
        queryKey: ['blueprint-versions', blueprintId],
      });
      onRestoreSuccess?.(data.restored_to_version);
      // Clear the status message after 5 s.
      setTimeout(() => setStatusMessage(null), 5000);
    },
    onError: (err: Error) => {
      setRestoreOpen(false);
      const msg = err.message.includes('409')
        ? 'The blueprint was modified by another user. Please refresh and try again.'
        : `Restore failed: ${err.message}`;
      setStatusMessage({ type: 'error', text: msg });
      setTimeout(() => setStatusMessage(null), 8000);
    },
  });

  // ── Event handlers ────────────────────────────────────────────────────────

  const handlePreview = useCallback((versionNumber: number) => {
    setPreviewVersion(versionNumber);
    setPreviewOpen(true);
  }, []);

  const handleClosePreview = useCallback(() => {
    setPreviewOpen(false);
    // Keep previewVersion until drawer animation finishes.
    setTimeout(() => setPreviewVersion(null), 300);
  }, []);

  const handleRestoreClick = useCallback((versionNumber: number) => {
    setRestoreVersion(versionNumber);
    setRestoreOpen(true);
  }, []);

  const handleRestoreConfirm = useCallback(() => {
    if (restoreVersion !== null) {
      restoreMutation.mutate(restoreVersion);
    }
  }, [restoreVersion, restoreMutation]);

  const handleRestoreCancel = useCallback(() => {
    setRestoreOpen(false);
    setRestoreVersion(null);
  }, []);

  // ── Render ────────────────────────────────────────────────────────────────

  const totalPages = versionList?.total_pages ?? 1;
  const hasPrev = page > 1;
  const hasNext = page < totalPages;

  return (
    <div
      data-testid="blueprint-version-history"
      className="flex flex-col gap-4"
    >
      {/* ── Panel header ── */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <History className="w-5 h-5 text-muted-foreground" />
          <h3 className="font-semibold text-sm" data-testid="blueprint-version-history-title">
            Version History
          </h3>
          {versionList && (
            <Badge
              variant="secondary"
              data-testid="blueprint-version-history-total-badge"
            >
              {versionList.total}
            </Badge>
          )}
        </div>
      </div>

      {/* ── Status message (success / error) ── */}
      {statusMessage && (
        <div
          data-testid={`blueprint-version-history-status-${statusMessage.type}`}
          className={`flex items-center gap-2 px-3 py-2 rounded-md text-sm ${
            statusMessage.type === 'success'
              ? 'bg-green-500/10 text-green-600 border border-green-500/20'
              : 'bg-destructive/10 text-destructive border border-destructive/20'
          }`}
        >
          {statusMessage.type === 'error' && (
            <AlertCircle className="w-4 h-4 shrink-0" />
          )}
          <span>{statusMessage.text}</span>
        </div>
      )}

      {/* ── Loading state ── */}
      {isLoading && (
        <div
          data-testid="blueprint-version-history-loading"
          className="flex items-center justify-center py-12"
        >
          <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
        </div>
      )}

      {/* ── Error state ── */}
      {isError && (
        <ErrorState
          message={
            (error as Error)?.message || 'Failed to load version history.'
          }
        />
      )}

      {/* ── Empty state ── */}
      {!isLoading && !isError && versionList?.items.length === 0 && (
        <EmptyState message="No version history yet. Edit and save the blueprint to create the first version." />
      )}

      {/* ── Version table ── */}
      {!isLoading && !isError && (versionList?.items.length ?? 0) > 0 && (
        <>
          <Table data-testid="blueprint-version-history-table">
            <TableHeader>
              <TableRow>
                <TableHead
                  className="w-20"
                  data-testid="blueprint-version-history-col-version"
                >
                  Version
                </TableHead>
                <TableHead data-testid="blueprint-version-history-col-created-by">
                  Created By
                </TableHead>
                <TableHead data-testid="blueprint-version-history-col-created-at">
                  Date
                </TableHead>
                <TableHead data-testid="blueprint-version-history-col-summary">
                  Change Summary
                </TableHead>
                <TableHead
                  className="text-right"
                  data-testid="blueprint-version-history-col-actions"
                >
                  Actions
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {versionList!.items.map((v: VersionSummary) => (
                <TableRow
                  key={v.version}
                  data-testid={`blueprint-version-history-row-${v.version}`}
                >
                  {/* Version badge */}
                  <TableCell data-testid={`blueprint-version-history-row-${v.version}-version`}>
                    <Badge variant="outline" className="font-mono text-xs">
                      v{v.version}
                    </Badge>
                  </TableCell>

                  {/* Created by */}
                  <TableCell
                    className="text-sm text-muted-foreground max-w-[160px] truncate"
                    data-testid={`blueprint-version-history-row-${v.version}-created-by`}
                    title={v.created_by}
                  >
                    {v.created_by || '—'}
                  </TableCell>

                  {/* Created at */}
                  <TableCell
                    className="text-sm whitespace-nowrap"
                    data-testid={`blueprint-version-history-row-${v.version}-created-at`}
                  >
                    {formatTimestamp(v.created_at)}
                  </TableCell>

                  {/* Change summary */}
                  <TableCell
                    className="text-sm text-muted-foreground max-w-[260px] truncate"
                    data-testid={`blueprint-version-history-row-${v.version}-summary`}
                    title={v.change_summary ?? ''}
                  >
                    {v.change_summary || <span className="italic opacity-50">No summary</span>}
                  </TableCell>

                  {/* Actions */}
                  <TableCell className="text-right">
                    <div className="flex items-center justify-end gap-2">
                      <Button
                        variant="ghost"
                        size="sm"
                        data-testid={`blueprint-version-history-preview-btn-${v.version}`}
                        onClick={() => handlePreview(v.version)}
                        title={`Preview version ${v.version}`}
                      >
                        <Eye className="w-4 h-4" />
                        <span className="sr-only">Preview v{v.version}</span>
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        data-testid={`blueprint-version-history-restore-btn-${v.version}`}
                        onClick={() => handleRestoreClick(v.version)}
                        title={`Restore to version ${v.version}`}
                        className="text-destructive hover:text-destructive hover:bg-destructive/10"
                      >
                        <RotateCcw className="w-4 h-4" />
                        <span className="sr-only">Restore v{v.version}</span>
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>

          {/* ── Pagination controls ── */}
          {totalPages > 1 && (
            <div
              data-testid="blueprint-version-history-pagination"
              className="flex items-center justify-between text-sm text-muted-foreground"
            >
              <span data-testid="blueprint-version-history-pagination-info">
                Page {page} of {totalPages} ({versionList!.total} total)
              </span>
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  data-testid="blueprint-version-history-pagination-prev"
                  disabled={!hasPrev}
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                >
                  <ChevronLeft className="w-4 h-4" />
                  Prev
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  data-testid="blueprint-version-history-pagination-next"
                  disabled={!hasNext}
                  onClick={() => setPage((p) => p + 1)}
                >
                  Next
                  <ChevronRight className="w-4 h-4" />
                </Button>
              </div>
            </div>
          )}
        </>
      )}

      {/* ── Preview drawer ── */}
      <PreviewDrawer
        blueprintId={blueprintId}
        versionNumber={previewVersion}
        open={previewOpen}
        onClose={handleClosePreview}
      />

      {/* ── Restore confirmation dialog ── */}
      <RestoreDialog
        versionNumber={restoreVersion}
        open={restoreOpen}
        isPending={restoreMutation.isPending}
        onConfirm={handleRestoreConfirm}
        onCancel={handleRestoreCancel}
      />
    </div>
  );
};

export default BlueprintVersionHistory;
