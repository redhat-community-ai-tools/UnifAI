import React from "react";
import {
  Bot,
  Brain,
  Wrench,
  Circle,
  Server,
  Search,
  GitBranch,
  Lock,
  Box,
} from "lucide-react";
import { DownloadFile } from "@/utils/guideLoader";

export interface CategoryDisplay {
  icon: React.ReactNode;
  color: string;
}

export const getCategoryDisplay = (category: string): CategoryDisplay => {
  const categoryMap: { [key: string]: CategoryDisplay } = {
    llms: { icon: <Brain className="w-4 h-4" />, color: "#8A2BE2" },
    tools: { icon: <Wrench className="w-4 h-4" />, color: "#00B0FF" },
    nodes: { icon: <Circle className="w-4 h-4" />, color: "#FFB300" },
    orchestrators: { icon: <Bot className="w-4 h-4" />, color: "#00BCD4" },
    providers: { icon: <Server className="w-4 h-4" />, color: "#FF5722" },
    retrievers: { icon: <Search className="w-4 h-4" />, color: "#4CAF50" },
    conditions: { icon: <GitBranch className="w-4 h-4" />, color: "#9C27B0" },
    auths: { icon: <Lock className="w-4 h-4" />, color: "#F44336" },
    sandboxes: { icon: <Box className="w-4 h-4" />, color: "#795548" },
    default: { icon: <Box className="w-4 h-4" />, color: "#607D8B" },
  };
  return categoryMap[category] || categoryMap.default;
};

export const getCategoryDisplayName = (category: string) => {
  const nameMap: { [key: string]: string } = {
    nodes: "Agents",
    orchestrators: "Orchestrators",
    llms: "LLMs",
    tools: "Tools",
    retrievers: "Retrievers",
    providers: "Providers",
    conditions: "Conditions",
    auths: "Auths",
    sandboxes: "Sandboxes",
  };

  return (
    nameMap[category] || category.charAt(0).toUpperCase() + category.slice(1)
  );
};

export const getCategorySingularDisplayName = (category: string): string => {
  const nameMap: { [key: string]: string } = {
    nodes: "Agent",
    orchestrators: "Orchestrator",
    llms: "LLM",
    tools: "Tool",
    retrievers: "Retriever",
    providers: "Provider",
    conditions: "Condition",
  };
  return (
    nameMap[category] || category.charAt(0).toUpperCase() + category.slice(1)
  );
};

export const handleDownloadFile = (downloadFile: DownloadFile, setDownloadingFile: any) => {
    setDownloadingFile(downloadFile.path);
    fetch(downloadFile.path)
      .then((response) => {
        if (!response.ok) {
          throw new Error(`File not found: ${response.status}`);
        }
        return response.text();
      })
      .then((fileContent) => {
        const blob = new Blob([fileContent], { type: "text/plain" });
        const url = window.URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = url;
        link.download = downloadFile.filename;
        link.style.display = "none";
        document.body.appendChild(link);
        link.click();
        
        setTimeout(() => {
          document.body.removeChild(link);
          window.URL.revokeObjectURL(url);
          setDownloadingFile(null);
        }, 100);
      })
      .catch((error) => {
        console.error("Download failed:", error);
        setDownloadingFile(null);
      });
  };