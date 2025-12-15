import { motion } from "framer-motion";
import { Sparkles } from "lucide-react";

export default function PageHeader() {
  return (
    <motion.div 
      initial={{ opacity: 0, y: -10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4 }}
      className="mb-8"
    >
      <div className="flex items-center gap-3 mb-3">
        <div className="p-2 rounded-lg bg-gradient-to-r from-primary/20 to-secondary/20">
          <Sparkles className="w-6 h-6 text-primary" />
        </div>
        <h1 className="text-3xl font-bold text-white">
          Get to Know UnifAI
        </h1>
      </div>
      <p className="text-gray-400 text-lg max-w-5xl">
        Explore the core concepts, architecture, and resources behind your agentic AI creation platform.
      </p>
    </motion.div>
  );
}