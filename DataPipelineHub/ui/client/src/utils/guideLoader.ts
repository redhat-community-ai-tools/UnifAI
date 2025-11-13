// Guide loader utility
// Loads YAML guide files and converts them to structured data
import yaml from "js-yaml";

export interface DownloadFile {
  path: string;
  filename: string;
  label?: string;
  trigger?: string; // Optional: text pattern to match in code blocks to show download button
}

export interface Guide {
  guide_title: string;
  title: string;
  description?: string;
  category: string;
  section: string;
  order: number;
  download_files?: DownloadFile[]; // Optional: list of downloadable files
  steps: Array<{
    step: number;
    title: string;
    body: string;
  }>;
}

export interface GuidesByCategory {
  [category: string]: Guide[];
}

// Parse YAML using js-yaml library
export const parseYAML = (yamlText: string): Guide | null => {
  try {
    const parsed = yaml.load(yamlText) as any;
    
    if (!parsed || typeof parsed !== "object") {
      return null;
    }
    
    const guide: Guide = {
      guide_title: parsed.guide_title || parsed.title || "",
      title: parsed.title || "",
      description: parsed.description,
      category: parsed.category || "",
      section: parsed.section || "",
      order: parsed.order || 0,
      download_files: parsed.download_files || [],
      steps: (parsed.steps || []).map((step: any) => ({
        step: step.step || 0,
        title: step.title || "",
        body: step.body || "",
      })),
    };
    
    // Validate guide structure
    if (guide.guide_title && guide.category && guide.section && guide.steps.length > 0) {
      return guide;
    }
    
    return null;
  } catch (error) {
    console.error("Error parsing YAML:", error);
    return null;
  }
};

// Load a guide from a URL
export const loadGuide = async (url: string): Promise<Guide | null> => {
  try {
    const response = await fetch(url);
    if (!response.ok) {
      return null;
    }
    const yamlText = await response.text();
    return parseYAML(yamlText);
  } catch (error) {
    console.error(`Error loading guide from ${url}:`, error);
    return null;
  }
};

// Load all guides for a section
export const loadGuidesForSection = async (section: string, category?: string): Promise<GuidesByCategory> => {
  // Define guide paths - in production, this could be dynamic or come from an API
  const guidePaths: { [key: string]: string[] } = {
    "agentic-inventory": [
      "/guides/agentic-inventory/providers/google-mcp-provider.yaml",
    ],
    "agentic-ai-workflows": [],
  };
  
  const sectionPaths = guidePaths[section] || [];
  const guides: Guide[] = [];
  
  // Load all guides in parallel
  const results = await Promise.all(
    sectionPaths.map((path) => loadGuide(path))
  );
  
  // Filter out null results
  results.forEach((guide) => {
    if (guide && guide.section === section) {
      guides.push(guide);
    }
  });
  
  // Sort guides by order
  guides.sort((a, b) => a.order - b.order);
  
  // Return all guides in a single "all" category (no category separation)
  return {
    "all": guides
  };
};

