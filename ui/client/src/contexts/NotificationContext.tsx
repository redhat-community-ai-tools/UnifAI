import React, { createContext, useContext, useEffect, useState, ReactNode } from 'react';
import { 
  ShareInvite, 
  listShares, 
  createShare, 
  acceptShare, 
  declineShare,
  CreateShareRequest,
  AcceptShareRequest,
  DeclineShareRequest 
} from '@/api/shares';
import { useAuth } from './AuthContext';
import { useView } from './ViewContext';

interface NotificationContextType {
  receivedNotifications: ShareInvite[];
  sentNotifications: ShareInvite[];
  isLoading: boolean;
  error: string | null;
  pendingNotificationsCount: number;
  hasUnreadNotifications: boolean;
  refreshNotifications: () => Promise<void>;
  sendNotification: (request: CreateShareRequest) => Promise<void>;
  acceptNotification: (shareId: string) => Promise<void>;
  declineNotification: (shareId: string) => Promise<void>;
  clearError: () => void;
}

const NotificationContext = createContext<NotificationContextType | undefined>(undefined);

interface NotificationProviderProps {
  children: ReactNode;
}

export const NotificationProvider: React.FC<NotificationProviderProps> = ({ children }) => {
  const { user, isAuthenticated } = useAuth();
  const { viewMode, selectedTeam, teams } = useView();
  const [receivedNotifications, setReceivedNotifications] = useState<ShareInvite[]>([]);
  const [sentNotifications, setSentNotifications] = useState<ShareInvite[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const userId = user?.username || '';
  const contextUserId = viewMode === 'team' && selectedTeam
    ? selectedTeam.id
    : userId;

  // Computed values
  const pendingNotificationsCount = receivedNotifications.filter(
    (notification) => notification.status === 'pending'
  ).length;

  const hasUnreadNotifications = pendingNotificationsCount > 0;

  // Refresh notifications from the API
  const refreshNotifications = async () => {
    if (!isAuthenticated || !userId) return;

    setIsLoading(true);
    setError(null);

    try {
      // Fetch both received and sent notifications in parallel
      const sentTeamName =
        viewMode === 'team' && selectedTeam
          ? (
              selectedTeam.name?.trim()
              || teams.find((t) => t.id === selectedTeam.id)?.name?.trim()
              || ''
            )
          : '';
      const [receivedResponse, sentResponse] = await Promise.all([
        listShares('received', userId),
        viewMode === 'team' && selectedTeam
          ? listShares('sent', selectedTeam.id, undefined, 0, 100, 'team', sentTeamName || undefined)
          : listShares('sent', userId),
      ]);

      setReceivedNotifications(receivedResponse.invites);
      setSentNotifications(sentResponse.invites);
    } catch (err) {
      console.error('Failed to fetch notifications:', err);
      setError(err instanceof Error ? err.message : 'Failed to fetch notifications');
    } finally {
      setIsLoading(false);
    }
  };

  const sendNotification = async (request: CreateShareRequest) => {
    setError(null);
    
    try {
      const senderType = viewMode === 'team' && selectedTeam ? 'team' : 'user';
      const senderDisplayName =
        senderType === 'team'
          ? (
              selectedTeam?.name?.trim()
              || teams.find((t) => t.id === selectedTeam?.id)?.name?.trim()
              || selectedTeam?.id
            )
          : (user?.username || contextUserId);
      await createShare({
        ...request,
        senderIdentityId: contextUserId,
        senderType,
        senderDisplayName,
      });
      await refreshNotifications();
    } catch (err) {
      console.error('Failed to send notification:', err);
      setError(err instanceof Error ? err.message : 'Failed to send notification');
      throw err;
    }
  };

  // Accept a notification
  const acceptNotification = async (shareId: string) => {
    setError(null);
    
    try {
      await acceptShare({ shareId });
      
      // Update the local state to reflect the change
      setReceivedNotifications(prev => 
        prev.map(notification => 
          notification.share_id === shareId 
            ? { ...notification, status: 'accepted' as const }
            : notification
        )
      );
    } catch (err) {
      console.error('Failed to accept notification:', err);
      setError(err instanceof Error ? err.message : 'Failed to accept notification');
      throw err;
    }
  };

  // Decline a notification
  const declineNotification = async (shareId: string) => {
    setError(null);
    
    try {
      await declineShare({ shareId });
      
      // Update the local state to reflect the change
      setReceivedNotifications(prev => 
        prev.map(notification => 
          notification.share_id === shareId 
            ? { ...notification, status: 'declined' as const }
            : notification
        )
      );
    } catch (err) {
      console.error('Failed to decline notification:', err);
      setError(err instanceof Error ? err.message : 'Failed to decline notification');
      throw err;
    }
  };

  const clearError = () => setError(null);

  // Auto-fetch notifications when user logs in
  useEffect(() => {
    if (isAuthenticated && userId) {
      refreshNotifications();
    } else {
      // Clear notifications when user logs out
      setReceivedNotifications([]);
      setSentNotifications([]);
      setError(null);
    }
  }, [isAuthenticated, userId, viewMode, selectedTeam?.id, teams]);

  // Set up periodic refresh (every 30 seconds)
  useEffect(() => {
    if (!isAuthenticated || !userId) return;

    const interval = setInterval(() => {
      refreshNotifications();
    }, 30000); // 30 seconds

    return () => clearInterval(interval);
  }, [isAuthenticated, userId, viewMode, selectedTeam?.id, teams]);

  const value: NotificationContextType = {
    receivedNotifications,
    sentNotifications,
    isLoading,
    error,
    pendingNotificationsCount,
    hasUnreadNotifications,
    refreshNotifications,
    sendNotification,
    acceptNotification,
    declineNotification,
    clearError,
  };

  return (
    <NotificationContext.Provider value={value}>
      {children}
    </NotificationContext.Provider>
  );
};

export const useNotifications = (): NotificationContextType => {
  const context = useContext(NotificationContext);
  if (context === undefined) {
    throw new Error('useNotifications must be used within a NotificationProvider');
  }
  return context;
};
