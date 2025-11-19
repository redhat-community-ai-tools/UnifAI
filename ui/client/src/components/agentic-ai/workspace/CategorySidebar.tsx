
import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { 
  Bot, 
  Server, 
  Search, 
  Brain, 
  Database, 
  Wrench,
  GitBranch,
  Layers,
  ChevronRight,
  ChevronDown,
  LoaderCircle
} from 'lucide-react';
import { ElementCategory, ElementType } from '../../../types/workspace';

interface CategorySidebarProps {
  categories: ElementCategory[];
  selectedCategory: string | null;
  selectedElementType: ElementType | null;
  onElementTypeSelect: (category: string, elementType: ElementType) => void;
  isLoading: boolean;
}

const getCategoryIcon = (category: string) => {
  const iconMap: { [key: string]: React.ReactNode } = {
    nodes: <Bot className="h-4 w-4" />,
    llms: <Brain className="h-4 w-4" />,
    tools: <Wrench className="h-4 w-4" />,
    retrievers: <Search className="h-4 w-4" />,
    providers: <Server className="h-4 w-4" />,
    conditions: <GitBranch className="h-4 w-4" />
  };
  
  return iconMap[category] || <Layers className="h-4 w-4" />;
};

const getCategoryDisplayName = (category: string) => {
  const nameMap: { [key: string]: string } = {
    nodes: 'Agents',
    llms: 'LLMs',
    tools: 'Tools',
    retrievers: 'Retrievers',
    providers: 'Providers',
    conditions: 'Conditions'
  };
  
  return nameMap[category] || category.charAt(0).toUpperCase() + category.slice(1);
};

export const CategorySidebar: React.FC<CategorySidebarProps> = ({
  categories,
  selectedCategory,
  selectedElementType,
  onElementTypeSelect,
  isLoading
}) => {
  const [expandedCategories, setExpandedCategories] = React.useState<Set<string>>(new Set());

  const toggleCategory = (category: string) => {
    const newExpanded = new Set(expandedCategories);
    if (newExpanded.has(category)) {
      newExpanded.delete(category);
    } else {
      newExpanded.add(category);
    }
    setExpandedCategories(newExpanded);
  };

  const handleElementTypeClick = (category: string, elementType: ElementType) => {
    onElementTypeSelect(category, elementType);
  };

  if (isLoading && categories.length === 0) {
    return (
      <Card className="bg-background-card shadow-card border-gray-800 h-full">
        <CardContent className="flex items-center justify-center h-32">
          <LoaderCircle className="h-6 w-6 animate-spin" />
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="bg-background-card shadow-card border-gray-800 h-full">
      <CardHeader className="py-3 px-4 border-b border-gray-800">
        <CardTitle className="text-sm font-medium">Categories</CardTitle>
      </CardHeader>
      <CardContent className="p-0 h-full overflow-y-auto">
        <div className="space-y-1">
          {categories.map((category) => (
            <div key={category.category}>
              {/* Category Header */}
              <Button
                variant="ghost"
                className="w-full justify-between px-4 py-3 rounded-none text-left"
                onClick={() => toggleCategory(category.category)}
              >
                <div className="flex items-center">
                  {getCategoryIcon(category.category)}
                  <span className="ml-2 text-sm">
                    {getCategoryDisplayName(category.category)} ({category.elements.length})
                  </span>
                </div>
                {expandedCategories.has(category.category) ? (
                  <ChevronDown className="h-4 w-4" />
                ) : (
                  <ChevronRight className="h-4 w-4" />
                )}
              </Button>

              {/* Element Types */}
              {expandedCategories.has(category.category) && (
                <div className="ml-4 border-l border-gray-800">
                  {category.elements.map((elementType) => (
                    <Button
                      key={`${elementType.category}-${elementType.type}`}
                      variant="ghost"
                      className={`w-full justify-start px-4 py-2 rounded-none text-xs ${
                        selectedElementType?.type === elementType.type && 
                        selectedElementType?.category === elementType.category
                          ? 'bg-primary bg-opacity-20 text-secondary border-r-2 border-primary'
                          : 'text-gray-400 hover:text-gray-200'
                      }`}
                      onClick={() => handleElementTypeClick(category.category, elementType)}
                    >
                      <div className="w-2 h-2 rounded-full bg-gray-500 mr-3 flex-shrink-0" />
                      <span className="truncate">{elementType.name}</span>
                    </Button>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
};
