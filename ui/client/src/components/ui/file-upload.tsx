import React, { useRef, useState, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Upload, CheckCircle2, X, Loader2 } from "lucide-react";
import axiosInstance from "@/http/axiosAgentConfig";
import { cn } from "@/lib/utils";

interface FileUploadProps {
  accept: string;
  uploadEndpoint: string;
  validateFormat?: string;
  maxSizeBytes?: number;
  value?: string;
  disabled?: boolean;
  hasError?: boolean;
  onUploadSuccess: (content: string, filename: string) => void;
  onUploadError?: (error: string) => void;
  onClear?: () => void;
}

export const FileUpload: React.FC<FileUploadProps> = ({
  accept,
  uploadEndpoint,
  validateFormat = "pem",
  maxSizeBytes = 16384,
  value,
  disabled = false,
  hasError = false,
  onUploadSuccess,
  onUploadError,
  onClear,
}) => {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [uploadedFilename, setUploadedFilename] = useState<string | null>(null);

  const handleFileSelect = useCallback(
    async (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (!file) return;

      if (file.size > maxSizeBytes) {
        const msg = `File too large (${file.size} bytes). Maximum is ${maxSizeBytes} bytes.`;
        setError(msg);
        onUploadError?.(msg);
        return;
      }

      setIsUploading(true);
      setError(null);

      try {
        const formData = new FormData();
        formData.append("file", file);
        formData.append("format", validateFormat);

        const response = await axiosInstance.post(uploadEndpoint, formData, {
          headers: { "Content-Type": "multipart/form-data" },
        });

        setUploadedFilename(response.data.filename || file.name);
        onUploadSuccess(response.data.content, response.data.filename || file.name);
        setError(null);
      } catch (err: any) {
        const msg =
          err?.response?.data?.error || "Upload failed. Please try again.";
        setError(msg);
        onUploadError?.(msg);
      } finally {
        setIsUploading(false);
        if (fileInputRef.current) {
          fileInputRef.current.value = "";
        }
      }
    },
    [uploadEndpoint, validateFormat, maxSizeBytes, onUploadSuccess, onUploadError],
  );

  const handleClear = useCallback(() => {
    setUploadedFilename(null);
    setError(null);
    onClear?.();
  }, [onClear]);

  const hasValue = !!value;

  if (hasValue) {
    return (
      <div className="flex items-center gap-2">
        <Badge variant="secondary" className="flex items-center gap-1.5 py-1 px-3">
          <CheckCircle2 className="h-3.5 w-3.5 text-green-500" />
          <span className="text-xs">
            {uploadedFilename
              ? `${uploadedFilename} uploaded`
              : "Certificate uploaded"}
          </span>
        </Badge>
        {!disabled && (
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="h-7 w-7 p-0"
            onClick={handleClear}
          >
            <X className="h-3.5 w-3.5 text-muted-foreground hover:text-red-400" />
          </Button>
        )}
      </div>
    );
  }

  return (
    <div className="space-y-1">
      <input
        ref={fileInputRef}
        type="file"
        accept={accept}
        className="hidden"
        onChange={handleFileSelect}
        disabled={disabled || isUploading}
      />
      <Button
        type="button"
        variant="outline"
        size="sm"
        disabled={disabled || isUploading}
        className={cn(
          "gap-1.5",
          hasError && "border-red-500",
        )}
        onClick={() => fileInputRef.current?.click()}
      >
        {isUploading ? (
          <Loader2 className="h-3.5 w-3.5 animate-spin" />
        ) : (
          <Upload className="h-3.5 w-3.5" />
        )}
        {isUploading ? "Uploading..." : "Choose file..."}
      </Button>
      {error && (
        <p className="text-xs text-red-500">{error}</p>
      )}
    </div>
  );
};
