import { createContext, useContext, useState, ReactNode } from "react";

export interface Project {
  id: string;
  name: string;
  shortName: string;
  icon: "project" | "robot" | "database";
  color: string;
  updatedTime: string;
  processingPercentage: number;
  isActive: boolean;
  sources: number;
  documents: number;
}

interface ProjectContextType {
  projects: Project[];
  currentProject: Project | null;
  setCurrentProject: (project: Project) => void;
}

// Create the project context with a default value
const defaultContextValue: ProjectContextType = {
  projects: [],
  currentProject: null,
  setCurrentProject: () => {},
};

// Create context with default value instead of undefined
const ProjectContext = createContext<ProjectContextType>(defaultContextValue);

export function ProjectProvider({ children }: { children: ReactNode }) {
  // Sample projects data
  const defaultProjects: Project[] = [
    {
      id: "1",
      name: "Test Autmation Generator",
      shortName: "TAG",
      icon: "project",
      color: "primary",
      updatedTime: "2 hours ago",
      processingPercentage: 87,
      isActive: true,
      sources: 3,
      documents: 12,
    },
    {
      id: "2",
      name: "AI Assistant",
      shortName: "AI",
      icon: "robot",
      color: "secondary",
      updatedTime: "5 days ago",
      processingPercentage: 100,
      isActive: false,
      sources: 2,
      documents: 5.2,
    },
    {
      id: "3",
      name: "Data Warehouse",
      shortName: "DW",
      icon: "database",
      color: "accent",
      updatedTime: "1 day ago",
      processingPercentage: 62,
      isActive: false,
      sources: 1,
      documents: 8.9,
    },
  ];

  const [projects] = useState<Project[]>(defaultProjects);
  const [currentProject, setCurrentProject] = useState<Project | null>(
    defaultProjects[0],
  );

  return (
    <ProjectContext.Provider
      value={{ projects, currentProject, setCurrentProject }}
    >
      {children}
    </ProjectContext.Provider>
  );
}

export function useProject() {
  const context = useContext(ProjectContext);
  return context;
}
