import React, { memo } from 'react';
import { motion } from "framer-motion";
import { AlertCircle } from "lucide-react";

interface StatusIndicatorProps {
  status: string;
}

export const StatusIndicator = memo(({ status }: StatusIndicatorProps) => {
  switch (status) {
    case 'processing':
      return (
        <motion.div
          animate={{ rotate: 360 }}
          transition={{ repeat: Infinity, duration: 1.5, ease: "linear" }}
          className="inline-block"
        >
          <AlertCircle className="h-3 w-3 text-[#FFB300]" />
        </motion.div>
      );
    case 'complete':
      return <div className="w-3 h-3 bg-[#00E676] rounded-full" />;
    case 'error':
      return <div className="w-3 h-3 bg-[#FF1744] rounded-full" />;
    default:
      return <div className="w-3 h-3 bg-gray-400 rounded-full" />;
  }
});