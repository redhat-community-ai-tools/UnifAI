import React, {
  forwardRef,
  useCallback,
  useImperativeHandle,
  useState,
} from "react";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { ElementData } from "@/components/agentic-ai/workspace/ElementData";
import { ResourceInUseModal, type InUseData } from "@/components/agentic-ai/workspace/ResourceInUseModal";
import { useToast } from "@/hooks/use-toast";
import type { ElementCategory, ElementInstance, ElementType } from "@/types/workspace";

/** Subset of `useWorkspaceData` needed for delete / in-use / preview flows. */
export interface WorkspaceElementDeletionWorkspaceApis {
  fetchElementInstances: (category: string, type: string) => Promise<void>;
  fetchResourceById: (resourceId: string) => Promise<{
    rid: string;
    name: string;
    cfg_dict: unknown;
    category: string;
    type: string;
    version: number;
    created: string;
    updated: string;
    nested_refs: string[];
  } | null>;
  checkElementUsage: (rid: string) => Promise<
    | { inUse: false }
    | {
        inUse: true;
        category: string;
        allowed_mode: string;
        blueprints: unknown[];
        resources: unknown[];
      }
  >;
  deleteElement: (rid: string) => Promise<
    | { deleted: true }
    | {
        deleted: false;
        inUse: true;
        category: string;
        allowed_mode: string;
        blueprints: unknown[];
        resources: unknown[];
      }
    | { deleted: false; inUse: false }
  >;
  forceDeleteElement: (
    rid: string,
    mode: "replace" | "detach" | "cascade",
    replacementId?: string,
  ) => Promise<boolean>;
  fetchResourcesForCategory: (category: string) => Promise<
    Array<{ rid: string; name: string; type: string }>
  >;
}

export interface WorkspaceElementDeletionFlowProps {
  selectedElementType: ElementType | null;
  elementInstances: ElementInstance[];
  categories: ElementCategory[];
  workspace: WorkspaceElementDeletionWorkspaceApis;
}

export type WorkspaceElementDeletionFlowHandle = {
  handleDeleteElement: (rid: string) => Promise<void>;
};

export const WorkspaceElementDeletionFlow = forwardRef<
  WorkspaceElementDeletionFlowHandle,
  WorkspaceElementDeletionFlowProps
>(function WorkspaceElementDeletionFlow(
  { selectedElementType, elementInstances, categories, workspace },
  ref,
) {
  const { toast } = useToast();
  const {
    fetchElementInstances,
    fetchResourceById,
    checkElementUsage,
    deleteElement,
    forceDeleteElement,
    fetchResourcesForCategory,
  } = workspace;

  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [elementToDelete, setElementToDelete] = useState<ElementInstance | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  const [showInUseModal, setShowInUseModal] = useState(false);
  const [inUseData, setInUseData] = useState<InUseData | null>(null);
  const [replacementOptions, setReplacementOptions] = useState<
    Array<{ rid: string; name: string; type: string }>
  >([]);
  const [isLoadingReplacements, setIsLoadingReplacements] = useState(false);

  const [previewResource, setPreviewResource] = useState<ElementInstance | null>(null);
  const [previewResourceType, setPreviewResourceType] = useState<ElementType | null>(null);
  const [isResourcePreviewOpen, setIsResourcePreviewOpen] = useState(false);
  const [isLoadingResourcePreview, setIsLoadingResourcePreview] = useState(false);

  const handleDeleteElement = useCallback(
    async (rid: string) => {
      const element = elementInstances.find((el) => el.rid === rid);
      if (!element) return;

      setElementToDelete(element);

      try {
        const usage = await checkElementUsage(rid);
        if ("inUse" in usage && usage.inUse) {
          setInUseData({
            category: usage.category,
            allowed_mode: usage.allowed_mode as "replace" | "detach" | "cascade",
            blueprints: usage.blueprints as InUseData["blueprints"],
            resources: usage.resources as InUseData["resources"],
          });
          setShowInUseModal(true);

          if (usage.allowed_mode === "replace") {
            setIsLoadingReplacements(true);
            try {
              const options = await fetchResourcesForCategory(usage.category);
              setReplacementOptions(options.filter((o) => o.rid !== element.rid));
            } finally {
              setIsLoadingReplacements(false);
            }
          }
        } else {
          setShowDeleteModal(true);
        }
      } catch (error) {
        console.error("Error during element deletion check:", error);
        toast({
          title: "Error",
          description: "Failed to check element usage. Please try again.",
          variant: "destructive",
        });
        setElementToDelete(null);
      }
    },
    [checkElementUsage, elementInstances, fetchResourcesForCategory, toast],
  );

  useImperativeHandle(ref, () => ({ handleDeleteElement }), [handleDeleteElement]);

  const confirmDeleteElement = useCallback(async () => {
    if (!elementToDelete || !selectedElementType) return;

    setIsDeleting(true);
    try {
      const result = await deleteElement(elementToDelete.rid);
      if (result.deleted) {
        await fetchElementInstances(selectedElementType.category, selectedElementType.type);
        setShowDeleteModal(false);
        setElementToDelete(null);
      } else if ("inUse" in result && result.inUse) {
        setShowDeleteModal(false);
        setInUseData({
          category: result.category,
          allowed_mode: result.allowed_mode as "replace" | "detach" | "cascade",
          blueprints: result.blueprints as InUseData["blueprints"],
          resources: result.resources as InUseData["resources"],
        });
        setShowInUseModal(true);
        if (result.allowed_mode === "replace") {
          setIsLoadingReplacements(true);
          try {
            const options = await fetchResourcesForCategory(result.category);
            setReplacementOptions(options.filter((o) => o.rid !== elementToDelete.rid));
          } finally {
            setIsLoadingReplacements(false);
          }
        }
      }
    } catch (error) {
      console.error("Error deleting element:", error);
    } finally {
      setIsDeleting(false);
    }
  }, [
    deleteElement,
    elementToDelete,
    fetchElementInstances,
    fetchResourcesForCategory,
    selectedElementType,
  ]);

  const cancelDeleteElement = useCallback(() => {
    setShowDeleteModal(false);
    setElementToDelete(null);
  }, []);

  const handleForceDelete = useCallback(
    async (mode: "replace" | "detach" | "cascade", replacementId?: string) => {
      if (!elementToDelete || !selectedElementType) return;
      const success = await forceDeleteElement(elementToDelete.rid, mode, replacementId);
      if (success) {
        setShowInUseModal(false);
        setInUseData(null);
        setElementToDelete(null);
        setReplacementOptions([]);
        await fetchElementInstances(selectedElementType.category, selectedElementType.type);
      }
    },
    [elementToDelete, fetchElementInstances, forceDeleteElement, selectedElementType],
  );

  const closeInUseModal = useCallback(() => {
    setShowInUseModal(false);
    setInUseData(null);
    setElementToDelete(null);
    setReplacementOptions([]);
  }, []);

  const handleDependentResourceClick = useCallback(
    async (resourceId: string, resourceCategory?: string, resourceType?: string) => {
      setIsLoadingResourcePreview(true);
      try {
        let resource;
        try {
          resource = await fetchResourceById(resourceId);
        } catch (err) {
          console.error("Error loading dependent resource:", err);
          toast({
            title: "Error",
            description: "Failed to load resource preview. Please try again.",
            variant: "destructive",
          });
          return;
        }
        if (!resource) {
          toast({
            title: "Not Found",
            description: "That resource could not be loaded.",
            variant: "destructive",
          });
          return;
        }

        const matchedCategory = categories.find(
          (c) => c.category === (resourceCategory || resource.category),
        );
        const elType: ElementType =
          matchedCategory?.elements.find((e) => e.type === (resourceType || resource.type)) || {
            type: resource.type,
            name: resource.type,
            category: resource.category,
          };

        setPreviewResource({
          rid: resource.rid,
          name: resource.name,
          config: resource.cfg_dict,
          category: resource.category,
          type: resource.type,
          version: resource.version,
          created: resource.created,
          updated: resource.updated,
          nested_refs: resource.nested_refs,
        });
        setPreviewResourceType(elType);
        setIsResourcePreviewOpen(true);
      } finally {
        setIsLoadingResourcePreview(false);
      }
    },
    [categories, fetchResourceById, toast],
  );

  return (
    <>
      <AlertDialog open={showDeleteModal} onOpenChange={setShowDeleteModal}>
        <AlertDialogContent
          overlayClassName="bg-black/90"
          className="bg-zinc-800 border-zinc-600 text-zinc-100 shadow-2xl overflow-hidden max-h-[90vh]"
        >
          <AlertDialogHeader>
            <AlertDialogTitle>
              Delete {selectedElementType?.name || "Element"}
            </AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete &quot;
              {elementToDelete?.name ||
                `${selectedElementType?.name || "Element"} Instance`}
              &quot;?
              <br />
              <br />
              <strong>Be aware that this action is irreversible.</strong>
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel
              onClick={cancelDeleteElement}
              className="bg-background-dark border-gray-700 hover:bg-background-surface"
            >
              Cancel
            </AlertDialogCancel>
            <AlertDialogAction
              onClick={confirmDeleteElement}
              disabled={isDeleting}
              className="bg-red-600 hover:bg-red-700 text-white"
            >
              {isDeleting ? "Deleting..." : "Delete"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {inUseData && (
        <ResourceInUseModal
          open={showInUseModal}
          onClose={() => {
            if (isResourcePreviewOpen) return;
            closeInUseModal();
          }}
          elementName={elementToDelete?.name || "Element"}
          inUseData={inUseData}
          replacementOptions={replacementOptions}
          isLoadingReplacements={isLoadingReplacements}
          isLoadingResourcePreview={isLoadingResourcePreview}
          onForceDelete={handleForceDelete}
          onResourceClick={handleDependentResourceClick}
        />
      )}

      {previewResourceType && (
        <ElementData
          element={previewResource}
          elementType={previewResourceType}
          isOpen={isResourcePreviewOpen}
          onOpenChange={(open) => {
            setIsResourcePreviewOpen(open);
            if (!open) {
              setPreviewResource(null);
              setPreviewResourceType(null);
            }
          }}
          elementSchema={null}
        />
      )}
    </>
  );
});

WorkspaceElementDeletionFlow.displayName = "WorkspaceElementDeletionFlow";
