import { useMemo } from "react";
import { useTheme } from "@/contexts/ThemeContext";
import { deriveThemeColors } from "@/lib/colorUtils";

/**
 * Lightened tint of the site's accent color — the raw `primary` color can be
 * nearly unreadable for small icon glyphs/text on the dark background with
 * darker accent choices (e.g. red). Used by inventory card icons/badges.
 */
export function usePrimaryLightColor(): string {
  const { primaryHex } = useTheme();
  return useMemo(() => deriveThemeColors(primaryHex).primaryLight, [primaryHex]);
}
