import React, { memo, useCallback, useMemo, useRef, useEffect } from 'react';
import { ChevronDown, ChevronRight, Wrench } from "lucide-react";
import { StreamLogEntry, ToolEntry } from './types';
import { StatusIndicator } from './StatusIndicator';
import { preprocessText, MarkdownComponents } from "./helpers/TextComponents";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

interface StreamLogItemProps {
  log: StreamLogEntry;
  messageId: string;
  onToggleExpansion: (messageId: string, nodeId: string) => void;
}

// Separate component for tool call display
const ToolCallItem = ({ tool }: { tool: ToolEntry }) => (
  <div className="flex items-start space-x-3 p-3 bg-blue-950/30 border border-blue-800/40 rounded-md mb-2 last:mb-0">
    <div className="flex-shrink-0 mt-0.5">
      <Wrench className="h-4 w-4 text-blue-400" />
    </div>
    <div className="flex-1 min-w-0">
      <div className="flex items-center space-x-2 mb-1">
        <span className="text-sm font-medium text-blue-300">
          Tool Calling ({tool.name})
        </span>
      </div>
      
      {/* Args section */}
      {tool.args && Object.keys(tool.args).length > 0 && (
        <div className="mb-2">
          <span className="text-xs font-medium text-blue-400 uppercase tracking-wide block mb-1">
            args:
          </span>
          <div className="bg-gray-800/50 rounded p-2">
            <table className="w-full text-xs">
              <tbody>
                {Object.entries(tool.args).map(([key, value]) => (
                  <tr key={key} className="border-b border-gray-700 last:border-b-0">
                    <td className="text-gray-400 pr-3 py-1 font-mono">{key}</td>
                    <td className="text-gray-300 py-1 font-mono">
                      {typeof value === 'object' ? JSON.stringify(value) : String(value)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
      
      {/* {tool.output && (
        <div className="text-sm text-gray-300">
          <span className="text-gray-400">result:</span>{' '}
          <span className="font-mono bg-gray-800/50 px-1.5 py-0.5 rounded text-xs">
            {tool.output}
          </span>
        </div>
      )} */}
    </div>
  </div>
);

ToolCallItem.displayName = 'ToolCallItem';

// Separate component for tools section
const ToolsSection = ({ tools }: { tools: ToolEntry[] }) => {
  if (!tools || tools.length === 0) return null;

  return (
    <div className="px-3 pb-2">
      <div className="mb-2">
        <span className="text-xs font-medium text-blue-400 uppercase tracking-wide">
          Tool Calls ({tools.length})
        </span>
      </div>
      <div className="space-y-2">
        {tools.map((tool, index) => (
          <ToolCallItem key={`${tool.name}-${index}`} tool={tool} />
        ))}
      </div>
    </div>
  );
};

ToolsSection.displayName = 'ToolsSection';

// Separate component for message content with performance optimization
const MessageContent = memo(({ 
  message, 
  status, 
  hasMoreThanTwoLines, 
  previewText,
  isExpanded,
  onToggleExpansion
}: {
  message: string;
  status: string;
  hasMoreThanTwoLines: boolean;
  previewText: string;
  isExpanded: boolean;
  onToggleExpansion?: () => void;
}) => {
  const textRef = useRef<HTMLDivElement>(null);
  const textColorClass = status === 'error' ? 'text-[#FF1744]' : 'text-gray-300';
  
  // Update text content directly in DOM for collapsed view only to avoid re-renders
  useEffect(() => {
    if (textRef.current && !isExpanded) {
      if (textRef.current.textContent !== previewText) {
        textRef.current.textContent = previewText;
      }
    }
  }, [previewText, isExpanded]);
  
  const handleToggleMessage = useCallback(() => {
    if (onToggleExpansion) {
      onToggleExpansion();
    }
  }, [onToggleExpansion]);
  
  return (
    <div className="w-full">
      <div className={`text-sm whitespace-pre-wrap break-words w-full ${textColorClass}`}>
        {isExpanded ? (
          <ReactMarkdown
            components={MarkdownComponents}
            remarkPlugins={[remarkGfm]}
          >
            {preprocessText(message)}
          </ReactMarkdown>
        ) : (
          <div 
            ref={textRef}
            className="font-mono"
          >
            {previewText}
          </div>
        )}
      </div>
      
      {hasMoreThanTwoLines && !isExpanded && onToggleExpansion && (
        <button
          onClick={handleToggleMessage}
          className="mt-2 text-xs text-blue-400 hover:text-blue-300 transition-colors flex items-center space-x-1 group"
        >
          <span>Show full log</span>
          <ChevronRight className="h-3 w-3 group-hover:scale-110 transition-transform" />
        </button>
      )}
    </div>
  );
}, (prevProps, nextProps) => {
  // Only re-render on structural changes, not content changes
  return (
    prevProps.status === nextProps.status &&
    prevProps.hasMoreThanTwoLines === nextProps.hasMoreThanTwoLines &&
    prevProps.isExpanded === nextProps.isExpanded &&
    prevProps.onToggleExpansion === nextProps.onToggleExpansion
    // Deliberately excluding message and previewText to avoid re-renders
  );
});

MessageContent.displayName = 'MessageContent';

export const StreamLogItem = memo(({ log, messageId, onToggleExpansion }: StreamLogItemProps) => {
  const expandedContentRef = useRef<HTMLDivElement>(null);
  const collapsedContentRef = useRef<HTMLDivElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  const handleToggle = useCallback(() => {
    onToggleExpansion(messageId, log.nodeId);
  }, [messageId, log.nodeId, onToggleExpansion]);

  const getStatusText = useCallback((status: string) => {
    switch (status) {
      case 'processing': return 'Generating...';
      case 'complete': return 'Complete';
      case 'error': return 'Error';
      default: return 'Unknown';
    }
  }, []);

  // Memoize message analysis to avoid recalculation
  const messageAnalysis = useMemo(() => {
    const message = log.message || 'Processing...';
    const lines = message.split('\n');
    const hasMoreThanTwoLines = lines.length > 2;
    const previewText = hasMoreThanTwoLines ? lines.slice(0, 2).join('\n') + '...' : message;
    
    return {
      message,
      hasMoreThanTwoLines,
      previewText
    };
  }, [log.message]);

  const hasTools = log.tools && log.tools.length > 0;
  // The expansion is now handled purely by the style attributes in JSX

  return (
    <div 
      ref={containerRef}
      className="border border-gray-700 rounded-lg overflow-hidden w-full"
      data-node-id={log.nodeId}
    >
      <div
        className="flex items-center justify-between p-3 bg-gray-800 cursor-pointer hover:bg-gray-750 transition-colors w-full"
        onClick={handleToggle}
      >
        <div className="flex items-center space-x-2">
          <StatusIndicator status={log.status} />
          <span className="text-sm font-medium text-gray-200">
            {log.nodeName}
          </span>
          <span className="text-xs text-gray-400">
            {getStatusText(log.status)}
          </span>
          {hasTools && (
            <div className="flex items-center space-x-1">
              <Wrench className="h-3 w-3 text-blue-400" />
              <span className="text-xs text-blue-400">
                {log.tools.length} tool{log.tools.length !== 1 ? 's' : ''}
              </span>
            </div>
          )}
        </div>
        {log.isExpanded ? (
          <ChevronDown className="h-4 w-4 text-gray-400" />
        ) : (
          <ChevronRight className="h-4 w-4 text-gray-400" />
        )}
      </div>
      
      {/* Expanded content - always rendered but controlled via CSS */}
      <div 
        ref={expandedContentRef}
        className="w-full transition-all duration-200 ease-in-out"
        style={{ 
          display: log.isExpanded ? 'block' : 'none',
          opacity: log.isExpanded ? 1 : 0,
          maxHeight: log.isExpanded ? 'none' : '0px',
          overflow: 'hidden'
        }}
      >
        {/* Tools Section */}
        {hasTools && (
          <div className="bg-gray-900 border-t border-gray-700 w-full">
            <ToolsSection tools={log.tools} />
          </div>
        )}
        
        {/* Message Section */}
        <div className={`p-3 bg-gray-900 w-full ${hasTools ? '' : 'border-t border-gray-700'}`}>
          <MessageContent
            message={messageAnalysis.message}
            status={log.status}
            hasMoreThanTwoLines={messageAnalysis.hasMoreThanTwoLines}
            previewText={messageAnalysis.previewText}
            isExpanded={true}
          />
        </div>
      </div>
      
      {/* Collapsed content - always rendered but controlled via CSS */}
      <div 
        ref={collapsedContentRef}
        className="p-3 bg-gray-900 border-t border-gray-700 w-full"
        style={{ display: log.isExpanded ? 'none' : 'block' }}
      >
        <MessageContent
          message={messageAnalysis.message}
          status={log.status}
          hasMoreThanTwoLines={messageAnalysis.hasMoreThanTwoLines}
          previewText={messageAnalysis.previewText}
          isExpanded={false}
          onToggleExpansion={handleToggle}
        />
      </div>
    </div>
  );
}, (prevProps, nextProps) => {
  // Custom comparison function for memo - prevent re-renders on expansion changes
  const prevLog = prevProps.log;
  const nextLog = nextProps.log;
  
  // Quick checks for structural changes
  if (
    prevLog.nodeId !== nextLog.nodeId ||
    prevProps.messageId !== nextProps.messageId ||
    prevLog.status !== nextLog.status ||
    prevLog.nodeName !== nextLog.nodeName ||
    prevLog.isExpanded !== nextLog.isExpanded
  ) {
    return false;
  }

  // Check message changes
  if (prevLog.message !== nextLog.message) {
    return false;
  }
  
  // Efficient tools comparison
  const prevTools = prevLog.tools || [];
  const nextTools = nextLog.tools || [];
  
  if (prevTools.length !== nextTools.length) {
    return false;
  }
  
  // Quick comparison using tool IDs and outputs
  for (let i = 0; i < prevTools.length; i++) {
    if (prevTools[i]?.id !== nextTools[i]?.id || 
        prevTools[i]?.output !== nextTools[i]?.output) {
      return false;
    }
  }
  
  return true;
});

StreamLogItem.displayName = 'StreamLogItem';