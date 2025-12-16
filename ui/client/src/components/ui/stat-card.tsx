import { Card, CardContent } from "@/components/ui/card";
import { Loader2 } from "lucide-react";
import { ReactNode } from "react";

interface StatCardProps {
  icon: ReactNode;
  title: ReactNode;
  value: string | number;
  subtext: string;
  isLoading?: boolean;
  iconColor?: string;
  iconBgColor?: string;
  error?: Error | null;
}

export function StatCard({
  icon,
  title,
  value,
  subtext,
  isLoading = false,
  iconColor,
  iconBgColor,
  error,
}: StatCardProps) {
  return (
    <Card className="rounded-xl border-0 shadow-none bg-transparent">
      <div className="relative p-4 border-b border-border">
        <div
          className="absolute top-2 right-4 w-8 h-8 rounded-lg flex items-center justify-center"
          style={{
            backgroundColor: iconBgColor || "rgba(var(--primary), 0.2)",
            color: iconColor || "var(--primary)",
          }}
        >
          {icon}
        </div>
        <h3 className="text-lg font-semibold text-white flex items-center">
          {title}
        </h3>
      </div>
      <CardContent className="p-4">
        {isLoading ? (
          <div className="flex items-center justify-center h-16">
            <Loader2
              className="w-6 h-6 animate-spin"
              style={{ color: iconColor }}
            />
          </div>
        ) : error ? (
          <div className="space-y-2">
            <p className="text-lg font-semibold text-red-400">Error</p>
            <p className="text-xs text-gray-400">Failed to load data</p>
          </div>
        ) : (
          <div className="space-y-2">
            <p className="text-3xl font-bold text-white">{value}</p>
            <p className="text-xs text-gray-400">{subtext}</p>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

