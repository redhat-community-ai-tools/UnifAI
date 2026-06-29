import React, { memo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { ShieldAlert } from 'lucide-react';

interface ApprovalBadgeProps {
  pendingCount: number;
  onClick?: () => void;
}

export const ApprovalBadge = memo(({ pendingCount, onClick }: ApprovalBadgeProps) => {
  return (
    <AnimatePresence>
      {pendingCount > 0 && (
        <motion.button
          initial={{ opacity: 0, scale: 0.8, y: 10 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.8, y: 10 }}
          transition={{ duration: 0.2 }}
          onClick={onClick}
          className="
            flex items-center gap-2 px-3 py-2 rounded-lg
            bg-gray-800/80 border border-gray-600/60
            text-gray-300 text-xs font-medium
            shadow-lg shadow-gray-900/20
            hover:bg-gray-700/80 transition-colors
            cursor-pointer
          "
          title="Scroll to pending approval"
        >
          <motion.div
            animate={{ scale: [1, 1.2, 1] }}
            transition={{ repeat: Infinity, duration: 1.5, ease: 'easeInOut' }}
          >
            <ShieldAlert className="h-4 w-4" />
          </motion.div>
          <span>
            {pendingCount} Pending Approval{pendingCount !== 1 ? 's' : ''}
          </span>
        </motion.button>
      )}
    </AnimatePresence>
  );
});

ApprovalBadge.displayName = 'ApprovalBadge';
