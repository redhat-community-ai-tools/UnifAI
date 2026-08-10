import React from 'react';
import { Loader2, CheckCircle, XCircle, Lock } from 'lucide-react';
import { cn } from '@/lib/utils';
import { SignInStatus } from '@/hooks/use-builtin-sign-in';

interface StatusConfig {
  icon: React.ReactNode;
  color: string;
  label?: string;
  bold?: boolean;
}

const STATUS_CONFIG: Partial<Record<SignInStatus, StatusConfig>> = {
  checking: { icon: <Loader2 className="h-4 w-4 animate-spin" />, color: 'text-blue-400', label: 'Checking...' },
  authenticated: { icon: <CheckCircle className="h-4 w-4" />, color: 'text-green-400', label: 'Signed In', bold: true },
  error: { icon: <XCircle className="h-4 w-4" />, color: 'text-red-400' },
  not_configured: { icon: <XCircle className="h-4 w-4" />, color: 'text-orange-400' },
  challenge: { icon: <Lock className="h-4 w-4" />, color: 'text-yellow-400', label: 'Sign in required' },
};

interface SignInStatusIndicatorProps {
  status: SignInStatus;
  /** Fallback text for statuses without a fixed label (error, not_configured). */
  message: string;
}

/** Small icon + label for a built-in MCP card's current sign-in state. */
export const SignInStatusIndicator: React.FC<SignInStatusIndicatorProps> = ({ status, message }) => {
  const config = STATUS_CONFIG[status];
  if (!config) return null;

  return (
    <div className={cn('flex items-center gap-2', config.color)}>
      {config.icon}
      <span className={cn('text-xs', config.bold && 'font-medium')}>{config.label ?? message}</span>
    </div>
  );
};
