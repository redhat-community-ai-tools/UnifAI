import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { motion, AnimatePresence } from "framer-motion";
import { ArrowLeft, ChevronRight, Globe, LoaderCircle } from "lucide-react";
import type { ElementType } from "@/types/workspace";
import { DROPDOWN_BG, getCategoryMeta, type WizardStep } from "./types";

interface CategoryOption {
  category: string;
  elements: ElementType[];
}

interface AddResourceWizardPanelProps {
  step: WizardStep;
  availableCategories: CategoryOption[];
  selectedCategoryKey: string;
  selectedCategoryElements: ElementType[];
  selectedElementType: ElementType | null;
  isLoadingSchema: boolean;
  newElementAvailableToAll: boolean;
  editingElementName?: string;
  onCategoryChange: (value: string) => void;
  onTypeChange: (value: string) => void;
  onAvailableToAllChange: (value: boolean) => void;
  onBack: () => void;
  onNext: () => void;
  onCancel: () => void;
}

/**
 * The "Add New" category/type-selection wizard, plus the loading/"configuring"
 * transition card shown while opening the element form. Split out of
 * ``RepositoryManagement.tsx`` — purely presentational, driven by the wizard
 * state owned by the parent.
 */
export function AddResourceWizardPanel({
  step,
  availableCategories,
  selectedCategoryKey,
  selectedCategoryElements,
  selectedElementType,
  isLoadingSchema,
  newElementAvailableToAll,
  editingElementName,
  onCategoryChange,
  onTypeChange,
  onAvailableToAllChange,
  onBack,
  onNext,
  onCancel,
}: AddResourceWizardPanelProps) {
  return (
    <AnimatePresence>
      {step === "select-category" && (
        <motion.div
          initial={{ opacity: 0, height: 0 }}
          animate={{ opacity: 1, height: "auto" }}
          exit={{ opacity: 0, height: 0 }}
          transition={{ duration: 0.25 }}
        >
          <Card className="bg-background-card shadow-card border-gray-800 border-primary/30">
            <CardContent className="p-6">
              <div className="flex items-center gap-2 mb-6">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={onBack}
                  className="text-gray-400 hover:text-white -ml-2"
                >
                  <ArrowLeft className="h-4 w-4 mr-1" />
                  Cancel
                </Button>
                <div className="h-4 w-px bg-gray-700" />
                <h3 className="text-sm font-medium text-gray-300">
                  Add New Resource
                </h3>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="space-y-2">
                  <label className="text-sm font-medium text-gray-300">
                    Resource Category
                  </label>
                  {/* Keyed on the value: when the wizard stays open across two
                      "Add to category" clicks (or "Add New" while already
                      open), Radix Select's controlled value can get stuck
                      showing the previous selection because the outgoing
                      item's portaled text isn't cleared without a remount
                      (see radix-ui/primitives#1569, unfixed as of the
                      @radix-ui/react-select version pinned here). Forcing a
                      fresh instance per value sidesteps that. */}
                  <Select
                    key={selectedCategoryKey || "none"}
                    value={selectedCategoryKey}
                    onValueChange={onCategoryChange}
                  >
                    <SelectTrigger className="bg-background-dark border-gray-700">
                      <SelectValue placeholder="Choose a category..." />
                    </SelectTrigger>
                    <SelectContent className={DROPDOWN_BG}>
                      {availableCategories.map((cat) => {
                        const meta = getCategoryMeta(cat.category);
                        return (
                          <SelectItem key={cat.category} value={cat.category}>
                            <div className="flex items-center gap-2">
                              {meta.icon}
                              <span>{meta.label}</span>
                              <span className="text-xs text-gray-500 ml-1">
                                ({cat.elements.length})
                              </span>
                            </div>
                          </SelectItem>
                        );
                      })}
                    </SelectContent>
                  </Select>
                  {selectedCategoryKey && (
                    <p className="text-xs text-gray-500">
                      {getCategoryMeta(selectedCategoryKey).description}
                    </p>
                  )}
                </div>

                <div className="space-y-2">
                  <label className="text-sm font-medium text-gray-300">
                    Resource Type
                  </label>
                  {/* Same Radix Select remount workaround as the category
                      dropdown above — the type list (and value) fully
                      changes whenever the category changes anyway, so keying
                      on the category is a natural remount boundary. */}
                  <Select
                    key={selectedCategoryKey}
                    value={selectedElementType?.type ?? ""}
                    onValueChange={onTypeChange}
                    disabled={!selectedCategoryKey}
                  >
                    <SelectTrigger className="bg-background-dark border-gray-700">
                      <SelectValue
                        placeholder={
                          selectedCategoryKey
                            ? "Choose a type..."
                            : "Select a category first"
                        }
                      />
                    </SelectTrigger>
                    <SelectContent className={DROPDOWN_BG}>
                      {selectedCategoryElements.map((el) => (
                        <SelectItem key={el.type} value={el.type}>
                          {el.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>

              {selectedElementType && (
                <div className="mt-6 pt-4 border-t border-gray-800 space-y-4">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <Globe className="h-4 w-4 text-green-400" />
                      <div>
                        <p className="text-sm font-medium text-gray-200">
                          Available to All
                        </p>
                        <p className="text-xs text-gray-500">
                          When enabled, all users will see this resource in their workspace
                        </p>
                      </div>
                    </div>
                    <Switch
                      checked={newElementAvailableToAll}
                      onCheckedChange={onAvailableToAllChange}
                    />
                  </div>
                </div>
              )}

              <div className="flex justify-end mt-6 pt-4 border-t border-gray-800">
                <Button
                  onClick={onNext}
                  disabled={!selectedElementType || isLoadingSchema}
                  className="bg-primary hover:bg-primary/80"
                >
                  {isLoadingSchema ? (
                    <>
                      <LoaderCircle className="h-4 w-4 mr-2 animate-spin" />
                      Loading...
                    </>
                  ) : (
                    <>
                      Next
                      <ChevronRight className="h-4 w-4 ml-2" />
                    </>
                  )}
                </Button>
              </div>
            </CardContent>
          </Card>
        </motion.div>
      )}

      {step === "configure" && (
        <motion.div
          initial={{ opacity: 0, height: 0 }}
          animate={{ opacity: 1, height: "auto" }}
          exit={{ opacity: 0, height: 0 }}
          transition={{ duration: 0.25 }}
        >
          <Card className="bg-background-card shadow-card border-gray-800 border-green-500/30">
            <CardContent className="p-6">
              <div className="flex items-center justify-center py-4 gap-3">
                <LoaderCircle className="h-5 w-5 animate-spin text-green-400" />
                <p className="text-sm text-gray-300">
                  {editingElementName ? "Editing" : "Configuring"}{" "}
                  <span className="text-white font-medium">
                    {selectedElementType?.name}
                  </span>{" "}
                  — fill in the form and save.
                </p>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={onCancel}
                  className="text-gray-400 hover:text-white ml-2"
                >
                  Cancel
                </Button>
              </div>
            </CardContent>
          </Card>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
