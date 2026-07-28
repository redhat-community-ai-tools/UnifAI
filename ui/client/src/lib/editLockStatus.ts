/** Common shape of a resolved edit-lock holder, shared by the builtin and team lock APIs. */
export interface EditLockHolderLike {
  userId: string;
  displayName: string;
}

export type EditLockResolvedLike = EditLockHolderLike | null | "unknown" | undefined;

export interface EditLockStatus {
  /** True when someone other than `currentUsername` holds the lock. */
  lockedByOther: boolean;
  /** True when the server couldn't confirm lock state — treat as "don't assume unlocked". */
  lockUnknown: boolean;
  /** Display name for whoever holds the lock, falling back to `fallbackLabel`. */
  lockedByLabel: string;
}

/**
 * Resolves a polled edit-lock value (builtin resources or team entities —
 * both use the `{ userId, displayName } | null | "unknown"` shape) into the
 * flags/label needed to render a lock indicator. Shared by `ElementGrid` and
 * `BuiltinResourceTable` so the two don't drift.
 */
export function resolveEditLockStatus(
  lockHolder: EditLockResolvedLike,
  currentUsername: string,
  fallbackLabel: string,
): EditLockStatus {
  const lockUnknown = lockHolder === "unknown";
  const lockedByOther =
    !lockUnknown && !!lockHolder && !!currentUsername && lockHolder.userId !== currentUsername;
  const lockedByLabel = lockUnknown
    ? "unknown"
    : lockHolder?.displayName?.trim() || lockHolder?.userId || fallbackLabel;
  return { lockedByOther, lockUnknown, lockedByLabel };
}
