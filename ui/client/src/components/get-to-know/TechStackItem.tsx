import { motion } from "framer-motion";
import { 
  SiPython, 
  SiFlask, 
  SiCelery, 
  SiRabbitmq, 
  SiMongodb, 
  SiReact, 
  SiTypescript, 
  SiUmami
} from "react-icons/si";
import { FaDatabase, FaLink, FaRobot, FaCubes } from "react-icons/fa";

interface TechStackItemProps {
  name: string;
  icon: string;
  index: number;
}

const techIconMap: Record<string, React.ReactNode> = {
  python: <SiPython className="w-6 h-6" />,
  flask: <SiFlask className="w-6 h-6" />,
  celery: <SiCelery className="w-6 h-6" />,
  rabbitmq: <SiRabbitmq className="w-6 h-6" />,
  qdrant: <FaDatabase className="w-6 h-6" />,
  mongodb: <SiMongodb className="w-6 h-6" />,
  react: <SiReact className="w-6 h-6" />,
  typescript: <SiTypescript className="w-6 h-6" />,
  langgraph: <FaCubes className="w-6 h-6" />,
  langchain: <FaLink className="w-6 h-6" />,
  a2a: <FaRobot className="w-6 h-6" />,
  umami: <SiUmami className="w-6 h-6" />,
  default: <FaCubes className="w-6 h-6" />
};

const techColorMap: Record<string, string> = {
  python: "text-yellow-400 bg-yellow-400/10",
  flask: "text-gray-300 bg-gray-300/10",
  celery: "text-green-400 bg-green-400/10",
  rabbitmq: "text-orange-400 bg-orange-400/10",
  qdrant: "text-purple-400 bg-purple-400/10",
  mongodb: "text-green-500 bg-green-500/10",
  react: "text-cyan-400 bg-cyan-400/10",
  typescript: "text-blue-400 bg-blue-400/10",
  langgraph: "text-indigo-400 bg-indigo-400/10",
  langchain: "text-teal-400 bg-teal-400/10",
  a2a: "text-pink-400 bg-pink-400/10",
  umami: "text-black-400 bg-black-400/10",
  default: "text-gray-400 bg-gray-400/10"
};

export default function TechStackItem({ name, icon, index }: TechStackItemProps) {
  const IconComponent = techIconMap[icon] || techIconMap.default;
  const colorClasses = techColorMap[icon] || techColorMap.default;
  const [textColor, bgColor] = colorClasses.split(" ");

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.9 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.2, delay: index * 0.05 }}
      className={`flex items-center gap-3 px-4 py-3 rounded-lg border border-gray-800 bg-background-card hover:border-gray-700 transition-colors`}
    >
      <div className={`p-2 rounded-md ${bgColor}`}>
        <span className={textColor}>{IconComponent}</span>
      </div>
      <span className="text-sm font-medium text-white">{name}</span>
    </motion.div>
  );
}