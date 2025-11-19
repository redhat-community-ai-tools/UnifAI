import { CheckCircle2, Circle, Clock, AlertCircle } from 'lucide-react';

// Status colors and icons
export const getStatusConfig = (status: string) => {
  switch (status) {
    case 'done':
      return {
        icon: CheckCircle2,
        color: 'text-green-400',
        bgColor: 'bg-green-400/10',
        borderColor: 'border-green-400/30'
      };
    case 'in_progress':
      return {
        icon: Clock,
        color: 'text-blue-400',
        bgColor: 'bg-blue-400/10',
        borderColor: 'border-blue-400/30'
      };
    case 'failed':
      return {
        icon: AlertCircle,
        color: 'text-red-400',
        bgColor: 'bg-red-400/10',
        borderColor: 'border-red-400/30'
      };
    default: // pending
      return {
        icon: Circle,
        color: 'text-gray-400',
        bgColor: 'bg-gray-400/10',
        borderColor: 'border-gray-400/30'
      };
  }
};

// Format timestamp for display
export const formatTimestamp = (timestamp: string) => {
  return new Date(timestamp).toLocaleTimeString([], { 
    hour: '2-digit', 
    minute: '2-digit',
    second: '2-digit'
  });
};
