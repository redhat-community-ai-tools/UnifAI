import { ReactNode } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { motion } from "framer-motion";

interface StatusItemProps {
  label: string;
  value: string;
  color: string;
}

interface StatusCardProps {
  title: string;
  value: string | number;
  icon: ReactNode;
  iconBgColor: string;
  statusItems?: StatusItemProps[];
  progressItems?: {
    label: string;
    value: string;
    percentage: number;
    color: string;
  }[];
}

export default function StatusCard({ 
  title, 
  value, 
  icon, 
  iconBgColor, 
  statusItems, 
  progressItems 
}: StatusCardProps) {
  return (
    <Card className="bg-background-card shadow-card hover:shadow-card-hover transition-all border-0">
      <CardContent className="p-5">
        <div className="flex justify-between items-start mb-4">
          <div>
            <span className="text-gray-400 text-sm">{title}</span>
            <h3 className="font-heading font-bold text-2xl mt-1">{value}</h3>
          </div>
          <div className={`p-2 rounded-md bg-opacity-20 ${iconBgColor} text-${iconBgColor.split('-')[0]}`}>
            {icon}
          </div>
        </div>
        
        <div className="space-y-2">
          {statusItems && statusItems.map((item, index) => (
            <div key={index} className="flex items-center justify-between">
              <span className="text-xs text-gray-400">{item.label}</span>
              <motion.span 
                initial={{ opacity: 0, x: 10 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: index * 0.1 }}
                className="text-xs font-medium flex items-center"
              >
                <span className={`w-2 h-2 rounded-full bg-${item.color} mr-1`}></span>
                {item.value}
              </motion.span>
            </div>
          ))}
          
          {progressItems && progressItems.map((item, index) => (
            <div key={index}>
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs text-gray-400">{item.label}</span>
                <span className="text-xs font-medium">{item.value}</span>
              </div>
              <div className="h-1.5 w-full bg-background-dark rounded-full overflow-hidden">
                <motion.div 
                  initial={{ width: 0 }}
                  animate={{ width: `${item.percentage}%` }}
                  transition={{ duration: 1, delay: index * 0.2 }}
                  className={`h-full ${item.color} rounded-full`}
                />
              </div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
