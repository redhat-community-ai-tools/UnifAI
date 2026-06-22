import React, { useState, useMemo } from 'react';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { motion } from 'framer-motion';
import { 
  Search, 
  Filter, 
  Grid3X3, 
  List,
  LoaderCircle,
  FolderOpen,
  Plus
} from 'lucide-react';
import { TemplateListItem, TemplateCategory } from '@/types/templates';
import { TemplateCard } from './TemplateCard';

interface TemplateCatalogProps {
  templates: TemplateListItem[];
  categories: TemplateCategory[];
  isLoading: boolean;
  isAdmin?: boolean;
  onSelectTemplate: (template: TemplateListItem) => void;
  onAddTemplate?: () => void;
  onViewYaml?: (template: TemplateListItem) => void;
  onDeleteTemplate?: (template: TemplateListItem) => void;
}

export const TemplateCatalog: React.FC<TemplateCatalogProps> = ({
  templates,
  categories,
  isLoading,
  isAdmin = false,
  onSelectTemplate,
  onAddTemplate,
  onViewYaml,
  onDeleteTemplate,
}) => {
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid');

  const filteredTemplates = useMemo(() => {
    return templates.filter(template => {
      const matchesSearch = !searchQuery || 
        template.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        template.description.toLowerCase().includes(searchQuery.toLowerCase()) ||
        template.tags?.some(tag => tag.toLowerCase().includes(searchQuery.toLowerCase()));
      
      const matchesCategory = !selectedCategory || template.category === selectedCategory;
      
      return matchesSearch && matchesCategory;
    });
  }, [templates, searchQuery, selectedCategory]);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <LoaderCircle className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row gap-4">
        <div className="relative flex-1 dark-inputs">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search templates..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-10 bg-card border-border focus:border-primary"
          />
        </div>
        
        <div className="flex items-center gap-2">
          {isAdmin && (
            <Button
              size="sm"
              onClick={onAddTemplate}
              className="bg-primary hover:bg-primary/90"
            >
              <Plus className="h-4 w-4 mr-1" />
              Add Template
            </Button>
          )}
          <Button
            variant={viewMode === 'grid' ? 'default' : 'outline'}
            size="sm"
            onClick={() => setViewMode('grid')}
            className={viewMode === 'grid' ? 'bg-primary hover:bg-primary/90' : 'border-border'}
          >
            <Grid3X3 className="h-4 w-4" />
          </Button>
          <Button
            variant={viewMode === 'list' ? 'default' : 'outline'}
            size="sm"
            onClick={() => setViewMode('list')}
            className={viewMode === 'list' ? 'bg-primary hover:bg-primary/90' : 'border-border'}
          >
            <List className="h-4 w-4" />
          </Button>
        </div>
      </div>

      <div className="flex flex-wrap gap-2">
        <Button
          variant={selectedCategory === null ? 'default' : 'outline'}
          size="sm"
          onClick={() => setSelectedCategory(null)}
          className={selectedCategory === null ? 'bg-primary hover:bg-primary/90' : 'border-border'}
        >
          <Filter className="h-3 w-3 mr-1" />
          All
          <Badge variant="secondary" className="ml-2 bg-white/10">
            {templates.length}
          </Badge>
        </Button>
        {categories.map((category) => (
          <Button
            key={category.name}
            variant={selectedCategory === category.name ? 'default' : 'outline'}
            size="sm"
            onClick={() => setSelectedCategory(category.name)}
            className={selectedCategory === category.name ? 'bg-primary hover:bg-primary/90' : 'border-border'}
          >
            {category.name}
            <Badge variant="secondary" className="ml-2 bg-white/10">
              {category.count}
            </Badge>
          </Button>
        ))}
      </div>

      {filteredTemplates.length === 0 ? (
        <motion.div 
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="flex flex-col items-center justify-center h-64 text-muted-foreground"
        >
          <FolderOpen className="h-12 w-12 mb-4 opacity-50" />
          <h3 className="text-lg font-medium mb-2">No templates found</h3>
          <p className="text-sm text-center max-w-md">
            {searchQuery 
              ? `No templates match "${searchQuery}". Try a different search term.`
              : 'No templates available in this category.'}
          </p>
        </motion.div>
      ) : (
        <div className={
          viewMode === 'grid' 
            ? 'grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6'
            : 'flex flex-col gap-4'
        }>
          {filteredTemplates.map((template, index) => (
            <TemplateCard
              key={template.template_id}
              template={template}
              index={index}
              isAdmin={isAdmin}
              onSelect={onSelectTemplate}
              onViewYaml={onViewYaml}
              onDelete={onDeleteTemplate}
            />
          ))}
        </div>
      )}
    </div>
  );
};

export default TemplateCatalog;