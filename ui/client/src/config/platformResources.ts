// Import README.md content from the project root
import readmeContent from "../../../../README.md?raw";

export { readmeContent };

export interface PlatformResource {
    id: string;
    icon: string;
    title: string;
    description: string;
    url: string;
  }

  export interface VideoConfig {
    enabled: boolean;
    type: "direct" | "gdrive";
    src: string;
    startTime: number;
    endTime: number;
    playbackRate: number;
    title?: string;
    description?: string;
    label?: string;
    showLoopBadge?: boolean;
  }
  
  export const introVideoConfig: VideoConfig = {
    enabled: true,
    type: "direct",
    // src: "1yGcVaM5XiY3yhFMTKvxgLfVw8HcJAxL9",
    src: '/intro-video.mp4',
    startTime: 0,
    endTime: 43,
    playbackRate: 2,
    title: "See UnifAI in Action",
    description: "Watch how workflows are created in our platform",
    label: "Platform Demo",
    showLoopBadge: true
  };
  
  export const platformResources: PlatformResource[] = [
    {
      id: "github",
      icon: "github",
      title: "Source Code on GitHub",
      description: "Browse the full agentic framework, including inventory, blueprints, workflows, and chat modules.",
      url: "https://github.com/redhat-community-ai-tools/UnifAI"
    },
    {
      id: "docs",
      icon: "docs",
      title: "Technical Documentation",
      description: "Explore system architecture, internal components, API contracts, and platform design decisions.",
      url: "https://drive.google.com/drive/folders/1qPGQJKS2fa18LHen7v6ueOGGvb-acfzm?usp=drive_link"
    },
    {
      id: "slides",
      icon: "slides",
      title: "Architecture & Platform Overview Slides",
      description: "High-level explanation of unifAI's architecture, modules, and platform features.",
      url: "https://drive.google.com/drive/folders/1ONMrhOCaPxJdn7Lm04NIkvYirJ4EyH8h?usp=drive_link"
    },
    {
      id: "videos",
      icon: "videos",
      title: "Video Walkthroughs",
      description: "Watch demos, onboarding guides, and technical deep dives.",
      url: "https://drive.google.com/drive/folders/1Xw8qsKlVhJ1ESRcjR6YYft73di4x7J9e?usp=drive_link"
    }
  ];
  
  export interface TechStackItem {
    name: string;
    icon: string;
    category: "backend" | "frontend" | "agentic";
  }
  
  export const techStackItems: TechStackItem[] = [
    { name: "Python", icon: "python", category: "backend" },
    { name: "Flask", icon: "flask", category: "backend" },
    { name: "Celery", icon: "celery", category: "backend" },
    { name: "RabbitMQ", icon: "rabbitmq", category: "backend" },
    { name: "Qdrant", icon: "qdrant", category: "backend" },
    { name: "MongoDB", icon: "mongodb", category: "backend" },
    { name: "React", icon: "react", category: "frontend" },
    { name: "TypeScript", icon: "typescript", category: "frontend" },
    { name: "LangGraph", icon: "langgraph", category: "agentic" },
    { name: "LangChain", icon: "langchain", category: "agentic" },
    { name: "A2A (Agents-to-Agents)", icon: "a2a", category: "agentic" }
  ];
  