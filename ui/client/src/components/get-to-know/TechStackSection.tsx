import { motion } from "framer-motion";
import TechStackItem from "./TechStackItem";
import { techStackItems, TechStackItem as TechStackItemType } from "@/config/platformResources";

interface CategoryConfig {
  key: "backend" | "frontend" | "agentic";
  title: string;
  gradient: string;
}

const categories: CategoryConfig[] = [
  { key: "backend", title: "Backend", gradient: "from-green-500 to-emerald-600" },
  { key: "frontend", title: "Frontend", gradient: "from-cyan-500 to-blue-600" },
  { key: "agentic", title: "Agentic & LLM Layer", gradient: "from-purple-500 to-pink-600" }
];

export default function TechStackSection() {
  const getItemsByCategory = (category: string): TechStackItemType[] => {
    return techStackItems.filter(item => item.category === category);
  };

  return (
    <section className="mb-10">
      <h2 className="text-xl font-semibold text-white mb-6">
        Technology Stack
      </h2>
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {categories.map((category, categoryIndex) => (
          <motion.div
            key={category.key}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3, delay: categoryIndex * 0.1 }}
            className="bg-background-card border border-gray-800 rounded-xl p-5"
          >
            <div className="flex items-center gap-2 mb-4">
              <div className={`w-2 h-2 rounded-full bg-gradient-to-r ${category.gradient}`} />
              <h3 className="text-lg font-medium text-white">{category.title}</h3>
            </div>
            <div className="space-y-2">
              {getItemsByCategory(category.key).map((item, index) => (
                <TechStackItem
                  key={item.name}
                  name={item.name}
                  icon={item.icon}
                  index={index}
                />
              ))}
            </div>
          </motion.div>
        ))}
      </div>
    </section>
  );
}
