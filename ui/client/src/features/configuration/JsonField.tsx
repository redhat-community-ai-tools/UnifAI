import { useState, useEffect, useRef } from "react";
import { AlertCircle, CheckCircle2 } from "lucide-react";

interface JsonFieldProps {
  value: unknown;
  onChange: (value: unknown) => void;
  placeholder?: string;
}

export default function JsonField({ value, onChange, placeholder }: JsonFieldProps) {
  const [raw, setRaw] = useState(() => {
    try {
      return JSON.stringify(value ?? {}, null, 2);
    } catch {
      return "{}";
    }
  });
  const [error, setError] = useState<string | null>(null);
  const pendingChange = useRef<unknown>(null);

  // Keep raw in sync if parent resets the value (e.g. Reset button)
  useEffect(() => {
    try {
      const incoming = JSON.stringify(value ?? {}, null, 2);
      // Only overwrite if it differs from what we'd produce from the last parse
      if (pendingChange.current === null) {
        setRaw(incoming);
        setError(null);
      }
    } catch {
      // ignore
    }
  }, [value]);

  function handleChange(text: string) {
    setRaw(text);
    try {
      const parsed = JSON.parse(text);
      setError(null);
      pendingChange.current = parsed;
      onChange(parsed);
    } catch (e: unknown) {
      const msg = e instanceof SyntaxError ? e.message : "Invalid JSON";
      setError(msg);
      pendingChange.current = null;
    }
  }

  function handleBlur() {
    // Pretty-print on blur when valid
    if (!error && pendingChange.current !== null) {
      setRaw(JSON.stringify(pendingChange.current, null, 2));
      pendingChange.current = null;
    }
  }

  return (
    <div className="space-y-1">
      <div className="relative">
        <textarea
          value={raw}
          onChange={(e) => handleChange(e.target.value)}
          onBlur={handleBlur}
          placeholder={placeholder ?? "{}"}
          rows={18}
          spellCheck={false}
          className={[
            "w-full rounded-md border bg-background-dark p-3",
            "font-mono text-xs text-gray-100 resize-y",
            "focus:outline-none focus:ring-1",
            error
              ? "border-red-500 focus:ring-red-500"
              : "border-border focus:ring-primary",
          ].join(" ")}
        />
        <span className="absolute top-2 right-3 flex items-center gap-1">
          {error ? (
            <AlertCircle className="h-4 w-4 text-red-400" />
          ) : (
            <CheckCircle2 className="h-4 w-4 text-green-400" />
          )}
        </span>
      </div>

      {error && (
        <p className="text-xs text-red-400 flex items-center gap-1">
          <AlertCircle className="h-3 w-3 shrink-0" />
          {error}
        </p>
      )}

      {!error && (
        <p className="text-xs text-gray-500">Valid JSON — changes apply on Save.</p>
      )}
    </div>
  );
}
