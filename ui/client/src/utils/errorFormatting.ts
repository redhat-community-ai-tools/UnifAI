/**
 * Utilities for formatting error messages from backend responses
 */

export interface PipelineIssue {
  doc_name?: string;
  issue_type?: string;
  message?: string;
}

/**
 * Formats error messages from pipeline registration issues
 * Handles file size errors and other error types
 */
export function formatPipelineError(issue: PipelineIssue): { title: string; description: string } {
  const issueType = String(issue.issue_type || "");
  const message = String(issue.message || "");
  const docName = String(issue.doc_name || "");
  
  const title = issueType ? issueType.toUpperCase() : "Upload issue";
  
  // Format description with document name and error message
  let description = "";
  if (docName) {
    description = `Document "${docName}"`;
  }
  
  if (message) {
    // Check if message contains file size error
    if (message.toLowerCase().includes("file size") || message.toLowerCase().includes("exceeds maximum")) {
      // Extract file size and max size from message if available
      const sizeMatch = message.match(/File size \(([\d.]+) MB\) exceeds maximum allowed size \(([\d.]+) MB\)/i);
      if (sizeMatch) {
        const [, fileSize, maxSize] = sizeMatch;
        description = `${description ? description + " " : ""}embedding failed: file size (${fileSize} MB) exceeds the allowed size (${maxSize} MB).`;
      } else {
        description = `${description ? description + " " : ""}embedding failed: ${message}`;
      }
    } else {
      description = `${description ? description + " " : ""}${message}`;
    }
  }
  
  return {
    title,
    description: description || "An error occurred during embedding.",
  };
}