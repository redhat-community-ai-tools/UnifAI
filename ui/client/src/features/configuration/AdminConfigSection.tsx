import { useState, useEffect } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/hooks/use-toast";
import { FaSave, FaUndo } from "react-icons/fa";
import {
  updateAdminConfigSection,
  type SectionValue,
  type FieldValue,
} from "@/api/adminConfig";
import AdminConfigFieldRenderer from "./AdminConfigFieldRenderer";

/**
 * Renders a single admin_config section as a card with editable fields,
 * save/reset buttons, and mutation handling.
 */
export default function AdminConfigSection({
  section,
}: {
  section: SectionValue;
}) {
  const queryClient = useQueryClient();
  const { toast } = useToast();

  const [values, setValues] = useState<Record<string, unknown>>(() =>
    buildInitialValues(section.fields),
  );
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);

  useEffect(() => {
    setValues(buildInitialValues(section.fields));
    setHasUnsavedChanges(false);
  }, [section]);

  const mutation = useMutation({
    mutationFn: (vals: Record<string, unknown>) =>
      updateAdminConfigSection(section.key, vals),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin_config"] });
      queryClient.invalidateQueries({ queryKey: ["admin-access"] });
      setTimeout(() => {
        queryClient.invalidateQueries({ queryKey: ["availableSlackChannels"] });
        queryClient.invalidateQueries({ queryKey: ["embeddedSlackChannels"] });
      }, 3000);
      toast({
        title: "Saved",
        description: `${section.title} updated successfully.`,
      });
      setHasUnsavedChanges(false);
    },
    onError: (err: Error) => {
      toast({
        variant: "destructive",
        title: "Save failed",
        description: err.message,
      });
    },
  });

  const handleFieldChange = (fieldKey: string, newValue: unknown) => {
    setValues((prev) => ({ ...prev, [fieldKey]: newValue }));
    setHasUnsavedChanges(true);
  };

  const handleSave = () => mutation.mutate(values);

  const handleReset = () => {
    setValues(buildInitialValues(section.fields));
    setHasUnsavedChanges(false);
  };

  return (
    <Card className="bg-background-card shadow-card border-gray-800">
      <CardContent className="p-6">
        <div className="flex items-start justify-between mb-1">
          <div>
            <h3 className="text-lg font-heading font-semibold">
              {section.title}
            </h3>
            {section.description && (
              <p className="text-sm text-gray-400 mt-1 max-w-2xl">
                {section.description}
              </p>
            )}
          </div>
          {section.updated_at && (
            <Badge
              variant="outline"
              className="text-xs text-gray-500 shrink-0"
            >
              Last updated:{" "}
              {new Date(section.updated_at).toLocaleDateString()}
            </Badge>
          )}
        </div>

        <div className="mt-6 space-y-6">
          {section.fields.map((field) => (
            <AdminConfigFieldRenderer
              key={field.key}
              field={field}
              value={values[field.key]}
              onChange={(v) => handleFieldChange(field.key, v)}
            />
          ))}
        </div>

        <div className="flex items-center gap-3 mt-8 pt-4 border-t border-gray-800">
          <Button
            onClick={handleSave}
            disabled={!hasUnsavedChanges || mutation.isPending}
            className="bg-primary"
          >
            <FaSave className="mr-2 w-3.5 h-3.5" />
            {mutation.isPending ? "Saving..." : "Save Changes"}
          </Button>
          <Button
            variant="outline"
            onClick={handleReset}
            disabled={!hasUnsavedChanges || mutation.isPending}
          >
            <FaUndo className="mr-2 w-3.5 h-3.5" />
            Reset
          </Button>
          {hasUnsavedChanges && (
            <span className="text-xs text-amber-400 ml-2">
              Unsaved changes
            </span>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

// ─────────────────────────────────────────────────────────────────────────────

function buildInitialValues(fields: FieldValue[]): Record<string, unknown> {
  const result: Record<string, unknown> = {};
  for (const f of fields) {
    result[f.key] = f.value ?? f.default ?? null;
  }
  return result;
}
