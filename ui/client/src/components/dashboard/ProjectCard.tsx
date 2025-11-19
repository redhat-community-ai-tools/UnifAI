import React from "react";
import { Card } from "@/components/ui/card";
import { motion } from "framer-motion";
import { FaProjectDiagram, FaRobot, FaDatabase, FaEllipsisV } from "react-icons/fa";
import SimpleTooltip from "@/components/shared/SimpleTooltip";

interface ProjectCardProps {
  name: string;
  shortName: string;
  icon: 'project' | 'robot' | 'database';
  updatedTime: string;
  processingPercentage: number;
  color: string;
  isActive: boolean;
  sources: number;
  documents: number;
}

export default function ProjectCard({
  name,
  shortName,
  icon,
  updatedTime,
  processingPercentage,
  color,
  isActive,
  sources,
  documents
}: ProjectCardProps) {
  const getIcon = () => {
    switch (icon) {
      case 'project':
        return <FaProjectDiagram />;
      case 'robot':
        return <FaRobot />;
      case 'database':
        return <FaDatabase />;
      default:
        return <FaProjectDiagram />;
    }
  };
  
  return (
    <Card className={`bg-background-card shadow-card hover:shadow-card-hover transition-all border-0 overflow-hidden group`}>
      <div className={`h-1 w-full bg-${color}`}></div>
      <div className="p-5">
        <div className="flex justify-between items-start mb-3">
          <div className="flex items-center space-x-3">
            <div className={`w-10 h-10 rounded-md bg-${color} bg-opacity-20 flex items-center justify-center text-${color}`}>
              {getIcon()}
            </div>
            <div>
              <h3 className={`font-heading font-semibold text-white group-hover:text-${color} transition-colors`}>{name}</h3>
              <p className="text-xs text-gray-400">Updated {updatedTime}</p>
            </div>
          </div>
          <div className="flex space-x-1">
            <motion.div 
              className={`w-2 h-2 rounded-full bg-${isActive ? 'success' : 'gray-600'} mt-1.5`}
            />
            {isActive && (
              <motion.div 
                className="w-2 h-2 rounded-full bg-success mt-1.5"
                animate={{ opacity: [1, 0.4, 1] }}
                transition={{ duration: 2, repeat: Infinity }}
              />
            )}
          </div>
        </div>
        <div className="space-y-3 mb-4">
          <div>
            <div className="flex items-center justify-between mb-1">
              <span className="text-xs text-gray-400">Processing</span>
              <span className="text-xs font-medium">{processingPercentage}%</span>
            </div>
            <div className="h-1.5 w-full bg-background-dark rounded-full overflow-hidden">
              <motion.div 
                initial={{ width: 0 }}
                animate={{ width: `${processingPercentage}%` }}
                transition={{ duration: 1 }}
                className={`h-full bg-${color} rounded-full`}
              />
            </div>
          </div>
        </div>
        <div className="flex items-center justify-between text-xs">
          <div className="flex items-center space-x-3">
            <span className="px-2 py-0.5 rounded-md bg-background-dark text-gray-400">{sources} Sources</span>
            <span className="px-2 py-0.5 rounded-md bg-background-dark text-gray-400">{documents}k Documents</span>
          </div>
          <SimpleTooltip content={<p>Project options</p>}>
            <button className={`text-${color} hover:text-white transition-colors`}>
              <FaEllipsisV />
            </button>
          </SimpleTooltip>
        </div>
      </div>
    </Card>
  );
}
