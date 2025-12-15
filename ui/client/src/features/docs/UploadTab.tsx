import { useState, useEffect, useRef } from "react";
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
  Plus
} from "lucide-react";
import { toast } from "@/hooks/use-toast";
import { cn } from "@/lib/utils";
import { ProcessingOptions } from "./ProcessingOptions";
import { embedDocs, uploadDocs, getSupportedFileExtensions } from "@/api/docs";
import { useAuth } from '@/contexts/AuthContext';

interface UploadTabProps {
    setShowUploadModal: (show: boolean) => void;
    fetchDocuments: any;
}

interface FileWithTags {
    file: File;
    tags: string[];
    showTagInput: boolean;
    id: string;
}

export const UploadTab: React.FC<UploadTabProps> = ({
    setShowUploadModal, fetchDocuments
}) => {
    const { user } = useAuth();
    
    const [isDragging, setIsDragging] = useState(false);
    const [selectedFiles, setSelectedFiles] = useState<FileWithTags[]>([]);
    const [isUploading, setIsUploading] = useState(false);
    const [uploadProgress, setUploadProgress] = useState(0);
    const [supportedExtensions, setSupportedExtensions] = useState<string[]>([]);
    const fileInputRef = useRef<HTMLInputElement>(null);

    useEffect(() => {
        const loadSupportedExtensions = async () => {
            try {
                const extensions = await getSupportedFileExtensions();
                setSupportedExtensions(extensions);
            } catch (err) {
                console.error("Failed to load supported extensions:", err);
                setSupportedExtensions([".pdf", ".docx", ".txt", ".md"]);
            }
        };
        loadSupportedExtensions();
    }, []);

    const isFileExtensionSupported = (fileName: string): boolean => {
        const extension = fileName.toLowerCase().substring(fileName.lastIndexOf('.'));
        return supportedExtensions.includes(extension);
    };
    
    const validateFiles = (files: FileList): { validFiles: File[], invalidFiles: string[] } => {
        const validFiles: File[] = [];
        const invalidFiles: string[] = [];
        
        Array.from(files).forEach(file => {
            if (isFileExtensionSupported(file.name)) {
                validFiles.push(file);
            } else {
                invalidFiles.push(file.name);
            }
        });
        
        return { validFiles, invalidFiles };
    };
    
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

    const handleFiles = (files: FileList) => {
        const { validFiles, invalidFiles } = validateFiles(files);
        
        if (invalidFiles.length > 0) {
            const invalidExtensions = Array.from(new Set(invalidFiles.map(file => 
                file.substring(file.lastIndexOf('.')).toLowerCase()
            )));
            toast({
                variant: "destructive",
                title: "Invalid file type",
                description: `Unsupported extensions: ${invalidExtensions.join(', ')}`
            });
        }
        
        if (validFiles.length > 0) {
            const currentFileCount = selectedFiles.length;
            const totalAfterAdd = currentFileCount + validFiles.length;
            
            if (totalAfterAdd > 5) {
                toast({
                    variant: "destructive",
                    title: "Too many files",
                    description: "Maximum of 5 documents allowed."
                });
                return;
            }
            
            const newFiles = validFiles.map(file => ({
                file,
                tags: [],
                showTagInput: false,
                id: Math.random().toString(36).substring(7)
            }));
            
            setSelectedFiles((prev) => [...prev, ...newFiles]);
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

    const uploadFiles = async () => {
        if (selectedFiles.length === 0) return;
        
        setIsUploading(true);
        setUploadProgress(0);
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
                
                // Pass tags if the backend supports it, for now we assume it's part of metadata or separate call
                // The uploadDocs function signature is: uploadDocs(files: {name: string, content: string}[]): Promise<any>
                // If we need to send tags, we might need to update the API or use a different endpoint.
                // For this implementation, we'll stick to the existing uploadDocs for file content.
                // Ideally, tags should be associated with the document after upload or during embedding.
                
                await uploadDocs([{ name: item.file.name, content: base64 }]);
                
                uploadedCount++;
                setUploadProgress(Math.round((uploadedCount / selectedFiles.length) * 90));
            }

            const docs = selectedFiles.map((item) => ({
                source_name: item.file.name,
                tags: item.tags
            }));
            
            const res = await embedDocs(docs, user?.username || 'default');
            
            const issues = res?.registration?.issues || [];
            if (issues.length > 0) {
                issues.forEach((issue: any) => {
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
                description: "Documents uploaded and processed successfully.",
            });
            
            if (fetchDocuments) await fetchDocuments();
            setSelectedFiles([]);
            setShowUploadModal(false);
            
        } catch (err) {
            console.error("Upload failed", err);
            const message = (err as Error)?.message || "There was an error uploading your documents.";
            toast({
                variant: "destructive",
                title: "Upload failed",
                description: message,
            });
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
                            onClick={uploadFiles}
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
                        selectedFiles.length >= 5 ? "opacity-50 cursor-not-allowed" : "cursor-pointer"
                    )}
                    onDragEnter={selectedFiles.length < 5 ? handleDragEnter : undefined}
                    onDragLeave={selectedFiles.length < 5 ? handleDragLeave : undefined}
                    onDragOver={selectedFiles.length < 5 ? handleDragOver : undefined}
                    onDrop={selectedFiles.length < 5 ? handleDrop : undefined}
                    onClick={selectedFiles.length < 5 ? () => fileInputRef.current?.click() : undefined}
                >
                    <CardContent className="flex flex-col items-center justify-center h-full min-h-[300px] py-12 text-center">
                        <input 
                            ref={fileInputRef}
                            type="file" 
                            multiple 
                            className="hidden" 
                            onChange={handleFileSelect}
                            disabled={selectedFiles.length >= 5 || isUploading}
                        />
                        
                        <div className={cn(
                            "w-20 h-20 rounded-full flex items-center justify-center mb-6 transition-transform duration-300",
                            isDragging ? "bg-primary/20 scale-110" : "bg-background shadow-sm border border-border"
                        )}>
                            <Upload className={cn("h-10 w-10", isDragging ? "text-primary" : "text-muted-foreground")} />
                        </div>
                        
                        <h3 className="text-xl font-semibold text-foreground mb-2">
                            {selectedFiles.length >= 5 ? "Maximum files reached" : "Click to upload or drag and drop"}
                        </h3>
                        <p className="text-sm text-muted-foreground max-w-xs mx-auto">
                            {selectedFiles.length >= 5 
                                ? "Please remove a file to add another." 
                                : `Supported formats: ${supportedExtensions.map(ext => ext.replace('.', '').toUpperCase()).join(', ')}`}
                        </p>
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
