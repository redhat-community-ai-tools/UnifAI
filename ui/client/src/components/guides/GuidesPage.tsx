import React, { useState, useEffect, useMemo } from "react";
import { useLocation } from "wouter";
import Sidebar from "@/components/layout/Sidebar";
import Header from "@/components/layout/Header";
import { Input } from "@/components/ui/input";
import { GuideRenderer } from "./GuideRenderer";
import { Card, CardContent } from "@/components/ui/card";
import { BookOpen, HelpCircle, FileText, MessageSquare, Workflow } from "lucide-react";
import { loadGuidesForSection, GuidesByCategory, Guide } from "@/utils/guideLoader";


// Section configuration
const SECTIONS = [
  {
    id: 'agentic-inventory',
    name: 'Agentic Inventory',
    icon: <FileText className="h-5 w-5" />,
    color: 'text-blue-400'
  },
  {
    id: 'agentic-ai-workflows',
    name: 'Agentic AI Workflows',
    icon: <Workflow className="h-5 w-5" />,
    color: 'text-orange-400'
  }
];

export const GuidesPage: React.FC = () => {
  const [location] = useLocation();
  const [guidesByCategory, setGuidesByCategory] = useState<GuidesByCategory>({});
  const [isLoading, setIsLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedGuide, setSelectedGuide] = useState<Guide | null>(null);
  
  // Parse URL params for section and guide
  const urlParams = new URLSearchParams(location.split('?')[1] || '');
  const sectionParam = urlParams.get('section') || 'agentic-inventory';
  const guideParam = urlParams.get('guide');
  
  const [activeSection, setActiveSection] = useState<string>(sectionParam);

  useEffect(() => {
    const load = async () => {
      setIsLoading(true);
      
      // Clear search and selected guide when switching sections
      setSearchQuery("");
      setSelectedGuide(null);
      
      // Load all guides for the section
      const guides = await loadGuidesForSection(activeSection);
      setGuidesByCategory(guides);
      
      setIsLoading(false);
    };
    
    load();
  }, [activeSection, location]);

  // Get all guides for current section (flatten all categories)
  const allGuides = useMemo(() => {
    return Object.values(guidesByCategory).flat();
  }, [guidesByCategory]);

// Filter guides by search query
  const filteredGuides = useMemo(() => {
    if (!searchQuery.trim()) {
      return allGuides;
    }
    const query = searchQuery.toLowerCase();
    return allGuides.filter(guide => 
      guide.guide_title.toLowerCase().includes(query) ||
      guide.title.toLowerCase().includes(query)
    );
  }, [allGuides, searchQuery]);

  // Select guide from URL param or first guide (only if no guideParam and guides are loaded)
  useEffect(() => {
    if (guideParam && allGuides.length > 0) {
      const guide = allGuides.find(g => 
        decodeURIComponent(g.guide_title) === decodeURIComponent(guideParam) || 
        decodeURIComponent(g.title) === decodeURIComponent(guideParam)
      );
      if (guide) {
        setSelectedGuide(guide);
        return;
      }
    }
    
    // Check if current selectedGuide is still valid in current category/section
    if (selectedGuide) {
      const isStillValid = allGuides.includes(selectedGuide);
      if (!isStillValid) {
        setSelectedGuide(null);
      }
    }
    
    // Only auto-select first guide if:
    // 1. No guideParam in URL
    // 2. No selectedGuide currently
    // 3. Guides are available
    if (!guideParam && !selectedGuide && filteredGuides.length > 0) {
      setSelectedGuide(filteredGuides[0]);
    } else if (filteredGuides.length === 0) {
      setSelectedGuide(null);
    }
  }, [guideParam, allGuides, filteredGuides, selectedGuide]);

  // Update URL when selection changes
  useEffect(() => {
    if (selectedGuide) {
      const newUrl = `/guides?section=${activeSection}&guide=${encodeURIComponent(selectedGuide.guide_title)}`;
      if (location !== newUrl) {
        window.history.replaceState({}, '', newUrl);
      }
    }
  }, [selectedGuide, activeSection, location]);

  const categories = Object.keys(guidesByCategory).sort();
  const hasGuides = categories.some(cat => guidesByCategory[cat].length > 0);

  if (isLoading) {
    return (
      <div className="flex h-screen overflow-hidden">
        <Sidebar />
        <div className="flex-1 flex flex-col overflow-hidden">
          <Header title="How-To Guides" onToggleSidebar={() => {}} />
          <main className="flex-1 overflow-y-auto p-6 bg-background-dark">
            <div className="flex items-center justify-center h-64">
              <div className="text-center text-gray-400">
                <p>Loading guides...</p>
              </div>
            </div>
          </main>
        </div>
      </div>
    );
  }


  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar />
      <div className="flex-1 flex flex-col overflow-hidden">
        <Header title="How-To Guides" onToggleSidebar={() => {}} />
        <main className="flex-1 overflow-hidden p-6 bg-background-dark flex flex-col">
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 flex-1 min-h-0">
            {/* Left Navigation Panel */}
            <div className="lg:col-span-2 flex flex-col">
              <Card className="bg-background-card border-gray-800 h-full flex flex-col">
                <CardContent className="p-4 flex flex-col flex-1 overflow-hidden">
                  <h2 className="text-lg font-semibold text-foreground mb-4">Sections</h2>
                  
                  {/* Section Navigation */}
                  <div className="space-y-2 mb-6">
                    {SECTIONS.map((section) => (
                      <button
                        key={section.id}
                        onClick={() => {
                          setActiveSection(section.id);
                          setSelectedGuide(null);
                          setSearchQuery("");
                        }}
                        className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg transition-all ${
                          activeSection === section.id
                            ? 'bg-primary text-white shadow-lg'
                            : 'bg-background-dark text-muted-foreground hover:bg-background-dark/80 hover:text-foreground'
                        }`}
                      >
                        <span className={activeSection === section.id ? 'text-white' : section.color}>
                          {section.icon}
                        </span>
                        <span className="font-medium">{section.name}</span>
                      </button>
                    ))}
                  </div>


                  {/* Guide List */}
                  <div className="border-t border-gray-700 pt-4 flex flex-col flex-1 overflow-hidden">
                    <h3 className="text-sm font-semibold text-foreground mb-3 uppercase tracking-wider text-muted-foreground">
                      Available Guides
                    </h3>
                    <div className="mb-4">
                      <Input
                        placeholder="Search guides..."
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        className="bg-background-dark w-full focus-visible:ring-0 focus-visible:border-primary focus-visible:border-2"
                      />
                    </div>
                    <div className="space-y-1 flex-1 overflow-y-auto">
                      {filteredGuides.length > 0 ? (
                        filteredGuides.map((guide, index) => (
                          <button
                            key={index}
                            onClick={() => setSelectedGuide(guide)}
                            className={`w-full text-left px-3 py-2 rounded-md text-sm transition-colors ${
                              selectedGuide?.guide_title === guide.guide_title
                                ? "bg-primary/30 text-white"
                                : "text-muted-foreground hover:bg-background-dark hover:text-foreground"
                            }`}
                          >
                            {guide.guide_title}
                          </button>
                        ))
                      ) : (
                        <p className="text-sm text-muted-foreground text-center py-4">
                          No guides found
                        </p>
                      )}
                    </div>
                  </div>
                </CardContent>
              </Card>
            </div>

            {/* Right Content Area */}
            <div className="lg:col-span-10 flex flex-col min-h-0">
              <div className="flex-1 overflow-y-auto rounded-lg bg-background-card/60 backdrop-blur-sm border border-gray-700/50 min-h-0">
                {!hasGuides ? (
                  <div className="p-12 text-center flex items-center justify-center min-h-full">
                    <div>
                      <HelpCircle className="h-16 w-16 mx-auto mb-4 text-gray-500" />
                      <h3 className="text-xl font-semibold text-foreground mb-2">
                        No guides available yet
                      </h3>
                      <p className="text-muted-foreground max-w-md mx-auto">
                        No guides have been created here yet. Feel free to contact us to add guides or check back later.
                      </p>
                    </div>
                  </div>
                ) : selectedGuide ? (
                  <div className="p-6">
                    <GuideRenderer
                      title={selectedGuide.title}
                      description={selectedGuide.description}
                      steps={selectedGuide.steps}
                      downloadFiles={selectedGuide.download_files}
                    />
                  </div>
                ) : (
                  <div className="p-12 text-center flex items-center justify-center min-h-full">
                    <div>
                      <BookOpen className="h-16 w-16 mx-auto mb-4 text-gray-500" />
                      <h3 className="text-xl font-semibold text-foreground mb-2">
                        Select a guide
                      </h3>
                      <p className="text-muted-foreground max-w-md mx-auto">
                        Choose a guide from the list to view its contents.
                      </p>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        </main>
      </div>
    </div>
  );
};

export default GuidesPage;
