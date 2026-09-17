import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { type FieldValue } from "@/api/adminConfig";
import StringListField from "./StringListField";
import JsonField from "./JsonField";

export default function AdminConfigFieldRenderer({
  field,
  value,
  onChange,
}: {
  field: FieldValue;
  value: unknown;
  onChange: (value: unknown) => void;
}) {
  return (
    <div>
      <Label className="text-base font-medium">{field.label}</Label>
      {field.description && (
        <p className="text-xs text-gray-400 mt-1 mb-2">{field.description}</p>
      )}

      {field.field_type === "string_list" && (
        <StringListField
          value={Array.isArray(value) ? (value as string[]) : []}
          onChange={(v) => onChange(v)}
          placeholder={field.placeholder}
        />
      )}

      {field.field_type === "string" && (
        <Input
          value={typeof value === "string" ? value : ""}
          onChange={(e) => onChange(e.target.value)}
          placeholder={field.placeholder}
          className="bg-background-dark max-w-md"
        />
      )}

      {field.field_type === "number" && (
        <Input
          type="number"
          value={typeof value === "number" ? value : 0}
          onChange={(e) => onChange(Number(e.target.value))}
          placeholder={field.placeholder}
          className="bg-background-dark w-32"
        />
      )}

      {field.field_type === "boolean" && (
        <div className="flex items-center gap-3 mt-1">
          <Switch
            checked={Boolean(value)}
            onCheckedChange={(checked) => onChange(checked)}
          />
          <span className="text-sm text-gray-400">
            {value ? "Enabled" : "Disabled"}
          </span>
        </div>
      )}

      {field.field_type === "json" && (
        <JsonField
          value={value}
          onChange={onChange}
          placeholder={field.placeholder}
        />
      )}
    </div>
  );
}
