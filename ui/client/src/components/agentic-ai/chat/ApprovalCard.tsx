import React, { memo, useState, useCallback } from 'react';
import { motion } from 'framer-motion';
import {
  ShieldAlert, ShieldCheck, ShieldX, ShieldQuestion,
  Check, X, MessageSquare, Pencil, Loader2, Zap,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import type { ApprovalEntry, ApprovalDecision, ApprovalStatus, AutoRuleAction } from './types';

// ─── Props ──────────────────────────────────────────────────────────────────

interface ApprovalCardProps {
  approval: ApprovalEntry;
  sessionId: string;
  onDecision: (
    requestId: string,
    decision: ApprovalDecision,
    feedback?: string,
    modifiedArgs?: Record<string, any>,
  ) => Promise<void>;
  onAutoRule?: (
    requestId: string,
    nodeUid: string | null,
    toolName: string | null,
    action: AutoRuleAction,
  ) => Promise<void>;
}

// ─── Status rendering helpers ───────────────────────────────────────────────

const STATUS_CONFIG: Record<ApprovalStatus, {
  icon: React.ElementType;
  iconClass: string;
  borderClass: string;
  bgClass: string;
  label: string;
}> = {
  pending: {
    icon: ShieldAlert,
    iconClass: 'text-amber-400',
    borderClass: 'border-amber-700/60',
    bgClass: 'bg-amber-950/30',
    label: 'Approval Required',
  },
  approved: {
    icon: ShieldCheck,
    iconClass: 'text-green-400',
    borderClass: 'border-green-800/40',
    bgClass: 'bg-green-950/30',
    label: 'Approved',
  },
  rejected: {
    icon: ShieldX,
    iconClass: 'text-red-400',
    borderClass: 'border-red-800/40',
    bgClass: 'bg-red-950/30',
    label: 'Rejected',
  },
  modified: {
    icon: Pencil,
    iconClass: 'text-orange-400',
    borderClass: 'border-orange-800/40',
    bgClass: 'bg-orange-950/30',
    label: 'Modified & Executed',
  },
  redirected: {
    icon: MessageSquare,
    iconClass: 'text-blue-400',
    borderClass: 'border-blue-800/40',
    bgClass: 'bg-blue-950/30',
    label: 'Redirected',
  },
  timed_out: {
    icon: ShieldQuestion,
    iconClass: 'text-gray-400',
    borderClass: 'border-gray-700/40',
    bgClass: 'bg-gray-900/30',
    label: 'Timed Out',
  },
};

// ─── Resolved (post-decision) card ──────────────────────────────────────────

const ResolvedBadge = memo(({ approval }: { approval: ApprovalEntry }) => {
  const cfg = STATUS_CONFIG[approval.status] || STATUS_CONFIG.pending;
  const Icon = cfg.icon;

  return (
    <div className={`flex items-center gap-2 p-2.5 rounded-md border ${cfg.borderClass} ${cfg.bgClass}`}>
      <Icon className={`h-4 w-4 flex-shrink-0 ${cfg.iconClass}`} />
      <div className="flex-1 min-w-0">
        <span className="text-xs font-medium text-gray-300">
          {cfg.label}
        </span>
        <span className="text-xs text-gray-400 mx-1.5">·</span>
        <span className="text-xs text-gray-400 font-mono">{approval.toolName}</span>
      </div>
      {approval.feedback && (
        <span className="text-xs text-gray-400 truncate max-w-[200px]" title={approval.feedback}>
          {approval.feedback}
        </span>
      )}
    </div>
  );
});
ResolvedBadge.displayName = 'ResolvedBadge';

// ─── Main component ─────────────────────────────────────────────────────────

export const ApprovalCard = memo(({ approval, sessionId, onDecision, onAutoRule }: ApprovalCardProps) => {
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [showFeedback, setShowFeedback] = useState<'reject' | 'redirect' | null>(null);
  const [feedbackText, setFeedbackText] = useState('');

  const handleDecision = useCallback(
    async (decision: ApprovalDecision, feedback?: string) => {
      setIsSubmitting(true);
      try {
        await onDecision(approval.requestId, decision, feedback);
      } finally {
        setIsSubmitting(false);
        setShowFeedback(null);
        setFeedbackText('');
      }
    },
    [approval.requestId, onDecision],
  );

  const handleFeedbackSubmit = useCallback(() => {
    if (!showFeedback) return;
    handleDecision(showFeedback, feedbackText || undefined);
  }, [showFeedback, feedbackText, handleDecision]);

  const handleAutoRuleClick = useCallback(
    async (nodeUid: string | null, toolName: string | null, action: AutoRuleAction) => {
      if (!onAutoRule) return;
      setIsSubmitting(true);
      try {
        await onAutoRule(approval.requestId, nodeUid, toolName, action);
      } finally {
        setIsSubmitting(false);
      }
    },
    [approval.requestId, onAutoRule],
  );

  if (approval.status !== 'pending') {
    return <ResolvedBadge approval={approval} />;
  }

  const cfg = STATUS_CONFIG.pending;
  const Icon = cfg.icon;

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.97 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.2 }}
      className={`rounded-md border ${cfg.borderClass} ${cfg.bgClass} overflow-hidden`}
    >
      {/* Header */}
      <div className="flex items-start gap-3 p-3">
        <div className="flex-shrink-0 mt-0.5">
          <motion.div
            animate={{ scale: [1, 1.15, 1] }}
            transition={{ repeat: Infinity, duration: 2, ease: 'easeInOut' }}
          >
            <Icon className={`h-5 w-5 ${cfg.iconClass}`} />
          </motion.div>
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-sm font-medium text-amber-300">
              {cfg.label}
            </span>
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-900/40 text-amber-400 font-mono uppercase">
              {approval.accessMode}
            </span>
          </div>
          <div className="text-xs text-gray-400 mb-2">
            <span className="text-gray-300 font-medium">{approval.originNodeName}</span>
            {' wants to execute '}
            <span className="text-amber-300 font-mono">{approval.toolName}</span>
          </div>

          {/* Args table */}
          {Object.keys(approval.toolArgs).length > 0 && (
            <div className="bg-gray-800/50 rounded p-2 mb-3">
              <table className="w-full text-xs">
                <tbody>
                  {Object.entries(approval.toolArgs).map(([key, value]) => (
                    <tr key={key} className="border-b border-gray-700/50 last:border-b-0">
                      <td className="text-gray-400 pr-3 py-1 font-mono align-top">{key}</td>
                      <td className="text-gray-300 py-1 font-mono break-all">
                        {typeof value === 'object' ? JSON.stringify(value) : String(value)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* Feedback input (shown for reject/redirect) */}
          {showFeedback && (
            <div className="mb-3 space-y-2">
              <Textarea
                value={feedbackText}
                onChange={(e) => setFeedbackText(e.target.value)}
                placeholder={
                  showFeedback === 'reject'
                    ? 'Reason for rejection...'
                    : 'New instructions for the agent...'
                }
                className="bg-gray-800/70 border-gray-600 text-xs min-h-[60px] resize-none"
                autoFocus
              />
              <div className="flex gap-2">
                <Button
                  size="sm"
                  variant="outline"
                  className="h-7 text-xs border-gray-600"
                  onClick={() => { setShowFeedback(null); setFeedbackText(''); }}
                  disabled={isSubmitting}
                >
                  Cancel
                </Button>
                <Button
                  size="sm"
                  className="h-7 text-xs"
                  onClick={handleFeedbackSubmit}
                  disabled={isSubmitting}
                >
                  {isSubmitting ? <Loader2 className="h-3 w-3 animate-spin mr-1" /> : null}
                  {showFeedback === 'reject' ? 'Reject' : 'Redirect'}
                </Button>
              </div>
            </div>
          )}

          {/* Action buttons */}
          {!showFeedback && (
            <div className="flex items-center gap-2">
              <Button
                size="sm"
                className="h-7 text-xs bg-green-700 hover:bg-green-600 text-white"
                onClick={() => handleDecision('approve')}
                disabled={isSubmitting}
              >
                {isSubmitting ? (
                  <Loader2 className="h-3 w-3 animate-spin mr-1" />
                ) : (
                  <Check className="h-3 w-3 mr-1" />
                )}
                Approve
              </Button>
              <Button
                size="sm"
                variant="outline"
                className="h-7 text-xs border-red-800/50 text-red-400 hover:bg-red-950/40 hover:text-red-300"
                onClick={() => setShowFeedback('reject')}
                disabled={isSubmitting}
              >
                <X className="h-3 w-3 mr-1" />
                Reject
              </Button>
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button
                    size="sm"
                    variant="ghost"
                    className="h-7 text-xs text-gray-400 hover:text-gray-200"
                    disabled={isSubmitting}
                  >
                    More...
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="start" className="bg-popover border-gray-700 min-w-[250px]">
                  <DropdownMenuItem onClick={() => setShowFeedback('redirect')}>
                    <MessageSquare className="h-3.5 w-3.5 mr-2" />
                    Redirect (new instructions)
                  </DropdownMenuItem>

                  {onAutoRule && (
                    <>
                      <DropdownMenuSeparator />

                      <DropdownMenuItem
                        onClick={() => handleAutoRuleClick(approval.originNodeUid, approval.toolName, 'auto_approve')}
                      >
                        <Zap className="h-3.5 w-3.5 mr-2 text-green-400" />
                        <span>Always approve <span className="font-mono text-green-300">{approval.toolName}</span> from <span className="text-gray-300">{approval.originNodeName}</span></span>
                      </DropdownMenuItem>
                      <DropdownMenuItem
                        onClick={() => handleAutoRuleClick(null, approval.toolName, 'auto_approve')}
                      >
                        <Zap className="h-3.5 w-3.5 mr-2 text-green-400" />
                        <span>Always approve <span className="font-mono text-green-300">{approval.toolName}</span> from any agent</span>
                      </DropdownMenuItem>
                      <DropdownMenuItem
                        onClick={() => handleAutoRuleClick(approval.originNodeUid, null, 'auto_approve')}
                      >
                        <Zap className="h-3.5 w-3.5 mr-2 text-green-400" />
                        <span>Always approve all tools from <span className="text-gray-300">{approval.originNodeName}</span></span>
                      </DropdownMenuItem>

                      <DropdownMenuSeparator />

                      <DropdownMenuItem
                        onClick={() => handleAutoRuleClick(approval.originNodeUid, approval.toolName, 'auto_reject')}
                      >
                        <X className="h-3.5 w-3.5 mr-2 text-red-400" />
                        <span>Always reject <span className="font-mono text-red-300">{approval.toolName}</span> from <span className="text-gray-300">{approval.originNodeName}</span></span>
                      </DropdownMenuItem>
                      <DropdownMenuItem
                        onClick={() => handleAutoRuleClick(null, approval.toolName, 'auto_reject')}
                      >
                        <X className="h-3.5 w-3.5 mr-2 text-red-400" />
                        <span>Always reject <span className="font-mono text-red-300">{approval.toolName}</span> from any agent</span>
                      </DropdownMenuItem>
                    </>
                  )}
                </DropdownMenuContent>
              </DropdownMenu>
            </div>
          )}
        </div>
      </div>
    </motion.div>
  );
});

ApprovalCard.displayName = 'ApprovalCard';
