
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
import { Loader2, RefreshCw, ChevronDown, Check, CheckCheck, X } from 'lucide-react';
import axios from "../../../http/axiosAgentConfig";

// Type guard to check if hint is an ApiHint (has endpoint) vs ActionHint (has action_uid)
const isApiHint = (hint: any): boolean => {
  return hint && typeof hint.endpoint === 'string' && hint.endpoint.length > 0;
};

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
  currentValue?: string[];
}

const SEARCH_DEBOUNCE_DELAY = 300; // ms
const SELECT_ALL_VALUE = "__select_all__";


export const FieldPopulation: React.FC<FieldPopulationProps> = ({
  fieldName,
  populateHint,
  elementActions,
  selectedElementType,
  formData,
  onPopulateResult,
  autoTrigger = false,
  hideUI = false,
  currentValue = []
}) => {
  const [isLoading, setIsLoading] = useState(false);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [populatedOptions, setPopulatedOptions] = useState<OptionItem[]>([]);
  const [selectedValues, setSelectedValues] = useState<string[]>(currentValue);
  const [isDropdownOpen, setIsDropdownOpen] = useState(false);
  const [shouldKeepOpen, setShouldKeepOpen] = useState(false);
  const [hasAutoTriggered, setHasAutoTriggered] = useState(false);
  const [hasLoadedOnce, setHasLoadedOnce] = useState(false); // Track if options were ever loaded
  const [isInitialized, setIsInitialized] = useState(false); // Track if we've synced with parent value
  
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

  const isSelectAll = (value: string) => value === SELECT_ALL_VALUE;

  // Extract hint flags with defaults for backwards compatibility
  const supportsPagination = populateHint.pagination === true;
  const supportsSearch = populateHint.search === true;
  const labelField = populateHint.label_field;
  const valueField = populateHint.value_field;

  // Determine if this is an ApiHint or ActionHint
  const useApiHint = isApiHint(populateHint);

  // Find the populate action from elementActions (only needed for ActionHint)
  const populateAction = !useApiHint
    ? elementActions.find(action => action.uid === populateHint.action_uid)
    : null;

  // For ActionHint, we need a valid action; for ApiHint, we need an endpoint
  if (!useApiHint && !populateAction) {
    return null;
  }
  if (useApiHint && !populateHint.endpoint) {
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

  // When a user edits an existing element, ensure that any previously saved selections are reflected as "selected" in the dropdown. This only runs once
  // on initial mount to avoid overwriting user changes during the editing session
  useEffect(() => {
    if (!isInitialized && currentValue && currentValue.length > 0) {
      setSelectedValues(currentValue);
      setIsInitialized(true);
    }
  }, [currentValue, isInitialized]);

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

  const applySelection = (values: string[]) => {
    setSelectedValues(values);
    onPopulateResult(fieldName, values, populateHint.multi_select || false);
  };

  /**
   * Toggle between "Select All" and "Clear All" for multi-select dropdowns.
   * 
   * Behavior:
   * - If ALL options are currently selected → Clear all selections (empty array)
   * - If ANY options are unselected → Select all available options
   * 
   * This allows users to quickly select/deselect all options with a single click.
   * The `allOptionsSelected` flag (computed elsewhere) determines which action to take.
   */
  const toggleSelectAll = () => {
    const allValues = populatedOptions.map(o => o.value);
    applySelection(allOptionsSelected ? [] : allValues);
  };

  const handleSelectChange = (value: string) => {
    if (!value || value === "__no_options_disabled__" || value === "__load_more__") return;
    if (isSelectAll(value)) return toggleSelectAll();

    const newValues = populateHint.multi_select
      ? selectedValues.includes(value)
        ? selectedValues.filter(v => v !== value)
        : [...selectedValues, value]
      : [value];

    applySelection(newValues);
  };

  const handleItemSelect = (value: string) => {
    handleSelectChange(value);
    if (populateHint.multi_select) setShouldKeepOpen(true);
  };

  const removeSelectedValue = (value: string) => {
    applySelection(selectedValues.filter(v => v !== value));
  };


  // Perform population via ActionHint (action system)
  const performActionPopulation = async (inputData: any) => {
    if (!populateAction) {
      throw new Error('Populate action not found');
    }

    const response = await axios.post('/actions/action.execute', {
      uid: populateAction.uid,
      inputData
    });

    return response.data;
  };

  // Perform population via ApiHint (direct API call)
  const performApiPopulation = async (requestBody: any) => {
    // Determine the HTTP method (default to POST)
    const method = (populateHint.method || 'POST').toUpperCase();
    const endpoint = populateHint.endpoint;

    let response;
    if (method === 'GET') {
      // For GET requests, send data as query params
      response = await axios.get(endpoint, { params: requestBody });
    } else {
      // For POST/PUT/PATCH, send data in body
      response = await axios({
        method: method.toLowerCase(),
        url: endpoint,
        data: requestBody
      });
    }

    return response.data;
  };

  const performPopulation = async (cursor: string | null = null, searchRegex: string | null = null) => {
    const isLoadMore = cursor !== null;
    
    if (isLoadMore) {
      setIsLoadingMore(true);
    } else {
      setIsLoading(true);
    }

    try {
      // Prepare input/request data based on dependencies
      const inputData: any = {};
      
      // Map dependencies from populate hint
      if (populateHint.dependencies && Object.keys(populateHint.dependencies).length > 0) {
        Object.entries(populateHint.dependencies).forEach(([configField, requestField]) => {
          const configValue = formData[configField];
          if (configValue !== undefined && configValue !== null && configValue !== '') {
            inputData[requestField as string] = configValue;
          }
        });
      } else if (!useApiHint && populateAction) {
        // For ActionHint without explicit dependencies, use form data directly
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

      // Use the appropriate population method based on hint type
      const responseData = useApiHint
        ? await performApiPopulation(inputData)
        : await performActionPopulation(inputData);

      // Extract results based on field_mapping
      const fieldMapping = populateHint.field_mapping || 'results';
      const rawResults = responseData[fieldMapping] || [];
      
    
      if (populateHint.selection_type === 'automatic' && !Array.isArray(rawResults)) {
        onPopulateResult(fieldName, rawResults, false);
        return;
      }
      
      const normalizedResults = normalizeOptions(rawResults);
      const newOptionValues = new Set(normalizedResults.map(opt => opt.value));
      
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
          
          // Validate existing selections - remove any that no longer exist in new results
          setSelectedValues(prevSelected => {
            if (prevSelected.length === 0) return prevSelected;
            const validatedSelections = prevSelected.filter(val => newOptionValues.has(val));
            
            // If selections changed (some were removed), notify parent
            if (validatedSelections.length !== prevSelected.length) {
              // Use setTimeout to avoid state update during render
              setTimeout(() => {
                onPopulateResult(fieldName, validatedSelections, populateHint.multi_select || false);
              }, 0);
            }
            
            return validatedSelections;
          });
        } else {
          // Search: update with results (even if empty - will show "No results found")
          setPopulatedOptions(normalizedResults);
        }
      }

      // Update pagination state if supported
      if (supportsPagination) {
        setPagination({
          nextCursor: responseData.nextCursor || responseData.next_cursor || null,
          hasMore: responseData.hasMore ?? responseData.has_more ?? false,
          total: responseData.total ?? null
        });
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
  
  // Check if all options are selected (for showing Select All vs Clear All)
  const allOptionsSelected = populatedOptions.length > 0 && 
    selectedValues.length === populatedOptions.length;

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
              {/* Select All / Clear All option for multi-select */}
              {populateHint.multi_select && populatedOptions.length > 0 && !searchTerm && (
                <CommandItem
                  value={SELECT_ALL_VALUE}
                  onSelect={handleSelectChange}
                  className="font-medium border-b border-gray-700 mb-1 pb-2"
                >
                  {allOptionsSelected ? (
                    <>
                      <X className="mr-2 h-4 w-4 text-red-400" />
                      <span className="text-red-400">Clear All</span>
                    </>
                  ) : (
                    <>
                      <CheckCheck className="mr-2 h-4 w-4 text-green-400" />
                      <span className="text-green-400">Select All ({populatedOptions.length})</span>
                    </>
                  )}
                </CommandItem>
              )}

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
        {/* Select All / Clear All option for multi-select */}
        {populateHint.multi_select && populatedOptions.length > 0 && (
          <SelectItem 
            value={SELECT_ALL_VALUE}
            className="font-medium border-b border-gray-700"
          >
            {allOptionsSelected ? (
              <span className="flex items-center gap-2 text-red-400">
                <X className="h-3 w-3" />
                Clear All
              </span>
            ) : (
              <span className="flex items-center gap-2 text-green-400">
                <CheckCheck className="h-3 w-3" />
                Select All ({populatedOptions.length})
              </span>
            )}
          </SelectItem>
        )}

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
          {useApiHint ? `Fetch ${populateHint.field_mapping || 'options'}` : populateAction?.uid}
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
