import { motion } from "framer-motion";

const stats = [
  { value: "5", label: "Talks & Sessions" },
  { value: "12", label: "Speakers" },
  { value: "3h 30m", label: "Duration" },
  { value: "6", label: "Key Projects" },
];

export default function EventStatsBar() {
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay: 0.1 }}
      className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-10"
    >
      {stats.map((stat) => (
        <div
          key={stat.label}
          className="bg-background-card border border-gray-800 rounded-xl p-4 text-center"
        >
          <p className="text-3xl font-bold text-primary mb-1">{stat.value}</p>
          <p className="text-gray-400 text-sm">{stat.label}</p>
        </div>
      ))}
    </motion.div>
  );
}
