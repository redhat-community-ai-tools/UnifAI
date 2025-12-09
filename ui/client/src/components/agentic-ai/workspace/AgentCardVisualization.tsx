import React, { useState } from 'react';
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { 
  ChevronDown, 
  ChevronRight, 
  Code2, 
  Info, 
  Sparkles,
  FileJson,
  CheckCircle2,
  Layers
} from 'lucide-react';

interface Skill {
  id: string;
  name: string;
  description: string;
  tags: string[];
  examples?: string[] | null;
  input_modes?: string[] | null;
  output_modes?: string[] | null;
  security?: Array<Record<string, string[]>> | null;
}

interface AgentCard {
  name: string;
  version: string;
  description?: string;
  skills?: Skill[];
}

interface AgentCardVisualizationProps {
  agentCard: AgentCard | null;
  isLoading?: boolean;
}

export const AgentCardVisualization: React.FC<AgentCardVisualizationProps> = ({
  agentCard,
  isLoading = false
}) => {
  if (isLoading) {
    return (
      <Card className="bg-gradient-to-br from-blue-950/30 to-purple-950/30 border-blue-800/50">
        <CardContent className="pt-6">
          <div className="flex items-center justify-center py-8">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-400"></div>
            <span className="ml-3 text-gray-400">Loading agent card...</span>
          </div>
        </CardContent>
      </Card>
    );
  }

  if (!agentCard) {
    return (
      <Card className="bg-background-dark border-gray-700">
        <CardContent className="pt-6">
          <div className="flex items-center justify-center py-8 text-gray-500">
            <Info className="h-5 w-5 mr-2" />
            <span>No agent card available.</span>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-4 animate-in fade-in duration-500">
      {/* Agent Header Card */}
      <Card className="bg-gradient-to-br from-blue-950/40 to-purple-950/40 border-blue-800/50 shadow-lg">
        <CardHeader className="pb-3">
          <div className="flex items-start justify-between">
            <div className="flex items-center gap-3">
              <div className="bg-blue-500/20 p-2 rounded-lg border border-blue-500/30">
                <Sparkles className="h-6 w-6 text-blue-400" />
              </div>
              <div>
                <CardTitle className="text-2xl font-bold text-white flex items-center gap-2">
                  {agentCard.name}
                  <CheckCircle2 className="h-5 w-5 text-green-400" />
                </CardTitle>
                <CardDescription className="text-gray-400 mt-1">
                  A2A Agent Node
                </CardDescription>
              </div>
            </div>
            <Badge variant="secondary" className="bg-blue-900/50 text-blue-300 border-blue-700">
              v{agentCard.version}
            </Badge>
          </div>
        </CardHeader>
        <CardContent>
          {agentCard.description && (
            <p className="text-gray-300 leading-relaxed">
              {agentCard.description}
            </p>
          )}
          
          {agentCard.skills && agentCard.skills.length > 0 && (
            <div className="mt-4 flex items-center gap-2">
              <Layers className="h-4 w-4 text-purple-400" />
              <span className="text-sm text-gray-400">
                {agentCard.skills.length} skill{agentCard.skills.length !== 1 ? 's' : ''} available
              </span>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Skills Section */}
      {agentCard.skills && agentCard.skills.length > 0 && (
        <div className="space-y-3">
          <div className="flex items-center gap-2 px-1">
            <Code2 className="h-5 w-5 text-purple-400" />
            <h3 className="text-lg font-semibold text-white">Available Skills</h3>
          </div>
          
          <div className="grid gap-3">
            {agentCard.skills.map((skill, index) => (
              <SkillCard key={index} skill={skill} index={index} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

interface SkillCardProps {
  skill: Skill;
  index: number;
}

const SkillCard: React.FC<SkillCardProps> = ({ skill, index }) => {
  const [isExpanded, setIsExpanded] = useState(false);
  const hasAdditionalInfo = skill.examples || skill.input_modes || skill.output_modes || skill.security;

  return (
    <Card className="bg-background-dark border-gray-700 hover:border-gray-600 transition-colors">
      <CardHeader className="pb-3">
        <div className="space-y-3">
          {/* Skill Header */}
          <div className="flex items-start justify-between gap-4">
            <div className="flex-1">
              <div className="flex items-center gap-2 mb-2">
                <Badge variant="outline" className="bg-purple-950/30 text-purple-300 border-purple-700">
                  #{index + 1}
                </Badge>
                <CardTitle className="text-lg font-mono text-blue-300">
                  {skill.name}
                </CardTitle>
              </div>
              <CardDescription className="text-gray-400 leading-relaxed">
                {skill.description}
              </CardDescription>
            </div>
            
            {hasAdditionalInfo && (
              <button
                type="button"
                onClick={() => setIsExpanded(!isExpanded)}
                className="flex items-center gap-1 px-3 py-1.5 rounded-md bg-gray-800 hover:bg-gray-700 text-gray-300 text-xs transition-colors"
                aria-label="Toggle skill details"
              >
                {isExpanded ? (
                  <>
                    <ChevronDown className="h-4 w-4" />
                    Hide Details
                  </>
                ) : (
                  <>
                    <ChevronRight className="h-4 w-4" />
                    View Details
                  </>
                )}
              </button>
            )}
          </div>

          {/* Tags */}
          {skill.tags && skill.tags.length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {skill.tags.map((tag, idx) => (
                <Badge 
                  key={idx} 
                  variant="secondary" 
                  className="bg-blue-950/30 text-blue-300 border-blue-800/50 text-xs"
                >
                  {tag}
                </Badge>
              ))}
            </div>
          )}

          {/* Skill ID (subtle) */}
          <div className="text-xs text-gray-500 font-mono">
            ID: {skill.id}
          </div>

          {/* Expanded Details */}
          {isExpanded && hasAdditionalInfo && (
            <div className="pt-3 space-y-3 border-t border-gray-700">
              {/* Examples */}
              {skill.examples && skill.examples.length > 0 && (
                <div>
                  <h5 className="text-sm font-semibold text-gray-300 mb-2 flex items-center gap-2">
                    <FileJson className="h-4 w-4 text-green-400" />
                    Examples
                  </h5>
                  <div className="space-y-1.5">
                    {skill.examples.map((example, idx) => (
                      <div 
                        key={idx} 
                        className="bg-gray-900/50 rounded p-2 text-sm text-gray-300 border-l-2 border-green-500/50"
                      >
                        "{example}"
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Input/Output Modes */}
              <div className="grid grid-cols-2 gap-3">
                {skill.input_modes && skill.input_modes.length > 0 && (
                  <div>
                    <h5 className="text-xs font-semibold text-gray-400 mb-1.5">Input Modes</h5>
                    <div className="space-y-1">
                      {skill.input_modes.map((mode, idx) => (
                        <Badge 
                          key={idx} 
                          variant="outline" 
                          className="bg-green-950/20 text-green-300 border-green-800 text-xs font-mono"
                        >
                          {mode}
                        </Badge>
                      ))}
                    </div>
                  </div>
                )}

                {skill.output_modes && skill.output_modes.length > 0 && (
                  <div>
                    <h5 className="text-xs font-semibold text-gray-400 mb-1.5">Output Modes</h5>
                    <div className="space-y-1">
                      {skill.output_modes.map((mode, idx) => (
                        <Badge 
                          key={idx} 
                          variant="outline" 
                          className="bg-orange-950/20 text-orange-300 border-orange-800 text-xs font-mono"
                        >
                          {mode}
                        </Badge>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              {/* Security */}
              {skill.security && skill.security.length > 0 && (
                <div>
                  <h5 className="text-sm font-semibold text-gray-300 mb-2 flex items-center gap-2">
                    <Info className="h-4 w-4 text-yellow-400" />
                    Security Requirements
                  </h5>
                  <div className="bg-yellow-950/10 border border-yellow-800/30 rounded p-2">
                    <pre className="text-xs text-gray-300 font-mono overflow-x-auto">
                      {JSON.stringify(skill.security, null, 2)}
                    </pre>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </CardHeader>
    </Card>
  );
};

