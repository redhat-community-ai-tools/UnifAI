import React, { ReactElement, cloneElement } from 'react';
import { UmamiEvents, UmamiEventData } from '@/config/umamiEvents';
import { useAuth } from '@/contexts/AuthContext';

interface UmamiTrackProps {
  event: UmamiEvents | string;
  eventData?: UmamiEventData;
  children: ReactElement;
  includeUserData?: boolean; // Optional flag to control automatic user data inclusion
}

export const UmamiTrack: React.FC<UmamiTrackProps> = ({
  event,
  eventData,
  children,
  includeUserData = true, // Default to true for automatic inclusion
}) => {
  const { user } = useAuth();

  // Build the umami props object
  const umamiProps: Record<string, string> = {
    'data-umami-event': event,
  };

  // Automatically include user data if enabled
  const mergedEventData: UmamiEventData = { ...eventData };
  
  if (includeUserData && user) {
    // Only add userId if it's not already provided in eventData
    if (!mergedEventData.userId) {
      mergedEventData.userId = user.sub;
    }
  }

  // Add event data as additional data attributes
  if (mergedEventData && Object.keys(mergedEventData).length > 0) {
    Object.entries(mergedEventData).forEach(([key, value]) => {
      if (value !== undefined && value !== null) {
        // Convert camelCase to kebab-case for data attributes
        const kebabKey = key.replace(/([A-Z])/g, '-$1').toLowerCase();
        umamiProps[`data-umami-event-${kebabKey}`] = String(value);
      }
    });
  }

  // Clone the child element and add umami props
  return cloneElement(children, umamiProps);
};
