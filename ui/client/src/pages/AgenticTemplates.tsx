import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useLocation } from 'wouter';
import Header from '@/components/layout/Header';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  TemplateCatalog,
  TemplateDetailView,
  InstantiationProgress,
  ViewYamlDialog,
  CreateTemplateDialog,
} from '@/components/agentic-ai/templates';
import type { TemplateDetailViewRef } from '@/components/agentic-ai/templates';
import { ConfirmDialog } from '@/components/shared/ConfirmDialog';
import { useTemplates } from '@/hooks/use-templates';
import { useAdminAccess } from '@/hooks/use-admin-access';
import { useAuth } from '@/contexts/AuthContext';
import { useToast } from '@/hooks/use-toast';
import { createSession } from '@/api/sessions';
import { getTemplate, createTemplate, deleteTemplate } from '@/api/templates';
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
  const { isAdmin } = useAdminAccess();

  // Admin dialog state
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [isCreatingTemplate, setIsCreatingTemplate] = useState(false);
  const [showYamlDialog, setShowYamlDialog] = useState(false);
  const [yamlViewDraft, setYamlViewDraft] = useState<Record<string, any> | null>(null);
  const [yamlViewName, setYamlViewName] = useState('');
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [templateToDelete, setTemplateToDelete] = useState<TemplateListItem | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

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
    
    const blueprintName = `${selectedTemplate.name} - ${new Date().toLocaleDateString()}`;
    
    await materialize(selectedTemplate.template_id, data, user.username, blueprintName);
  }, [selectedTemplate, materialize, user]);

  const handleRetryInstantiation = useCallback(() => {
    resetInstantiation();
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
      await createSession({ blueprintId: instantiationResult.blueprint_id });
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

  // ── Admin handlers ──────────────────────────────────────────────────

  const handleViewYaml = useCallback(async (template: TemplateListItem) => {
    try {
      const detail = await getTemplate(template.template_id);
      setYamlViewDraft(detail.draft);
      setYamlViewName(template.name);
      setShowYamlDialog(true);
    } catch (err) {
      console.error('Error fetching template for YAML view:', err);
      toast({
        title: 'Error',
        description: 'Failed to load template YAML.',
        variant: 'destructive'
      });
    }
  }, [toast]);

  const handleDeleteRequest = useCallback((template: TemplateListItem) => {
    setTemplateToDelete(template);
    setShowDeleteConfirm(true);
  }, []);

  const handleDeleteConfirm = useCallback(async () => {
    if (!templateToDelete || !user) return;
    setIsDeleting(true);
    try {
      await deleteTemplate(templateToDelete.template_id, user.username);
      toast({ title: 'Deleted', description: `Template "${templateToDelete.name}" deleted.` });
      setShowDeleteConfirm(false);
      setTemplateToDelete(null);
      fetchTemplates();
    } catch (err) {
      console.error('Error deleting template:', err);
      toast({
        title: 'Error',
        description: 'Failed to delete template.',
        variant: 'destructive'
      });
    } finally {
      setIsDeleting(false);
    }
  }, [templateToDelete, fetchTemplates, toast, user]);

  const handleCreateTemplate = useCallback(async (data: {
    draft: Record<string, any>;
    placeholders: Record<string, any>;
    metadata: Record<string, any>;
  }) => {
    if (!user) return;
    setIsCreatingTemplate(true);
    try {
      const result = await createTemplate(data, user.username);
      toast({ title: 'Created', description: `Template created (${result.template_id}).` });
      setShowCreateDialog(false);
      fetchTemplates();
    } catch (err: any) {
      const msg = err.response?.data?.error || 'Failed to create template.';
      toast({ title: 'Error', description: msg, variant: 'destructive' });
    } finally {
      setIsCreatingTemplate(false);
    }
  }, [fetchTemplates, toast, user]);

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
                  <p className="text-muted-foreground">
                    Choose a template to create production-ready agentic workflows in minutes.
                    Each template provides a complete solution that you can customize to your needs.
                  </p>
                </div>

                <TemplateCatalog
                  templates={templates}
                  categories={categories}
                  isLoading={isLoading}
                  isAdmin={isAdmin}
                  onSelectTemplate={handleSelectTemplate}
                    onAddTemplate={() => setShowCreateDialog(true)}
                    onViewYaml={handleViewYaml}
                    onDeleteTemplate={handleDeleteRequest}
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

      {/* Admin dialogs */}
      <CreateTemplateDialog
        open={showCreateDialog}
        onOpenChange={setShowCreateDialog}
        onSubmit={handleCreateTemplate}
        isSubmitting={isCreatingTemplate}
      />

      <ViewYamlDialog
        open={showYamlDialog}
        onOpenChange={setShowYamlDialog}
        templateName={yamlViewName}
        draft={yamlViewDraft}
      />

      <ConfirmDialog
        open={showDeleteConfirm}
        title="Delete Template"
        message={`Are you sure you want to delete "${templateToDelete?.name}"? This action cannot be undone.`}
        confirmLabel="Delete"
        onConfirm={handleDeleteConfirm}
        onCancel={() => { setShowDeleteConfirm(false); setTemplateToDelete(null); }}
        loading={isDeleting}
      />
    </>
  );
}