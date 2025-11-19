import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { FaDownload } from "react-icons/fa";
import { motion } from "framer-motion";

interface DataSourceStat {
  source: string;
  color: string;
  count: string;
  percentage: number;
}

interface DataSourceStatsProps {
  totalVectors: string;
  stats: DataSourceStat[];
}

export default function DataSourceStats({ totalVectors, stats }: DataSourceStatsProps) {
  // Calculate stroke-dashoffset based on percentage
  const calculateOffset = (percentage: number) => {
    const circumference = 2 * Math.PI * 40;
    return circumference - (percentage / 100) * circumference;
  };

  // Calculate rotation for start position of each segment
  const calculateRotation = (index: number) => {
    let rotation = -90; // Start from the top
    
    for (let i = 0; i < index; i++) {
      rotation += (stats[i].percentage / 100) * 360;
    }
    
    return rotation;
  };

  return (
    <Card className="bg-background-card shadow-card border-0">
      <CardContent className="p-5">
        <div className="relative h-48 mb-4">
          <svg className="w-full h-full" viewBox="0 0 100 100">
            {/* Background circle */}
            <circle cx="50" cy="50" r="40" fill="none" stroke="#333" strokeWidth="10" />
            
            {/* Data source segments */}
            {stats.map((stat, index) => (
              <motion.circle
                key={index}
                cx="50" 
                cy="50" 
                r="40" 
                fill="none" 
                stroke={`var(--${stat.color})`} 
                strokeWidth="10" 
                strokeDasharray={2 * Math.PI * 40}
                initial={{ strokeDashoffset: 2 * Math.PI * 40 }}
                animate={{ strokeDashoffset: calculateOffset(stat.percentage) }}
                transition={{ duration: 1.5, delay: index * 0.2 }}
                transform={`rotate(${calculateRotation(index)} 50 50)`}
              />
            ))}
          </svg>
          
          <div className="absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 text-center">
            <motion.p 
              initial={{ opacity: 0, scale: 0.8 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ delay: 0.5 }}
              className="font-heading font-bold text-2xl"
            >
              {totalVectors}
            </motion.p>
            <p className="text-xs text-gray-400">Total Vectors</p>
          </div>
        </div>
        
        <div className="space-y-3">
          {stats.map((stat, index) => (
            <motion.div 
              key={index}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.8 + index * 0.1 }}
              className="flex items-center justify-between"
            >
              <div className="flex items-center">
                <span className={`w-3 h-3 rounded-full bg-${stat.color} mr-2`}></span>
                <span className="text-sm">{stat.source}</span>
              </div>
              <div className="text-right">
                <span className="text-sm font-medium">{stat.count}</span>
                <span className="text-xs text-gray-400 ml-1">{stat.percentage}%</span>
              </div>
            </motion.div>
          ))}
        </div>
        
        <Separator className="my-4 bg-gray-800" />
        
        <Button variant="outline" className="w-full bg-background-dark hover:bg-opacity-80 text-gray-400 hover:text-white">
          <FaDownload className="mr-2" />
          <span>Export Analytics Report</span>
        </Button>
      </CardContent>
    </Card>
  );
}
