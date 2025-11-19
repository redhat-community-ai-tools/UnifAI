import React, { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { FaTimes, FaUser, FaCube, FaHashtag, FaEnvelope, FaPaperPlane, FaArrowLeft } from 'react-icons/fa';
import { FaShareNodes } from "react-icons/fa6";
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import SimpleTooltip from '@/components/shared/SimpleTooltip';
import { useNotifications } from '@/contexts/NotificationContext';
import { useShared } from '@/contexts/SharedContext';
import { ShareInvite } from '@/api/shares';

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

  // Send notification form state
  const [sendForm, setSendForm] = useState({
    recipientUserId: '',
    message: '',
  });

  const [isSending, setIsSending] = useState(false);

  // Handle click outside to close panel
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

  // Reset form when shareItem changes
  useEffect(() => {
    if (shareItem) {
      setSendForm({
        recipientUserId: '',
        message: '',
      });
    }
  }, [shareItem]);

  // Handle form input changes
  const handleSendFormChange = (field: string, value: string) => {
    setSendForm(prev => ({ ...prev, [field]: value }));
    if (error) clearError();
  };

  // Handle send notification
  const handleSendNotification = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!sendForm.recipientUserId || !shareItem) {
      return;
    }

    setIsSending(true);
    try {
      await sendNotification({
        recipientUserId: sendForm.recipientUserId,
        itemKind: shareItem.itemKind,
        itemId: shareItem.itemId,
        message: sendForm.message || undefined,
      });
      
      // Reset form on success
      setSendForm({
        recipientUserId: '',
        message: '',
      });
      
      // Switch back to list view
      setSharedPanelView('list');
    } catch (err) {
      // Error is handled by the context
    } finally {
      setIsSending(false);
    }
  };

  // Format date for display
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

  // Get status badge variant
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

  // Check if send form is valid
  const isSendFormValid = sendForm.recipientUserId && shareItem;

  if (!isOpen) return null;

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
            {sharedPanelView === 'send' && (
              <button
                onClick={() => setSharedPanelView('list')}
                className="p-1 rounded-full hover:bg-background-card text-gray-400 hover:text-white transition-colors mr-2"
              >
                <FaArrowLeft />
              </button>
            )}
            <h2 className="text-lg font-semibold text-white flex items-center gap-2">
              <FaShareNodes className="text-accent" />
              {sharedPanelView === 'list' ? 'Shared System' : 'Share Item'}
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
          {sharedPanelView === 'list' ? (
            // List View - Received/Sent Tabs
            <Tabs defaultValue="received" className="w-full">
              <TabsList className="grid w-full grid-cols-2 mb-4">
                <TabsTrigger value="received">Received</TabsTrigger>
                <TabsTrigger value="sent">Sent</TabsTrigger>
              </TabsList>

              {/* Received Tab */}
              <TabsContent value="received" className="mt-0">
                <div className="space-y-3 max-h-80 overflow-y-auto">
                  {isLoading ? (
                    <div className="text-center py-6 text-gray-400">
                      Loading shared items...
                    </div>
                  ) : receivedNotifications.length === 0 ? (
                    <div className="text-center py-6 text-gray-400">
                      No received shares found
                    </div>
                  ) : (
                    <div className="space-y-2">
                      {receivedNotifications.map((notification) => (
                        <div
                          key={notification.share_id}
                          className="p-3 bg-background-card border border-gray-700 rounded-lg"
                        >
                          <div className="flex items-center gap-2 mb-2">
                            <span className="text-sm font-medium text-white truncate">
                              {notification.item_name}
                            </span>
                            {getStatusBadge(notification.status)}
                          </div>
                          <div className="flex items-center gap-4 text-xs text-gray-400 mb-2">
                            <span className="flex items-center gap-1">
                              <FaUser className="w-3 h-3" />
                              {notification.sender_user_id}
                            </span>
                            <span className="flex items-center gap-1">
                              <FaCube className="w-3 h-3" />
                              {notification.item_kind}
                            </span>
                            <span>{formatDate(notification.created_at)}</span>
                          </div>
                          {notification.message && (
                            <div className="text-xs text-gray-300 mb-2 p-2 bg-gray-800 rounded">
                              💬 {notification.message}
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </TabsContent>

              {/* Sent Tab */}
              <TabsContent value="sent" className="mt-0">
                <div className="space-y-3 max-h-80 overflow-y-auto">
                  {isLoading ? (
                    <div className="text-center py-6 text-gray-400">
                      Loading shared items...
                    </div>
                  ) : sentNotifications.length === 0 ? (
                    <div className="text-center py-6 text-gray-400">
                      No sent shares found
                    </div>
                  ) : (
                    <div className="space-y-2">
                      {sentNotifications.map((notification) => (
                        <div
                          key={notification.share_id}
                          className="p-3 bg-background-card border border-gray-700 rounded-lg"
                        >
                          <div className="flex items-center gap-2 mb-2">
                            <span className="text-sm font-medium text-white truncate">
                              {notification.item_name}
                            </span>
                            {getStatusBadge(notification.status)}
                          </div>
                          <div className="flex items-center gap-4 text-xs text-gray-400 mb-2">
                            <span className="flex items-center gap-1">
                              <FaUser className="w-3 h-3" />
                              to {notification.recipient_user_id}
                            </span>
                            <span className="flex items-center gap-1">
                              <FaCube className="w-3 h-3" />
                              {notification.item_kind}
                            </span>
                            <span>{formatDate(notification.created_at)}</span>
                          </div>
                          {notification.message && (
                            <div className="text-xs text-gray-300 mb-2 p-2 bg-gray-800 rounded">
                              💬 {notification.message}
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </TabsContent>
            </Tabs>
          ) : (
            // Send View
            <div className="space-y-4">
              {/* Item Info */}
              {shareItem && (
                <div className="p-3 bg-background-card border border-gray-700 rounded-lg">
                  <h3 className="text-sm font-medium text-white mb-2">Sharing Item</h3>
                  <div className="flex items-center gap-4 text-xs text-gray-400">
                    <span className="flex items-center gap-1">
                      <FaCube className="w-3 h-3" />
                      {shareItem.itemKind}
                    </span>
                    <span className="flex items-center gap-1">
                      <FaHashtag className="w-3 h-3" />
                      {shareItem.itemId}
                    </span>
                  </div>
                  {shareItem.itemName && (
                    <div className="text-sm text-white mt-1">{shareItem.itemName}</div>
                  )}
                </div>
              )}

              {/* Send Form */}
              <form onSubmit={handleSendNotification} className="space-y-3">
                {/* Recipient User ID */}
                <div>
                  <Label htmlFor="recipientUserId" className="flex items-center gap-2 mb-1">
                    <FaUser className="w-3 h-3 text-accent" />
                    Recipient User ID *
                  </Label>
                  <Input
                    id="recipientUserId"
                    placeholder="Enter recipient username"
                    value={sendForm.recipientUserId}
                    onChange={(e) => handleSendFormChange('recipientUserId', e.target.value)}
                    className="input-dark-theme-text-white placeholder:text-gray-400 bg-gray-800 border-gray-600"
                    required
                  />
                </div>

                {/* Message (Optional) */}
                <div>
                  <Label htmlFor="message" className="flex items-center gap-2 mb-1">
                    <FaEnvelope className="w-3 h-3 text-accent" />
                    Message (Optional)
                  </Label>
                  <Input
                    id="message"
                    placeholder="Add a message..."
                    value={sendForm.message}
                    onChange={(e) => handleSendFormChange('message', e.target.value)}
                    className="input-dark-theme-text-white placeholder:text-gray-400 bg-gray-800 border-gray-600"
                  />
                </div>

                {/* Send Button */}
                <div className="flex justify-end pt-2">
                  <Button
                    type="submit"
                    disabled={!isSendFormValid || isSending}
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
          )}
        </div>
      </motion.div>
    </AnimatePresence>
  );
}
