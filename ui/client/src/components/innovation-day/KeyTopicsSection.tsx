import { motion } from "framer-motion";
import { BookOpen, Code2, FlaskConical, GitBranch, Layers, Sparkles } from "lucide-react";

interface Topic {
  icon: React.ReactNode;
  title: string;
  subtitle: string;
  description: string;
  tags: string[];
  gradient: string;
}

const topics: Topic[] = [
  {
    icon: <Layers className="w-5 h-5" />,
    title: "Is Orchestration the Future?",
    subtitle: "Multi-Agent Systems",
    description:
      "Exploring A2A (Agent-to-Agent) communications for multi-agent architectures, peer-to-peer collaboration patterns, and overcoming current limitations in multi-agent software development lifecycles.",
    tags: ["A2A Protocol", "Multi-Agent", "Peer-to-Peer", "SDLC"],
    gradient: "from-violet-500/20 to-violet-900/10 border-violet-500/20",
  },
  {
    icon: <GitBranch className="w-5 h-5" />,
    title: "Fullsend",
    subtitle: "Autonomous Agentic SDLC",
    description:
      "A living design corpus and shipping platform (MVP) enabling fully autonomous agentic software development life cycles on Git forges. Redefining how software is built and shipped at scale.",
    tags: ["Git Forges", "Autonomous", "MVP", "SDLC Platform"],
    gradient: "from-cyan-500/20 to-cyan-900/10 border-cyan-500/20",
  },
  {
    icon: <FlaskConical className="w-5 h-5" />,
    title: "Eval-Hub",
    subtitle: "AI Model Evaluation Service",
    description:
      "A lightweight REST API service for orchestrating AI model evaluations at scale. Provides centralized evaluation management and result tracking across different models and datasets.",
    tags: ["REST API", "Evaluation", "Orchestration", "Model Assessment"],
    gradient: "from-purple-500/20 to-purple-900/10 border-purple-500/20",
  },
  {
    icon: <Code2 className="w-5 h-5" />,
    title: "agent-eval-harness",
    subtitle: "Agent Evaluation Framework",
    description:
      "A comprehensive evaluation framework for assessing AI agent skills against curated test datasets. Supports CLI plugins like /eval-setup-lint, /eval-setup-review, and /eval-setup-security.",
    tags: ["Harness", "CLI Plugins", "Test Datasets", "Code Agents"],
    gradient: "from-blue-500/20 to-blue-900/10 border-blue-500/20",
  },
  {
    icon: <BookOpen className="w-5 h-5" />,
    title: "sdg_hub",
    subtitle: "Synthetic Data Generation",
    description:
      "A Python framework for building and composing synthetic data generation (SDG) pipelines. Enables creation of high-quality training data at scale for AI model fine-tuning and evaluation.",
    tags: ["Python", "SDG Pipelines", "Fine-tuning", "Data Generation"],
    gradient: "from-green-500/20 to-green-900/10 border-green-500/20",
  },
  {
    icon: <Sparkles className="w-5 h-5" />,
    title: "Compass Project",
    subtitle: "Quality & Consistency Tooling",
    description:
      "Tooling and frameworks designed to ensure AI agent code setups are working correctly, safe, and internally consistent — bridging quality estimation with actionable developer insights.",
    tags: ["Quality Estimation", "Safety", "Consistency", "Developer Tools"],
    gradient: "from-primary/20 to-red-900/10 border-primary/20",
  },
];

export default function KeyTopicsSection() {
  return (
    <section className="mb-10">
      <div className="flex items-center gap-3 mb-6">
        <BookOpen className="w-5 h-5 text-primary" />
        <h2 className="text-xl font-semibold text-white">Key Topics & Projects</h2>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
        {topics.map((topic, index) => (
          <motion.div
            key={topic.title}
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3, delay: index * 0.07 }}
            className={`bg-gradient-to-br ${topic.gradient} border rounded-xl p-5 bg-background-card/60 hover:scale-[1.01] transition-transform`}
          >
            <div className="flex items-start gap-3 mb-3">
              <div className="p-2 rounded-lg bg-background-card/80 text-primary flex-shrink-0">
                {topic.icon}
              </div>
              <div>
                <h3 className="text-white font-semibold text-sm">{topic.title}</h3>
                <p className="text-gray-500 text-xs">{topic.subtitle}</p>
              </div>
            </div>

            <p className="text-gray-400 text-sm leading-relaxed mb-4">{topic.description}</p>

            <div className="flex flex-wrap gap-1.5">
              {topic.tags.map((tag) => (
                <span
                  key={tag}
                  className="text-xs px-2 py-0.5 rounded-full bg-background-card/80 border border-gray-700 text-gray-400"
                >
                  {tag}
                </span>
              ))}
            </div>
          </motion.div>
        ))}
      </div>
    </section>
  );
}
