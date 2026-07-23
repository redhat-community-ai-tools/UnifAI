import React from "react";
import { CardField } from "@/lib/cardFields";

interface CardFieldListProps {
  fields: CardField[];
  /** Cap how many rows render before the rest collapse into a "+N more" hint. */
  maxRows?: number;
}

/**
 * Renders the `hints.card`-selected config fields for an element instance —
 * shared by `BuiltInElementCard` and the custom-element card in
 * `ElementGrid`, which each resolve `getCardFields()` for their own
 * ownership context ("builtin" vs "custom") before handing the result here.
 */
export const CardFieldList: React.FC<CardFieldListProps> = ({ fields, maxRows = 6 }) => {
  if (fields.length === 0) return null;

  const visibleFields = fields.slice(0, maxRows);
  const hiddenCount = fields.length - visibleFields.length;

  return (
    <div className="flex flex-col gap-1.5 w-full">
      {visibleFields.map((field) => (
        <div key={field.key} className="flex items-baseline justify-between gap-2 text-xs">
          <span className="text-gray-500 flex-shrink-0">{field.label}</span>
          <span className="text-gray-300 truncate text-right" title={field.value}>
            {field.value}
          </span>
        </div>
      ))}
      {hiddenCount > 0 && (
        <span className="text-xs text-gray-600 italic text-right">+{hiddenCount} more</span>
      )}
    </div>
  );
};
