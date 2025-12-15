
import React, { useState, useEffect, useRef } from 'react';
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { 
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import { Loader2, RefreshCw, ChevronDown, Check } from 'lucide-react';
import axios from "../../../http/axiosAgentConfig";

// Type for option items - can be string or object with label/value
interface OptionItem {
  label: string;
  value: string;
}

interface PaginationState {
  nextCursor: string | null;
  hasMore: boolean;
  total: number | null;
}

interface FieldPopulationProps {
  fieldName: string;
  populateHint: any;
  elementActions: any[];
  selectedElementType: any;
  formData: any;
  onPopulateResult: (fieldName: string, results: string[] | any, multiSelect: boolean) => void;
  autoTrigger?: boolean;
  hideUI?: boolean;
}

const SEARCH_DEBOUNCE_DELAY = 300; // ms

export const FieldPopulation: React.FC<FieldPopulationProps> = ({
  fieldName,
  populateHint,
  elementActions,
  selectedElementType,
  formData,
  onPopulateResult,
  autoTrigger = false,
  hideUI = false
}) => {
  const [isLoading, setIsLoading] = useState(false);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [populatedOptions, setPopulatedOptions] = useState<OptionItem[]>([]);
  const [selectedValues, setSelectedValues] = useState<string[]>([]);
  const [isDropdownOpen, setIsDropdownOpen] = useState(false);
  const [shouldKeepOpen, setShouldKeepOpen] = useState(false);
  const [hasAutoTriggered, setHasAutoTriggered] = useState(false);
  const [hasLoadedOnce, setHasLoadedOnce] = useState(false); // Track if options were ever loaded
  
  // Search state
  const [searchTerm, setSearchTerm] = useState('');
  const [debouncedSearchTerm, setDebouncedSearchTerm] = useState('');
  const [isSearching, setIsSearching] = useState(false);
  const searchTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  
  // Pagination state
  const [pagination, setPagination] = useState<PaginationState>({
    nextCursor: null,
    hasMore: false,
    total: null
  });

  // Extract hint flags with defaults for backwards compatibility
  const supportsPagination = populateHint.pagination === true;
  const supportsSearch = populateHint.search === true;
  const labelField = populateHint.label_field;
  const valueField = populateHint.value_field;

  // Find the populate action from elementActions
  const populateAction = elementActions.find(
    action => action.uid === populateHint.action_uid
  );

  if (!populateAction) {
    return null;
  }

  // Helper to normalize items to OptionItem format
  const normalizeOptions = (items: any[]): OptionItem[] => {
    if (!items || !Array.isArray(items)) return [];
    
    return items.map(item => {
      // If item is a string, use it for both label and value
      if (typeof item === 'string') {
        return { label: item, value: item };
      }
      
      // If item is an object with label_field/value_field specified
      if (labelField && valueField && typeof item === 'object') {
        return {
          label: item[labelField] || String(item[valueField] || ''),
          value: String(item[valueField] || '')
        };
      }
      
      // If item is an object with label/value properties (pre-normalized)
      if (typeof item === 'object' && 'label' in item && 'value' in item) {
        return {
          label: String(item.label),
          value: String(item.value)
        };
      }
      
      // Fallback: stringify the item
      return { label: String(item), value: String(item) };
    });
  };

  // Effect to force dropdown to stay open for multi-select
  useEffect(() => {
    if (shouldKeepOpen && populateHint.multi_select && !isDropdownOpen) {
      const timer = setTimeout(() => {
        setIsDropdownOpen(true);
        setShouldKeepOpen(false);
      }, 50);
      return () => clearTimeout(timer);
    }
  }, [shouldKeepOpen, populateHint.multi_select, isDropdownOpen]);

  // Effect to reset auto-trigger state when dependency values change
  useEffect(() => {    
    setHasAutoTriggered(false);
  }, [Object.keys(populateHint.dependencies || {}).map((depKey) => formData[depKey]).join(',')]);

  // Effect to auto-trigger population when dependencies are satisfied
  useEffect(() => {
    if (autoTrigger && !hasAutoTriggered && !isLoading) {
      // Check if all required dependencies have values
      const dependencies = populateHint.dependencies || {};
      const allDependenciesSatisfied = Object.keys(dependencies).every(
        (depKey) => formData[depKey] !== undefined && formData[depKey] !== null && formData[depKey] !== ''
      );

      if (allDependenciesSatisfied) {
        setHasAutoTriggered(true);
        performPopulation();
      }
    }
  }, [autoTrigger, hasAutoTriggered, isLoading, formData]);

  // Debounced search effect
  useEffect(() => {
    if (!supportsSearch) return;
    
    // Clear existing timeout
    if (searchTimeoutRef.current) {
      clearTimeout(searchTimeoutRef.current);
    }

    if (searchTerm.trim()) {
      setIsSearching(true);
      
      searchTimeoutRef.current = setTimeout(() => {
        setDebouncedSearchTerm(searchTerm.trim());
        setIsSearching(false);
      }, SEARCH_DEBOUNCE_DELAY);
    } else {
      setDebouncedSearchTerm('');
      setIsSearching(false);
    }

    return () => {
      if (searchTimeoutRef.current) {
        clearTimeout(searchTimeoutRef.current);
      }
    };
  }, [searchTerm, supportsSearch]);

  // Effect to re-fetch when debounced search term changes
  useEffect(() => {
    if (supportsSearch && hasLoadedOnce) {
      // Reset and fetch with new search term
      performPopulation(null, debouncedSearchTerm);
    }
  }, [debouncedSearchTerm]);

  const performPopulation = async (cursor: string | null = null, searchRegex: string | null = null) => {
    const isLoadMore = cursor !== null;
    
    if (isLoadMore) {
      setIsLoadingMore(true);
    } else {
      setIsLoading(true);
    }

    try {
      // Prepare input data based on populate action's input schema
      const inputData: any = {};
      
      // Map dependencies from populate hint or use field name directly
      if (populateHint.dependencies && Object.keys(populateHint.dependencies).length > 0) {
        Object.entries(populateHint.dependencies).forEach(([configField, actionField]) => {
          const configValue = formData[configField];
          if (configValue !== undefined && configValue !== null && configValue !== '') {
            inputData[actionField as string] = configValue;
          }
        });
      } else {
        // If no dependencies specified, use form data directly
        Object.keys(populateAction.input_schema?.properties || {}).forEach(inputField => {
          if (formData[inputField] !== undefined && formData[inputField] !== null && formData[inputField] !== '') {
            inputData[inputField] = formData[inputField];
          }
        });
      }

      // Add pagination params if supported
      if (supportsPagination) {
        inputData.limit = 30;
        if (cursor) {
          inputData.cursor = cursor;
        }
      }

      // Add search param if supported and provided
      if (supportsSearch && searchRegex) {
        inputData.search_regex = searchRegex;
      }

      const response = await axios.post('/actions/action.execute', {
        uid: populateAction.uid,
        inputData
      });

      // Extract results based on field_mapping
      const fieldMapping = populateHint.field_mapping || 'results';
      const rawResults = response.data[fieldMapping] || [];
      const normalizedResults = normalizeOptions(rawResults);
      
      if (populateHint.selection_type == 'manual' || populateHint.multi_select) {
        if (isLoadMore) {
          // Append to existing options
          setPopulatedOptions(prev => [...prev, ...normalizedResults]);
        } else if (!searchRegex) {
          // Initial fetch (not search) - replace options and mark as loaded
          setPopulatedOptions(normalizedResults);
          if (normalizedResults.length > 0) {
            setHasLoadedOnce(true);
          }
        } else {
          // Search: update with results (even if empty - will show "No results found")
          setPopulatedOptions(normalizedResults);
        }
      }

      // Update pagination state if supported
      if (supportsPagination) {
        setPagination({
          nextCursor: response.data.nextCursor || response.data.next_cursor || null,
          hasMore: response.data.hasMore ?? response.data.has_more ?? false,
          total: response.data.total ?? null
        });
      }

      // Only report to parent on initial load (not load more or search)
      if (!isLoadMore && !searchRegex) {
        // For backwards compatibility, send values based on the original format
        const resultValues = normalizedResults.map(opt => opt.value);
        onPopulateResult(fieldName, resultValues, populateHint.multi_select || false);
      }

    } catch (error: any) {
      console.error('Population error:', error);
      const errorMessage = error.response?.data?.message || 'Population failed';
      console.warn(`Failed to populate ${fieldName}:`, errorMessage);
      // Only clear options on initial load failure, not on search failure
      if (!isLoadMore && !searchRegex) {
        setPopulatedOptions([]);
        setPagination({ nextCursor: null, hasMore: false, total: null });
      }
      // For search errors, keep existing options visible
    } finally {
      if (isLoadMore) {
        setIsLoadingMore(false);
      } else {
        setIsLoading(false);
      }
    }
  };

  const handleLoadMore = () => {
    if (pagination.nextCursor && !isLoadingMore) {
      performPopulation(pagination.nextCursor, debouncedSearchTerm || null);
    }
  };

  const handleSelectChange = (value: string) => {
    if (!value || value === "__no_options_disabled__" || value === "__load_more__") return;

    let newSelectedValues: string[];
    
    if (populateHint.multi_select) {
      // Multi-select: toggle selection
      if (selectedValues.includes(value)) {
        newSelectedValues = selectedValues.filter(v => v !== value);
      } else {
        newSelectedValues = [...selectedValues, value];
      }
    } else {
      // Single select: replace current selection
      newSelectedValues = [value];
    }

    setSelectedValues(newSelectedValues);
    
    // Update parent component with selected values
    onPopulateResult(fieldName, newSelectedValues, populateHint.multi_select || false);
  };

  // Handle item selection for multi-select to keep dropdown open
  const handleItemSelect = (value: string) => {
    handleSelectChange(value);
    // For multi-select, signal that we want to keep the dropdown open
    if (populateHint.multi_select) {
      setShouldKeepOpen(true);
    }
  };

  const removeSelectedValue = (valueToRemove: string) => {
    const newSelectedValues = selectedValues.filter(val => val !== valueToRemove);
    setSelectedValues(newSelectedValues);
    onPopulateResult(fieldName, newSelectedValues, populateHint.multi_select || false);
  };

  const getAvailableOptions = (): OptionItem[] => {
    if (populateHint.multi_select) {
      // For multi-select, show options that aren't already selected
      return populatedOptions.filter(option => !selectedValues.includes(option.value));
    }
    // For single select, show all options
    return populatedOptions;
  };

  // Get the display label for a selected value
  const getDisplayLabel = (value: string): string => {
    const option = populatedOptions.find(opt => opt.value === value);
    return option?.label || value;
  };

  const availableOptions = getAvailableOptions();
  const remainingCount = pagination.total 
    ? pagination.total - populatedOptions.length 
    : null;

  // Hide UI when auto-triggering (keep logic running in background)
  if (hideUI) {
    return null;
  }

  // Render searchable dropdown with Command component
  const renderSearchableDropdown = () => (
    <Popover open={isDropdownOpen} onOpenChange={setIsDropdownOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          role="combobox"
          aria-expanded={isDropdownOpen}
          className="w-full justify-between bg-background-dark"
        >
          {populateHint.multi_select 
            ? `Add ${populateHint.field_mapping || 'option'}...`
            : selectedValues.length > 0 
              ? getDisplayLabel(selectedValues[0])
              : `Select ${populateHint.field_mapping || 'option'}...`
          }
          <ChevronDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
        </Button>
      </PopoverTrigger>
      <PopoverContent 
        className="w-[--radix-popover-trigger-width] p-0" 
        align="start"
        onOpenAutoFocus={(e) => e.preventDefault()}
        onInteractOutside={(e) => {
          // Prevent closing when interacting with elements inside the popover
          const target = e.target as HTMLElement;
          if (target.closest('[data-radix-popper-content-wrapper]')) {
            e.preventDefault();
          }
        }}
      >
        <Command shouldFilter={false} loop>
        <div className="[&_input]:!text-white">
            <CommandInput 
              placeholder={`Search ${populateHint.field_mapping || 'options'}...`}
              value={searchTerm}
              onValueChange={setSearchTerm}
            />
          </div>
          {isSearching && (
            <div className="flex items-center justify-center py-2">
              <Loader2 className="h-4 w-4 animate-spin text-gray-400" />
              <span className="ml-2 text-sm text-gray-400">Searching...</span>
            </div>
          )}
          <CommandList>
            <CommandEmpty>
              {isLoading ? 'Loading...' : isSearching ? 'Searching...' : searchTerm ? 'No matching results found.' : 'No options found.'}
            </CommandEmpty>
            <CommandGroup>
              {availableOptions.map((option: OptionItem) => (
                <CommandItem
                  key={option.value}
                  value={option.value}
                  onSelect={() => {
                    handleItemSelect(option.value);
                    if (!populateHint.multi_select) {
                      setIsDropdownOpen(false);
                    }
                  }}
                >
                  <Check
                    className={`mr-2 h-4 w-4 ${
                      selectedValues.includes(option.value) ? "opacity-100" : "opacity-0"
                    }`}
                  />
                  {option.label}
                </CommandItem>
              ))}
              
              {/* Load More option for pagination */}
              {supportsPagination && pagination.hasMore && (
                <CommandItem
                  value="__load_more__"
                  onSelect={handleLoadMore}
                  className="text-blue-400 font-medium justify-center cursor-pointer"
                >
                  {isLoadingMore ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      Loading more...
                    </>
                  ) : (
                    <>
                      <ChevronDown className="mr-2 h-4 w-4" />
                      Load more{remainingCount !== null ? ` (${remainingCount} remaining)` : '...'}
                    </>
                  )}
                </CommandItem>
              )}
            </CommandGroup>
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );

  // Render standard dropdown (for backwards compatibility - no search)
  const renderStandardDropdown = () => (
    <Select
      value=""
      open={isDropdownOpen}
      onOpenChange={(open) => {
        setIsDropdownOpen(open);
      }}
      onValueChange={(value) => {
        if (value === "__load_more__") {
          handleLoadMore();
          return;
        }
        if (populateHint.multi_select) {
          handleItemSelect(value);
        } else {
          handleSelectChange(value);
          setIsDropdownOpen(false);
        }
      }}
    >
      <SelectTrigger className="bg-background-dark">
        <SelectValue placeholder={
          populateHint.multi_select 
            ? `Add ${populateHint.field_mapping || 'option'}...`
            : `Select ${populateHint.field_mapping || 'option'}...`
        } />
      </SelectTrigger>
      <SelectContent
        onCloseAutoFocus={(e) => {
          if (populateHint.multi_select) {
            e.preventDefault();
          }
        }}
        onPointerDownOutside={() => {
          setIsDropdownOpen(false);
        }}
        onEscapeKeyDown={() => {
          setIsDropdownOpen(false);
        }}
      >
        {availableOptions.map((option: OptionItem, index: number) => (
          <SelectItem 
            key={`${option.value}-${index}`} 
            value={option.value}
            onSelect={(event) => {
              if (populateHint.multi_select) {
                event.preventDefault();
                handleItemSelect(option.value);
              }
            }}
          >
            {option.label}
          </SelectItem>
        ))}
        
        {/* Load More option for pagination */}
        {supportsPagination && pagination.hasMore && (
          <SelectItem 
            value="__load_more__" 
            className="text-blue-400 font-medium cursor-pointer"
          >
            {isLoadingMore ? (
              <span className="flex items-center gap-2">
                <Loader2 className="h-3 w-3 animate-spin" />
                Loading...
              </span>
            ) : (
              <span className="flex items-center gap-2">
                <ChevronDown className="h-3 w-3" />
                Load more{remainingCount !== null ? ` (${remainingCount} remaining)` : '...'}
              </span>
            )}
          </SelectItem>
        )}
        
        {availableOptions.length === 0 && populatedOptions.length > 0 && (
          <SelectItem value="__no_options_disabled__" disabled>
            {populateHint.multi_select ? 'All options selected' : 'No options available'}
          </SelectItem>
        )}
        {populatedOptions.length === 0 && (
          <SelectItem value="__no_options_disabled__" disabled>
            No options available
          </SelectItem>
        )}
      </SelectContent>
    </Select>
  );

  return (
    <div className="space-y-3">
      {/* Populate Button */}
      <div className="flex items-center gap-2 flex-wrap">
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={() => performPopulation()}
          disabled={isLoading}
          className="flex items-center gap-2"
        >
          {isLoading ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <RefreshCw className="h-4 w-4" />
          )}
          {populateAction.uid}
        </Button>
        <Badge variant="outline" className="text-xs">
          populate
        </Badge>
        {populateHint.multi_select && (
          <Badge variant="outline" className="text-xs">
            multi-select
          </Badge>
        )}
        {supportsPagination && (
          <Badge variant="outline" className="text-xs text-blue-400 border-blue-400/50">
            paginated
          </Badge>
        )}
        {supportsSearch && (
          <Badge variant="outline" className="text-xs text-green-400 border-green-400/50">
            searchable
          </Badge>
        )}
      </div>

      {/* Selection Dropdown (show if we have ever loaded options - keeps visible during search) */}
      {(hasLoadedOnce || populatedOptions.length > 0) && (
        <div className="space-y-2">
          {/* Use searchable dropdown if search is supported, otherwise use standard dropdown */}
          {supportsSearch ? renderSearchableDropdown() : renderStandardDropdown()}

          {/* Show selected items (for multi-select or single select) */}
          {selectedValues.length > 0 && (
            <div className="flex flex-wrap gap-2">
              {selectedValues.map((selectedValue: string, index: number) => (
                <Badge
                  key={index}
                  variant="secondary"
                  className="flex items-center gap-1 bg-gray-700 text-white border-gray-600 hover:bg-gray-600"
                >
                  {getDisplayLabel(selectedValue)}
                  <button
                    type="button"
                    onClick={() => removeSelectedValue(selectedValue)}
                    className="ml-1 text-xs text-gray-300 hover:text-red-400 transition-colors"
                  >
                    ×
                  </button>
                </Badge>
              ))}
            </div>
          )}

          {/* Show total count if available */}
          {supportsPagination && pagination.total !== null && (
            <p className="text-xs text-gray-400">
              Showing {populatedOptions.length} of {pagination.total} {populateHint.field_mapping || 'options'}
            </p>
          )}
        </div>
      )}

      {/* Show message when no options populated yet */}
      {!hasLoadedOnce && populatedOptions.length === 0 && !isLoading && (
        <p className="text-xs text-gray-400">
          Click the button above to populate {populateHint.field_mapping || 'options'}
        </p>
      )}
    </div>
  );
};
