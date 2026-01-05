import { useState, useRef } from "react";
import type React from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { 
  FileText, 
  Upload, 
  X, 
  CloudUpload,
  Tag,
  CircleX,
  Loader2
} from "lucide-react";
import { toast } from "@/hooks/use-toast";
import { cn } from "@/lib/utils";
import { ProcessingOptions } from "./ProcessingOptions";
import { embedDocs, uploadDocs, getSupportedFileExtensions, validateFiles as validateFilesApi } from "@/api/docs";
import { useAuth } from '@/contexts/AuthContext';
import { formatPipelineError } from "@/utils/errorFormatting";
import { useQuery } from "@tanstack/react-query";

interface UploadTabProps {
    setShowUploadModal: (showUploadModal: boolean) => void;
    fetchDocuments: () => Promise<any>;
}

interface FileWithTags {
    file: File;
    tags: string[];
    showTagInput: boolean;
    id: string;
}

export const UploadTab: React.FC<UploadTabProps> = ({
    setShowUploadModal, fetchDocuments: refetchDocuments
}) => {
    const { user } = useAuth();
    
    const [isDragging, setIsDragging] = useState(false);
    const [selectedFiles, setSelectedFiles] = useState<FileWithTags[]>([]);
    const [isUploading, setIsUploading] = useState(false);
    const [isValidating, setIsValidating] = useState(false);
    const [error, setError] = useState<string>("");
    const [uploadProgress, setUploadProgress] = useState(0);
    const fileInputRef = useRef<HTMLInputElement>(null);

    // Use TanStack Query for caching supported extensions (for display only)
    const { data: supportedExtensions = [] } = useQuery({
        queryKey: ['supportedFileExtensions'],
        queryFn: getSupportedFileExtensions,
        staleTime: Infinity,
    });

    const handleDragEnter = (e: React.DragEvent) => {
        e.preventDefault();
        e.stopPropagation();
        setIsDragging(true);
    };

    const handleDragLeave = (e: React.DragEvent) => {
        e.preventDefault();
        e.stopPropagation();
        if (e.currentTarget.contains(e.relatedTarget as Node)) return;
        setIsDragging(false);
    };

    const handleDragOver = (e: React.DragEvent) => {
        e.preventDefault();
        e.stopPropagation();
        setIsDragging(true);
    };

    const handleDrop = (e: React.DragEvent) => {
        e.preventDefault();
        e.stopPropagation();
        setIsDragging(false);
        handleFiles(e.dataTransfer.files);
    };

    /**
     * Handle file selection/drop - validates files via backend API
     * 
     * Backend validation checks:
     * - File extension support
     * - File size limits (50 MB max)
     * - Duplicate filenames (allows re-upload of FAILED documents)
     * 
     * Only valid files are added to the selection list.
     * Invalid files are rejected and errors are shown in the error box.
     * Files already in the selection list are silently ignored.
     */
    const handleFiles = async (files: FileList) => {
        const currentUsername = user?.username || 'default';
        const filesArray = Array.from(files);
        
        // Get names of files already in the selection list
        const alreadySelectedNames = new Set(selectedFiles.map(f => f.file.name));
        
        // Filter out files that are already in the selection list (silently ignore them)
        const trulyNewFiles = filesArray.filter(file => !alreadySelectedNames.has(file.name));
        
        // If all files were already selected, just return silently
        if (trulyNewFiles.length === 0) {
            return;
        }
        
        // Check max file limit
        const currentFileCount = selectedFiles.length;
        if (currentFileCount + trulyNewFiles.length > 5) {
            setError(`Maximum of 5 documents allowed. You have ${currentFileCount} selected and tried to add ${trulyNewFiles.length} more.`);
            return;
        }

        // Build file metadata for backend validation
        // Include already selected files so backend can check for duplicates in the batch
        const existingFileNames = selectedFiles.map(f => ({
            name: f.file.name,
            size: f.file.size
        }));
        
        const newFilesMetadata = trulyNewFiles.map(file => ({
            name: file.name,
            size: file.size
        }));
        
        // Combine existing and new for complete validation
        const allFilesMetadata = [...existingFileNames, ...newFilesMetadata];

        setIsValidating(true);
        setError("");

        try {
            // Validate all files via backend API
            const result = await validateFilesApi(allFilesMetadata, currentUsername, true);
            
            // Get errors for new files only
            const newFileErrors = result.errors.filter(err => 
                newFilesMetadata.some(nf => nf.name === err.file_name)
            );

            // Display validation errors in the error box only (no toast)
            if (newFileErrors.length > 0) {
                const errorsByType: Record<string, string[]> = {};
                
                newFileErrors.forEach(err => {
                    if (!errorsByType[err.error_type]) {
                        errorsByType[err.error_type] = [];
                    }
                    errorsByType[err.error_type].push(`${err.file_name}`);
                });

                const errorMessages: string[] = [];
                
                if (errorsByType.extension) {
                    errorMessages.push(`Unsupported file types: ${errorsByType.extension.join(', ')}`);
                }
                if (errorsByType.size) {
                    errorMessages.push(`Files too large (max 50 MB): ${errorsByType.size.join(', ')}`);
                }
                if (errorsByType.duplicate) {
                    errorMessages.push(`Duplicate names: ${errorsByType.duplicate.join(', ')}`);
                }

                if (errorMessages.length > 0) {
                    setError(errorMessages.join('\n') + '\n\nThese files were not added.');
                }
            }

            // Build a set of valid file names from backend response (for new files only)
            // Use a count-based approach to handle multiple files with the same name correctly
            const validNameCounts: Record<string, number> = {};
            result.valid_files
                .filter(vf => newFilesMetadata.some(nf => nf.name === vf.name))
                .forEach(vf => {
                    validNameCounts[vf.name] = (validNameCounts[vf.name] || 0) + 1;
                });
            
            // Track how many of each name we've added to prevent duplicates
            const addedNameCounts: Record<string, number> = {};
            
            // Add ONLY valid files to selection - one per valid name from backend
            const validNewFiles: File[] = [];
            for (const file of trulyNewFiles) {
                const allowedCount = validNameCounts[file.name] || 0;
                const addedCount = addedNameCounts[file.name] || 0;
                
                if (addedCount < allowedCount) {
                    validNewFiles.push(file);
                    addedNameCounts[file.name] = addedCount + 1;
                }
            }
            
            if (validNewFiles.length > 0) {
                const newFiles = validNewFiles.map(file => ({
                    file,
                    tags: [],
                    showTagInput: false,
                    id: Math.random().toString(36).substring(7)
                }));
                
                setSelectedFiles(prev => [...prev, ...newFiles]);
            }

        } catch (err) {
            console.error("File validation failed", err);
            const message = (err as Error)?.message || "Failed to validate files. Please try again.";
            setError(message);
        } finally {
            setIsValidating(false);
        }
    };

    const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
        if (e.target.files) {
            handleFiles(e.target.files);
        }
    };

    const removeFile = (id: string) => {
        setSelectedFiles(prev => prev.filter((item) => item.id !== id));
    };

    const toggleTagInput = (id: string) => {
        setSelectedFiles(prev => prev.map(item => 
            item.id === id ? { ...item, showTagInput: !item.showTagInput } : item
        ));
    };

    const addTag = (id: string, tag: string) => {
        if (!tag.trim()) return;
        setSelectedFiles(prev => prev.map(item => {
            if (item.id === id && !item.tags.includes(tag.trim())) {
                return { ...item, tags: [...item.tags, tag.trim()] };
            }
            return item;
        }));
    };

    const removeTag = (id: string, tagToRemove: string) => {
        setSelectedFiles(prev => prev.map(item => {
            if (item.id === id) {
                return { ...item, tags: item.tags.filter(tag => tag !== tagToRemove) };
            }
            return item;
        }));
    };

    const handleUpload = async () => {
        if (selectedFiles.length === 0) return;
        
        setIsUploading(true);
        setUploadProgress(0);
        
        try {
            await uploadFiles();
            await startPipeline();
        } catch (err) {
            setIsUploading(false);
        }
    };

    const uploadFiles = async () => {
        let uploadedCount = 0;
        
        try {
            for (const item of selectedFiles) {
                const base64 = await new Promise<string>((resolve, reject) => {
                    const reader = new FileReader();
                    reader.onload = () => {
                        const result = reader.result as string;
                        resolve(result.split(",")[1]);
                    };
                    reader.onerror = reject;
                    reader.readAsDataURL(item.file);
                });
                
                await uploadDocs([{ name: item.file.name, content: base64 }]);
                
                uploadedCount++;
                setUploadProgress(Math.round((uploadedCount / selectedFiles.length) * 50));
            }
        } catch (err) {
            console.error("File upload failed", err);
            const message = (err as Error)?.message || "Failed to upload files. Please try again.";
            setError(message);
            toast({
                variant: "destructive",
                title: (
                    <span className="inline-flex items-center gap-2">
                        <CircleX className="h-4 w-4 text-red-500" />
                        <span>Upload failed</span>
                    </span>
                ),
                description: message,
            });
            throw err;
        }
    };

    const startPipeline = async () => {
        try {
            const docs = selectedFiles.map((item) => ({
                source_name: item.file.name,
                tags: item.tags
            }));
            
            setUploadProgress(60);
            
            // Pass skip_validation=true since files were pre-validated
            const res = await embedDocs(docs, user?.username || 'default', true);
            
            const issues = res?.registration?.issues || [];
            if (issues.length > 0) {
                issues.forEach((issue: any) => {
                    const { title: titleText, description } = formatPipelineError(issue);

                    toast({
                        variant: "destructive",
                        title: String(issue.issue_type || "Upload issue").toUpperCase(),
                        description: issue.message,
                    });
                });
            }

            setUploadProgress(100);
            
            toast({
                title: "Success",
                description: "Documents uploaded and processing started.",
            });
            
            if (refetchDocuments) await refetchDocuments();
            setSelectedFiles([]);
            setShowUploadModal(false);
            
        } catch (err) {
            console.error("Embedding failed", err);
            const message = (err as Error)?.message || "There was an error processing your documents.";
            setError(message);
            toast({
                variant: "destructive",
                title: (
                    <span className="inline-flex items-center gap-2">
                        <CircleX className="h-4 w-4 text-red-500" />
                        <span>Processing failed</span>
                    </span>
                ),
                description: message,
            });
            throw err;
        } finally {
            setIsUploading(false);
        }
    };

    return (
        <div className="w-full max-w-5xl mx-auto space-y-6 mt-10">
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-2xl font-bold text-foreground tracking-tight">Upload Documents</h2>
                    <p className="text-muted-foreground mt-1">Add documents to your knowledge base.</p>
                </div>
                <div className="flex gap-2">
                    <Button variant="outline" onClick={() => setShowUploadModal(false)}>Cancel</Button>
                    {selectedFiles.length > 0 && !isUploading && (
                        <Button 
                            onClick={handleUpload}
                            className="bg-primary hover:bg-primary/90 text-primary-foreground shadow-sm transition-all hover:shadow-md"
                        >
                            <CloudUpload className="mr-2 h-4 w-4" />
                            Upload {selectedFiles.length} File{selectedFiles.length !== 1 ? 's' : ''}
                        </Button>
                    )}
                </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-12">
                {/* Left Side: Drag & Drop Area */}
                <Card 
                    className={cn(
                        "border-2 border-dashed transition-all duration-300 ease-in-out bg-card h-[650px]",
                        isDragging 
                            ? "border-primary bg-primary/10 ring-4 ring-primary/20" 
                            : "border-border hover:border-primary/50 hover:bg-accent/50",
                        (selectedFiles.length >= 5 || isValidating) ? "opacity-50 cursor-not-allowed" : "cursor-pointer"
                    )}
                    onDragEnter={selectedFiles.length < 5 && !isValidating ? handleDragEnter : undefined}
                    onDragLeave={selectedFiles.length < 5 && !isValidating ? handleDragLeave : undefined}
                    onDragOver={selectedFiles.length < 5 && !isValidating ? handleDragOver : undefined}
                    onDrop={selectedFiles.length < 5 && !isValidating ? handleDrop : undefined}
                    onClick={selectedFiles.length < 5 && !isValidating ? () => fileInputRef.current?.click() : undefined}
                >
                    <CardContent className="flex flex-col items-center justify-center h-full min-h-[300px] py-12 text-center">
                        <input 
                            ref={fileInputRef}
                            type="file" 
                            multiple 
                            className="hidden" 
                            onChange={handleFileSelect}
                            disabled={selectedFiles.length >= 5 || isUploading || isValidating}
                        />
                        
                        <div className={cn(
                            "w-20 h-20 rounded-full flex items-center justify-center mb-6 transition-transform duration-300",
                            isDragging ? "bg-primary/20 scale-110" : "bg-background shadow-sm border border-border"
                        )}>
                            {isValidating ? (
                                <Loader2 className="h-10 w-10 text-primary animate-spin" />
                            ) : (
                                <Upload className={cn("h-10 w-10", isDragging ? "text-primary" : "text-muted-foreground")} />
                            )}
                        </div>
                        
                        <h3 className="text-xl font-semibold text-foreground mb-2">
                            {isValidating 
                                ? "Validating files..." 
                                : selectedFiles.length >= 5 
                                    ? "Maximum files reached" 
                                    : "Click to upload or drag and drop"
                            }
                        </h3>
                        <p className="text-sm text-muted-foreground max-w-xs mx-auto mb-4">
                            {isValidating 
                                ? "Checking file types, sizes, and duplicates..."
                                : selectedFiles.length >= 5 
                                    ? "Please remove a file to add another." 
                                    : ""
                            }
                        </p>
                        
                        {/* Additional details */}
                        <div className="flex flex-col items-center gap-2 text-xs text-muted-foreground">
                            <p>
                                Supported formats: {supportedExtensions.map(ext => ext.toUpperCase().substring(1)).join(', ')}
                            </p>
                            <p>
                                Maximum file size: <span className="font-semibold text-foreground/70">50 MB</span> per file
                            </p>
                            <p>
                                Maximum files: <span className="font-semibold text-foreground/70">5</span> documents
                            </p>
                        </div>
                        
                        {/* Error display */}
                        {error && (
                            <div className="mt-6 w-full max-w-sm">
                                <p className="text-sm text-red-500 bg-red-500/10 border border-red-500/20 rounded-md px-3 py-2 whitespace-pre-line">{error}</p>
                            </div>
                        )}
                    </CardContent>
                </Card>

                {/* Right Side: File List */}
                <div className="flex flex-col h-[650px]">
                    {selectedFiles.length > 0 ? (
                        <div className="space-y-4 h-full flex flex-col">
                            <h4 className="text-sm font-medium text-muted-foreground uppercase tracking-wider">
                                Selected Files ({selectedFiles.length}/5)
                            </h4>
                            <div className="flex-1 overflow-y-auto pr-2 space-y-3 scrollbar-thin scrollbar-thumb-muted scrollbar-track-transparent">
                                {selectedFiles.map((item) => (
                                    <div 
                                        key={item.id}
                                        className="group flex flex-col p-4 bg-card border border-border rounded-xl shadow-sm hover:shadow-md transition-all duration-200"
                                    >
                                        <div className="flex items-start justify-between w-full">
                                            <div className="flex items-center space-x-4 overflow-hidden">
                                                <div className="h-10 w-10 shrink-0 rounded-lg bg-primary/10 flex items-center justify-center border border-primary/20">
                                                    <FileText className="h-5 w-5 text-primary" />
                                                </div>
                                                <div className="min-w-0">
                                                    <div className="flex items-center gap-2">
                                                        <p className="text-sm font-semibold text-foreground truncate">
                                                            {item.file.name}
                                                        </p>
                                                        <Badge variant="secondary" className="text-[10px] h-5 px-1.5 uppercase">
                                                            {item.file.name.split('.').pop()}
                                                        </Badge>
                                                    </div>
                                                    <p className="text-xs text-muted-foreground">
                                                        {(item.file.size / 1024).toFixed(0)} KB
                                                    </p>
                                                </div>
                                            </div>
                                        </div>

                                        {/* Tags Section */}
                                        {item.tags.length > 0 && (
                                            <div className="flex flex-wrap gap-2 mt-3">
                                                {item.tags.map((tag, idx) => (
                                                    <Badge key={idx} variant="outline" className="text-xs gap-1 pl-2 pr-1 py-0.5 h-6">
                                                        {tag}
                                                        <button 
                                                            onClick={(e) => {
                                                                e.stopPropagation();
                                                                removeTag(item.id, tag);
                                                            }}
                                                            className="hover:text-destructive focus:outline-none"
                                                        >
                                                            <X className="h-3 w-3" />
                                                        </button>
                                                    </Badge>
                                                ))}
                                            </div>
                                        )}

                                        {/* Add Tag Input */}
                                        {item.showTagInput && (
                                            <div className="mt-3 flex gap-2 animate-in slide-in-from-top-1 duration-200">
                                                <Input
                                                    autoFocus
                                                    placeholder="Type tag and press Enter..."
                                                    className="h-8 text-xs dark:bg-zinc-800 dark:!text-white dark:border-zinc-700"
                                                    onKeyDown={(e) => {
                                                        if (e.key === 'Enter') {
                                                            e.preventDefault();
                                                            addTag(item.id, e.currentTarget.value);
                                                            e.currentTarget.value = '';
                                                        }
                                                    }}
                                                />
                                                <Button 
                                                    variant="ghost" 
                                                    size="sm" 
                                                    className="h-8 w-8 p-0"
                                                    onClick={() => toggleTagInput(item.id)}
                                                >
                                                    <X className="h-4 w-4" />
                                                </Button>
                                            </div>
                                        )}

                                        {/* Bottom Actions */}
                                        <div className="flex items-center justify-end gap-2 mt-4 -mx-4 -mb-4 px-4 py-2 bg-zinc-50/50 dark:bg-zinc-900/30 border-t border-border rounded-b-xl">
                                            <Button
                                                variant="ghost"
                                                size="sm"
                                                onClick={() => toggleTagInput(item.id)}
                                                className="h-7 text-xs text-muted-foreground hover:text-primary"
                                            >
                                                <Tag className="h-3 w-3 mr-1.5" />
                                                Add Tag
                                            </Button>
                                            <Button
                                                variant="ghost"
                                                size="sm"
                                                onClick={() => removeFile(item.id)}
                                                className="h-7 text-xs text-muted-foreground hover:text-destructive"
                                            >
                                                <X className="h-3 w-3 mr-1.5" />
                                                Remove
                                            </Button>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </div>
                    ) : (
                        <div className="h-full flex flex-col items-center justify-center border-2 border-dashed border-border rounded-xl bg-muted/20 p-6 text-center min-h-[300px]">
                             <div className="w-16 h-16 rounded-full bg-background flex items-center justify-center mb-4 opacity-50">
                                <FileText className="h-8 w-8 text-muted-foreground" />
                             </div>
                             <h4 className="text-lg font-medium text-foreground mb-1">No files selected</h4>
                             <p className="text-sm text-muted-foreground max-w-xs">
                                Uploaded files will appear here ready for processing.
                             </p>
                        </div>
                    )}
                </div>
            </div>

            {isUploading && (
                <div className="p-6 bg-card border border-border rounded-xl shadow-sm mt-6">
                    <div className="flex items-center justify-between mb-3">
                        <div className="flex items-center gap-3">
                            <div className="animate-spin rounded-full h-4 w-4 border-2 border-primary border-t-transparent"></div>
                            <span className="text-sm font-medium text-foreground">Uploading documents...</span>
                        </div>
                        <span className="text-sm font-medium text-primary">{uploadProgress}%</span>
                    </div>
                    <Progress value={uploadProgress} className="h-2 bg-muted" />
                </div>
            )}
            
            <ProcessingOptions />
        </div>
    );
};
