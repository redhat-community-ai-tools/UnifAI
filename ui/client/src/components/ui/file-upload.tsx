import { useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Upload, X, CheckCircle, Loader2 } from "lucide-react";
import { uploadResourceFile } from "@/api/resources";

interface FileUploadProps {
  accept: string;
  formatType?: string;
  maxSizeBytes?: number;
  value?: string;
  filename?: string;
  disabled?: boolean;
  hasError?: boolean;
  onUploadSuccess: (content: string, filename: string) => void;
  onUploadError?: (error: string) => void;
  onClear?: () => void;
}

export function FileUpload({
  accept,
  formatType = "pem",
  maxSizeBytes = 16384,
  value,
  filename: existingFilename,
  disabled,
  hasError,
  onUploadSuccess,
  onUploadError,
  onClear,
}: FileUploadProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadedFilename, setUploadedFilename] = useState(existingFilename || "");
  const [error, setError] = useState("");

  const hasValue = !!value;

  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (file.size > maxSizeBytes) {
      const msg = `File too large (${file.size} bytes). Maximum is ${maxSizeBytes} bytes.`;
      setError(msg);
      onUploadError?.(msg);
      return;
    }

    setIsUploading(true);
    setError("");

    try {
      const { content, filename: returnedFilename } = await uploadResourceFile(file, formatType);
      setUploadedFilename(returnedFilename || file.name);
      onUploadSuccess(content, returnedFilename || file.name);
    } catch (err: any) {
      const msg =
        err?.response?.data?.error || err?.message || "Upload failed";
      setError(msg);
      onUploadError?.(msg);
    } finally {
      setIsUploading(false);
      if (inputRef.current) {
        inputRef.current.value = "";
      }
    }
  };

  const handleClear = () => {
    setUploadedFilename("");
    setError("");
    onClear?.();
  };

  if (hasValue) {
    return (
      <div className="flex items-center gap-2">
        <Badge variant="outline" className="gap-1 text-green-400 border-green-400/30">
          <CheckCircle className="h-3 w-3" />
          {uploadedFilename || "file uploaded"}
        </Badge>
        {!disabled && (
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={handleClear}
            className="h-6 px-2 text-xs text-gray-400 hover:text-red-400"
          >
            <X className="h-3 w-3 mr-1" />
            Clear
          </Button>
        )}
      </div>
    );
  }

  return (
    <div className="space-y-1">
      <input
        ref={inputRef}
        type="file"
        accept={accept}
        onChange={handleFileSelect}
        className="hidden"
        disabled={disabled || isUploading}
      />
      <Button
        type="button"
        variant="outline"
        size="sm"
        onClick={() => inputRef.current?.click()}
        disabled={disabled || isUploading}
        className={`gap-2 ${hasError || error ? "border-red-500" : ""}`}
      >
        {isUploading ? (
          <>
            <Loader2 className="h-4 w-4 animate-spin" />
            Uploading...
          </>
        ) : (
          <>
            <Upload className="h-4 w-4" />
            Choose file...
          </>
        )}
      </Button>
      {error && <p className="text-xs text-red-500">{error}</p>}
    </div>
  );
}
