import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { FaCheckCircle, FaExclamationCircle, FaSync } from "react-icons/fa";
import { motion } from "framer-motion";

type ActivityType = 'success' | 'error' | 'info';

interface ActivityItem {
  id: string;
  type: ActivityType;
  title: string;
  time: string;
  description: string;
  project: {
    name: string;
    color: string;
  };
  source: string;
}

interface ActivityFeedProps {
  activities: ActivityItem[];
}

export default function ActivityFeed({ activities }: ActivityFeedProps) {
  const getIcon = (type: ActivityType) => {
    switch (type) {
      case 'success':
        return <FaCheckCircle className="text-sm" />;
      case 'error':
        return <FaExclamationCircle className="text-sm" />;
      case 'info':
        return <FaSync className="text-sm" />;
    }
  };

  const getIconBgColor = (type: ActivityType) => {
    switch (type) {
      case 'success':
        return 'bg-success bg-opacity-20 text-success';
      case 'error':
        return 'bg-error bg-opacity-20 text-error';
      case 'info':
        return 'bg-primary bg-opacity-20 text-primary';
    }
  };

  return (
    <Card className="bg-background-card shadow-card border-0">
      <CardContent className="p-5">
        <div className="space-y-4">
          {activities.map((activity, index) => (
            <motion.div
              key={activity.id}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: index * 0.1 }}
              className={`flex items-start space-x-3 ${
                index < activities.length - 1 ? 'pb-4 border-b border-gray-800' : ''
              }`}
            >
              <div className={`p-2 rounded-full ${getIconBgColor(activity.type)} mt-1`}>
                {getIcon(activity.type)}
              </div>
              <div className="flex-grow">
                <div className="flex justify-between">
                  <p className="text-sm font-medium">{activity.title}</p>
                  <span className="text-xs text-gray-400">{activity.time}</span>
                </div>
                <p className="text-xs text-gray-400 mt-1">{activity.description}</p>
                <div className="flex items-center space-x-2 mt-2">
                  <Badge variant="outline" className={`bg-${activity.project.color} bg-opacity-10 text-${activity.project.color} border-0 text-xs`}>
                    {activity.project.name}
                  </Badge>
                  <Badge variant="outline" className="bg-background-dark text-gray-400 border-0 text-xs">
                    {activity.source}
                  </Badge>
                </div>
              </div>
            </motion.div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
