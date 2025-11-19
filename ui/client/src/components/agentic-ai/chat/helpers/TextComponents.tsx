// Custom markdown components for styling
export const MarkdownComponents = {
  // Headings
  h1: ({ children, ...props }: any) => (
    <h1 className="text-xl font-bold mb-3 mt-4 text-gray-100" {...props}>{children}</h1>
  ),
  h2: ({ children, ...props }: any) => (
    <h2 className="text-lg font-semibold mb-2 mt-3 text-gray-100" {...props}>{children}</h2>
  ),
  h3: ({ children, ...props }: any) => (
    <h3 className="text-base font-semibold mb-2 mt-2 text-gray-100" {...props}>{children}</h3>
  ),
  
  // Text formatting
  strong: ({ children, ...props }: any) => (
    <strong className="font-bold text-gray-100" {...props}>{children}</strong>
  ),
  em: ({ children, ...props }: any) => (
    <em className="italic text-gray-100" {...props}>{children}</em>
  ),
  
  // Lists - Simplified with better spacing
  ul: ({ children, ...props }: any) => (
    <ul className="list-disc ml-6 mb-3 space-y-1 text-gray-200" {...props}>{children}</ul>
  ),
  ol: ({ children, ...props }: any) => (
    <ol className="list-decimal ml-6 mb-3 space-y-1 text-gray-200" {...props}>{children}</ol>
  ),
  li: ({ children, ...props }: any) => (
    <li className="text-gray-200 leading-normal pl-1" {...props}>{children}</li>
  ),
  
  // Code blocks - Simplified approach
  code: ({ inline, className, children, ...props }: any) => {
    // Block code (triple backticks)
    if (!inline) {
      return (
        <pre className="bg-gray-900 text-cyan-300 p-3 rounded-lg overflow-x-auto mb-3 mt-2">
          <code className="font-mono text-sm">{children}</code>
        </pre>
      );
    }
    
    // Inline code (single backticks) - Always render inline
    return (
      <code 
        className="bg-gray-800 text-cyan-300 px-1.5 py-0.5 mx-0.5 rounded text-sm font-mono" 
        {...props}
      >
        {children}
      </code>
    );
  },
  
  // Blockquotes
  blockquote: ({ children, ...props }: any) => (
    <blockquote className="border-l-4 border-primary pl-4 py-1 my-2 italic text-gray-300" {...props}>
      {children}
    </blockquote>
  ),
  
  // Tables
  table: ({ children, ...props }: any) => (
    <div className="overflow-x-auto my-3">
      <table className="min-w-full border-collapse border border-gray-700" {...props}>
        {children}
      </table>
    </div>
  ),
  th: ({ children, ...props }: any) => (
    <th className="border border-gray-700 px-3 py-2 bg-gray-800 text-gray-100 font-semibold text-left" {...props}>
      {children}
    </th>
  ),
  td: ({ children, ...props }: any) => (
    <td className="border border-gray-700 px-3 py-2 text-gray-200" {...props}>
      {children}
    </td>
  ),
  
  // Paragraphs
  p: ({ children, ...props }: any) => (
    <p className="mb-3 text-gray-200 leading-relaxed" {...props}>{children}</p>
  ),
  
  // Links
  a: ({ href, children, ...props }: any) => (
    <a 
      href={href} 
      target="_blank" 
      rel="noopener noreferrer"
      className="text-primary hover:text-primary/80 underline"
      {...props}
    >
      {children}
    </a>
  ),
};

// Minimal preprocessing - let react-markdown handle most formatting
export const preprocessText = (text: string): string => {
  // Only convert literal \n to actual newlines
  return text.replace(/\\n/g, '\n').trim();
};