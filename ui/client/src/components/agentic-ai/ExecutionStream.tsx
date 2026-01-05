import React, { useState, useRef, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { motion, AnimatePresence } from "framer-motion";
import { 
  Pause, Play, Trash2, Download, Info, AlertCircle, CheckCircle,
  Search, User, FileSearch, GitPullRequest, Database, Code, MessageSquare, Brain, Wrench, Layers
} from "lucide-react";
import { GraphNode } from "../../pages/AgenticWorkflows"
import { useStreamingData, NodeEntry } from "./StreamingDataContext"
import axios from '../../http/axiosAgentConfig'
import { GraphFlow } from './graphs/interfaces'
import { useAuth } from "@/contexts/AuthContext";

interface LogEntry {
  id: string;
  timestamp: Date;
  agent: string;
  message: string;
  status: 'info' | 'processing' | 'success' | 'error';
}

const agentIcons: React.FC<{ className?: string }>[] = [
  Layers,
  User,
  Search,
  FileSearch,
  GitPullRequest,
  Database,
  Wrench,
  MessageSquare,
  Brain,
];

const getRandomAgentIcon = (): JSX.Element => {
  const IconComponent = agentIcons[Math.floor(Math.random() * agentIcons.length)];
  return <IconComponent className="h-4 w-4 mr-2" />;
};

type ExecutionStreamProps = {
  blueprintId: string;
  isLiveRequest: boolean;
};

type AgentNode = {
  id: string,
  name: string,
  description: string | null,
  icon: React.ReactElement,
}

export default function ExecutionStream({
  blueprintId, isLiveRequest
}: ExecutionStreamProps): React.ReactElement {
  const [logs, setLogs] = useState<LogEntry[]>([
    {
      id: '1',
      timestamp: new Date(),
      agent: 'System',
      message: 'Agentic AI system initialized and ready.',
      status: 'info',
    }
  ]);
  
  const [agentNodes, setAgentNodes] = useState<AgentNode[] | null>(null);
  const [selectedNode, setSelectedNode] = useState<AgentNode | null>(null);
  const [autoscroll, setAutoscroll] = useState(true);
  const [isPaused, setIsPaused] = useState(false);
  const logsEndRef = useRef<HTMLDivElement>(null);
  const { nodeListRef } = useStreamingData();
  const { user } = useAuth();

  const extractNodeData = (graphFlow: GraphFlow): { id: string; name: string; description: string | null }[] => {
    if (!graphFlow || !graphFlow.plan) {
      return [];
    }
  
    return graphFlow.plan.map(item => {
      const node = graphFlow.nodes.find(node => node.rid === item.node);

      return {
        id: item.uid,
        name: node?.name || item.meta?.display_name || "General Node",
        description: node?.config?.description || item.meta?.description || null
      }
    });
  };
  
  // Create agent nodes from selected graph nodes on component mount
  useEffect(() => {
    const getGraphNodes = async () => {
      const response = await axios.get(`/blueprints/available.blueprints.resolved.get?userId=${user?.username || "default"}`);
      const blueprintObjects = response.data;
      
      // Find the specific graph flow by blueprint_id
      const targetBlueprintObj = blueprintObjects.find((blueprintObj: any, index: number) => 
        blueprintObj.blueprint_id === blueprintId
      );
  
      return targetBlueprintObj ? extractNodeData(targetBlueprintObj.spec_dict) : [];
    }
  
    const fetchAndSetNodes = async () => {
      const nodeData = await getGraphNodes();
      
      const nodes = nodeData.map((node: { id: string; name: string; description: string | null }) => ({
        id: node.id,
        name: node.name,
        description: node.description,
        icon: getRandomAgentIcon(),
      })) || null;

      setAgentNodes(nodes);
      setSelectedNode(nodes && nodes.length > 0 ? nodes[0] : null);
    };
  
    fetchAndSetNodes();
  }, [blueprintId]);

  // Set up polling interval to get real-time node data
  useEffect(() => {
    let interval: NodeJS.Timeout | null = null;
  
    if (isLiveRequest && !isPaused) {
      interval = setInterval(() => {
        const list = Array.from(nodeListRef.current.values());
        
        // Process new entries and update logs
        setLogs(prevLogs => {
          // Keep the system log
          const systemLogs = prevLogs.filter(log => log.agent === 'System');
          const updatedLogs = [...systemLogs];
          
          // Process each entry from nodeListRef
          list.forEach(entry => {
            const matchingNode = agentNodes?.find(node => node.id === entry.node_uid);
            
            if (matchingNode) {
              // Create a new log entry
              const newLog: LogEntry = {
                id: `${entry.node_uid}`, // Use node_uid as id to ensure only one log per node
                timestamp: new Date(),
                agent: matchingNode.name,
                message: entry.text,
                status: mapStreamToStatus(entry.stream),
              };
              
              // Add the new log (this will replace any previous log for this node)
              updatedLogs.push(newLog);
            }
          });
          
          return updatedLogs;
        });
      }, 100);
    }
  
    return () => {
      if (interval) {
        clearInterval(interval);
      }
    };
  }, [isLiveRequest, isPaused, nodeListRef, agentNodes]);
  
  // Map stream type to status
  const mapStreamToStatus = (stream: string): 'info' | 'processing' | 'success' | 'error' => {
    switch (stream) {
      case 'PROGRESS':
        return 'processing';
      case 'ERROR':
        return 'error';
      case 'COMPLETE':
        return 'success';
      default:
        return 'info';
    }
  };
  
  // Filter logs based on selected node
  const filteredLogs = selectedNode 
    ? logs.filter(log => log.id === selectedNode.id || log.agent === 'System')
    : logs;
  
  // Scroll to bottom when new logs are added
  useEffect(() => {
    if (autoscroll) {
      scrollToBottom();
    }
  }, [filteredLogs, autoscroll]);

  // Auto-scroll function
  const scrollToBottom = () => {
    logsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  // Format timestamp
  const formatTime = (date: Date) => {
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  };

  // Clear logs
  const clearLogs = () => {
    setLogs([
      {
        id: Date.now().toString(),
        timestamp: new Date(),
        agent: 'System',
        message: 'Execution logs cleared.',
        status: 'info',
      },
    ]);
  };

  // Toggle streaming pause
  const togglePause = () => {
    setIsPaused(!isPaused);
  };

  // Status icon component
  const StatusIcon = ({ status }: { status: string }) => {
    switch (status) {
      case 'info':
        return <Info className="h-4 w-4 text-[#00B0FF]" />;
      case 'processing':
        return (
          <motion.div
            animate={{ rotate: 360 }}
            transition={{ repeat: Infinity, duration: 1.5, ease: "linear" }}
          >
            <AlertCircle className="h-4 w-4 text-[#FFB300]" />
          </motion.div>
        );
      case 'success':
        return <CheckCircle className="h-4 w-4" style={{ color: 'hsl(var(--success))' }} />;
      case 'error':
        return <AlertCircle className="h-4 w-4 text-[#FF1744]" />;
      default:
        return <Info className="h-4 w-4 text-[#00B0FF]" />;
    }
  };

  return (
    <Card className="bg-background-card shadow-card border-gray-800 flex flex-col h-full">
      <CardHeader className="py-4 px-6 flex flex-row justify-between items-center">
        <CardTitle className="text-lg font-heading">Execution Stream</CardTitle>
        <div className="flex space-x-2">
          <Button
            variant="ghost"
            size="sm"
            onClick={togglePause}
            disabled={!isLiveRequest}
            className={`${!isLiveRequest ? 'opacity-50 cursor-not-allowed' : 'text-gray-400 hover:text-gray-100'}`}
          >
            {isPaused ? <Play className="h-4 w-4" /> : <Pause className="h-4 w-4" />}
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={clearLogs}
            className="text-gray-400 hover:text-gray-100"
          >
            <Trash2 className="h-4 w-4" />
          </Button>
          <Button
            variant="ghost"
            size="sm"
            className="text-gray-400 hover:text-gray-100"
          >
            <Download className="h-4 w-4" />
          </Button>
        </div>
      </CardHeader>
      <CardContent className="flex-grow overflow-hidden p-0 flex flex-col">
        <div className="flex h-full">
          {/* Agent nodes sidebar */}
          <div className="w-1/5 min-w-1/5 max-w-1/5 border-r border-gray-800 bg-background-dark overflow-y-auto">
            <div className="py-3 px-4 border-b border-gray-800 bg-background-surface">
              <h3 className="text-sm font-medium">Agent Nodes</h3>
            </div>
            <div className="py-2">
              {agentNodes?.map((node) => (
                <motion.div
                  key={node.id}
                  className={`px-4 py-2 border-l-2 cursor-pointer ${
                    selectedNode?.id === node.id
                      ? 'border-[#00B0FF] bg-[#00B0FF] bg-opacity-10'
                      : 'border-transparent hover:bg-background-surface'
                  }`}
                  onClick={() => setSelectedNode(node)}
                  whileHover={{ x: 2 }}
                  transition={{ duration: 0.1 }}
                >
                  <div className="flex items-center">
                    {node.icon}
                    <span className="text-sm font-medium truncate">{node.name}</span>
                  </div>
                  {node.description && (
                    <p className="text-xs text-gray-400 mt-1 truncate">{node.description}</p>
                  )}
                </motion.div>
              ))}
            </div>
          </div>
          
          {/* Log stream */}
          <div className="flex-grow flex flex-col w-4/5 overflow-hidden">
            <div 
              className="flex-grow overflow-y-auto p-4 font-mono text-sm bg-background-dark"
              style={{ maxHeight: 'calc(100% - 2rem)' }}
            >
              <div className="w-full">
                <AnimatePresence>
                  {filteredLogs.map((log) => (
                    <motion.div
                      key={log.id}
                      initial={{ opacity: 0, y: 5 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ duration: 0.2 }}
                      className="mb-2 pb-2 border-b border-gray-800"
                    >
                      <div className="flex items-start">
                        <div className="mt-1 mr-2 flex-shrink-0">
                          <StatusIcon status={log.status} />
                        </div>
                        <div className="min-w-0 w-full">
                          <div className="flex items-center text-xs mb-1">
                            <span className="text-gray-400 flex-shrink-0">{formatTime(log.timestamp)}</span>
                            <span className={`ml-2 px-1.5 py-0.5 rounded text-xs flex-shrink-0 ${
                              log.status === 'info' ? 'bg-[#00B0FF] bg-opacity-20 text-[#00B0FF]' :
                              log.status === 'processing' ? 'bg-[#FFB300] bg-opacity-20 text-[#FFB300]' :
                              log.status === 'success' ? 'bg-[hsl(var(--success))] bg-opacity-20 text-[hsl(var(--success))]' :
                              'bg-[#FF1744] bg-opacity-20 text-[#FF1744]'
                            }`}>
                              {log.agent}
                            </span>
                          </div>
                          <div className={`break-words overflow-x-auto whitespace-pre-wrap ${
                            log.status === 'error' ? 'text-[#FF1744]' : 'text-gray-300'
                          }`}>
                            {log.message}
                          </div>
                        </div>
                      </div>
                    </motion.div>
                  ))}
                </AnimatePresence>
                <div ref={logsEndRef} />
              </div>
            </div>
            <div className="px-4 py-2 border-t border-gray-800 flex justify-between items-center text-xs">
              <span className="text-gray-400">
                {filteredLogs.length} log entries
                {selectedNode ? ` for ${selectedNode.name}` : ''}
              </span>
              <div className="flex items-center">
                <input
                  type="checkbox"
                  id="autoscroll"
                  checked={autoscroll}
                  onChange={() => setAutoscroll(!autoscroll)}
                  className="mr-2"
                />
                <label htmlFor="autoscroll" className="text-gray-400">Auto-scroll</label>
              </div>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
