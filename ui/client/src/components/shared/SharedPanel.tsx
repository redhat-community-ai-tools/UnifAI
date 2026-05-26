import React, { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { FaTimes, FaUser, FaCube, FaHashtag, FaEnvelope, FaPaperPlane, FaArrowLeft, FaUsers } from 'react-icons/fa';
import { FaShareNodes } from "react-icons/fa6";
import { Download } from 'lucide-react';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { useNotifications } from '@/contexts/NotificationContext';
import { useShared, SharedPanelView } from '@/contexts/SharedContext';
import { useView } from '@/contexts/ViewContext';
import { useAuth } from '@/contexts/AuthContext';
import { ShareInvite, shareToTeam, formatShareSenderLabel } from '@/api/shares';
import { getEffectiveMemberCount } from '@/api/teams';
import UserDirectorySearch from '@/components/shared/UserDirectorySearch';
import type { DirectoryUser } from '@/api/directory';

interface SharedPanelProps {
  isOpen: boolean;
  onClose: () => void;
}

export default function SharedPanel({ isOpen, onClose }: SharedPanelProps) {
  const panelRef = useRef<HTMLDivElement>(null);
  const {
    receivedNotifications,
    sentNotifications,
    isLoading,
    error,
    sendNotification,
    clearError,
  } = useNotifications();

  const {
    sharedPanelView,
    shareItem,
    setSharedPanelView,
  } = useShared();

  const { viewMode, selectedTeam, teams } = useView();
  const { user, accessToken } = useAuth();

  const [sendForm, setSendForm] = useState({
    recipientUserId: '',
    message: '',
  });

  const [isSending, setIsSending] = useState(false);
  const [teamShareError, setTeamShareError] = useState<string | null>(null);
  const [selectedRecipient, setSelectedRecipient] = useState<DirectoryUser | null>(null);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      const target = event.target as Node;
      if (panelRef.current && !panelRef.current.contains(target)) {
        onClose();
      }
    };

    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    }

    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [isOpen, onClose]);

  useEffect(() => {
    if (shareItem) {
      setSendForm({ recipientUserId: '', message: '' });
      setTeamShareError(null);
      setSelectedRecipient(null);
    }
  }, [shareItem]);

  const handleRecipientSelect = (dirUser: DirectoryUser) => {
    setSelectedRecipient(dirUser);
    setSendForm(prev => ({ ...prev, recipientUserId: dirUser.user_id || dirUser.username }));
    if (error) clearError();
  };

  const handleRecipientInputChange = () => {
    setSelectedRecipient(null);
    setSendForm(prev => ({ ...prev, recipientUserId: '' }));
    if (error) clearError();
  };

  const handleSendNotification = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedRecipient || !sendForm.recipientUserId || !shareItem) return;

    setIsSending(true);
    try {
      await sendNotification({
        recipientUserId: sendForm.recipientUserId,
        itemKind: shareItem.itemKind,
        itemId: shareItem.itemId,
        message: sendForm.message || undefined,
      });
      setSendForm({ recipientUserId: '', message: '' });
      setSelectedRecipient(null);
      setSharedPanelView('list');
    } catch (err) {
      // Error handled by context
    } finally {
      setIsSending(false);
    }
  };

  const handleCopyToPersonal = async () => {
    if (!shareItem || !user?.username) return;

    setIsSending(true);
    try {
      await sendNotification({
        recipientUserId: user.username,
        itemKind: shareItem.itemKind,
        itemId: shareItem.itemId,
        message: 'Copied to personal workspace',
        autoAccept: true,
      });
      setSendForm({ recipientUserId: '', message: '' });
      setSharedPanelView('list');
    } catch (err) {
      // Error handled by context
    } finally {
      setIsSending(false);
    }
  };

  const handleShareToTeam = async (teamId: string) => {
    if (!shareItem) return;

    setIsSending(true);
    setTeamShareError(null);
    try {
      await shareToTeam({
        teamName: teamId,
        itemKind: shareItem.itemKind,
        itemId: shareItem.itemId,
      });
      setSharedPanelView('list');
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Failed to share with team';
      setTeamShareError(msg);
    } finally {
      setIsSending(false);
    }
  };

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    const now = new Date();
    const diffInMinutes = Math.floor((now.getTime() - date.getTime()) / (1000 * 60));
    if (diffInMinutes < 1) return 'Just now';
    if (diffInMinutes < 60) return `${diffInMinutes}m ago`;
    if (diffInMinutes < 1440) return `${Math.floor(diffInMinutes / 60)}h ago`;
    if (diffInMinutes < 10080) return `${Math.floor(diffInMinutes / 1440)}d ago`;
    return date.toLocaleDateString();
  };

  const getStatusBadge = (status: ShareInvite['status']) => {
    switch (status) {
      case 'pending':
        return <Badge variant="secondary" className="bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-300">Pending</Badge>;
      case 'accepted':
        return <Badge variant="secondary" className="bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-300">Accepted</Badge>;
      case 'declined':
        return <Badge variant="secondary" className="bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-300">Declined</Badge>;
      case 'canceled':
        return <Badge variant="secondary" className="bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-300">Canceled</Badge>;
      default:
        return <Badge variant="secondary">{status}</Badge>;
    }
  };

  const getHeaderTitle = (view: SharedPanelView) => {
    switch (view) {
      case 'list': return 'Shared System';
      case 'send-choice': return 'Share Item';
      case 'send-user': return 'Share with User';
      case 'send-team': return 'Share with Team';
    }
  };

  const handleBack = () => {
    if (sharedPanelView === 'send-user' || sharedPanelView === 'send-team') {
      setSharedPanelView('send-choice');
    } else if (sharedPanelView === 'send-choice') {
      setSharedPanelView('list');
    }
  };

  if (!isOpen) return null;

  const renderShareItemInfo = () => {
    if (!shareItem) return null;
    return (
      <div className="p-3 bg-background-card border border-gray-700 rounded-lg">
        <h3 className="text-sm font-medium text-white mb-2">Sharing Item</h3>
        <div className="flex items-center gap-4 text-xs text-gray-400">
          <span className="flex items-center gap-1">
            <FaCube className="w-3 h-3" />
            {shareItem.itemKind}
          </span>
          <span className="flex items-center gap-1">
            <FaHashtag className="w-3 h-3" />
            {shareItem.itemId.slice(0, 12)}...
          </span>
        </div>
        {shareItem.itemName && (
          <div className="text-sm text-white mt-1">{shareItem.itemName}</div>
        )}
      </div>
    );
  };

  const renderSendChoice = () => (
    <div className="space-y-4">
      {renderShareItemInfo()}

      <div className="space-y-3">
        <button
          onClick={() => setSharedPanelView('send-user')}
          className="w-full p-4 bg-background-card border border-gray-700 rounded-lg hover:border-accent hover:bg-accent/5 transition-all group text-left"
        >
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-full bg-blue-500/10 flex items-center justify-center group-hover:bg-blue-500/20 transition-colors">
              <FaUser className="w-4 h-4 text-blue-400" />
            </div>
            <div>
              <div className="text-sm font-medium text-white">Share with User</div>
              <div className="text-xs text-gray-400">Send to a specific user by username</div>
            </div>
          </div>
        </button>

        <button
          onClick={() => setSharedPanelView('send-team')}
          className="w-full p-4 bg-background-card border border-gray-700 rounded-lg hover:border-accent hover:bg-accent/5 transition-all group text-left"
        >
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-full bg-purple-500/10 flex items-center justify-center group-hover:bg-purple-500/20 transition-colors">
              <FaUsers className="w-4 h-4 text-purple-400" />
            </div>
            <div>
              <div className="text-sm font-medium text-white">Share with Team</div>
              <div className="text-xs text-gray-400">Clone directly into a team workspace</div>
            </div>
          </div>
        </button>
      </div>
    </div>
  );

  const renderSendUser = () => (
    <div className="space-y-4">
      {renderShareItemInfo()}

      {viewMode === 'team' && user?.username && (
        <button
          onClick={handleCopyToPersonal}
          disabled={isSending}
          className="w-full p-3 bg-background-card border border-dashed border-gray-600 rounded-lg hover:border-accent hover:bg-accent/5 transition-all group text-left"
        >
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-full bg-green-500/10 flex items-center justify-center group-hover:bg-green-500/20 transition-colors">
              <Download className="w-4 h-4 text-green-400" />
            </div>
            <div>
              <div className="text-sm font-medium text-white">
                {isSending ? 'Copying...' : 'Copy to Personal Workspace'}
              </div>
              <div className="text-xs text-gray-400">
                Instantly copy to your account ({user.username})
              </div>
            </div>
          </div>
        </button>
      )}

      <form onSubmit={handleSendNotification} className="space-y-3">
        <div>
          <Label htmlFor="recipientUserId" className="flex items-center gap-2 mb-1">
            <FaUser className="w-3 h-3 text-accent" />
            Recipient User ID *
          </Label>
          <UserDirectorySearch
            key={shareItem?.itemId ?? 'no-item'}
            onSelect={handleRecipientSelect}
            onInputChange={handleRecipientInputChange}
            clearOnSelect={false}
            accessToken={accessToken}
            placeholder="Search for a user..."
            inputClassName="bg-gray-800 border-gray-600 text-white placeholder:text-gray-400"
          />
          {selectedRecipient && (
            <div className="mt-2 p-2 bg-accent/10 border border-accent/30 rounded-md flex items-center gap-2">
              <FaUser className="w-3 h-3 text-accent flex-shrink-0" />
              <div className="min-w-0">
                <span className="text-sm text-white font-medium">{selectedRecipient.display_name}</span>
                <span className="text-xs text-gray-400 ml-2">({selectedRecipient.username})</span>
                {selectedRecipient.email && (
                  <span className="text-xs text-gray-500 ml-2">{selectedRecipient.email}</span>
                )}
              </div>
            </div>
          )}
        </div>

        <div>
          <Label htmlFor="message" className="flex items-center gap-2 mb-1">
            <FaEnvelope className="w-3 h-3 text-accent" />
            Message (Optional)
          </Label>
          <Input
            id="message"
            placeholder="Add a message..."
            value={sendForm.message}
            onChange={(e) => {
              setSendForm(prev => ({ ...prev, message: e.target.value }));
              if (error) clearError();
            }}
            className="input-dark-theme-text-white placeholder:text-gray-400 bg-gray-800 border-gray-600"
          />
        </div>

        <div className="flex justify-end pt-2">
          <Button
            type="submit"
            disabled={!selectedRecipient || !shareItem || isSending}
            className="bg-accent hover:bg-accent/90"
          >
            {isSending ? (
              <>Sending...</>
            ) : (
              <>
                <FaPaperPlane className="w-3 h-3 mr-2" />
                Send Share Request
              </>
            )}
          </Button>
        </div>
      </form>
    </div>
  );

  const renderSendTeam = () => (
    <div className="space-y-4">
      {renderShareItemInfo()}

      {teamShareError && (
        <div className="p-3 bg-red-900/40 border border-red-800 rounded-md">
          <p className="text-sm text-red-300">{teamShareError}</p>
        </div>
      )}

      <div>
        <Label className="flex items-center gap-2 mb-2">
          <FaUsers className="w-3 h-3 text-purple-400" />
          Select a Team
        </Label>
        <div className="space-y-2 max-h-64 overflow-y-auto">
          {teams.length === 0 ? (
            <div className="text-center py-6 text-gray-400 text-sm">
              You are not a member of any team yet.
            </div>
          ) : (
            teams.map((team) => {
              const count = getEffectiveMemberCount(team.members, team.effective_member_count);
              return (
                <button
                  key={team.id}
                  onClick={() => handleShareToTeam(team.id)}
                  disabled={isSending}
                  className="w-full p-3 bg-background-card border border-gray-700 rounded-lg hover:border-purple-500/50 hover:bg-purple-500/5 transition-all text-left disabled:opacity-50"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3 min-w-0">
                      <div className="w-8 h-8 rounded-full bg-purple-500/10 flex items-center justify-center flex-shrink-0">
                        <FaUsers className="w-3.5 h-3.5 text-purple-400" />
                      </div>
                      <div className="min-w-0">
                        <div className="text-sm font-medium text-white truncate">{team.name}</div>
                        <div className="text-xs text-gray-400">
                          {count} member{count !== 1 ? 's' : ''}
                        </div>
                      </div>
                    </div>
                    <FaPaperPlane className="w-3 h-3 text-gray-500 flex-shrink-0" />
                  </div>
                </button>
              );
            })
          )}
        </div>
      </div>
    </div>
  );

  const renderListView = () => (
    <Tabs defaultValue="received" className="w-full">
      <TabsList className="grid w-full grid-cols-2 mb-4">
        <TabsTrigger value="received">Received</TabsTrigger>
        <TabsTrigger value="sent">Sent</TabsTrigger>
      </TabsList>

      <TabsContent value="received" className="mt-0">
        <div className="space-y-3 max-h-80 overflow-y-auto">
          {isLoading ? (
            <div className="text-center py-6 text-gray-400">Loading shared items...</div>
          ) : receivedNotifications.length === 0 ? (
            <div className="text-center py-6 text-gray-400">No received shares found</div>
          ) : (
            <div className="space-y-2">
              {receivedNotifications.map((notification) => (
                <div key={notification.share_id} className="p-3 bg-background-card border border-gray-700 rounded-lg">
                  <div className="flex items-center gap-2 mb-2">
                    <span className="text-sm font-medium text-white truncate">{notification.item_name}</span>
                    {getStatusBadge(notification.status)}
                  </div>
                  <div className="flex items-center gap-4 text-xs text-gray-400 mb-2">
                    <span className="flex items-center gap-1">
                      <FaUser className="w-3 h-3" />
                      {formatShareSenderLabel(notification)}
                    </span>
                    <span className="flex items-center gap-1">
                      <FaCube className="w-3 h-3" />
                      {notification.item_kind}
                    </span>
                    <span>{formatDate(notification.created_at)}</span>
                  </div>
                  {notification.message && (
                    <div className="text-xs text-gray-300 mb-2 p-2 bg-gray-800 rounded">
                      {notification.message}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </TabsContent>

      <TabsContent value="sent" className="mt-0">
        <div className="space-y-3 max-h-80 overflow-y-auto">
          {isLoading ? (
            <div className="text-center py-6 text-gray-400">Loading shared items...</div>
          ) : sentNotifications.length === 0 ? (
            <div className="text-center py-6 text-gray-400">No sent shares found</div>
          ) : (
            <div className="space-y-2">
              {sentNotifications.map((notification) => (
                <div key={notification.share_id} className="p-3 bg-background-card border border-gray-700 rounded-lg">
                  <div className="flex items-center gap-2 mb-2">
                    <span className="text-sm font-medium text-white truncate">{notification.item_name}</span>
                    {getStatusBadge(notification.status)}
                  </div>
                  <div className="flex items-center gap-4 text-xs text-gray-400 mb-2">
                    <span className="flex items-center gap-1">
                      <FaUser className="w-3 h-3" />
                      with {notification.recipient_user_id}
                    </span>
                    <span className="flex items-center gap-1">
                      <FaCube className="w-3 h-3" />
                      {notification.item_kind}
                    </span>
                    <span>{formatDate(notification.created_at)}</span>
                  </div>
                  {notification.message && (
                    <div className="text-xs text-gray-300 mb-2 p-2 bg-gray-800 rounded">
                      {notification.message}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </TabsContent>
    </Tabs>
  );

  return (
    <AnimatePresence>
      <motion.div
        ref={panelRef}
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: -10 }}
        transition={{ duration: 0.2 }}
        className="absolute top-full right-0 z-50 mt-2 w-96 bg-gray-900 border border-gray-800 rounded-lg shadow-2xl overflow-hidden"
        style={{ backgroundColor: '#111827', opacity: 1 }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-gray-800 bg-gray-900">
          <div className="flex items-center gap-2">
            {sharedPanelView !== 'list' && (
              <button
                onClick={handleBack}
                className="p-1 rounded-full hover:bg-background-card text-gray-400 hover:text-white transition-colors mr-2"
              >
                <FaArrowLeft />
              </button>
            )}
            <h2 className="text-lg font-semibold text-white flex items-center gap-2">
              <FaShareNodes className="text-accent" />
              {getHeaderTitle(sharedPanelView)}
            </h2>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-full hover:bg-background-card text-gray-400 hover:text-white transition-colors"
          >
            <FaTimes />
          </button>
        </div>

        {/* Error Display */}
        {error && (
          <div className="mx-4 mt-2 p-3 bg-red-100 dark:bg-red-900 border border-red-300 dark:border-red-800 rounded-md">
            <p className="text-sm text-red-800 dark:text-red-300">{error}</p>
          </div>
        )}

        {/* Content */}
        <div className="p-4 bg-gray-900">
          {sharedPanelView === 'list' && renderListView()}
          {sharedPanelView === 'send-choice' && renderSendChoice()}
          {sharedPanelView === 'send-user' && renderSendUser()}
          {sharedPanelView === 'send-team' && renderSendTeam()}
        </div>
      </motion.div>
    </AnimatePresence>
  );
}
