import React, { useState, useEffect } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Input } from "@/components/ui/input";
import axios from "../../../http/axiosAgentConfig";

interface ConditionalEdgeModalProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: (branchConfig: any) => void;
  sourceNodeId: string;
  targetNodeId: string;
  conditionType: string;
  existingBranches?: string[];
  sourceNodeName?: string;
  targetNodeName?: string;
}

interface ConditionSpec {
  name: string;
  category: string;
  description: string;
  type: string;
  config_schema: any;
  output_schema: any;
}

const ConditionalEdgeModal: React.FC<ConditionalEdgeModalProps> = ({
  isOpen,
  onClose,
  onConfirm,
  sourceNodeId,
  targetNodeId,
  conditionType,
  existingBranches = [],
  sourceNodeName,
  targetNodeName,
}) => {
  const [conditionSpec, setConditionSpec] = useState<ConditionSpec | null>(null);
  const [selectedBranch, setSelectedBranch] = useState<string>("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (isOpen && conditionType) {
      fetchConditionSpec();
    }
  }, [isOpen, conditionType]);

  const fetchConditionSpec = async () => {
    try {
      setLoading(true);
      const response = await axios.get(
        `/catalog/element.spec.get?category=conditions&type=${conditionType}`,
      );
      setConditionSpec(response.data);
    } catch (error) {
      console.error("Error fetching condition spec:", error);
    } finally {
      setLoading(false);
    }
  };

  const handleConfirm = () => {
    let branchConfig: any = {};

    if (conditionType === "router_boolean") {
      branchConfig.branch = selectedBranch;
    }

    onConfirm(branchConfig);
  };

  const getAvailableBranches = () => {
    if (!conditionSpec?.output_schema?.symbolic_branches) return [];

    return conditionSpec.output_schema.symbolic_branches.filter(
      (branch: any) => !existingBranches.includes(String(branch.name)),
    );
  };

  const isFormValid = () => {
    if (conditionType === "router_direct") return true;
    if (conditionType === "router_boolean") {
      if (!selectedBranch) return false;
    }
    return true;
  };

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-[425px] bg-gray-900 border-gray-700">
        <DialogHeader>
          <DialogTitle className="text-white">
            Configure Conditional Edge
          </DialogTitle>
        </DialogHeader>

        {loading ? (
          <div className="flex justify-center p-4">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-white"></div>
          </div>
        ) : (
          <div className="space-y-4">
            <div>
              <Label className="text-gray-300">Condition Type</Label>
              <p className="text-sm text-gray-400">{conditionType}</p>
            </div>

            <div>
              <Label className="text-gray-300">Source → Target</Label>
              <p className="text-sm text-gray-400">
                {sourceNodeName || sourceNodeId} →{" "}
                {targetNodeName || targetNodeId}
              </p>
            </div>

            {conditionType === "router_boolean" && (
              <div>
                <Label className="text-gray-300">Branch Output</Label>
                <Select
                  value={selectedBranch}
                  onValueChange={setSelectedBranch}
                >
                  <SelectTrigger className="bg-gray-800 border-gray-600 text-white">
                    <SelectValue placeholder="Select branch output" />
                  </SelectTrigger>
                  <SelectContent className="bg-gray-800 border-gray-600">
                    {getAvailableBranches().map((branch: any) => (
                      <SelectItem
                        key={String(branch.name)}
                        value={String(branch.name)}
                        className="text-white hover:bg-gray-700"
                      >
                        {branch.display_name} ({String(branch.name)})
                      </SelectItem>
                    ))}
                  </SelectContent>
                  <p className="text-xs text-gray-500 mt-1">
                    {
                      getAvailableBranches().find(
                        (b: any) => String(b.name) === selectedBranch,
                      )?.description
                    }
                  </p>
                </Select>
              </div>
            )}

            <div className="flex justify-end space-x-2 pt-4">
              <Button
                variant="outline"
                onClick={onClose}
                className="border-gray-600 text-gray-300"
              >
                Cancel
              </Button>
              <Button
                onClick={handleConfirm}
                disabled={!isFormValid()}
                className="bg-primary hover:bg-primary/80"
              >
                Create Edge
              </Button>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
};

export default ConditionalEdgeModal;
