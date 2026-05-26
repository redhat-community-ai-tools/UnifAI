import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useLocation } from 'wouter';
import Header from '@/components/layout/Header';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  TemplateCatalog,
  TemplateDetailView,
  InstantiationProgress
} from '@/components/agentic-ai/templates';
import type { TemplateDetailViewRef } from '@/components/agentic-ai/templates';
import { useTemplates } from '@/hooks/use-templates';
import { useAuth } from '@/contexts/AuthContext';
import { useToast } from '@/hooks/use-toast';
import { createSession } from '@/api/sessions';
import { TemplateListItem, TemplateFormData } from '@/types/templates';

type ViewMode = 'catalog' | 'detail';

export default function AgenticTemplates() {
  const [, navigate] = useLocation();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [viewMode, setViewMode] = useState<ViewMode>('catalog');
  const [isCreatingSession, setIsCreatingSession] = useState(false);
  const templateDetailRef = useRef<TemplateDetailViewRef>(null);
  const { user } = useAuth();
  const { toast } = useToast();

  const {
    templates,
    selectedTemplate,
    normalizedFields,
    isLoading,
    error,
    instantiationStatus,
    instantiationResult,
    fetchTemplates,
    fetchTemplateDetail,
    materialize,
    resetInstantiation,
    getCategories,
    setSelectedTemplate,
    getValidationResults
  } = useTemplates();

  useEffect(() => {
    fetchTemplates();
  }, [fetchTemplates]);

  const handleSelectTemplate = useCallback(async (template: TemplateListItem) => {
    setSelectedTemplate(template);
    setViewMode('detail');
    
    await fetchTemplateDetail(template.template_id);
  }, [setSelectedTemplate, fetchTemplateDetail]);

  const handleBackToCatalog = useCallback(() => {
    setViewMode('catalog');
    setSelectedTemplate(null);
  }, [setSelectedTemplate]);

  const handleGenerateWorkflow = useCallback(async (data: TemplateFormData) => {
    if (!selectedTemplate || !user) return;
    
    // Generate a blueprint name based on template name
    const blueprintName = `${selectedTemplate.name} - ${new Date().toLocaleDateString()}`;
    
    await materialize(selectedTemplate.template_id, data, user.username, blueprintName);
  }, [selectedTemplate, materialize, user]);

  const handleRetryInstantiation = useCallback(() => {
    resetInstantiation();
    // Reset form fields to defaults
    templateDetailRef.current?.resetForm();
  }, [resetInstantiation]);

  const handleNavigateToWorkflow = useCallback(() => {
    resetInstantiation();
    navigate('/agentic-ai');
  }, [resetInstantiation, navigate]);

  const handleNavigateToChat = useCallback(async () => {
    if (!instantiationResult?.blueprint_id || !user) {
      toast({
        title: 'Error',
        description: 'Could not create chat session. Missing workflow or user information.',
        variant: 'destructive'
      });
      return;
    }

    setIsCreatingSession(true);
    try {
      // Create a new chat session with the blueprint
      await createSession({ blueprintId: instantiationResult.blueprint_id, userId: user.username });
      resetInstantiation();
      navigate('/agentic-chats');
    } catch (err) {
      console.error('Error creating chat session:', err);
      toast({
        title: 'Error',
        description: 'Failed to create chat session. Please try again.',
        variant: 'destructive'
      });
    } finally {
      setIsCreatingSession(false);
    }
  }, [instantiationResult, user, resetInstantiation, navigate, toast]);

  const handleCloseProgress = useCallback(() => {
    resetInstantiation();
  }, [resetInstantiation]);

  const categories = getCategories();

  const isGenerating = instantiationStatus !== 'idle' && 
                       instantiationStatus !== 'completed' && 
                       instantiationStatus !== 'failed';

  const validationResults = getValidationResults();

  return (
    <>
      <Header 
        title="Agentic AI Templates" 
        onToggleSidebar={() => setSidebarOpen(!sidebarOpen)} 
      />

      <main className="flex-1 overflow-y-auto bg-background-dark">
        <div className="p-6">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
          >
            {viewMode === 'catalog' && (
              <>
                <div className="mb-6">
                  <h1 className="text-3xl font-heading font-bold mb-2">
                    Workflow Templates
                  </h1>
                  <p className="text-gray-400">
                    Choose a template to create production-ready agentic workflows in minutes.
                    Each template provides a complete solution that you can customize to your needs.
                  </p>
                </div>

                <TemplateCatalog
                  templates={templates}
                  categories={categories}
                  isLoading={isLoading}
                  onSelectTemplate={handleSelectTemplate}
                />
              </>
            )}

            <AnimatePresence mode="wait">
              {viewMode === 'detail' && selectedTemplate && (
                <TemplateDetailView
                  ref={templateDetailRef}
                  key="detail"
                  template={selectedTemplate}
                  fields={normalizedFields}
                  onBack={handleBackToCatalog}
                  onGenerate={handleGenerateWorkflow}
                  isSubmitting={isGenerating}
                />
              )}
            </AnimatePresence>
          </motion.div>
        </div>
      </main>

      <InstantiationProgress
        status={instantiationStatus}
        result={instantiationResult}
        error={error}
        validationResults={validationResults}
        onClose={handleCloseProgress}
        onRetry={handleRetryInstantiation}
        onNavigateToWorkflow={handleNavigateToWorkflow}
        onNavigateToChat={handleNavigateToChat}
        isCreatingSession={isCreatingSession}
      />
    </>
  );
}