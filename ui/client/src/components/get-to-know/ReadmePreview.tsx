import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { ChevronDown, ChevronUp, BookOpen } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { readmeContent } from "@/config/platformResources";

export default function ReadmePreview() {
  const [isExpanded, setIsExpanded] = useState(true);

  return (
    <section className="mb-10">
      <Card className="bg-background-card border-gray-800 overflow-hidden">
        <CardHeader className="border-b border-gray-800 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-primary/10">
                <BookOpen className="w-5 h-5 text-primary" />
              </div>
              <CardTitle className="text-lg font-semibold text-white">
                What is unifAI?
              </CardTitle>
            </div>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setIsExpanded(!isExpanded)}
              className="text-gray-400 hover:text-white"
            >
              {isExpanded ? (
                <>
                  <span className="mr-2 text-sm">Collapse</span>
                  <ChevronUp className="w-4 h-4" />
                </>
              ) : (
                <>
                  <span className="mr-2 text-sm">Expand</span>
                  <ChevronDown className="w-4 h-4" />
                </>
              )}
            </Button>
          </div>
        </CardHeader>
        <AnimatePresence>
          {isExpanded && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: "auto", opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              transition={{ duration: 0.3 }}
            >
              <CardContent className="p-6 max-h-[600px] overflow-y-auto">
                <div className="prose prose-invert prose-sm max-w-none">
                  <ReactMarkdown
                    remarkPlugins={[remarkGfm]}
                    components={{
                      h1: ({ children }) => (
                        <h1 className="text-2xl font-bold text-white mb-4 mt-0">
                          {children}
                        </h1>
                      ),
                      h2: ({ children }) => (
                        <h2 className="text-xl font-semibold text-white mt-6 mb-3 pb-2 border-b border-gray-800">
                          {children}
                        </h2>
                      ),
                      h3: ({ children }) => (
                        <h3 className="text-lg font-medium text-white mt-4 mb-2">
                          {children}
                        </h3>
                      ),
                      p: ({ children }) => (
                        <p className="text-gray-300 leading-relaxed mb-3">
                          {children}
                        </p>
                      ),
                      ul: ({ children }) => (
                        <ul className="list-disc list-inside text-gray-300 space-y-1 mb-4 ml-2">
                          {children}
                        </ul>
                      ),
                      ol: ({ children }) => (
                        <ol className="list-decimal list-inside text-gray-300 space-y-1 mb-4 ml-2">
                          {children}
                        </ol>
                      ),
                      li: ({ children }) => (
                        <li className="text-gray-300">{children}</li>
                      ),
                      strong: ({ children }) => (
                        <strong className="font-semibold text-white">{children}</strong>
                      ),
                      code: ({ children }) => (
                        <code className="px-1.5 py-0.5 rounded bg-gray-800 text-primary text-sm font-mono">
                          {children}
                        </code>
                      ),
                      pre: ({ children }) => (
                        <pre className="bg-gray-900 rounded-lg p-4 overflow-x-auto mb-4 border border-gray-800">
                          {children}
                        </pre>
                      ),
                    }}
                  >
                    {readmeContent}
                  </ReactMarkdown>
                </div>
              </CardContent>
            </motion.div>
          )}
        </AnimatePresence>
      </Card>
    </section>
  );
}