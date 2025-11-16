import React, { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { FaTimes, FaCheck, FaUser, FaCube, FaBell } from 'react-icons/fa';
import { Badge } from '@/components/ui/badge';
import SimpleTooltip from '@/components/shared/SimpleTooltip';
import { useNotifications } from '@/contexts/NotificationContext';
import { ShareInvite } from '@/api/shares';

interface NotificationPanelProps {
  isOpen: boolean;
  onClose: () => void;
}

export default function NotificationPanel({ isOpen, onClose }: NotificationPanelProps) {
  const panelRef = useRef<HTMLDivElement>(null);
  const {
    receivedNotifications,
    isLoading,
    error,
    acceptNotification,
    declineNotification,
  } = useNotifications();

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

  // Handle accept notification
  const handleAcceptNotification = async (shareId: string) => {
    try {
      await acceptNotification(shareId);
    } catch (err) {
      // Error is handled by the context
    }
  };

  // Handle decline notification
  const handleDeclineNotification = async (shareId: string) => {
    try {
      await declineNotification(shareId);
    } catch (err) {
      // Error is handled by the context
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

  // Filter only pending notifications for notifications panel
  const pendingNotifications = receivedNotifications?.filter(notification => notification.status === 'pending');

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
          <h2 className="text-lg font-semibold text-white flex items-center gap-2">
            <FaBell className="text-accent" />
            Notifications
          </h2>
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
          <div className="space-y-3 max-h-80 overflow-y-auto">
            {isLoading ? (
              <div className="text-center py-6 text-gray-400">
                Loading notifications...
              </div>
            ) : pendingNotifications.length === 0 ? (
              <div className="text-center py-6 text-gray-400">
                No pending notifications
              </div>
            ) : (
              <div className="space-y-2">
                <h3 className="text-sm font-medium text-gray-300 mb-3">Pending Share Requests ({pendingNotifications.length})</h3>
                {pendingNotifications.map((notification) => (
                  <div
                    key={notification.share_id}
                    className="p-3 bg-background-card border border-gray-700 rounded-lg"
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-2">
                          <span className="text-sm font-medium text-white truncate">
                            {notification.item_name}
                          </span>
                          <Badge variant="secondary" className="bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-300">
                            Pending
                          </Badge>
                        </div>
                        <div className="flex items-center gap-4 text-xs text-gray-400 mb-2">
                          <span className="flex items-center gap-1">
                            <FaUser className="w-3 h-3" />
                            from {notification.sender_user_id}
                          </span>
                          <span className="flex items-center gap-1">
                            <FaCube className="w-3 h-3" />
                            {notification.item_kind}
                          </span>
                          <span>{formatDate(notification.created_at)}</span>
                        </div>
                        {notification.message && (
                          <div className="text-xs text-gray-300 mb-3 p-2 bg-gray-800 rounded">
                            💬 {notification.message}
                          </div>
                        )}
                      </div>
                    </div>
                    
                    {/* Action buttons */}
                    <div className="flex items-center gap-2 justify-end">
                      <SimpleTooltip content={<p>Accept share request</p>}>
                        <button
                          onClick={() => handleAcceptNotification(notification.share_id)}
                          className="px-3 py-1.5 rounded-md bg-green-600 hover:bg-green-700 text-white text-xs font-medium transition-colors flex items-center gap-1"
                        >
                          <FaCheck className="w-3 h-3" />
                          Accept
                        </button>
                      </SimpleTooltip>
                      <SimpleTooltip content={<p>Decline share request</p>}>
                        <button
                          onClick={() => handleDeclineNotification(notification.share_id)}
                          className="px-3 py-1.5 rounded-md bg-red-600 hover:bg-red-700 text-white text-xs font-medium transition-colors flex items-center gap-1"
                        >
                          <FaTimes className="w-3 h-3" />
                          Decline
                        </button>
                      </SimpleTooltip>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </motion.div>
    </AnimatePresence>
  );
}
