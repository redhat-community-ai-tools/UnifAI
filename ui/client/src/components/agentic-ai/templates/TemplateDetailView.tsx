import React, { useState, useCallback, useEffect, useImperativeHandle, forwardRef } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  ArrowLeft,
  Zap,
  CheckCircle,
  Settings,
  Pencil,
  Eye,
  User,
  AlertCircle
} from 'lucide-react';
import { TemplateListItem, NormalizedField, TemplateFormData } from '@/types/templates';
import { getFieldDisplayType, getCategoryIcon, getFieldTypeIcon } from '@/utils/templateHelpers';
import { FieldInput } from './FieldInputs';

interface TemplateDetailViewProps {
  template: TemplateListItem;
  fields: NormalizedField[];
  onBack: () => void;
  onGenerate: (data: TemplateFormData) => void;
  isSubmitting?: boolean;
}

export interface TemplateDetailViewRef {
  resetForm: () => void;
}

/**
 * Get default value for a field based on its type
 */
const defaultValueByType: Record<string, () => any> = {
  array: () => [],
  boolean: () => false,
};

const getFieldDefaultValue = (field: NormalizedField): any => {
  if (field.default !== undefined) {
    return Array.isArray(field.default) ? [...field.default] : field.default;
  }
  return defaultValueByType[field.type]?.() ?? undefined;
};

interface FieldCardProps {
  field: NormalizedField;
  isEditing: boolean;
  value: any;
  onChange: (value: any) => void;
  error?: string;
  onClickToEdit?: () => void;
}

const FieldCard: React.FC<FieldCardProps> = ({ 
  field, 
  isEditing, 
  value, 
  onChange,
  error,
  onClickToEdit
}) => {

  return (
    <div className="relative h-auto min-h-[72px]" style={{ perspective: '1000px' }}>
      <AnimatePresence mode="wait">
        {!isEditing ? (
          <motion.div
            key="badge"
            initial={{ rotateX: -90, opacity: 0 }}
            animate={{ rotateX: 0, opacity: 1 }}
            exit={{ rotateX: 90, opacity: 0 }}
            transition={{ duration: 0.3, ease: 'easeInOut' }}
            className={`flex items-center gap-2 p-3 bg-background-dark rounded-lg border cursor-pointer hover:border-primary/50 transition-colors ${
              error ? 'border-red-500 bg-red-500/5' : 'border-gray-800'
            }`}
            style={{ transformStyle: 'preserve-3d', backfaceVisibility: 'hidden' }}
            onClick={onClickToEdit}
          >
            {error ? (
              <AlertCircle className="h-4 w-4 text-red-500 shrink-0" />
            ) : (
              getFieldTypeIcon(field.type, field.isSecret)
            )}
            <div className="flex-1">
              <div className="flex items-center gap-2">
                <span className={`text-sm font-medium ${error ? 'text-red-400' : 'text-gray-200'}`}>{field.label}</span>
                {field.required && (
                  <Badge variant="destructive" className="text-xs px-1.5 py-0">
                    Required
                  </Badge>
                )}
                <Badge variant="outline" className="text-xs px-1.5 py-0">
                  {getFieldDisplayType(field)}
                </Badge>
              </div>
              {error ? (
                <p className="text-xs text-red-500 mt-0.5 flex items-center gap-1">
                  {error}
                </p>
              ) : field.description ? (
                <p className="text-xs text-gray-500 mt-0.5">{field.description}</p>
              ) : null}
            </div>
          </motion.div>
        ) : (
          <motion.div
            key="input"
            initial={{ rotateX: 90, opacity: 0 }}
            animate={{ rotateX: 0, opacity: 1 }}
            exit={{ rotateX: -90, opacity: 0 }}
            transition={{ duration: 0.3, ease: 'easeInOut' }}
            className="p-3 bg-background-dark rounded-lg border border-primary/30"
            style={{ transformStyle: 'preserve-3d', backfaceVisibility: 'hidden' }}
          >
            <FieldInput
              field={field}
              value={value}
              onChange={onChange}
              error={error}
            />
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};

interface FieldsSectionProps {
  title: string;
  fields: NormalizedField[];
  isEditing: boolean;
  onToggleEdit: () => void;
  formData: TemplateFormData;
  onFieldChange: (key: string, value: any) => void;
  errors: Record<string, string>;
  showToggle: boolean;
}

const FieldsSection: React.FC<FieldsSectionProps> = ({
  title,
  fields,
  isEditing,
  onToggleEdit,
  formData,
  onFieldChange,
  errors,
  showToggle
}) => {
  if (fields.length === 0) return null;

  return (
    <div>
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-lg font-medium">
          {title}
          <span className="text-sm font-normal text-gray-500 ml-2">
            ({fields.length} fields)
          </span>
        </h3>
        {showToggle && (
          <Button
            variant="ghost"
            size="sm"
            onClick={onToggleEdit}
            className="text-primary hover:text-primary/90 hover:bg-primary/10 gap-2"
          >
            {isEditing ? (
              <>
                <Eye className="h-4 w-4" />
                View Mode
              </>
            ) : (
              <>
                <Pencil className="h-4 w-4" />
                Edit Fields
              </>
            )}
          </Button>
        )}
      </div>
      <div className="space-y-3">
        {fields.map((field, index) => (
          <motion.div
            key={field.key}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: index * 0.05 }}
          >
            <FieldCard
              field={field}
              isEditing={isEditing}
              value={formData[field.key]}
              onChange={(value) => onFieldChange(field.key, value)}
              error={errors[field.key]}
              onClickToEdit={!isEditing ? onToggleEdit : undefined}
            />
          </motion.div>
        ))}
      </div>
    </div>
  );
};

export const TemplateDetailView = forwardRef<TemplateDetailViewRef, TemplateDetailViewProps>(({
  template,
  fields,
  onBack,
  onGenerate,
  isSubmitting = false
}, ref) => {
  const [isEditingRequired, setIsEditingRequired] = useState(false);
  const [isEditingOptional, setIsEditingOptional] = useState(false);
  const [formData, setFormData] = useState<TemplateFormData>({});
  const [errors, setErrors] = useState<Record<string, string>>({});

  // Reset form to default values
  const resetForm = useCallback(() => {
    const initial = fields.reduce<TemplateFormData>((acc, field) => {
      acc[field.key] = getFieldDefaultValue(field);
      return acc;
    }, {});
    setFormData(initial);
    setErrors({});
    setIsEditingRequired(false);
    setIsEditingOptional(false);
  }, [fields]);

  // Expose resetForm to parent via ref
  useImperativeHandle(ref, () => ({
    resetForm
  }), [resetForm]);

  // Initialize form data with defaults
  useEffect(() => {
    resetForm();
  }, [resetForm]);

  const handleFieldChange = useCallback((key: string, value: any) => {
    setFormData(prev => ({ ...prev, [key]: value }));
    if (errors[key]) {
      setErrors(prev => {
        const next = { ...prev };
        delete next[key];
        return next;
      });
    }
  }, [errors]);

  const validateForm = useCallback((): boolean => {
    const newErrors: Record<string, string> = {};
    
    fields.forEach(field => {
      if (field.required) {
        const value = formData[field.key];
        
        if (value === undefined || value === null || value === '') {
          newErrors[field.key] = `${field.label} is required`;
        } else if (field.type === 'array' && Array.isArray(value) && value.length === 0) {
          newErrors[field.key] = `At least one ${field.label.toLowerCase()} is required`;
        }
      }

      // Validate pattern if specified
      if (field.pattern && formData[field.key]) {
        const regex = new RegExp(field.pattern);
        if (!regex.test(formData[field.key])) {
          newErrors[field.key] = `Invalid format for ${field.label}`;
        }
      }
    });

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  }, [fields, formData]);

  const handleGenerate = useCallback(() => {
    // Always validate first
    const isValid = validateForm();
    
    if (!isValid) {
      // If validation fails, switch to edit mode to show errors
      setIsEditingRequired(true);
      return;
    }

    // Validation passed, submit the form
    onGenerate(formData);
  }, [validateForm, onGenerate, formData]);

  const requiredFields = fields.filter(f => f.required);
  const optionalFields = fields.filter(f => !f.required);

  // Check if form has any filled data
  const hasFilledData = Object.values(formData).some(v => 
    v !== undefined && v !== null && v !== '' && 
    !(Array.isArray(v) && v.length === 0) &&
    v !== false
  );

  // Button text changes based on state
  const getButtonText = () => {
    if (isSubmitting) return 'Generating...';
    if (!isEditingRequired && !hasFilledData) return 'Configure & Generate';
    return 'Generate Workflow';
  };

  return (
    <motion.div
      initial={{ opacity: 0, x: 20 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: -20 }}
      transition={{ duration: 0.3 }}
      className="space-y-6 dark-inputs"
    >
      <Button 
        variant="ghost" 
        onClick={onBack}
        className="text-gray-400 hover:text-white"
      >
        <ArrowLeft className="h-4 w-4 mr-2" />
        Back to Templates
      </Button>

      <Card className="bg-background-card border-gray-800">
        <CardHeader className="border-b border-gray-800">
          <div className="flex items-start gap-4">
            <div className="w-14 h-14 rounded-xl bg-gradient-to-br from-primary to-primary/80 flex items-center justify-center text-white">
              {getCategoryIcon(template.category, "h-8 w-8")}
            </div>
            <div className="flex-1">
              <div className="flex items-start justify-between">
                <div>
                  <CardTitle className="text-2xl font-heading mb-2">
                    {template.name}
                  </CardTitle>
                  <div className="flex items-center gap-2 flex-wrap">
                    <Badge variant="outline">{template.category}</Badge>
                    <Badge variant="secondary" className="bg-gray-800">
                      v{template.version}
                    </Badge>
                    {template.author && (
                      <span className="flex items-center text-xs text-gray-400">
                        <User className="h-3 w-3 mr-1" />
                        {template.author}
                      </span>
                    )}
                    {template.placeholder_count !== undefined && (
                      <span className="flex items-center text-xs text-gray-400">
                        <Settings className="h-3 w-3 mr-1" />
                        {template.placeholder_count} field{template.placeholder_count !== 1 ? 's' : ''}
                      </span>
                    )}
                  </div>
                </div>
                <Button 
                  onClick={handleGenerate}
                  className="bg-primary hover:bg-primary/90"
                  disabled={isSubmitting}
                >
                  <Zap className="h-4 w-4 mr-2" />
                  {getButtonText()}
                </Button>
              </div>
            </div>
          </div>
        </CardHeader>
        
        <CardContent className="p-6 space-y-6">
          <div>
            <h3 className="text-lg font-medium mb-3">Description</h3>
            <p className="text-gray-400 leading-relaxed">{template.description}</p>
          </div>

          {template.output_capabilities && template.output_capabilities.length > 0 && (
            <div>
              <h3 className="text-lg font-medium mb-3">What You Get</h3>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                {template.output_capabilities.map((capability, idx) => (
                  <div 
                    key={idx}
                    className="flex items-center gap-2 p-3 bg-primary/10 rounded-lg border border-primary/20"
                  >
                    <CheckCircle className="h-5 w-5 text-primary" />
                    <span className="text-sm text-gray-200">{capability}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          <FieldsSection
            title="Required Inputs"
            fields={requiredFields}
            isEditing={isEditingRequired}
            onToggleEdit={() => setIsEditingRequired(!isEditingRequired)}
            formData={formData}
            onFieldChange={handleFieldChange}
            errors={errors}
            showToggle={requiredFields.length > 0}
          />

          <FieldsSection
            title="Optional Settings"
            fields={optionalFields}
            isEditing={isEditingOptional}
            onToggleEdit={() => setIsEditingOptional(!isEditingOptional)}
            formData={formData}
            onFieldChange={handleFieldChange}
            errors={errors}
            showToggle={optionalFields.length > 0}
          />

          {template.tags && template.tags.length > 0 && (
            <div>
              <h3 className="text-lg font-medium mb-3">Tags</h3>
              <div className="flex flex-wrap gap-2">
                {template.tags.map((tag, idx) => (
                  <span 
                    key={idx}
                    className="text-sm text-gray-400 bg-gray-800 px-3 py-1 rounded-full"
                  >
                    #{tag}
                  </span>
                ))}
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </motion.div>
  );
});

TemplateDetailView.displayName = 'TemplateDetailView';

export default TemplateDetailView;