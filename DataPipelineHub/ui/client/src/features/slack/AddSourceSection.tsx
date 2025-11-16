import React, { FC, useState, useMemo, useCallback, forwardRef, useImperativeHandle, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useInfiniteQuery, useQuery, useQueryClient } from '@tanstack/react-query';
import { FaSearch, FaSpinner } from 'react-icons/fa';
import { HiOutlineLockClosed } from 'react-icons/hi';

import { fetchAvailableSlackChannels, fetchEmbeddedSlackChannels, PaginatedChannelsResponse } from '@/api/slack';
import type { EmbedChannel, Channel } from '@/types';
import { Badge } from '@/components/ui/badge';
import { Tooltip, TooltipContent, TooltipTrigger, TooltipProvider } from '@/components/ui/tooltip';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Switch } from '@/components/ui/switch';
import { ChannelSettings, ChannelSettingsData, defaultChannelSettings } from './ChannelSettings';

const CHANNELS_PER_PAGE = 50;
const SEARCH_DEBOUNCE_DELAY = 2000; // 2 seconds

export const SCOPE = {
  ALL: 'all' as const,
  PUBLIC: 'public' as const,
  PRIVATE: 'private' as const,
};
export type Scope = typeof SCOPE[keyof typeof SCOPE];

const CHANNEL_TYPE = {
  PUBLIC: 'public_channel',
  PRIVATE: 'private_channel',
} as const;
type ChannelType = typeof CHANNEL_TYPE[keyof typeof CHANNEL_TYPE];
const ALL_CHANNEL_TYPES = 'private_channel,public_channel';

const CACHE_KEY = 'availableSlackChannels';

const scopeOptions = [
  { label: 'All', value: SCOPE.ALL },
  { label: 'Public', value: SCOPE.PUBLIC },
  { label: 'Private', value: SCOPE.PRIVATE },
];

interface ChannelWithSettings extends Channel {
  settings: {
    dateRange: string;
    communityPrivacy: 'public' | 'private';
    includeThreads: boolean;
    processFileContent: boolean;
  };
}

interface AddSourceSectionProps {
  onSave: () => Promise<void>;
  onCancel: () => void;
  isSubmitting?: boolean;
}

export interface AddSourceSectionHandle {
  getSelectedChannels: () => Promise<ChannelWithSettings[]>;
}

const getChannelUniqueId = (channel: Channel): string => {
  return `${channel.channel_id}_${channel.is_private ? 'private' : 'public'}`;
};

const parseChannelUniqueId = (uniqueId: string) => {
  const parts = uniqueId.split('_');
  return {
    channel_id: parts.slice(0, -1).join('_'),
    is_private: parts[parts.length - 1] === 'private'
  };
};

const AddSourceSection = forwardRef<AddSourceSectionHandle, AddSourceSectionProps>(({ onSave, onCancel, isSubmitting }, ref) => {
  const queryClient = useQueryClient();
  const [scope, setScope] = useState<Scope>(SCOPE.ALL);
  const [searchTerm, setSearchTerm] = useState<string>('');
  const [debouncedSearchTerm, setDebouncedSearchTerm] = useState<string>('');
  const [isSearching, setIsSearching] = useState<boolean>(false);
  const [selectedChannels, setSelectedChannels] = useState<string[]>([]);
  const [selectedChannelEntities, setSelectedChannelEntities] = useState<Record<string, Channel>>({});
  const [channelSettings, setChannelSettings] = useState<Record<string, ChannelSettingsData>>({});
  const [lastSelectedChannel, setLastSelectedChannel] = useState<string | null>(null);
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const searchTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  

  // Debounced search effect
  useEffect(() => {
    
    // Clear existing timeout
    if (searchTimeoutRef.current) {
      clearTimeout(searchTimeoutRef.current);
    }

    if (searchTerm.trim()) {
      // Show loading immediately when user starts typing
      setIsSearching(true);
      
      // Set timeout for API call
      searchTimeoutRef.current = setTimeout(() => {
        setDebouncedSearchTerm(searchTerm.trim());
        setIsSearching(false);
      }, SEARCH_DEBOUNCE_DELAY);
    } else {
      // Reset search immediately when search term is cleared
      setDebouncedSearchTerm('');
      setIsSearching(false);
    }

    // Cleanup timeout on unmount or search term change
    return () => {
      if (searchTimeoutRef.current) {
        clearTimeout(searchTimeoutRef.current);
      }
    };
  }, [searchTerm]);

  const typesParam = useMemo<ChannelType | typeof ALL_CHANNEL_TYPES>(() => {
    if (scope === SCOPE.PUBLIC) return CHANNEL_TYPE.PUBLIC;
    if (scope === SCOPE.PRIVATE) return CHANNEL_TYPE.PRIVATE;
    return ALL_CHANNEL_TYPES;
  }, [scope]);

  const {
    data: channelsData,
    isLoading,
    isError,
    error,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
  } = useInfiniteQuery<PaginatedChannelsResponse, Error>({
    queryKey: [CACHE_KEY, typesParam, debouncedSearchTerm],
    queryFn: async ({ pageParam }) => {
      // Use ^ for prefix matching - escape special chars and add ^ at start
      const searchRegex = debouncedSearchTerm ? `^${debouncedSearchTerm.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}` : undefined;
      
      // When searching, always use single query regardless of scope
      if (debouncedSearchTerm) {
        // For search, always search across all types when scope is ALL
        const searchTypes = scope === SCOPE.ALL ? ALL_CHANNEL_TYPES : (typesParam as ChannelType);
        
        return fetchAvailableSlackChannels(searchTypes, {
          cursor: pageParam as string | undefined,
          limit: CHANNELS_PER_PAGE,
          search_regex: searchRegex,
        });
      }
      
      // Normal mode without search - use existing logic
      if (scope === SCOPE.ALL) {
        const [pubResponse, privResponse] = await Promise.all([
          fetchAvailableSlackChannels(CHANNEL_TYPE.PUBLIC, {
            cursor: pageParam as string | undefined,
            limit: Math.ceil(CHANNELS_PER_PAGE / 2),
          }),
          fetchAvailableSlackChannels(CHANNEL_TYPE.PRIVATE, {
            cursor: pageParam as string | undefined,
            limit: Math.ceil(CHANNELS_PER_PAGE / 2),
          }),
        ]);

        const mergedChannels = [...pubResponse.channels, ...privResponse.channels];
        const uniqueChannels = Array.from(
          new Map(mergedChannels.map(c => [c.channel_id, c])).values()
        );

        return {
          channels: uniqueChannels,
          nextCursor: pubResponse.nextCursor || privResponse.nextCursor,
          hasMore: pubResponse.hasMore || privResponse.hasMore,
          total: (pubResponse.total || 0) + (privResponse.total || 0),
        };
      }

      return fetchAvailableSlackChannels(typesParam as ChannelType, {
        cursor: pageParam as string | undefined,
        limit: CHANNELS_PER_PAGE,
      });
    },
    getNextPageParam: (lastPage) => lastPage.nextCursor,
    staleTime: 5 * 60 * 1000,
    refetchOnMount: false,
    refetchOnWindowFocus: false,
    initialPageParam: undefined,
  });

  const channels = useMemo(() => {
    if (!channelsData?.pages) return [];
    return channelsData.pages.flatMap((page: PaginatedChannelsResponse) => page.channels);
  }, [channelsData]);

  const totalChannels = useMemo(() => {
    return channelsData?.pages?.[0]?.total || 0;
  }, [channelsData]);

  const { data: embedChannels = [] } = useQuery<EmbedChannel[], Error>({
    queryKey: ["embeddedSlackChannels"],
    queryFn: fetchEmbeddedSlackChannels,
    staleTime: 30 * 1000,
    refetchOnMount: true,
    refetchOnWindowFocus: true,
  });

  const getSelectedChannels = useCallback(async (): Promise<ChannelWithSettings[]> => {
    // Build payload per-channel using its own saved settings
    const result: ChannelWithSettings[] = [];
    for (const id of selectedChannels) {
      const channel = selectedChannelEntities[id] || channels.find(c => getChannelUniqueId(c) === id);
      if (!channel) continue;
      const settingsForThisChannel = channelSettings[id] || defaultChannelSettings;
      result.push({
        ...channel,
        settings: {
          dateRange: settingsForThisChannel.dateRange,
          communityPrivacy: 'public' as const,
          includeThreads: settingsForThisChannel.includeThreads,
          processFileContent: settingsForThisChannel.processFileContent,
        }
      });
    }
    return result;
  }, [selectedChannels, selectedChannelEntities, channelSettings, channels]);

  useImperativeHandle(ref, () => ({
    getSelectedChannels,
  }));

  const isChannelEmbedded = useCallback((channel: Channel) => {
    return embedChannels.some(embedded => embedded.name === channel.channel_name);
  }, [embedChannels]);

  // No client-side filtering needed since we now have server-side search
  const filteredChannels = channels;

  const handleToggleChannel = useCallback((channel: Channel) => {
    if (isChannelEmbedded(channel)) {
      return;
    }
    
    const uniqueId = getChannelUniqueId(channel);
    setSelectedChannels(prev => {
      const isCurrentlySelected = prev.includes(uniqueId);
      const newSelected = isCurrentlySelected 
        ? prev.filter(n => n !== uniqueId) 
        : [...prev, uniqueId];
      
      // Initialize settings for newly selected channels and set as last selected
      if (!isCurrentlySelected && newSelected.includes(uniqueId)) {
        setChannelSettings(prevSettings => ({
          ...prevSettings,
          [uniqueId]: defaultChannelSettings
        }));
        // Persist the channel entity for reliable payload building
        setSelectedChannelEntities(prevEntities => ({
          ...prevEntities,
          [uniqueId]: channel,
        }));
        // Set this as the last selected channel
        setLastSelectedChannel(uniqueId);
      } else if (isCurrentlySelected) {
        // If deselecting this channel, update lastSelectedChannel
        if (lastSelectedChannel === uniqueId) {
          // Set last selected to the most recent remaining channel, or null if none
          const remainingChannels = newSelected;
          setLastSelectedChannel(remainingChannels.length > 0 ? remainingChannels[remainingChannels.length - 1] : null);
        }
        // Remove the entity when deselecting
        setSelectedChannelEntities(prevEntities => {
          const copy = { ...prevEntities };
          delete copy[uniqueId];
          return copy;
        });
      }
      
      return newSelected;
    });
  }, [isChannelEmbedded, lastSelectedChannel]);

  const handleChannelSettingsChange = useCallback((channelId: string, settings: ChannelSettingsData) => {
    setChannelSettings(prev => ({
      ...prev,
      [channelId]: settings
    }));
  }, []);

  const selectableChannels = useMemo(() => 
    filteredChannels.filter(c => !isChannelEmbedded(c)), 
    [filteredChannels, isChannelEmbedded]
  );
  const selectableChannelIds = useMemo(() => 
    selectableChannels.map(c => getChannelUniqueId(c)), 
    [selectableChannels]
  );
  
  const allNames = useMemo(() => 
    filteredChannels
      .filter(c => !isChannelEmbedded(c))
      .map(c => getChannelUniqueId(c)), 
    [filteredChannels, isChannelEmbedded]
  );
  const allSelected = selectableChannelIds.length > 0 && selectableChannelIds.every(id => selectedChannels.includes(id));
  const handleSelectAll = useCallback(() => {
    setSelectedChannels(prev => {
      if (allSelected) {
        // Clear all selections
        setLastSelectedChannel(null);
        setSelectedChannelEntities({});
        return [];
      } else {
        // Select all available channels
        const newSelection = Array.from(new Set([...prev, ...allNames]));
        
        // Initialize settings for newly selected channels
        const newChannels = allNames.filter(id => !prev.includes(id));
        if (newChannels.length > 0) {
          setChannelSettings(prevSettings => {
            const newSettings = { ...prevSettings };
            newChannels.forEach(id => {
              if (!newSettings[id]) {
                newSettings[id] = defaultChannelSettings;
              }
            });
            return newSettings;
          });
          // Persist entities for all newly selected channels
          const idToChannel = new Map<string, Channel>(filteredChannels.map(c => [getChannelUniqueId(c), c]));
          setSelectedChannelEntities(prevEntities => {
            const copy = { ...prevEntities };
            newChannels.forEach(id => {
              const ch = idToChannel.get(id);
              if (ch) copy[id] = ch;
            });
            return copy;
          });
          
          // Set the last channel in the list as the last selected
          setLastSelectedChannel(newChannels[newChannels.length - 1]);
        }
        
        return newSelection;
      }
    });
  }, [allNames, allSelected]);

  const handleScroll = useCallback(() => {
    if (!scrollContainerRef.current || !hasNextPage || isFetchingNextPage) return;

    const { scrollTop, scrollHeight, clientHeight } = scrollContainerRef.current;
    const scrolledToBottom = scrollHeight - scrollTop - clientHeight < 100; // 100px threshold

    if (scrolledToBottom) {
      fetchNextPage();
    }
  }, [hasNextPage, isFetchingNextPage, fetchNextPage]);

  useEffect(() => {
    const container = scrollContainerRef.current;
    if (!container) return;

    container.addEventListener('scroll', handleScroll);
    return () => container.removeEventListener('scroll', handleScroll);
  }, [handleScroll]);

  // Ensure lastSelectedChannel is set when channels are selected
  useEffect(() => {
    if (selectedChannels.length > 0 && !lastSelectedChannel) {
      setLastSelectedChannel(selectedChannels[selectedChannels.length - 1]);
    }
  }, [selectedChannels, lastSelectedChannel]);

  const counts: Record<Scope, number> = useMemo(() => {
    if (scope === SCOPE.ALL) {
      return {
        [SCOPE.ALL]: totalChannels,
        [SCOPE.PUBLIC]: 0,
        [SCOPE.PRIVATE]: 0,
      };
    }

    return {
      [SCOPE.ALL]: 0,
      [SCOPE.PUBLIC]: scope === SCOPE.PUBLIC ? totalChannels : 0,
      [SCOPE.PRIVATE]: scope === SCOPE.PRIVATE ? totalChannels : 0,
    };
  }, [scope, totalChannels]);

  const noticeLines = [
    'Please be advised that this channel is now monitored by an AI tool for content analysis.',
    'This tool anonymously collects and embeds message content for processing.',
    'Your individual messages will not be linked to your identity.',
    'If you do not consent to this anonymous data collection, please opt out by leaving the channel.',
  ];

  return (
    <Card className="bg-background-card shadow-card border-gray-800">
      <CardContent className="p-4 space-y-4">
        <AnimatePresence>
          {selectedChannels.length > 0 && (
            <motion.div
              key="ai-monitoring-notice"
              initial={{ opacity: 0, y: -6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -6 }}
              transition={{ duration: 0.25 }}
              className="relative"
            >
              <div className="rounded-md border border-amber-500/20 bg-amber-500/10 p-3">
                <div className="text-sm text-white space-y-1">
                  {noticeLines.map((line, idx) => (
                    <motion.p
                      key={idx}
                      initial={{ opacity: 0, y: -4 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ duration: 0.2, delay: idx * 0.1 }}
                    >
                      {line}
                    </motion.p>
                  ))}
                </div>
              </div>
              <div className="absolute -bottom-2 left-6 w-0 h-0 border-l-[6px] border-l-transparent border-r-[6px] border-r-transparent border-t-[8px] border-t-amber-500/20"></div>
              <div className="absolute -bottom-[7px] left-6 w-0 h-0 border-l-[5px] border-l-transparent border-r-[5px] border-r-transparent border-t-[7px] border-t-amber-500/10"></div>
            </motion.div>
          )}
        </AnimatePresence>
        <h3 className="text-lg font-semibold">Channel Selection</h3>

        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-4">
            <div className="flex bg-muted rounded-lg p-1">
              {scopeOptions.map(({ label, value }) => (
                <button
                  key={value}
                  onClick={() => setScope(value)}
                  className={`px-3 py-1 rounded-md text-sm font-medium transition-colors ${
                    scope === value
                      ? 'bg-primary text-primary-foreground shadow-sm'
                      : 'text-muted-foreground hover:text-foreground hover:bg-background'
                  }`}
                >
                  {`${label} ${counts[value] > 0 ? `(${counts[value]})` : ''}`}
                </button>
              ))}
            </div>
            <div className="relative w-64">
              {!searchTerm && (
                <div className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 text-sm pointer-events-none">
                  Search Channels
                </div>
              )}
              <Input 
                id="channel-search" 
                value={searchTerm} 
                onChange={e => setSearchTerm(e.target.value)} 
                placeholder="" 
                className={`input-dark-theme pr-10 bg-input border-border ${searchTerm ? 'pl-3' : 'pl-28'}`}
              />
              <div className="absolute right-3 top-1/2 transform -translate-y-1/2">
                {isSearching || isLoading ? (
                  <FaSpinner className="animate-spin text-gray-400" />
                ) : (
                  <FaSearch className="text-gray-400" />
                )}
              </div>
            </div>
          </div>
          <div className="flex space-x-3">
            <Button 
              variant="outline" 
              onClick={onCancel}
              className="border-border text-foreground hover:bg-muted"
            >
              Cancel
            </Button>
            <Button
              onClick={onSave}
              disabled={isSubmitting}
              className="btn-animated bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
            >
              {isSubmitting && (
                <FaSpinner className="animate-spin text-current mr-2" />
              )}
              <span>
                {isSubmitting 
                  ? 'Submitting…' 
                  : `Add Channel${selectedChannels.length !== 1 ? 's' : ''} (${selectedChannels.length})`
                }
              </span>
            </Button>
          </div>
        </div>

        <div className="text-sm text-gray-400">
          Showing {filteredChannels.length} of {channels.length} loaded channels
          {totalChannels > 0 && channels.length < totalChannels && (
            <span> ({totalChannels} total)</span>
          )}
        </div>

        <TooltipProvider>
        <div 
          ref={scrollContainerRef}
          className="border border-gray-800 rounded-md h-48 overflow-y-auto bg-background-dark"
        >
          {isLoading && channels.length === 0 && (
            <div className="p-4 text-center text-gray-400">
              <FaSpinner className="animate-spin inline mr-2" />
              Loading channels...
            </div>
          )}
          
          {isError && (
            <div className="p-4 text-center text-red-500">{error?.message}</div>
          )}
          
          {!isLoading && !isError && filteredChannels.length === 0 && channels.length > 0 && (
            <div className="p-4 text-center text-gray-500">No channels found matching your search</div>
          )}
          
          {!isLoading && !isError && channels.length === 0 && (
            <div className="p-4 text-center text-gray-500">No channels available</div>
          )}

          {filteredChannels.map(c => {
            const isEmbedded = isChannelEmbedded(c);
            const uniqueId = getChannelUniqueId(c);
            const notMember = c.is_app_member === false || c.is_app_member === null;
            return (
              <div 
                key={uniqueId} 
                className={`flex items-center justify-between p-3 border-b border-gray-800 ${
                  (isEmbedded) ? 'opacity-60 cursor-not-allowed' : 'hover:bg-background-surface cursor-pointer'
                }`}
                onClick={() => !isEmbedded && handleToggleChannel(c)}
              >
                <div className="flex items-center">
                  <span className="text-gray-400 mr-2">{c.is_private ? <HiOutlineLockClosed className="inline" /> : '#'}</span>
                  <span>{c.channel_name}</span>
                  {c.is_private && <Badge className="ml-2 bg-gray-700/40 text-gray-400 border border-gray-700/40">Private</Badge>}
                  {!c.is_private && <Badge className="ml-2 bg-gray-700/40 text-gray-400 border border-gray-700/40">Public</Badge>}
                  {isEmbedded && <Badge className="ml-2 bg-[hsl(var(--success))]/20 text-[hsl(var(--success))] border border-[hsl(var(--success))]/30">Embedded</Badge>}
                </div>
                <div 
                  onClick={(e) => e.stopPropagation()} 
                  onPointerDown={(e) => e.stopPropagation()} 
                  onKeyDown={(e) => e.stopPropagation()}
                >
                  <Switch 
                    checked={isEmbedded || selectedChannels.includes(uniqueId)} 
                    disabled={isEmbedded}
                    onCheckedChange={() => handleToggleChannel(c)} 
                  />
                </div>
              </div>
            );
          })}

          {/* Loading indicator for infinite scroll */}
          {isFetchingNextPage && (
            <div className="p-4 text-center text-gray-400">
              <FaSpinner className="animate-spin inline mr-2" />
              Loading more channels...
            </div>
          )}

          {/* Load more button as fallback */}
          {hasNextPage && !isFetchingNextPage && (
            <div className="p-4 text-center">
              <Button 
                variant="outline" 
                size="sm" 
                onClick={() => fetchNextPage()}
                className="w-full"
              >
                Load More Channels
              </Button>
            </div>
          )}
        </div>
        </TooltipProvider>

        <div className="flex justify-between items-center">
          <span className="text-sm">{selectedChannels.length} channel{selectedChannels.length !== 1 && 's'} selected</span>
          <Button variant="outline" size="sm" onClick={handleSelectAll}>
            {allSelected ? 'Clear All' : 'Select All'}
          </Button>
        </div>

        {selectedChannels.length > 0 && lastSelectedChannel ? (
          <div className="space-y-4">
            <h3 className="text-lg font-semibold">Channel Settings</h3>
            <p className="text-sm text-gray-400">
              Configure settings for the most recently selected channel
              {selectedChannels.length > 1 && (
                <span className="text-amber-400 ml-1">
                  ({selectedChannels.length} channels selected total)
                </span>
              )}
            </p>
            
            <div className="space-y-4">
              {(() => {
                const channel = channels.find(c => getChannelUniqueId(c) === lastSelectedChannel);
                if (!channel) return null;
                
                return (
                  <ChannelSettings
                    key={lastSelectedChannel}
                    channelId={lastSelectedChannel}
                    channelName={channel.channel_name}
                    settings={channelSettings[lastSelectedChannel] || defaultChannelSettings}
                    onSettingsChange={handleChannelSettingsChange}
                  />
                );
              })()}
            </div>
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
});

export default AddSourceSection;