import { useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { FaFileAlt, FaUpload, FaTimes } from "react-icons/fa";
import { Progress } from "@/components/ui/progress";
import { ProcessingOptions } from "./ProcessingOptions";
import { embedDocs, uploadDocs, fetchDocuments } from "@/api/docs";
import { useToast } from "@/hooks/use-toast";
import { useQueryClient } from "@tanstack/react-query";

interface UploadTabProps {
    setShowUploadModal: (showUploadModal: boolean) => void;
    fetchDocuments: any;
}

export const UploadTab: React.FC<UploadTabProps> = ({
    setShowUploadModal, fetchDocuments
}) => {
    const [isDragging, setIsDragging] = useState(false);
    const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
    const [isUploading, setIsUploading] = useState(false);
    const [uploadProgress, setUploadProgress] = useState(0);
    const [error, setError] = useState<string>("");
    const [skippedDup, setSkippedDup] = useState<any>();
    
    const { toast } = useToast();
    const queryClient = useQueryClient();

    const handleDragEnter = (e: React.DragEvent) => {
        e.preventDefault();
        setIsDragging(true);
    };

    const handleDragLeave = (e: React.DragEvent) => {
        e.preventDefault();
        setIsDragging(false);
    };

    const handleDragOver = (e: React.DragEvent) => {
        e.preventDefault();
    };

    const handleDrop = (e: React.DragEvent) => {
        e.preventDefault();
        setIsDragging(false);
        handleFiles(e.dataTransfer.files);
    };

    const handleFiles = (files: FileList) => {
        setSelectedFiles((prev) => [...prev, ...Array.from(files)]);
    };

    const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
        handleFiles(e.target.files ? e.target.files : new FileList());
    };

    const uploadFiles = async (files: File[]) => {
        setIsUploading(true);
        setUploadProgress(0);
        let uploadedCount = 0;

        try {
            for (const file of files) {
                const base64 = await new Promise<string>((resolve, reject) => {
                    const reader = new FileReader();
                    reader.onload = () => {
                        const result = reader.result as string;
                        resolve(result.split(",")[1]);
                    };
                    reader.onerror = reject;
                    reader.readAsDataURL(file);
                });
                
                await uploadDocs([{ name: file.name, content: base64 }])

                uploadedCount += 1;
                setUploadProgress(uploadedCount);
            }

            setIsUploading(false);
            setShowUploadModal(false);
        } catch (err) {
            console.error("Upload failed", err);
            setError("Upload failed. Please try again.");
            setIsUploading(false);
        }
    };

    const startPipeline = async (docs: {source_name: string}[]) => {
        try {
            await embedDocs(docs)
            queryClient.invalidateQueries({ queryKey: ['documents'] });
            await fetchDocuments();
        } catch (error) {
            console.error(error);
            setError((error as Error).message);
        }
    }

    const handleSubmit = async () => {
        if (selectedFiles.length === 0) return;

        await uploadFiles(selectedFiles);

        const docs = selectedFiles.map((file) => ({source_name: file.name}));

        await startPipeline(docs);
        await fetchDocuments();
        setSelectedFiles([]);
    };


    return (
        <div className="space-y-6">
            <Card className="bg-background-card shadow-card border-gray-800 w-full">
                <CardContent className="p-6">
                    <div className="flex items-center justify-between mb-6">
                        <div className="flex items-center">
                            <FaFileAlt className="text-accent text-2xl mr-3" />
                            <h3 className="text-lg font-heading font-semibold">
                                Upload Documents
                            </h3>
                        </div>
                        <div className="flex justify-between mb-4">
                            <Button onClick={() => setShowUploadModal(false)}>Cancel</Button>
                        </div>
                    </div>

                    <div
                        className={`max-h-[400px] overflow-y-auto border-2 border-dashed rounded-lg flex flex-col items-center justify-center cursor-pointer transition-colors ${isDragging ? "border-primary bg-primary bg-opacity-5" : "border-gray-700 hover:border-gray-600"}`}
                        onDragEnter={handleDragEnter}
                        onDragLeave={handleDragLeave}
                        onDragOver={handleDragOver}
                        onDrop={handleDrop}
                        onClick={() =>document.getElementById("file-upload")?.click()}
                    >
                        {!isUploading ? (
                            <>
                                <div className="w-16 h-16 bg-background-surface rounded-full flex items-center justify-center mb-4">
                                    <FaUpload className="text-accent text-xl" />
                                </div>
                                <p className="font-semibold mb-1">
                                    Drag and drop files here
                                </p>
                                <p className="text-sm text-gray-400">
                                    or click to browse files
                                </p>
                                <p className="text-xs text-gray-500 mt-4">
                                    Supported formats: PDF, DOCX, TXT
                                </p>
                                <input id="file-upload" type="file" multiple className="hidden" onChange={handleFileSelect}/>
                            </>
                        ) : (
                            <div className="w-full px-8">
                                <div className="flex items-center justify-between mb-2">
                                    <span className="font-semibold">
                                        Uploading files...
                                    </span>
                                    <Button variant="ghost" size="sm" onClick={() => setIsUploading(false)}>
                                        <FaTimes className="h-4 w-4" />
                                    </Button>
                                </div>
                                <Progress value={(uploadProgress / selectedFiles.length) * 100} className="h-2 mb-2" />

                                <div className="flex justify-between text-xs text-gray-400">
                                    <span className="text-sm text-gray-300">
                                        {uploadProgress === selectedFiles.length
                                            ? "Upload complete!"
                                            : `Uploading ${uploadProgress} of ${selectedFiles.length} files...`}
                                    </span>
                                </div>
                            </div>
                        )}

                        {/* File list after upload */}
                        {selectedFiles.length > 0 && (
                            <ul className="mt-4 space-y-2">
                                {selectedFiles.map((file, idx) => (
                                    <li key={idx} className="flex items-center justify-between text-gray-300 bg-background-surface px-3 py-2 rounded">
                                        <span className="truncate max-w-[80%]">{file.name}</span>
                                        <button
                                            onClick={(e) => {
                                                e.stopPropagation(); 
                                                setSelectedFiles((prev) =>
                                                    prev.filter((_, i) => i !== idx)
                                                );
                                            }}
                                            className="text-gray-400 hover:text-red-500 transition-colors"
                                            title="Remove file"
                                        >
                                            <FaTimes className="w-4 h-4" />
                                        </button>
                                    </li>
                                ))}
                            </ul>
                        )}
                        {error && <p className="text-red-500 mt-4">{error}</p>}
                    </div>
                </CardContent>
                {selectedFiles.length > 0 && !isUploading && (
                    <div className="flex justify-end p-4">
                        <Button disabled={selectedFiles.length === 0} onClick={handleSubmit}>
                            Submit
                        </Button>
                    </div>
                )}
            </Card>

            <ProcessingOptions />
        </div>
    )
}

