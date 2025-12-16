import { motion } from "framer-motion";
import { Card, CardContent } from "@/components/ui/card";
import { FaGithub, FaYoutube, FaFileAlt } from "react-icons/fa";
import { SiGoogleslides, SiGoogledocs } from "react-icons/si";
import { ExternalLink } from "lucide-react";

interface ResourceLinkCardProps {
  icon: string;
  title: string;
  description: string;
  url: string;
  index: number;
}

const iconMap: Record<string, React.ReactNode> = {
  github: <FaGithub className="w-8 h-8" />,
  docs: <SiGoogledocs className="w-8 h-8" />,
  slides: <SiGoogleslides className="w-8 h-8" />,
  videos: <FaYoutube className="w-8 h-8" />,
  default: <FaFileAlt className="w-8 h-8" />
};

const iconColorMap: Record<string, string> = {
  github: "text-white",
  docs: "text-blue-400",
  slides: "text-yellow-400",
  videos: "text-red-400",
  default: "text-gray-400"
};

export default function ResourceLinkCard({ 
  icon, 
  title, 
  description, 
  url, 
  index 
}: ResourceLinkCardProps) {
  const IconComponent = iconMap[icon] || iconMap.default;
  const iconColor = iconColorMap[icon] || iconColorMap.default;

  return (
    <motion.a
      href={url}
      target="_blank"
      rel="noopener noreferrer"
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, delay: index * 0.1 }}
      className="block group"
    >
      <Card className="h-full bg-background-card border-gray-800 hover:border-primary transition-all duration-300 hover:shadow-lg hover:shadow-primary/10 cursor-pointer">
        <CardContent className="p-6">
          <div className="flex items-start justify-between mb-4">
            <div className={`p-3 rounded-lg bg-background-surface ${iconColor}`}>
              {IconComponent}
            </div>
            <ExternalLink className="w-4 h-4 text-gray-500 group-hover:text-primary transition-colors" />
          </div>
          <h3 className="text-lg font-semibold text-white mb-2 group-hover:text-primary transition-colors">
            {title}
          </h3>
          <p className="text-sm text-gray-400 leading-relaxed">
            {description}
          </p>
        </CardContent>
      </Card>
    </motion.a>
  );
}