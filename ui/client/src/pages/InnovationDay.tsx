import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import Sidebar from "@/components/layout/Sidebar";
import Header from "@/components/layout/Header";
import StatusBar from "@/components/layout/StatusBar";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import GlassPanel from "@/components/ui/GlassPanel";
import { useTheme } from "@/contexts/ThemeContext";
import {
  FaCalendarAlt,
  FaClock,
  FaMapMarkerAlt,
  FaUsers,
  FaRocket,
  FaChevronDown,
  FaChevronUp,
  FaLightbulb,
  FaCode,
  FaCogs,
  FaCheckCircle,
  FaMicrophone,
  FaNetworkWired,
  FaChartLine,
  FaStar,
  FaGithub,
  FaFlask,
  FaCompass,
  FaBullseye,
  FaUserTie,
  FaCoffee,
  FaHandshake,
  FaGlobe,
  FaTrophy,
} from "react-icons/fa";
import { Brain, Zap, Shield, Target, Layers, GitBranch, BarChart3, Users2 } from "lucide-react";

/* ─────────────────────────────────────────────────────────────────────────────
   DATA
───────────────────────────────────────────────────────────────────────────── */

const EVENT_META = {
  title: "Red Hat Innovation Day Q2 2026",
  subtitle: "IL Site",
  date: "Tuesday, June 16, 2026",
  time: "09:30 – 13:15",
  location: "Red Hat IL Site",
  theme:
    "Agentic Orchestration · ADLC · Evaluation · From AI Ideation to Business Value",
};

interface AgendaItem {
  id: string;
  start: string;
  end: string;
  title: string;
  speakers: string[];
  type: "logistics" | "talk" | "workshop" | "update" | "community";
  description: string;
  topics: string[];
  icon: React.ReactNode;
}

const AGENDA: AgendaItem[] = [
  {
    id: "registration",
    start: "09:30",
    end: "09:45",
    title: "Registration / Arrival",
    speakers: [],
    type: "logistics",
    description: "Check-in and badge pick-up. Welcome to Innovation Day Q2 2026!",
    topics: ["Check-in", "Welcome packet"],
    icon: <FaUserTie />,
  },
  {
    id: "coffee",
    start: "09:45",
    end: "10:00",
    title: "Coffee and Ma'affee",
    speakers: [],
    type: "logistics",
    description:
      "Networking over coffee. Connect with peers, share ideas, and warm up for a day of agentic exploration.",
    topics: ["Networking", "Peer connections"],
    icon: <FaCoffee />,
  },
  {
    id: "intro",
    start: "10:00",
    end: "10:05",
    title: "Intro to Innovation Day",
    speakers: ["Hofni Gartner"],
    type: "talk",
    description:
      "A brief welcome and orientation to Innovation Day Q2 2026. Overview of the agenda, goals, and community context.",
    topics: ["Welcome", "Agenda overview", "Goals"],
    icon: <FaRocket />,
  },
  {
    id: "orchestration",
    start: "10:05",
    end: "11:00",
    title: "Is Orchestration the Future?",
    speakers: ["Vlad Luzin", "Roy Nissim"],
    type: "talk",
    description:
      "A deep-dive into Agent-to-Agent (A2A) communications, peer-to-peer collaboration patterns, and overcoming the most stubborn limitations of multi-agent SDLC pipelines. We'll explore real-world topologies, failure modes, and the path toward robust agentic orchestration at scale.",
    topics: [
      "Agent-to-Agent (A2A) communications",
      "Peer-to-peer collaboration",
      "Multi-agent SDLC limitations",
      "Orchestration topologies",
      "Failure mode analysis",
    ],
    icon: <FaNetworkWired />,
  },
  {
    id: "fullsend",
    start: "11:00",
    end: "12:00",
    title: "Introduction to Fullsend",
    speakers: ["Barak Korren"],
    type: "workshop",
    description:
      "Fullsend is a living design corpus and shipping platform (MVP) enabling autonomous agentic SDLC on Git forges. Learn how the system coordinates design, implementation, review, and merge cycles without human-in-the-loop bottlenecks—and what it means for the future of software engineering.",
    topics: [
      "Living design corpus",
      "Autonomous agentic SDLC",
      "Git forge integrations",
      "MVP architecture overview",
      "Shipping pipeline demo",
    ],
    icon: <FaCode />,
  },
  {
    id: "eval",
    start: "12:00",
    end: "12:35",
    title: "Skill/Agents Related Quality and Evaluation",
    speakers: [
      "Ella Shulman",
      "Benjamin Kapner",
      "Carmel Soceanu",
      "Guy Ziv",
      "Sharon Dashet",
    ],
    type: "workshop",
    description:
      "A collaborative session covering quality estimation techniques for agentic skills and workflows, a live tour of Eval-Hub, agent-eval-harness internals, and an introduction to the Compass project for tracking evaluation metrics across teams.",
    topics: [
      "Quality estimation for agents",
      "Eval-Hub platform tour",
      "agent-eval-harness internals",
      "Compass project overview",
      "Cross-team evaluation metrics",
    ],
    icon: <FaFlask />,
  },
  {
    id: "unifai",
    start: "12:35",
    end: "12:50",
    title: "Updates from UnifAI",
    speakers: ["Nir Rashti", "Odai Odeh"],
    type: "update",
    description:
      "Latest updates on adapting UnifAI to ADLC flows. Focus on automation improvements, quick-setup capabilities, and how UnifAI integrates across the agentic toolchain ecosystem.",
    topics: [
      "ADLC flow integration",
      "Automation improvements",
      "Quick-setup capabilities",
      "Toolchain ecosystem fit",
    ],
    icon: <FaCogs />,
  },
  {
    id: "ambassador",
    start: "12:50",
    end: "13:00",
    title: "AI IL Ambassador Program",
    speakers: ["Ilanit Stein"],
    type: "community",
    description:
      "Success stories from the AI IL Ambassador Program, community updates, and upcoming initiatives. Hear how ambassadors are spreading AI best practices across Red Hat Israel.",
    topics: [
      "Ambassador success stories",
      "Community updates",
      "Upcoming initiatives",
      "Best practices sharing",
    ],
    icon: <FaGlobe />,
  },
];

const PROJECTS = [
  {
    name: "Code Agent Harness Evaluation",
    category: "Evaluation",
    status: "Active",
    description:
      "Framework for systematically evaluating code-generation agents across task complexity, language diversity, and edge-case coverage.",
    tags: ["Evaluation", "Code Gen", "Harness"],
    icon: <FaFlask className="text-purple-400" />,
    maturity: 72,
  },
  {
    name: "agent-eval-harness",
    category: "Evaluation",
    status: "Active",
    description:
      "Open-source harness to benchmark and compare agent behaviours in structured, reproducible evaluation environments.",
    tags: ["Open Source", "Benchmarking", "Agent"],
    icon: <FaBullseye className="text-blue-400" />,
    maturity: 68,
  },
  {
    name: "eval-hub",
    category: "Platform",
    status: "Active",
    description:
      "Centralised hub for evaluation results, trend analysis, and cross-project quality dashboards for agentic systems.",
    tags: ["Dashboard", "Analytics", "Hub"],
    icon: <BarChart3 className="text-green-400 w-4 h-4" />,
    maturity: 55,
  },
  {
    name: "sdg_hub",
    category: "Data",
    status: "Active",
    description:
      "Synthetic Data Generation hub — powers training pipelines with high-quality, domain-specific agentic task datasets.",
    tags: ["SDG", "Training Data", "AI"],
    icon: <Layers className="text-yellow-400 w-4 h-4" />,
    maturity: 80,
  },
  {
    name: "Fullsend",
    category: "SDLC",
    status: "MVP",
    description:
      "Living design corpus + shipping platform enabling fully autonomous SDLC on Git forges — from spec to merged PR without human intervention.",
    tags: ["Autonomous", "SDLC", "Git Forge"],
    icon: <GitBranch className="text-orange-400 w-4 h-4" />,
    maturity: 42,
  },
  {
    name: "UnifAI",
    category: "Platform",
    status: "Production",
    description:
      "Unified AI platform integrating RAG, agentic workflows, multi-agent orchestration, and team collaboration for Red Hat engineers.",
    tags: ["Platform", "RAG", "Agentic"],
    icon: <Zap className="text-primary w-4 h-4" />,
    maturity: 88,
  },
  {
    name: "Compass",
    category: "Evaluation",
    status: "Active",
    description:
      "Cross-project evaluation tracking and quality-gate enforcement, feeding standardised metrics back into CI/CD pipelines.",
    tags: ["Metrics", "Quality Gates", "CI/CD"],
    icon: <FaCompass className="text-red-400" />,
    maturity: 60,
  },
];

const COMMUNITY_METRICS = [
  {
    label: "Event Attendees",
    value: 87,
    max: 100,
    unit: "people",
    delta: "+23%",
    positive: true,
    icon: <FaUsers />,
    color: "text-blue-400",
  },
  {
    label: "AI-Assisted Coding Adoption",
    value: 64,
    max: 100,
    unit: "%",
    delta: "+18pp",
    positive: true,
    icon: <FaCode />,
    color: "text-green-400",
  },
  {
    label: "Community Workshops Held",
    value: 12,
    max: 20,
    unit: "sessions",
    delta: "+4",
    positive: true,
    icon: <FaHandshake />,
    color: "text-purple-400",
  },
  {
    label: "Best Practices (MCP) Published",
    value: 9,
    max: 15,
    unit: "docs",
    delta: "+3",
    positive: true,
    icon: <FaLightbulb />,
    color: "text-yellow-400",
  },
  {
    label: "Ambassador Program Members",
    value: 18,
    max: 25,
    unit: "ambassadors",
    delta: "+6",
    positive: true,
    icon: <FaStar />,
    color: "text-orange-400",
  },
  {
    label: "Visibility Score",
    value: 76,
    max: 100,
    unit: "pts",
    delta: "+11%",
    positive: true,
    icon: <FaChartLine />,
    color: "text-cyan-400",
  },
];

const COMMUNITY_SHIFT = [
  { label: "Presentations", q1: 70, q2: 40, fill: "#6B7280" },
  { label: "Workshops", q1: 20, q2: 40, fill: "#10B981" },
  { label: "Office Hours", q1: 10, q2: 20, fill: "#3B82F6" },
];

/* ─────────────────────────────────────────────────────────────────────────────
   SUB-COMPONENTS
───────────────────────────────────────────────────────────────────────────── */

const TYPE_CONFIG: Record<
  AgendaItem["type"],
  { label: string; color: string; bgColor: string; borderColor: string }
> = {
  logistics: {
    label: "Logistics",
    color: "text-gray-400",
    bgColor: "bg-gray-800/50",
    borderColor: "border-gray-700",
  },
  talk: {
    label: "Talk",
    color: "text-blue-400",
    bgColor: "bg-blue-900/20",
    borderColor: "border-blue-700/50",
  },
  workshop: {
    label: "Workshop",
    color: "text-purple-400",
    bgColor: "bg-purple-900/20",
    borderColor: "border-purple-700/50",
  },
  update: {
    label: "Update",
    color: "text-green-400",
    bgColor: "bg-green-900/20",
    borderColor: "border-green-700/50",
  },
  community: {
    label: "Community",
    color: "text-orange-400",
    bgColor: "bg-orange-900/20",
    borderColor: "border-orange-700/50",
  },
};

function AgendaCard({ item, index }: { item: AgendaItem; index: number }) {
  const [expanded, setExpanded] = useState(false);
  const cfg = TYPE_CONFIG[item.type];

  return (
    <motion.div
      initial={{ opacity: 0, x: -20 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.4, delay: index * 0.07 }}
      className="flex gap-4"
    >
      {/* Timeline line */}
      <div className="flex flex-col items-center">
        <div
          className={`w-9 h-9 rounded-full flex items-center justify-center text-sm flex-shrink-0 ${cfg.bgColor} border ${cfg.borderColor} ${cfg.color}`}
        >
          {item.icon}
        </div>
        {index < AGENDA.length - 1 && (
          <div className="w-px flex-1 mt-2 bg-gradient-to-b from-gray-700 to-transparent min-h-[24px]" />
        )}
      </div>

      {/* Card */}
      <div className={`flex-1 mb-4 rounded-xl border ${cfg.borderColor} ${cfg.bgColor} overflow-hidden`}>
        <div
          className="p-4 cursor-pointer select-none"
          onClick={() => item.type !== "logistics" && setExpanded(!expanded)}
        >
          <div className="flex items-start justify-between gap-3">
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 flex-wrap mb-1">
                <span className="text-xs font-mono text-gray-500">
                  {item.start}–{item.end}
                </span>
                <Badge
                  variant="outline"
                  className={`text-xs border-0 px-2 py-0 ${cfg.bgColor} ${cfg.color}`}
                >
                  {cfg.label}
                </Badge>
              </div>
              <h3 className="font-semibold text-white text-sm leading-snug">
                {item.title}
              </h3>
              {item.speakers.length > 0 && (
                <div className="flex items-center gap-1 mt-1 flex-wrap">
                  <FaMicrophone className="text-gray-500 text-xs" />
                  <span className="text-xs text-gray-400">
                    {item.speakers.join(" · ")}
                  </span>
                </div>
              )}
            </div>
            {item.type !== "logistics" && (
              <button
                className={`text-gray-500 hover:text-white transition-colors mt-1 flex-shrink-0`}
                aria-label={expanded ? "Collapse" : "Expand"}
              >
                {expanded ? <FaChevronUp /> : <FaChevronDown />}
              </button>
            )}
          </div>
        </div>

        <AnimatePresence>
          {expanded && (
            <motion.div
              key="expanded"
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: "auto", opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              transition={{ duration: 0.25 }}
              className="overflow-hidden"
            >
              <div className="px-4 pb-4 border-t border-white/5 pt-3">
                <p className="text-sm text-gray-300 leading-relaxed mb-3">
                  {item.description}
                </p>
                <div className="flex flex-wrap gap-2">
                  {item.topics.map((t) => (
                    <span
                      key={t}
                      className="text-xs bg-white/5 border border-white/10 text-gray-300 rounded-full px-2.5 py-0.5"
                    >
                      {t}
                    </span>
                  ))}
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </motion.div>
  );
}

function ProjectCard({ project, index }: { project: (typeof PROJECTS)[0]; index: number }) {
  const [hovered, setHovered] = useState(false);
  const statusColors: Record<string, string> = {
    Active: "bg-green-500/20 text-green-400 border-green-700/40",
    Production: "bg-blue-500/20 text-blue-400 border-blue-700/40",
    MVP: "bg-orange-500/20 text-orange-400 border-orange-700/40",
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay: index * 0.06 }}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      <Card
        className={`h-full transition-all duration-300 bg-background-card border border-gray-800 ${
          hovered ? "border-primary/40 shadow-lg shadow-primary/10" : ""
        }`}
      >
        <CardHeader className="pb-2">
          <div className="flex items-start justify-between gap-2">
            <div
              className={`w-9 h-9 rounded-lg flex items-center justify-center bg-white/5 border border-white/10 transition-all duration-300 ${
                hovered ? "scale-110" : ""
              }`}
            >
              {project.icon}
            </div>
            <span
              className={`text-xs border rounded-full px-2 py-0.5 ${
                statusColors[project.status] ?? "bg-gray-700 text-gray-400"
              }`}
            >
              {project.status}
            </span>
          </div>
          <CardTitle className="text-sm text-white mt-2">{project.name}</CardTitle>
          <CardDescription className="text-xs text-gray-500">
            {project.category}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <p className="text-xs text-gray-400 leading-relaxed mb-3">
            {project.description}
          </p>
          <div className="mb-3">
            <div className="flex justify-between text-xs text-gray-500 mb-1">
              <span>Maturity</span>
              <span>{project.maturity}%</span>
            </div>
            <Progress value={project.maturity} className="h-1.5" />
          </div>
          <div className="flex flex-wrap gap-1">
            {project.tags.map((t) => (
              <span
                key={t}
                className="text-[10px] bg-white/5 border border-white/8 text-gray-400 rounded px-1.5 py-0.5"
              >
                {t}
              </span>
            ))}
          </div>
        </CardContent>
      </Card>
    </motion.div>
  );
}

function MetricCard({
  metric,
  index,
}: {
  metric: (typeof COMMUNITY_METRICS)[0];
  index: number;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.35, delay: index * 0.07 }}
    >
      <GlassPanel className="p-4 h-full">
        <div className="flex items-center justify-between mb-3">
          <span className={`text-lg ${metric.color}`}>{metric.icon}</span>
          <span
            className={`text-xs font-semibold ${
              metric.positive ? "text-green-400" : "text-red-400"
            }`}
          >
            {metric.delta}
          </span>
        </div>
        <div className="text-2xl font-bold text-white mb-0.5">
          {metric.value}
          <span className="text-sm font-normal text-gray-500 ml-1">{metric.unit}</span>
        </div>
        <div className="text-xs text-gray-500 mb-3">{metric.label}</div>
        <Progress
          value={(metric.value / metric.max) * 100}
          className="h-1"
        />
      </GlassPanel>
    </motion.div>
  );
}

/* Community Shift bar: simple inline render to avoid Recharts in a static page */
function CommunityShiftChart() {
  return (
    <Card className="bg-background-card border border-gray-800">
      <CardHeader>
        <CardTitle className="text-sm text-white flex items-center gap-2">
          <Users2 className="w-4 h-4 text-primary" />
          Community Format Shift: Q1 → Q2
        </CardTitle>
        <CardDescription className="text-xs text-gray-500">
          Transitioning from passive presentations to active workshops and office hours
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          {COMMUNITY_SHIFT.map((row) => (
            <div key={row.label}>
              <div className="flex justify-between text-xs text-gray-400 mb-1.5">
                <span>{row.label}</span>
                <span className="text-gray-500">
                  Q1: {row.q1}% → Q2: <span className="text-white font-semibold">{row.q2}%</span>
                </span>
              </div>
              <div className="flex gap-1 h-5 rounded-lg overflow-hidden">
                <motion.div
                  initial={{ width: 0 }}
                  animate={{ width: `${row.q2}%` }}
                  transition={{ duration: 0.8, delay: 0.2 }}
                  style={{ backgroundColor: row.fill }}
                  className="rounded-l-lg opacity-90"
                />
                <div
                  style={{ width: `${100 - row.q2}%`, backgroundColor: "#1f2937" }}
                  className="rounded-r-lg"
                />
              </div>
            </div>
          ))}
        </div>
        <div className="flex gap-4 mt-4">
          {COMMUNITY_SHIFT.map((r) => (
            <div key={r.label} className="flex items-center gap-1.5">
              <div
                className="w-2.5 h-2.5 rounded-full"
                style={{ backgroundColor: r.fill }}
              />
              <span className="text-xs text-gray-500">{r.label}</span>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

/* ─────────────────────────────────────────────────────────────────────────────
   OVERVIEW TAB
───────────────────────────────────────────────────────────────────────────── */

function OverviewTab() {
  const { primaryHex } = useTheme();

  const pillars = [
    {
      icon: <Brain className="w-5 h-5" />,
      title: "Agentic Orchestration",
      description:
        "A2A communications, peer-to-peer collaboration, and conquering multi-agent SDLC limitations at scale.",
      color: "text-purple-400",
      bg: "bg-purple-900/15 border-purple-800/30",
    },
    {
      icon: <GitBranch className="w-5 h-5" />,
      title: "ADLC",
      description:
        "Agentic Software Development Life Cycle — autonomous design, implementation, review, and deployment pipelines.",
      color: "text-blue-400",
      bg: "bg-blue-900/15 border-blue-800/30",
    },
    {
      icon: <Shield className="w-5 h-5" />,
      title: "Evaluation",
      description:
        "Quality estimation, Eval-Hub, agent-eval-harness, and the Compass project for principled agent quality assurance.",
      color: "text-green-400",
      bg: "bg-green-900/15 border-green-800/30",
    },
    {
      icon: <Target className="w-5 h-5" />,
      title: "AI Ideation → Business Value",
      description:
        "Bridging the gap from exciting AI experiments to measurable, production-grade business outcomes.",
      color: "text-orange-400",
      bg: "bg-orange-900/15 border-orange-800/30",
    },
  ];

  const highlights = [
    { icon: <FaUsers />, value: "87", label: "Registered Attendees" },
    { icon: <FaMicrophone />, value: "11", label: "Speakers" },
    { icon: <FaCode />, value: "7", label: "Key Projects Showcased" },
    { icon: <FaClock />, value: "3h 45m", label: "Content Duration" },
  ];

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.4 }}
      className="space-y-8"
    >
      {/* Hero Banner */}
      <GlassPanel className="relative overflow-hidden p-8">
        <div
          className="absolute inset-0 opacity-10 pointer-events-none"
          style={{
            background: `radial-gradient(ellipse at 20% 50%, ${primaryHex}60 0%, transparent 60%),
                         radial-gradient(ellipse at 80% 20%, #3B82F660 0%, transparent 60%)`,
          }}
        />
        <div className="relative z-10">
          <div className="flex items-center gap-2 mb-3">
            <Badge
              className="bg-primary/20 text-primary border-primary/30 border text-xs"
            >
              Q2 2026
            </Badge>
            <Badge
              variant="outline"
              className="border-gray-700 text-gray-400 text-xs"
            >
              Simulation
            </Badge>
          </div>
          <h2 className="text-2xl font-bold text-white mb-2">{EVENT_META.title}</h2>
          <p className="text-gray-400 text-sm max-w-xl">{EVENT_META.theme}</p>

          <div className="flex flex-wrap gap-4 mt-5">
            <div className="flex items-center gap-2 text-sm text-gray-300">
              <FaCalendarAlt className="text-primary" />
              {EVENT_META.date}
            </div>
            <div className="flex items-center gap-2 text-sm text-gray-300">
              <FaClock className="text-primary" />
              {EVENT_META.time}
            </div>
            <div className="flex items-center gap-2 text-sm text-gray-300">
              <FaMapMarkerAlt className="text-primary" />
              {EVENT_META.location}
            </div>
          </div>
        </div>
      </GlassPanel>

      {/* Highlight Stats */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        {highlights.map((h, i) => (
          <motion.div
            key={h.label}
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.08, duration: 0.35 }}
          >
            <Card className="bg-background-card border border-gray-800 text-center py-5 px-3">
              <div className="text-primary text-xl mb-2 flex justify-center">{h.icon}</div>
              <div className="text-2xl font-bold text-white">{h.value}</div>
              <div className="text-xs text-gray-500 mt-1">{h.label}</div>
            </Card>
          </motion.div>
        ))}
      </div>

      {/* Theme Pillars */}
      <div>
        <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-4">
          Event Theme Pillars
        </h3>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {pillars.map((p, i) => (
            <motion.div
              key={p.title}
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.1, duration: 0.4 }}
            >
              <Card className={`border ${p.bg}`}>
                <CardContent className="pt-5">
                  <div className={`${p.color} mb-2`}>{p.icon}</div>
                  <h4 className="font-semibold text-white text-sm mb-1">{p.title}</h4>
                  <p className="text-xs text-gray-400 leading-relaxed">{p.description}</p>
                </CardContent>
              </Card>
            </motion.div>
          ))}
        </div>
      </div>

      {/* Quick Agenda Preview */}
      <div>
        <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-4">
          Session Quick-Look
        </h3>
        <div className="rounded-xl border border-gray-800 overflow-hidden divide-y divide-gray-800">
          {AGENDA.map((item) => {
            const cfg = TYPE_CONFIG[item.type];
            return (
              <div
                key={item.id}
                className="flex items-center gap-4 px-4 py-3 bg-background-card hover:bg-white/[.02] transition-colors"
              >
                <span className="text-xs font-mono text-gray-600 w-20 flex-shrink-0">
                  {item.start}
                </span>
                <span className={`text-xs ${cfg.color} flex-shrink-0`}>{item.icon}</span>
                <span className="text-sm text-gray-300 flex-1 truncate">{item.title}</span>
                {item.speakers.length > 0 && (
                  <span className="text-xs text-gray-600 hidden sm:block">
                    {item.speakers[0]}
                    {item.speakers.length > 1 && ` +${item.speakers.length - 1}`}
                  </span>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </motion.div>
  );
}

/* ─────────────────────────────────────────────────────────────────────────────
   AGENDA TAB
───────────────────────────────────────────────────────────────────────────── */

function AgendaTab() {
  const [filter, setFilter] = useState<AgendaItem["type"] | "all">("all");

  const types: Array<AgendaItem["type"] | "all"> = [
    "all",
    "talk",
    "workshop",
    "update",
    "community",
    "logistics",
  ];

  const filtered =
    filter === "all" ? AGENDA : AGENDA.filter((a) => a.type === filter);

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.4 }}
      className="space-y-6"
    >
      {/* Filter Chips */}
      <div className="flex flex-wrap gap-2">
        {types.map((t) => {
          const cfg = t === "all" ? null : TYPE_CONFIG[t];
          const isActive = filter === t;
          return (
            <button
              key={t}
              onClick={() => setFilter(t)}
              className={`text-xs px-3 py-1.5 rounded-full border transition-all duration-200 capitalize ${
                isActive
                  ? t === "all"
                    ? "bg-primary/20 text-primary border-primary/40"
                    : `${cfg?.bgColor} ${cfg?.color} ${cfg?.borderColor}`
                  : "bg-transparent text-gray-500 border-gray-700 hover:border-gray-600 hover:text-gray-300"
              }`}
            >
              {t}
            </button>
          );
        })}
      </div>

      {/* Timeline */}
      <div>
        {filtered.map((item, i) => (
          <AgendaCard key={item.id} item={item} index={i} />
        ))}
      </div>

      {filtered.length === 0 && (
        <div className="text-center py-12 text-gray-600">
          No sessions match this filter.
        </div>
      )}
    </motion.div>
  );
}

/* ─────────────────────────────────────────────────────────────────────────────
   PROJECTS TAB
───────────────────────────────────────────────────────────────────────────── */

function ProjectsTab() {
  const [search, setSearch] = useState("");
  const [categoryFilter, setCategoryFilter] = useState<string>("All");

  const categories = [
    "All",
    ...Array.from(new Set(PROJECTS.map((p) => p.category))),
  ];

  const filtered = PROJECTS.filter((p) => {
    const matchesSearch =
      search === "" ||
      p.name.toLowerCase().includes(search.toLowerCase()) ||
      p.description.toLowerCase().includes(search.toLowerCase()) ||
      p.tags.some((t) => t.toLowerCase().includes(search.toLowerCase()));
    const matchesCat =
      categoryFilter === "All" || p.category === categoryFilter;
    return matchesSearch && matchesCat;
  });

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.4 }}
      className="space-y-6"
    >
      {/* Controls */}
      <div className="flex flex-col sm:flex-row gap-3">
        <input
          type="text"
          placeholder="Search projects…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="flex-1 bg-background-card border border-gray-800 text-sm text-white rounded-lg px-3 py-2 placeholder-gray-600 focus:outline-none focus:border-primary/50 transition-colors"
        />
        <div className="flex gap-2 flex-wrap">
          {categories.map((c) => (
            <button
              key={c}
              onClick={() => setCategoryFilter(c)}
              className={`text-xs px-3 py-1.5 rounded-full border transition-all duration-200 ${
                categoryFilter === c
                  ? "bg-primary/20 text-primary border-primary/40"
                  : "bg-transparent text-gray-500 border-gray-700 hover:border-gray-600 hover:text-gray-300"
              }`}
            >
              {c}
            </button>
          ))}
        </div>
      </div>

      {/* Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {filtered.map((p, i) => (
          <ProjectCard key={p.name} project={p} index={i} />
        ))}
      </div>

      {filtered.length === 0 && (
        <div className="text-center py-12 text-gray-600">No projects found.</div>
      )}
    </motion.div>
  );
}

/* ─────────────────────────────────────────────────────────────────────────────
   METRICS TAB
───────────────────────────────────────────────────────────────────────────── */

function MetricsTab() {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.4 }}
      className="space-y-8"
    >
      {/* Metric Cards */}
      <div>
        <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-4">
          Community & Adoption Metrics
        </h3>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {COMMUNITY_METRICS.map((m, i) => (
            <MetricCard key={m.label} metric={m} index={i} />
          ))}
        </div>
      </div>

      {/* Community Shift Chart */}
      <CommunityShiftChart />

      {/* AI Coding Breakdown */}
      <Card className="bg-background-card border border-gray-800">
        <CardHeader>
          <CardTitle className="text-sm text-white flex items-center gap-2">
            <FaCode className="text-primary" />
            AI-Assisted Coding: Adoption Breakdown
          </CardTitle>
          <CardDescription className="text-xs text-gray-500">
            Tooling distribution across Red Hat IL engineers
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {[
              { tool: "Claude Code", pct: 38, color: "#BB86FC" },
              { tool: "GitHub Copilot", pct: 29, color: "#3B82F6" },
              { tool: "Cursor / Windsurf", pct: 19, color: "#10B981" },
              { tool: "Other / Custom MCP", pct: 14, color: "#F59E0B" },
            ].map((row) => (
              <div key={row.tool}>
                <div className="flex justify-between text-xs mb-1">
                  <span className="text-gray-300">{row.tool}</span>
                  <span className="text-gray-500">{row.pct}%</span>
                </div>
                <div className="h-2 bg-gray-800 rounded-full overflow-hidden">
                  <motion.div
                    initial={{ width: 0 }}
                    animate={{ width: `${row.pct}%` }}
                    transition={{ duration: 0.7, delay: 0.1 }}
                    style={{ backgroundColor: row.color }}
                    className="h-full rounded-full"
                  />
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Ambassador Program */}
      <Card className="bg-background-card border border-gray-800">
        <CardHeader>
          <CardTitle className="text-sm text-white flex items-center gap-2">
            <FaTrophy className="text-yellow-400" />
            AI IL Ambassador Program — Q2 Snapshot
          </CardTitle>
          <CardDescription className="text-xs text-gray-500">
            18 active ambassadors driving AI best-practice adoption across Red Hat Israel
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            {[
              { label: "Success Stories Shared", value: "24", icon: <FaCheckCircle className="text-green-400" /> },
              { label: "Peer Mentoring Sessions", value: "37", icon: <FaHandshake className="text-blue-400" /> },
              { label: "MCP Best Practices Published", value: "9", icon: <FaLightbulb className="text-yellow-400" /> },
            ].map((s) => (
              <div
                key={s.label}
                className="flex flex-col items-center text-center p-4 rounded-xl bg-white/[.03] border border-white/5"
              >
                <div className="text-xl mb-2">{s.icon}</div>
                <div className="text-2xl font-bold text-white">{s.value}</div>
                <div className="text-xs text-gray-500 mt-1">{s.label}</div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </motion.div>
  );
}

/* ─────────────────────────────────────────────────────────────────────────────
   PAGE ROOT
───────────────────────────────────────────────────────────────────────────── */

export default function InnovationDay() {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [activeTab, setActiveTab] = useState("overview");

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar />

      <div className="flex-1 flex flex-col overflow-hidden">
        <Header
          title="Innovation Day — Q2 2026"
          onToggleSidebar={() => setSidebarOpen(!sidebarOpen)}
        />

        <main className="flex-1 overflow-y-auto p-6 bg-background">
          <div className="max-w-5xl mx-auto">
            {/* Page heading */}
            <motion.div
              initial={{ opacity: 0, y: -12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.4 }}
              className="mb-6"
            >
              <div className="flex items-center gap-3 flex-wrap">
                <h1 className="text-xl font-bold text-white">
                  Red Hat Innovation Day Q2 2026
                </h1>
                <Badge className="bg-primary/20 text-primary border-primary/30 border">
                  IL Site
                </Badge>
                <Badge
                  variant="outline"
                  className="border-gray-700 text-gray-400 text-xs"
                >
                  Simulation
                </Badge>
              </div>
              <p className="text-sm text-gray-500 mt-1">
                {EVENT_META.date} · {EVENT_META.time} · {EVENT_META.location}
              </p>
            </motion.div>

            {/* Tabs */}
            <Tabs
              value={activeTab}
              onValueChange={setActiveTab}
              className="space-y-6"
            >
              <TabsList className="bg-background-card border border-gray-800 p-1 h-auto">
                {[
                  { value: "overview", label: "Overview", icon: <FaRocket className="text-xs" /> },
                  { value: "agenda", label: "Agenda", icon: <FaCalendarAlt className="text-xs" /> },
                  { value: "projects", label: "Projects & Tools", icon: <FaGithub className="text-xs" /> },
                  { value: "metrics", label: "Metrics", icon: <FaChartLine className="text-xs" /> },
                ].map((tab) => (
                  <TabsTrigger
                    key={tab.value}
                    value={tab.value}
                    className="text-xs data-[state=active]:bg-primary/20 data-[state=active]:text-primary flex items-center gap-1.5 px-4 py-2"
                  >
                    {tab.icon}
                    {tab.label}
                  </TabsTrigger>
                ))}
              </TabsList>

              <TabsContent value="overview">
                <OverviewTab />
              </TabsContent>
              <TabsContent value="agenda">
                <AgendaTab />
              </TabsContent>
              <TabsContent value="projects">
                <ProjectsTab />
              </TabsContent>
              <TabsContent value="metrics">
                <MetricsTab />
              </TabsContent>
            </Tabs>
          </div>
        </main>

        <StatusBar />
      </div>
    </div>
  );
}
