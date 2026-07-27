import { useState, useEffect, useRef } from "react";
import { useAuth } from "@/contexts/AuthContext";
import { useView, TeamInfo } from "@/contexts/ViewContext";
import { createTeam, updateTeam, deleteTeam, TeamMember, getEffectiveMemberCount } from "@/api/teams";
import { getDirectoryGroup } from "@/api/directory";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { X, Crown, Trash2, Users, User, Loader2, ChevronDown, ChevronRight } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
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
import UserDirectorySearch from "@/components/shared/UserDirectorySearch";
import type { DirectoryUser, DirectoryGroup } from "@/api/directory";

interface TeamSettingsModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  team: TeamInfo | null;
}

export default function TeamSettingsModal({ open, onOpenChange, team }: TeamSettingsModalProps) {
  const { user, accessToken } = useAuth();
  const { refreshTeams } = useView();
  const [teamName, setTeamName] = useState("");
  const [members, setMembers] = useState<TeamMember[]>([]);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [searchResetKey, setSearchResetKey] = useState(0);
  const isSubmittingRef = useRef(false);

  // Track which groups are expanded to show their members
  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(new Set());
  const [groupMembersCache, setGroupMembersCache] = useState<Record<string, string[]>>({});
  const [loadingGroupMembers, setLoadingGroupMembers] = useState<Set<string>>(new Set());

  const isEditing = !!team;

  useEffect(() => {
    if (open) {
      setGroupMembersCache({});
      if (team) {
        setTeamName(team.name);
        setMembers([...team.members]);
      } else {
        setTeamName("");
        setMembers(user?.username
          ? [{
              type: "user" as const,
              id: user.username,
              display_name: user.name || user.username,
            }]
          : []);
      }
      setError("");
      setExpandedGroups(new Set());
      setSearchResetKey((k) => k + 1);
    }
  }, [open, team, user?.username, user?.name]);

  const addMemberFromDirectory = (dirUser: DirectoryUser) => {
    const alreadyExists = members.some((m) => m.type === "user" && m.id === dirUser.user_id);
    if (!alreadyExists) {
      setMembers((prev) => [...prev, {
        type: "user" as const,
        id: dirUser.user_id,
        display_name: dirUser.display_name || dirUser.username,
      }]);
    }
    setError("");
    setSearchResetKey((k) => k + 1);
  };

  const addGroupAsReference = (group: DirectoryGroup) => {
    const alreadyExists = members.some((m) => m.type === "group" && m.id === group.group_id);
    if (alreadyExists) {
      setError(`Group "${group.name}" is already in this team`);
    } else {
      setMembers((prev) => [...prev, {
        type: "group" as const,
        id: group.group_id,
        display_name: group.name,
        group_members: group.members,
      }]);
    }
    setSearchResetKey((k) => k + 1);
  };

  const getGroupMembers = (groupId: string): string[] | undefined => {
    if (groupMembersCache[groupId]) return groupMembersCache[groupId];
    const member = members.find((m) => m.type === "group" && m.id === groupId);
    if (member?.group_members && member.group_members.length > 0) return member.group_members;
    return undefined;
  };

  const toggleGroupExpand = async (groupId: string) => {
    if (expandedGroups.has(groupId)) {
      setExpandedGroups((prev) => {
        const next = new Set(prev);
        next.delete(groupId);
        return next;
      });
      return;
    }

    // Open instantly when we already have members; avoid refetching on every toggle.
    const cached = getGroupMembers(groupId);
    if (cached && cached.length > 0) {
      setGroupMembersCache((prev) => ({ ...prev, [groupId]: cached }));
      setExpandedGroups((prev) => new Set(prev).add(groupId));
      return;
    }

    setLoadingGroupMembers((prev) => new Set(prev).add(groupId));
    try {
      const group = await getDirectoryGroup(groupId, accessToken);
      setGroupMembersCache((prev) => ({ ...prev, [groupId]: group.members }));
      setMembers((prev) =>
        prev.map((m) =>
          m.type === "group" && m.id === groupId
            ? { ...m, group_members: group.members }
            : m,
        ),
      );
      setExpandedGroups((prev) => new Set(prev).add(groupId));
    } catch {
      // LDAP unavailable — fall back to stored group_members
      const stored = getGroupMembers(groupId);
      if (stored) {
        setGroupMembersCache((prev) => ({ ...prev, [groupId]: stored }));
        setExpandedGroups((prev) => new Set(prev).add(groupId));
      } else {
        setError("Failed to load members for group");
      }
    } finally {
      setLoadingGroupMembers((prev) => {
        const next = new Set(prev);
        next.delete(groupId);
        return next;
      });
    }
  };

  const removeMember = (member: TeamMember) => {
    if (member.type === "user") {
      if (isEditing && member.id === team.created_by) return;
      if (!isEditing && member.id === user?.username) return;
    }
    setMembers(members.filter((m) => !(m.type === member.type && m.id === member.id)));
  };

  const handleSubmit = async () => {
    if (isSubmittingRef.current) return;
    if (!teamName.trim()) {
      setError("Team name is required");
      return;
    }
    if (members.length === 0) {
      setError("At least one member is required");
      return;
    }
    isSubmittingRef.current = true;
    setSaving(true);
    setError("");
    try {
      if (isEditing) {
        await updateTeam(team.id, { name: teamName.trim(), members });
      } else {
        if (!user?.username) {
          setError("Authentication required");
          setSaving(false);
          isSubmittingRef.current = false;
          return;
        }
        await createTeam(teamName.trim(), user.username, members);
      }
      onOpenChange(false);
      void refreshTeams();
    } catch (err: any) {
      const msg = err?.response?.data?.error || err?.message || "Operation failed";
      setError(msg);
    } finally {
      setSaving(false);
      isSubmittingRef.current = false;
    }
  };

  const handleDelete = async () => {
    if (!team || !user?.username || isDeleting) return;
    setIsDeleting(true);
    try {
      await deleteTeam(team.id, user.username);
      setDeleteConfirmOpen(false);
      onOpenChange(false);
      void refreshTeams();
    } catch (err: any) {
      setError(err?.response?.data?.error || err?.message || "Failed to delete team");
      console.error("Failed to delete team:", err);
    } finally {
      setIsDeleting(false);
    }
  };

  const userMemberIds = members.filter((m) => m.type === "user").map((m) => m.id);
  const userMemberIdSet = new Set(userMemberIds);

  return (
    <>
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent className="bg-background-card border-gray-800 sm:max-w-md overflow-visible">          
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Users className="w-5 h-5 text-primary" />
              {isEditing ? "Team Settings" : "Create New Team"}
            </DialogTitle>
          </DialogHeader>

          <div className="space-y-4 mt-2">
            <div>
              <Label htmlFor="modal-team-name" className="text-sm text-gray-400">Team Name</Label>
              <Input
                id="modal-team-name"
                value={teamName}
                onChange={(e) => setTeamName(e.target.value)}
                placeholder="e.g. Platform Engineering"
                className="mt-1.5 bg-background-dark border-gray-700"
              />
            </div>

            <div>
              <Label className="text-sm text-gray-400">Members</Label>
              <div className="mt-1.5">
                <UserDirectorySearch
                  key={searchResetKey}
                  onSelect={addMemberFromDirectory}
                  onSelectGroup={addGroupAsReference}
                  excludeUserIds={userMemberIds}
                  accessToken={accessToken}
                  inputClassName="bg-background-dark border-gray-700 text-gray-100 placeholder:text-gray-500"
                />
              </div>

              {/* Unified member list — groups and users together */}
              {members.length > 0 && (
                <div className="mt-3 rounded-lg border border-gray-800 bg-white/[.02] overflow-hidden divide-y divide-gray-800/60">
                  {members.map((m) => {
                    if (m.type === "group") {
                      const isExpanded = expandedGroups.has(m.id);
                      const isLoadingMembers = loadingGroupMembers.has(m.id);
                      const cachedMembers = groupMembersCache[m.id] || m.group_members;
                      const memberCount = cachedMembers?.length ?? 0;
                      return (
                        <div key={`group-${m.id}`}>
                          <div className="flex items-center gap-2 px-3 py-2">
                            <button
                              type="button"
                              onClick={() => toggleGroupExpand(m.id)}
                              className="flex items-center gap-2 flex-1 min-w-0 text-left group"
                            >
                              {isLoadingMembers ? (
                                <Loader2 className="w-3.5 h-3.5 animate-spin text-gray-500 flex-shrink-0" />
                              ) : isExpanded ? (
                                <ChevronDown className="w-3.5 h-3.5 text-gray-500 flex-shrink-0" />
                              ) : (
                                <ChevronRight className="w-3.5 h-3.5 text-gray-500 flex-shrink-0" />
                              )}
                              <Users className="w-3.5 h-3.5 text-purple-400 flex-shrink-0" />
                              <span className="text-xs text-gray-200 truncate group-hover:text-white transition-colors">
                                {m.display_name || m.id}
                              </span>
                              {memberCount > 0 && (
                                <span className="text-[10px] text-gray-600 flex-shrink-0">
                                  {memberCount} member{memberCount !== 1 ? "s" : ""}
                                </span>
                              )}
                            </button>
                            <button
                              onClick={() => removeMember(m)}
                              className="p-0.5 text-gray-600 hover:text-red-400 transition-colors flex-shrink-0"
                            >
                              <X className="w-3 h-3" />
                            </button>
                          </div>
                          {isExpanded && cachedMembers && (
                            <div className="px-3 pb-2 ml-[22px] border-l border-gray-800">
                              <div className="flex flex-wrap gap-1 pl-2">
                                {cachedMembers.map((uid) => {
                                  const alreadyInTeam = userMemberIdSet.has(uid);
                                  return (
                                    <span
                                      key={uid}
                                      className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] ${
                                        alreadyInTeam
                                          ? "text-gray-500 bg-gray-700/40"
                                          : "text-gray-400 bg-white/5"
                                      }`}
                                      title={alreadyInTeam ? "Already in team" : undefined}
                                    >
                                      <User className="w-2.5 h-2.5" />
                                      {uid}
                                      {alreadyInTeam && (
                                        <span className="text-[9px] text-gray-500">(already in team)</span>
                                      )}
                                    </span>
                                  );
                                })}
                              </div>
                            </div>
                          )}
                        </div>
                      );
                    }

                    // User member
                    const isCreator = isEditing ? m.id === team.created_by : m.id === user?.username;
                    return (
                      <div key={`user-${m.id}`} className="flex items-center gap-2 px-3 py-2">
                        <User className="w-3.5 h-3.5 text-blue-400 flex-shrink-0 ml-[18px]" />
                        <span className="text-xs text-gray-200 truncate flex-1">
                          {m.display_name || m.id}
                        </span>
                        {isCreator && <Crown className="w-3 h-3 text-amber-400 flex-shrink-0" />}
                        {!isCreator && (
                          <button
                            onClick={() => removeMember(m)}
                            className="p-0.5 text-gray-600 hover:text-red-400 transition-colors flex-shrink-0"
                          >
                            <X className="w-3 h-3" />
                          </button>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>

            {error && (
              <p className="text-sm text-red-400">{error}</p>
            )}

            <div className="flex items-center justify-between pt-3 border-t border-gray-800">
              {isEditing && team.created_by === user?.username ? (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setDeleteConfirmOpen(true)}
                  className="text-red-400 hover:text-red-300 hover:bg-red-500/10"
                >
                  <Trash2 className="w-3.5 h-3.5 mr-1.5" />
                  Delete Team
                </Button>
              ) : (
                <div />
              )}
              <div className="flex gap-2">
                <Button variant="outline" onClick={() => onOpenChange(false)} className="border-gray-700">
                  Cancel
                </Button>
                <Button className="bg-primary" onClick={handleSubmit} disabled={saving}>
                  {saving ? "Saving..." : isEditing ? "Save Changes" : "Create Team"}
                </Button>
              </div>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      <AlertDialog open={deleteConfirmOpen} onOpenChange={setDeleteConfirmOpen}>
        <AlertDialogContent className="bg-background-card border-gray-800">
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Team</AlertDialogTitle>
            <AlertDialogDescription asChild>
              <div className="space-y-2 text-sm text-gray-400">
                <p>
                  Are you sure you want to delete <strong className="text-gray-200">{team?.name}</strong>?
                  This action is <strong className="text-red-400">permanent and cannot be undone</strong>.
                </p>
                <p>
                  All data owned by this team will be permanently deleted, including:
                </p>
                <ul className="list-disc pl-5 space-y-0.5">
                  <li>All workflows (blueprints) created under this team</li>
                  <li>All resources (tools, prompts, models) owned by this team</li>
                  <li>All chat sessions and their history</li>
                </ul>
                <p className="text-red-400 font-medium">
                  None of this data can be recovered after deletion.
                </p>
              </div>
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDelete}
              disabled={isDeleting}
              className="bg-red-600 hover:bg-red-700"
            >
              {isDeleting ? "Deleting..." : "Delete"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}
