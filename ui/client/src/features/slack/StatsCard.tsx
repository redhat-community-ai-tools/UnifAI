import React from "react";
import { Card, CardContent } from "@/components/ui/card";
import { motion } from "framer-motion";

export interface StatsCardProps {
  icon: React.ElementType;
  label: string;
  value: number | string;
  delta?: number;
  status?: string;
  formatValue?: (v: number | string) => string;
  color?: keyof typeof COLOR_MAP;
  delay?: number;
}

// Predefined color mappings so Tailwind can generate all classes
const COLOR_MAP = {
  emerald: { bg: "bg-emerald-500/20", text: "text-emerald-400" },
  blue:    { bg: "bg-blue-500/20",    text: "text-blue-400"    },
  amber:   { bg: "bg-amber-400/20",   text: "text-amber-300"   },
  purple:  { bg: "bg-purple-500/20",  text: "text-purple-400"  },
} as const;

export const StatsCard: React.FC<StatsCardProps> = ({
  icon: Icon,
  label,
  value,
  delta,
  status,
  formatValue,
  color = "blue",
  delay = 0,
}) => {
  const formatted = formatValue ? formatValue(value) : value;
  const hasDelta = typeof delta === "number";
  const { bg, text } = COLOR_MAP[color];

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay }}
    >
      <Card className="gradient-border p-6">
        <CardContent className="p-0">
          <div className="flex items-center justify-between mb-4">
            <div className={`w-12 h-12 ${bg} rounded-lg flex items-center justify-center`}>
              <Icon className={`${text} text-xl`} />
            </div>
            {hasDelta && (
              <span className={`text-xs ${text} ${bg} px-2 py-1 rounded-full`}>
                {delta! >= 0 ? `+${delta}%` : `${delta}%`}
              </span>
            )}
          </div>

          <h3 className="text-2xl font-bold text-foreground mb-1">
            {formatted}
          </h3>

          <p className="text-sm text-muted-foreground flex items-center">
            {status && <span className="mr-1">{status}</span>}
            {label}
          </p>
        </CardContent>
      </Card>
    </motion.div>
  );
};


