import { motion } from "framer-motion";
import { CheckCircle, TrendingUp } from "lucide-react";

const updates = [
  {
    title: "From Presentations to Workshops",
    description:
      "Based on community survey feedback, Innovation Days are evolving to include more hands-on workshops and open office hours, giving attendees direct access to project authors.",
  },
  {
    title: "Increasing Visibility",
    description:
      "Broader communication and visibility across the IL site through the AI IL Ambassador Program — sharing success stories and growing the community organically.",
  },
  {
    title: "MCP Best Practices",
    description:
      "Adopting and standardising Model Context Protocol (MCP) best practices across teams to streamline AI-assisted coding workflows and tool integrations.",
  },
  {
    title: "AI Assisted Coding",
    description:
      "Accelerating AI-assisted coding adoption across engineering teams, with real examples, tips, and lessons learned from practitioners using Claude Code and similar tools daily.",
  },
  {
    title: "UnifAI – ADLC Adaptation",
    description:
      "UnifAI is adapting to Agentic Development Life Cycle flows, focusing on automation and quick setup for individuals and teams working with agentic pipelines.",
  },
];

export default function CommunityUpdatesSection() {
  return (
    <section className="mb-10">
      <div className="flex items-center gap-3 mb-6">
        <TrendingUp className="w-5 h-5 text-primary" />
        <h2 className="text-xl font-semibold text-white">Community Updates</h2>
      </div>

      <div className="bg-background-card border border-gray-800 rounded-xl p-6">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {updates.map((update, index) => (
            <motion.div
              key={update.title}
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.3, delay: index * 0.08 }}
              className="flex gap-3"
            >
              <CheckCircle className="w-5 h-5 text-green-400 flex-shrink-0 mt-0.5" />
              <div>
                <p className="text-white font-medium text-sm mb-1">{update.title}</p>
                <p className="text-gray-400 text-sm leading-relaxed">{update.description}</p>
              </div>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
