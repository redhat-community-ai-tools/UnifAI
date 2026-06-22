import React from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardFooter } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { motion } from 'framer-motion';
import { Clock, ArrowRight, Code, Trash2 } from 'lucide-react';
import { TemplateListItem } from '@/types/templates';
import { getCategoryIcon } from '@/utils/templateHelpers';

interface TemplateCardProps {
  template: TemplateListItem;
  index: number;
  isAdmin?: boolean;
  onSelect: (template: TemplateListItem) => void;
  onViewYaml?: (template: TemplateListItem) => void;
  onDelete?: (template: TemplateListItem) => void;
}

export const TemplateCard: React.FC<TemplateCardProps> = ({ 
  template, 
  index, 
  isAdmin = false,
  onSelect,
  onViewYaml,
  onDelete,
}) => {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, delay: index * 0.1 }}
      className="h-full"
    >
      <Card className="bg-card shadow-card border-border h-full flex flex-col hover:border-primary/50 transition-all duration-200 cursor-pointer group"
        onClick={() => onSelect(template)}
      >
        <CardHeader className="py-4 px-6 border-b border-border">
          <div className="flex items-start justify-between">
            <div className="flex items-center space-x-3">
              <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-primary to-primary/80 flex items-center justify-center text-white">
                {getCategoryIcon(template.category)}
              </div>
              <div>
                <CardTitle className="text-lg font-heading group-hover:text-primary transition-colors">
                  {template.name}
                </CardTitle>
                <Badge variant="outline" className="mt-1 text-xs">
                  {template.category}
                </Badge>
              </div>
            </div>

            {isAdmin && (
              <div className="flex items-center gap-1">
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-8 w-8 p-0 text-muted-foreground hover:text-primary"
                  title="View YAML"
                  aria-label="View YAML"
                  onClick={(e) => {
                    e.stopPropagation();
                    onViewYaml?.(template);
                  }}
                >
                  <Code className="h-4 w-4" />
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-8 w-8 p-0 text-muted-foreground hover:text-destructive"
                  title="Delete template"
                  aria-label="Delete template"
                  onClick={(e) => {
                    e.stopPropagation();
                    onDelete?.(template);
                  }}
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              </div>
            )}
          </div>
        </CardHeader>
        
        <CardContent className="p-4 flex-grow">
          <p className="text-sm text-muted-foreground line-clamp-3 mb-4">
            {template.description}
          </p>
          
          {template.output_capabilities && template.output_capabilities.length > 0 && (
            <div className="mb-4">
              <p className="text-xs text-muted-foreground mb-2">Capabilities:</p>
              <div className="flex flex-wrap gap-1">
                {template.output_capabilities.slice(0, 3).map((capability, idx) => (
                  <Badge 
                    key={idx} 
                    variant="secondary" 
                    className="text-xs bg-primary/10 text-primary border-primary/20"
                  >
                    {capability}
                  </Badge>
                ))}
              </div>
            </div>
          )}

          {template.tags && template.tags.length > 0 && (
            <div className="flex flex-wrap gap-1">
              {template.tags.slice(0, 3).map((tag, idx) => (
                <span 
                  key={idx} 
                  className="text-xs text-muted-foreground bg-muted px-2 py-0.5 rounded"
                >
                  #{tag}
                </span>
              ))}
            </div>
          )}
        </CardContent>

        <CardFooter className="px-6 py-3 border-t border-border bg-muted/30">
          <div className="flex items-center justify-between w-full">
            {template.placeholder_count !== undefined && (
              <div className="flex items-center text-xs text-muted-foreground">
                <Clock className="h-3 w-3 mr-1" />
                {template.placeholder_count} field{template.placeholder_count !== 1 ? 's' : ''} to configure
              </div>
            )}
            <Button 
              variant="ghost" 
              size="sm" 
              className="ml-auto text-primary hover:text-white hover:bg-primary"
              onClick={(e) => {
                e.stopPropagation();
                onSelect(template);
              }}
            >
              Create
              <ArrowRight className="h-4 w-4 ml-1" />
            </Button>
          </div>
        </CardFooter>
      </Card>
    </motion.div>
  );
};

export default TemplateCard;