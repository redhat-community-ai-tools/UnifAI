import React, { useState } from "react";
import { Copy, Check, Download } from "lucide-react";
import { Button } from "@/components/ui/button";
import ReactMarkdown from "react-markdown";
import { DownloadFile } from "@/utils/guideLoader";
import { handleDownloadFile } from "../shared/helpers";

interface Step {
  step: number;
  title: string;
  body: string;
}

interface GuideRendererProps {
  steps: Step[];
  title: string;
  description?: string;
  downloadFiles?: DownloadFile[];
}

export const GuideRenderer: React.FC<GuideRendererProps> = ({
  steps,
  title,
  description,
  downloadFiles = [],
}) => {
  const [commandCopied, setCommandCopied] = useState(false);
  const [downloadingFile, setDownloadingFile] = useState<string | null>(null);

  const copyCommandToClipboard = (command: string) => {
    navigator.clipboard.writeText(command).then(() => {
      setCommandCopied(true);
      setTimeout(() => setCommandCopied(false), 2000);
    }).catch(err => {
      console.error('Failed to copy:', err);
    });
  };


  // Check if a link points to a downloadable file
  const isDownloadableFile = (href: string): DownloadFile | null => {
    if (!downloadFiles || downloadFiles.length === 0) {
      return null;
    }
    
    // Check if the href matches any download file path
    for (const downloadFile of downloadFiles) {
      if (href === downloadFile.path || href.includes(downloadFile.filename)) {
        return downloadFile;
      }
    }
    
    return null;
  };

  // Extract code blocks from markdown and handle special actions
  const renderMarkdown = (content: string) => {
    return (
      <ReactMarkdown
        components={{
          code({ node, inline, className, children, ...props }: any) {
            const match = /language-(\w+)/.exec(className || "");
            const codeString = String(children).replace(/\n$/, "");
            
            if (!inline && match) {
              // Code blocks only have copy button, no download button
              return (
                <div className="relative">
                  <div className="absolute top-2 right-2 flex gap-2 z-10">
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      onClick={() => copyCommandToClipboard(codeString)}
                      className="h-7 px-2 text-xs bg-background-dark/80 hover:bg-background-dark"
                      title="Copy command"
                    >
                      {commandCopied ? (
                        <Check className="w-3 h-3 text-green-400" />
                      ) : (
                        <Copy className="w-3 h-3" />
                      )}
                    </Button>
                  </div>
                  <pre className="bg-background-dark p-4 rounded-md overflow-x-auto">
                    <code className={`language-${match[1]} text-sm font-mono text-foreground`} {...props}>
                      {codeString}
                    </code>
                  </pre>
                </div>
              );
            }
            
            return (
              <code className={className} {...props}>
                {children}
              </code>
            );
          },
          a({ node, href, children, ...props }: any) {
            // Check if this link points to a downloadable file
            const downloadableFile = isDownloadableFile(href || "");
            
            if (downloadableFile) {
              return (
                <a
                  href="#"
                  onClick={(e) => {
                    e.preventDefault();
                    handleDownloadFile(downloadableFile, setDownloadingFile);
                  }}
                  className="text-primary hover:underline cursor-pointer"
                  {...props}
                >
                  {children}
                </a>
              );
            }
            
            return (
              <a
                href={href}
                target="_blank"
                rel="noopener noreferrer"
                className="text-primary hover:underline"
                {...props}
              >
                {children}
              </a>
            );
          },
          h2({ node, children, ...props }: any) {
            return (
              <h2 className="text-lg font-semibold text-foreground mt-6 mb-3" {...props}>
                {children}
              </h2>
            );
          },
          h3({ node, children, ...props }: any) {
            return (
              <h3 className="text-base font-semibold text-foreground mt-4 mb-2" {...props}>
                {children}
              </h3>
            );
          },
          ul({ node, children, ...props }: any) {
            return (
              <ul className="list-disc list-inside space-y-1 text-sm text-muted-foreground ml-4" {...props}>
                {children}
              </ul>
            );
          },
          ol({ node, children, ...props }: any) {
            return (
              <ol className="list-decimal list-inside space-y-1 text-sm text-muted-foreground ml-4" {...props}>
                {children}
              </ol>
            );
          },
          li({ node, children, ...props }: any) {
            return (
              <li className="text-sm text-muted-foreground" {...props}>
                {children}
              </li>
            );
          },
          p({ node, children, ...props }: any) {
            return (
              <p className="text-sm text-muted-foreground mb-3" {...props}>
                {children}
              </p>
            );
          },
          strong({ node, children, ...props }: any) {
            return (
              <strong className="font-semibold text-foreground" {...props}>
                {children}
              </strong>
            );
          },
        }}
      >
        {content}
      </ReactMarkdown>
    );
  };

  return (
    <div className="space-y-6">
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-foreground mb-2">{title}</h1>
        {description && (
          <p className="text-muted-foreground text-base">{description}</p>
        )}
      </div>

      <div className="prose prose-invert max-w-none">
        {steps.map((step, index) => (
          <div key={step.step} className={index > 0 ? "mt-8" : ""}>
            <h2 className="text-2xl font-bold text-foreground mb-4">
              Step {step.step}: {step.title}
            </h2>
            <div className="text-base text-muted-foreground">
              {renderMarkdown(step.body)}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
