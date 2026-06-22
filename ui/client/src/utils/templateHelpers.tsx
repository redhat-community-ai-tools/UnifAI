import React from 'react';
import { 
  FileText, 
  MessageSquare, 
  Database, 
  GitBranch,
  Zap,
  Key,
  List,
  CheckCircle,
  Settings
} from 'lucide-react';
import { NormalizedField } from '@/types/templates';

/**
 * Get display-friendly type name for a template field
 */
export const getFieldDisplayType = (field: NormalizedField): string => {
  if (field.isSecret) return 'secret';
  if (field.type === 'array') return 'list';
  return field.type;
};

/**
 * Get icon for a template category
 * @param category - The category name
 * @param size - Icon size class (default: "h-6 w-6")
 */
export const getCategoryIcon = (category: string, size: string = "h-6 w-6"): React.ReactNode => {
  const iconMap: Record<string, React.ReactNode> = {
    devops: <GitBranch className={size} />,
    git: <GitBranch className={size} />,
    data: <Database className={size} />,
    database: <Database className={size} />,
    chat: <MessageSquare className={size} />,
    bot: <MessageSquare className={size} />,
    automation: <Zap className={size} />,
    workflow: <Zap className={size} />,
  };

  return (category && iconMap[category.toLowerCase()]) || <FileText className={size} />;
};

/**
 * Get icon for a field type
 * @param type - The field type
 * @param isSecret - Whether the field is a secret
 */
export const getFieldTypeIcon = (type: string, isSecret?: boolean): React.ReactNode => {
  if (isSecret) {
    return <Key className="h-4 w-4 text-yellow-500" />;
  }
  switch (type) {
    case 'secret':
      return <Key className="h-4 w-4 text-yellow-500" />;
    case 'array':
      return <List className="h-4 w-4 text-blue-500" />;
    case 'boolean':
      return <CheckCircle className="h-4 w-4 text-green-500" />;
    default:
      return <Settings className="h-4 w-4 text-gray-500" />;
  }
};

