import { useState, useEffect, useRef, useCallback } from 'react';
import { Loader2, Search, Users } from 'lucide-react';
import { Input } from '@/components/ui/input';
import {
  DirectoryUser,
  DirectoryGroup,
  searchDirectory,
  searchDirectoryUsers,
  getDirectoryStatus,
} from '@/api/directory';

export type { DirectoryUser, DirectoryGroup };

interface UserDirectorySearchProps {
  onSelect: (user: DirectoryUser) => void;
  onSelectGroup?: (group: DirectoryGroup) => void;
  onInputChange?: (value: string) => void;
  excludeUserIds?: string[];
  placeholder?: string;
  clearOnSelect?: boolean;
  accessToken?: string | null;
  inputClassName?: string;
}

export default function UserDirectorySearch({
  onSelect,
  onSelectGroup,
  onInputChange,
  excludeUserIds = [],
  placeholder,
  clearOnSelect = true,
  accessToken,
  inputClassName,
}: UserDirectorySearchProps) {
  const [directoryEnabled, setDirectoryEnabled] = useState(true);
  const [query, setQuery] = useState('');
  const [userResults, setUserResults] = useState<DirectoryUser[]>([]);
  const [groupResults, setGroupResults] = useState<DirectoryGroup[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [searchError, setSearchError] = useState('');

  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const searchIdRef = useRef(0);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const excludeUserIdsRef = useRef(excludeUserIds);
  excludeUserIdsRef.current = excludeUserIds;
  const searchCacheRef = useRef<Map<string, { users: DirectoryUser[]; groups: DirectoryGroup[] }>>(new Map());

  useEffect(() => {
    getDirectoryStatus()
      .then(({ enabled }) => setDirectoryEnabled(enabled))
      .catch(() => {
        setDirectoryEnabled(true);
      });
  }, []);

  useEffect(() => {
    if (!dropdownOpen) return;
    const handleClickOutside = (e: MouseEvent) => {
      if (
        dropdownRef.current && !dropdownRef.current.contains(e.target as Node) &&
        inputRef.current && !inputRef.current.contains(e.target as Node)
      ) {
        setDropdownOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [dropdownOpen]);

  useEffect(() => {
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, []);

  const handleChange = useCallback(
    (value: string) => {
      searchIdRef.current += 1;
      const requestId = searchIdRef.current;
      setQuery(value);
      setSearchError('');
      onInputChange?.(value);

      if (debounceRef.current) clearTimeout(debounceRef.current);

      const trimmed = value.trim().toLowerCase();
      if (!directoryEnabled || trimmed.length < 2) {
        if (requestId !== searchIdRef.current) return;
        setUserResults([]);
        setGroupResults([]);
        setDropdownOpen(false);
        setIsSearching(false);
        return;
      }

      const cached = searchCacheRef.current.get(trimmed);
      if (cached) {
        if (requestId !== searchIdRef.current) return;
        const filteredUsers = cached.users.filter((u) => !excludeUserIdsRef.current.includes(u.user_id));
        setUserResults(filteredUsers);
        setGroupResults(cached.groups);
        setDropdownOpen(true);
        setIsSearching(false);
        return;
      }

      setIsSearching(true);
      setDropdownOpen(true);

      debounceRef.current = setTimeout(async () => {
        const id = requestId;
        try {
          const result = onSelectGroup
            ? await searchDirectory(value.trim(), 10, accessToken)
            : { users: await searchDirectoryUsers(value.trim(), 10, accessToken), groups: [] };
          if (id !== searchIdRef.current) return;
          searchCacheRef.current.set(trimmed, result);
          const filteredUsers = result.users.filter((u) => !excludeUserIdsRef.current.includes(u.user_id));
          setUserResults(filteredUsers);
          setGroupResults(result.groups);
        } catch (err: unknown) {
          if (id !== searchIdRef.current) return;
          // Graceful fallback: if unified search fails, still try users-only
          // so people can continue selecting users while group lookup is down.
          if (onSelectGroup) {
            try {
              const users = await searchDirectoryUsers(value.trim(), 10, accessToken);
              if (id !== searchIdRef.current) return;
              const filteredUsers = users.filter((u) => !excludeUserIdsRef.current.includes(u.user_id));
              setUserResults(filteredUsers);
              setGroupResults([]);
              return;
            } catch {
              // keep original error handling below
            }
          }
          setUserResults([]);
          setGroupResults([]);
          const axiosErr = err as { response?: { status?: number } };
          if (axiosErr?.response?.status === 501) {
            setSearchError('Directory provider is not configured');
          } else {
            setSearchError('Search failed — try again');
          }
        } finally {
          if (id === searchIdRef.current) setIsSearching(false);
        }
      }, 250);
    },
    [directoryEnabled, accessToken, onInputChange, onSelectGroup],
  );

  const handleSelectUser = (user: DirectoryUser) => {
    onSelect(user);
    if (clearOnSelect) {
      setQuery('');
    } else {
      setQuery(user.username);
    }
    setUserResults([]);
    setGroupResults([]);
    setDropdownOpen(false);
  };

  const handleSelectGroup = (group: DirectoryGroup) => {
    onSelectGroup?.(group);
    if (clearOnSelect) setQuery('');
    setUserResults([]);
    setGroupResults([]);
    setDropdownOpen(false);
  };

  const hasResults = userResults.length > 0 || groupResults.length > 0;
  const defaultPlaceholder = directoryEnabled
    ? 'Search people or groups\u2026'
    : 'Enter username';

  return (
    <div className="relative">
      <div className="relative">
        {directoryEnabled && (
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-500 pointer-events-none" />
        )}
        <Input
          ref={inputRef}
          value={query}
          onChange={(e) => handleChange(e.target.value)}
          onFocus={() => {
            if (hasResults || isSearching) setDropdownOpen(true);
          }}
          placeholder={placeholder ?? defaultPlaceholder}
          className={`${directoryEnabled ? 'pl-9' : ''} ${inputClassName ?? ''}`}
          autoComplete="off"
        />
        {directoryEnabled && (
          <div className="absolute right-3 top-0 bottom-0 flex items-center pointer-events-none">
            <Loader2 className={`h-4 w-4 text-gray-400 ${isSearching ? 'animate-spin' : 'hidden'}`} />
          </div>
        )}
      </div>

      {dropdownOpen && directoryEnabled && query.trim().length >= 2 && (
        <div
          ref={dropdownRef}
          className="absolute z-[60] w-full mt-1 max-h-[280px] overflow-y-auto rounded-md border border-gray-700 bg-gray-900 shadow-lg"
        >
          {isSearching ? (
            <div className="flex items-center justify-center py-4 text-sm text-gray-400">
              <Loader2 className="w-4 h-4 mr-2 animate-spin" />
              Searching&hellip;
            </div>
          ) : searchError ? (
            <div className="px-3 py-4 text-sm text-amber-400 text-center">
              {searchError}
            </div>
          ) : !hasResults ? (
            <div className="px-3 py-4 text-sm text-gray-400 text-center">
              No results found
            </div>
          ) : (
            <>
              {groupResults.length > 0 && onSelectGroup && (
                <>
                  <div className="px-3 py-1.5 text-[10px] font-semibold uppercase tracking-wider text-gray-500 border-b border-gray-800">
                    Groups
                  </div>
                  {groupResults.map((g) => (
                    <button
                      key={`group-${g.group_id}`}
                      type="button"
                      onMouseDown={(e) => e.preventDefault()}
                      onClick={() => handleSelectGroup(g)}
                      className="w-full flex items-center gap-2.5 px-3 py-2 text-left hover:bg-white/10 transition-colors cursor-pointer"
                    >
                      <Users className="w-4 h-4 text-indigo-400 flex-shrink-0" />
                      <div className="flex flex-col min-w-0">
                        <span className="text-sm text-gray-100 truncate">{g.name}</span>
                        <span className="text-xs text-gray-400 truncate">
                          {g.members.length} member{g.members.length !== 1 ? 's' : ''}
                          {g.description ? ` \u00b7 ${g.description}` : ''}
                        </span>
                      </div>
                    </button>
                  ))}
                </>
              )}

              {userResults.length > 0 && (
                <>
                  {groupResults.length > 0 && onSelectGroup && (
                    <div className="px-3 py-1.5 text-[10px] font-semibold uppercase tracking-wider text-gray-500 border-b border-gray-800">
                      People
                    </div>
                  )}
                  {userResults.map((u) => (
                    <button
                      key={u.user_id}
                      type="button"
                      onMouseDown={(e) => e.preventDefault()}
                      onClick={() => handleSelectUser(u)}
                      className="w-full flex flex-col px-3 py-2 text-left hover:bg-white/10 transition-colors cursor-pointer"
                    >
                      <span className="text-sm text-gray-100">{u.display_name}</span>
                      <span className="text-xs text-gray-400">
                        {u.username}{u.email ? ` \u00b7 ${u.email}` : ''}
                      </span>
                    </button>
                  ))}
                </>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}
