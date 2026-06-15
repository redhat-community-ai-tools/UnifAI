import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  FaCalendarAlt,
  FaClock,
  FaMapMarkerAlt,
  FaLightbulb,
  FaChevronDown,
  FaChevronUp,
  FaMicrophone,
  FaRocket,
  FaUsers,
  FaCode,
  FaStar,
  FaFlask,
  FaProjectDiagram,
  FaGlobe,
  FaBolt,
  FaCheckCircle,
  FaCircle,
  FaBullhorn,
  FaStream,
} from "react-icons/fa";

import Sidebar from "@/components/layout/Sidebar";
import Header from "@/components/layout/Header";
import StatusBar from "@/components/layout/StatusBar";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

/* ─────────────────────────────── types ─────────────────────────────── */

interface AgendaItem {
  time: string;
  startMinutes: number; // minutes since midnight for live indicator
  endMinutes: number;
  title: string;
  speakers: string[];
  icon: string;
  type: "networking" | "keynote" | "session" | "update" | "program";
}

interface SessionDetail {
  id: number;
  title: string;
  duration: string;
  speakers: string[];
  icon: React.ReactNode;
  color: string;
  description: string;
  points: string[];
  tags: string[];
}

interface KeyProject {
  name: string;
  description: string;
  icon: React.ReactNode;
  tag: string;
  tagColor: string;
}

interface Speaker {
  name: string;
  session: string;
  initials: string;
  color: string;
}

interface CommunityNote {
  icon: React.ReactNode;
  title: string;
  description: string;
  color: string;
}

/* ──────────────────────────────── data ─────────────────────────────── */

// Event window: June 16 2026, 09:30–13:15 Israel time (UTC+3)
const EVENT_DATE = "Tuesday, June 16th, 2026";
const EVENT_START = "09:30";
const EVENT_END = "13:15";

const agendaItems: AgendaItem[] = [
  {
    time: "09:30 – 09:45",
    startMinutes: 9 * 60 + 30,
    endMinutes: 9 * 60 + 45,
    title: "Registration & Arrival",
    speakers: [],
    icon: "🚪",
    type: "networking",
  },
  {
    time: "09:45 – 10:00",
    startMinutes: 9 * 60 + 45,
    endMinutes: 10 * 60,
    title: "Coffee and Ma'affee",
    speakers: [],
    icon: "☕",
    type: "networking",
  },
  {
    time: "10:00 – 10:05",
    startMinutes: 10 * 60,
    endMinutes: 10 * 60 + 5,
    title: "Intro to Innovation Day",
    speakers: ["Hofni Gartner"],
    icon: "👋",
    type: "keynote",
  },
  {
    time: "10:05 – 11:00",
    startMinutes: 10 * 60 + 5,
    endMinutes: 11 * 60,
    title: "Is Orchestration the Future?",
    speakers: ["Vlad Luzin", "Roy Nissim"],
    icon: "🔗",
    type: "session",
  },
  {
    time: "11:00 – 12:00",
    startMinutes: 11 * 60,
    endMinutes: 12 * 60,
    title: "Introduction to Fullsend",
    speakers: ["Barak Korren"],
    icon: "🚀",
    type: "session",
  },
  {
    time: "12:00 – 12:35",
    startMinutes: 12 * 60,
    endMinutes: 12 * 60 + 35,
    title: "Skill/Agents Related Quality and Evaluation",
    speakers: [
      "Ella Shulman",
      "Benjamin Kapner",
      "Carmel Soceanu",
      "Guy Ziv",
      "Sharon Dashet",
    ],
    icon: "🧪",
    type: "session",
  },
  {
    time: "12:35 – 12:50",
    startMinutes: 12 * 60 + 35,
    endMinutes: 12 * 60 + 50,
    title: "Updates from UnifAI",
    speakers: ["Nir Rashti", "Odai Odeh"],
    icon: "🤖",
    type: "update",
  },
  {
    time: "12:50 – 13:00",
    startMinutes: 12 * 60 + 50,
    endMinutes: 13 * 60,
    title: "AI IL Ambassador Program",
    speakers: ["Ilanit Stein"],
    icon: "🌟",
    type: "program",
  },
  {
    time: "13:00 – 13:15",
    startMinutes: 13 * 60,
    endMinutes: 13 * 60 + 15,
    title: "Open Q&A / Wrap-up",
    speakers: [],
    icon: "💬",
    type: "networking",
  },
];

const sessionHighlights: SessionDetail[] = [
  {
    id: 1,
    title: "Is Orchestration the Future?",
    duration: "55 min",
    speakers: ["Vlad Luzin", "Roy Nissim"],
    icon: <FaProjectDiagram className="w-5 h-5" />,
    color: "#8B5CF6",
    description:
      "A deep-dive into multi-agent communication paradigms and whether orchestration is the right primitive for the next generation of agentic systems.",
    points: [
      "A2A (Agent-to-Agent) Communications for multi-agent systems",
      "Peer-to-peer collaboration patterns between autonomous agents",
      "Overcoming the scalability limits of current multi-agent SDLCs",
      "Real-world examples of orchestration failures and how to design around them",
    ],
    tags: ["Multi-Agent", "A2A", "Orchestration", "ADLC"],
  },
  {
    id: 2,
    title: "Introduction to Fullsend",
    duration: "60 min",
    speakers: ["Barak Korren"],
    icon: <FaRocket className="w-5 h-5" />,
    color: "#F59E0B",
    description:
      "Fullsend is a living design corpus and shipping platform enabling fully autonomous agentic software development life-cycles on top of standard Git forges.",
    points: [
      "Architecture of the Fullsend platform and its Git-native design",
      "How autonomous agents author, review, and merge code without human intervention",
      "Integration with existing CI/CD pipelines and quality gates",
      "Early results: velocity gains and defect rates in agentic SDLC",
    ],
    tags: ["Fullsend", "ADLC", "Automation", "Git"],
  },
  {
    id: 3,
    title: "Skill/Agents Related Quality and Evaluation",
    duration: "35 min",
    speakers: [
      "Ella Shulman",
      "Benjamin Kapner",
      "Carmel Soceanu",
      "Guy Ziv",
      "Sharon Dashet",
    ],
    icon: <FaFlask className="w-5 h-5" />,
    color: "#10B981",
    description:
      "Why quality estimation is a first-class concern in agentic workflows, and a tour of the eval toolchain built at Red Hat.",
    points: [
      "Why quality estimation matters in AI agent contexts",
      "Introduction to Eval-Hub — a lightweight REST API for orchestrating evals",
      "agent-eval-harness: framework for evaluating agent skills against test datasets",
      "The Compass project: measuring agent compass across quality dimensions",
    ],
    tags: ["Evaluation", "Eval-Hub", "agent-eval-harness", "Compass"],
  },
  {
    id: 4,
    title: "Updates from UnifAI",
    duration: "15 min",
    speakers: ["Nir Rashti", "Odai Odeh"],
    icon: <FaCode className="w-5 h-5" />,
    color: "#EF4444",
    description:
      "Latest updates from the UnifAI platform team — how the platform is evolving to support ADLC-first workflows.",
    points: [
      "Adapting the platform to ADLC flows and agentic pipelines",
      "Focus on automation and zero-friction setup for individuals and teams",
      "New integrations: MCP, Jira, Slack, and Git forge connectors",
      "Roadmap highlights for Q3 2026",
    ],
    tags: ["UnifAI", "MCP", "Automation", "Platform"],
  },
  {
    id: 5,
    title: "AI IL Ambassador Program",
    duration: "10 min",
    speakers: ["Ilanit Stein"],
    icon: <FaStar className="w-5 h-5" />,
    color: "#3B82F6",
    description:
      "Updates on the Israel site AI Ambassador Program — community successes, evangelism efforts, and the road ahead.",
    points: [
      "Q2 success stories and impact metrics from IL ambassadors",
      "Community visibility initiatives across the Red Hat org",
      "How to become an AI ambassador at the IL site",
    ],
    tags: ["Community", "Ambassador", "IL Site"],
  },
];

const keyProjects: KeyProject[] = [
  {
    name: "Code Agent Harness Evaluation",
    description:
      "Tools to verify that code-agent setups are working, safe, and internally consistent across configurations.",
    icon: <FaCode className="w-4 h-4" />,
    tag: "Evaluation",
    tagColor: "#10B981",
  },
  {
    name: "agent-eval-harness",
    description:
      "Framework for evaluating AI agent skills against curated test datasets with deterministic scoring.",
    icon: <FaFlask className="w-4 h-4" />,
    tag: "Framework",
    tagColor: "#8B5CF6",
  },
  {
    name: "eval-hub",
    description:
      "Lightweight REST API service for orchestrating AI model evaluations across teams and environments.",
    icon: <FaProjectDiagram className="w-4 h-4" />,
    tag: "API",
    tagColor: "#3B82F6",
  },
  {
    name: "sdg_hub",
    description:
      "Python framework for building synthetic data generation (SDG) pipelines for AI fine-tuning.",
    icon: <FaLightbulb className="w-4 h-4" />,
    tag: "Framework",
    tagColor: "#8B5CF6",
  },
  {
    name: "Fullsend",
    description:
      "Autonomous agentic SDLC platform that ships code from design to merge without human intervention.",
    icon: <FaRocket className="w-4 h-4" />,
    tag: "Platform",
    tagColor: "#F59E0B",
  },
  {
    name: "UnifAI",
    description:
      "Unified AI operations platform for managing RAG, agentic workflows, evaluations, and team workspaces.",
    icon: <FaBolt className="w-4 h-4" />,
    tag: "Platform",
    tagColor: "#EF4444",
  },
];

const speakers: Speaker[] = [
  { name: "Hofni Gartner", session: "Intro", initials: "HG", color: "#6B7280" },
  { name: "Vlad Luzin", session: "Orchestration", initials: "VL", color: "#8B5CF6" },
  { name: "Roy Nissim", session: "Orchestration", initials: "RN", color: "#8B5CF6" },
  { name: "Barak Korren", session: "Fullsend", initials: "BK", color: "#F59E0B" },
  { name: "Ella Shulman", session: "Evaluation", initials: "ES", color: "#10B981" },
  { name: "Benjamin Kapner", session: "Evaluation", initials: "BK", color: "#10B981" },
  { name: "Carmel Soceanu", session: "Evaluation", initials: "CS", color: "#10B981" },
  { name: "Guy Ziv", session: "Evaluation", initials: "GZ", color: "#10B981" },
  { name: "Sharon Dashet", session: "Evaluation", initials: "SD", color: "#10B981" },
  { name: "Nir Rashti", session: "UnifAI", initials: "NR", color: "#EF4444" },
  { name: "Odai Odeh", session: "UnifAI", initials: "OO", color: "#EF4444" },
  { name: "Ilanit Stein", session: "Ambassador", initials: "IS", color: "#3B82F6" },
];

const communityNotes: CommunityNote[] = [
  {
    icon: <FaStream className="w-4 h-4" />,
    title: "Format Shift",
    description:
      "Moving from presentation-heavy formats to interactive workshops and open office hours — more hands-on, more community-driven.",
    color: "#8B5CF6",
  },
  {
    icon: <FaGlobe className="w-4 h-4" />,
    title: "Community Visibility",
    description:
      "Increasing cross-org visibility for the IL AI community — sharing work more broadly across Red Hat engineering and product.",
    color: "#3B82F6",
  },
  {
    icon: <FaBolt className="w-4 h-4" />,
    title: "MCP Best Practices",
    description:
      "Adopting and publishing Model Context Protocol (MCP) best practices as the standard interface for tool-augmented agents.",
    color: "#F59E0B",
  },
  {
    icon: <FaCode className="w-4 h-4" />,
    title: "AI Assisted Coding",
    description:
      "Primary focus area: empowering engineers with AI coding assistants and agentic code-review pipelines across IL teams.",
    color: "#10B981",
  },
];

const themeTags = [
  "Agentic Orchestration",
  "ADLC",
  "Evaluation",
  "AI to Business Value",
];

const typeColors: Record<AgendaItem["type"], string> = {
  networking: "#6B7280",
  keynote: "#F59E0B",
  session: "#8B5CF6",
  update: "#EF4444",
  program: "#3B82F6",
};

/* ──────────────────────── helper: current-session ──────────────────── */

function getNowMinutes(): number {
  const now = new Date();
  return now.getHours() * 60 + now.getMinutes();
}

function getLiveSessionIndex(nowMin: number): number {
  return agendaItems.findIndex(
    (item) => nowMin >= item.startMinutes && nowMin < item.endMinutes
  );
}

/* ────────────────────────────── sub-components ─────────────────────── */

function InfoChip({ icon, label }: { icon: React.ReactNode; label: string }) {
  return (
    <div className="flex items-center gap-2 bg-white/5 border border-white/10 rounded-full px-4 py-1.5 text-sm text-gray-300">
      <span className="text-primary">{icon}</span>
      {label}
    </div>
  );
}

function ThemeTag({ label }: { label: string }) {
  return (
    <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-semibold bg-primary/20 text-primary border border-primary/30">
      {label}
    </span>
  );
}

function StatPill({
  value,
  label,
  icon,
}: {
  value: string | number;
  label: string;
  icon: React.ReactNode;
}) {
  return (
    <div className="flex flex-col items-center gap-1 px-5 py-3 rounded-xl bg-white/[.03] border border-white/10">
      <div className="text-primary text-sm">{icon}</div>
      <span className="text-2xl font-bold text-white">{value}</span>
      <span className="text-[11px] uppercase tracking-wider text-gray-500 font-medium">
        {label}
      </span>
    </div>
  );
}

function SectionHeading({
  icon,
  title,
  subtitle,
}: {
  icon: React.ReactNode;
  title: string;
  subtitle?: string;
}) {
  return (
    <div className="mb-5">
      <div className="flex items-center gap-2">
        {icon}
        <h2 className="text-lg font-heading font-bold text-white">{title}</h2>
      </div>
      {subtitle && (
        <p className="text-sm text-gray-500 mt-1 ml-6">{subtitle}</p>
      )}
    </div>
  );
}

function AgendaRow({
  item,
  index,
  isLive,
  isPast,
}: {
  item: AgendaItem;
  index: number;
  isLive: boolean;
  isPast: boolean;
}) {
  const typeColor = typeColors[item.type];
  return (
    <motion.tr
      initial={{ opacity: 0, x: -20 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.3, delay: index * 0.05 }}
      className={`border-b border-white/5 transition-colors ${
        isLive
          ? "bg-primary/5 border-l-2 border-l-primary"
          : isPast
          ? "opacity-50"
          : "hover:bg-white/[.03]"
      }`}
    >
      <td className="py-3 px-4 text-xs font-mono text-gray-400 whitespace-nowrap">
        <div className="flex items-center gap-2">
          {isLive && (
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-primary opacity-75" />
              <span className="relative inline-flex rounded-full h-2 w-2 bg-primary" />
            </span>
          )}
          {item.time}
        </div>
      </td>
      <td className="py-3 px-4 text-lg">{item.icon}</td>
      <td className="py-3 px-4">
        <div className="flex items-center gap-2">
          <span className="font-medium text-white">{item.title}</span>
          {isLive && (
            <span className="text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full bg-primary/20 text-primary border border-primary/30 animate-pulse">
              LIVE
            </span>
          )}
        </div>
      </td>
      <td className="py-3 px-4">
        <div
          className="inline-block text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full border"
          style={{
            backgroundColor: `${typeColor}22`,
            color: typeColor,
            borderColor: `${typeColor}44`,
          }}
        >
          {item.type}
        </div>
      </td>
      <td className="py-3 px-4 text-sm text-gray-400">
        {item.speakers.length > 0 ? item.speakers.join(", ") : "—"}
      </td>
    </motion.tr>
  );
}

function SessionCard({ session }: { session: SessionDetail }) {
  const [open, setOpen] = useState(false);

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="rounded-xl border border-white/10 bg-white/[.03] overflow-hidden"
    >
      <button
        className="w-full flex items-center gap-4 px-5 py-4 text-left hover:bg-white/[.04] transition-colors"
        onClick={() => setOpen(!open)}
        aria-expanded={open}
      >
        {/* Colored icon */}
        <div
          className="flex-shrink-0 w-10 h-10 rounded-xl flex items-center justify-center"
          style={{
            backgroundColor: `${session.color}22`,
            color: session.color,
          }}
        >
          {session.icon}
        </div>

        {/* Title + speakers */}
        <div className="flex-1 min-w-0">
          <p className="font-semibold text-white">{session.title}</p>
          <p className="text-xs text-gray-500 mt-0.5">
            {session.speakers.join(" · ")}
          </p>
        </div>

        {/* Duration badge */}
        <span
          className="flex-shrink-0 text-[10px] font-bold uppercase tracking-wider px-2 py-1 rounded-full border mr-2"
          style={{
            backgroundColor: `${session.color}18`,
            color: session.color,
            borderColor: `${session.color}40`,
          }}
        >
          {session.duration}
        </span>

        <span className="text-gray-500 flex-shrink-0">
          {open ? <FaChevronUp /> : <FaChevronDown />}
        </span>
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            key="content"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden"
          >
            <div className="px-5 pb-5 space-y-4">
              {/* Description */}
              <p className="text-sm text-gray-400 leading-relaxed border-l-2 pl-3" style={{ borderColor: session.color }}>
                {session.description}
              </p>

              {/* Points */}
              <ul className="space-y-2">
                {session.points.map((pt, i) => (
                  <li
                    key={i}
                    className="flex items-start gap-2 text-sm text-gray-400"
                  >
                    <FaCheckCircle
                      className="mt-0.5 flex-shrink-0 w-3.5 h-3.5"
                      style={{ color: session.color }}
                    />
                    {pt}
                  </li>
                ))}
              </ul>

              {/* Tags */}
              <div className="flex flex-wrap gap-1.5 pt-1">
                {session.tags.map((tag) => (
                  <span
                    key={tag}
                    className="text-[10px] font-semibold uppercase tracking-wider px-2 py-0.5 rounded-full bg-white/5 text-gray-500 border border-white/10"
                  >
                    {tag}
                  </span>
                ))}
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}

function ProjectCard({ project }: { project: KeyProject }) {
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.97 }}
      animate={{ opacity: 1, scale: 1 }}
      className="rounded-xl border border-white/10 bg-white/[.03] p-4 flex flex-col gap-3 hover:border-primary/40 transition-colors group"
    >
      <div className="flex items-center justify-between">
        <div
          className="w-9 h-9 rounded-lg flex items-center justify-center transition-colors"
          style={{
            backgroundColor: `${project.tagColor}18`,
            color: project.tagColor,
          }}
        >
          {project.icon}
        </div>
        <span
          className="text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full border"
          style={{
            backgroundColor: `${project.tagColor}18`,
            color: project.tagColor,
            borderColor: `${project.tagColor}40`,
          }}
        >
          {project.tag}
        </span>
      </div>
      <div>
        <p className="font-semibold text-white text-sm group-hover:text-primary transition-colors">
          {project.name}
        </p>
        <p className="text-xs text-gray-500 leading-relaxed mt-1">
          {project.description}
        </p>
      </div>
    </motion.div>
  );
}

function SpeakerBadge({ speaker }: { speaker: Speaker }) {
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.9 }}
      animate={{ opacity: 1, scale: 1 }}
      className="flex items-center gap-2.5 rounded-xl border border-white/10 bg-white/[.03] px-3 py-2 hover:border-white/20 transition-colors"
    >
      <div
        className="w-8 h-8 rounded-full flex items-center justify-center text-white text-xs font-bold flex-shrink-0"
        style={{ backgroundColor: speaker.color }}
      >
        {speaker.initials}
      </div>
      <div className="min-w-0">
        <p className="text-sm font-medium text-white truncate">{speaker.name}</p>
        <p className="text-[11px] text-gray-500 truncate">{speaker.session}</p>
      </div>
    </motion.div>
  );
}

function CommunityNoteCard({ note }: { note: CommunityNote }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className="rounded-xl border border-white/10 bg-white/[.03] p-4 flex gap-4"
    >
      <div
        className="flex-shrink-0 w-9 h-9 rounded-lg flex items-center justify-center mt-0.5"
        style={{ backgroundColor: `${note.color}22`, color: note.color }}
      >
        {note.icon}
      </div>
      <div>
        <p className="font-semibold text-white text-sm">{note.title}</p>
        <p className="text-xs text-gray-500 leading-relaxed mt-1">
          {note.description}
        </p>
      </div>
    </motion.div>
  );
}

function LiveIndicator() {
  const [nowMin, setNowMin] = useState(getNowMinutes());
  const [show, setShow] = useState(true);

  useEffect(() => {
    const id = setInterval(() => setNowMin(getNowMinutes()), 30_000);
    return () => clearInterval(id);
  }, []);

  const liveIdx = getLiveSessionIndex(nowMin);
  const isEventDay = true; // simulated as always-on for demo purposes
  const liveItem = liveIdx !== -1 ? agendaItems[liveIdx] : null;

  if (!isEventDay || !liveItem || !show) return null;

  return (
    <motion.div
      initial={{ opacity: 0, y: -8 }}
      animate={{ opacity: 1, y: 0 }}
      className="relative rounded-xl border border-primary/30 bg-primary/5 px-4 py-3 flex items-center gap-3"
    >
      <span className="relative flex h-3 w-3">
        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-primary opacity-60" />
        <span className="relative inline-flex rounded-full h-3 w-3 bg-primary" />
      </span>
      <div className="flex-1">
        <span className="text-xs font-bold text-primary uppercase tracking-wider">
          Live Now
        </span>
        <span className="text-sm text-white ml-2 font-medium">
          {liveItem.icon} {liveItem.title}
        </span>
        {liveItem.speakers.length > 0 && (
          <span className="text-xs text-gray-400 ml-2">
            · {liveItem.speakers.join(", ")}
          </span>
        )}
      </div>
      <button
        onClick={() => setShow(false)}
        className="text-gray-600 hover:text-gray-400 transition-colors text-xs"
        aria-label="Dismiss"
      >
        ✕
      </button>
    </motion.div>
  );
}

/* ─────────────────────────── timeline progress ─────────────────────── */

function AgendaTimeline() {
  const [nowMin, setNowMin] = useState(getNowMinutes());

  useEffect(() => {
    const id = setInterval(() => setNowMin(getNowMinutes()), 30_000);
    return () => clearInterval(id);
  }, []);

  const liveIdx = getLiveSessionIndex(nowMin);

  return (
    <div className="relative pl-6 space-y-1">
      {/* Vertical rail */}
      <div className="absolute left-[10px] top-2 bottom-2 w-0.5 bg-white/10 rounded-full" />

      {agendaItems.map((item, i) => {
        const isLive = i === liveIdx;
        const isPast = liveIdx !== -1 && i < liveIdx;
        const typeColor = typeColors[item.type];

        return (
          <motion.div
            key={i}
            initial={{ opacity: 0, x: -10 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: i * 0.04 }}
            className={`relative flex gap-4 items-start py-2.5 px-4 rounded-xl transition-colors ${
              isLive ? "bg-primary/5 border border-primary/25" : ""
            } ${isPast ? "opacity-40" : ""}`}
          >
            {/* Dot on the rail */}
            <div
              className={`absolute -left-[18px] top-4 w-3.5 h-3.5 rounded-full border-2 flex-shrink-0 transition-transform ${
                isLive ? "scale-125" : ""
              }`}
              style={{
                backgroundColor: isLive ? typeColor : isPast ? "#374151" : "#1f2937",
                borderColor: isLive ? typeColor : isPast ? "#374151" : typeColor + "66",
              }}
            >
              {isLive && (
                <span
                  className="absolute inset-0 rounded-full animate-ping opacity-50"
                  style={{ backgroundColor: typeColor }}
                />
              )}
            </div>

            {/* Time */}
            <div className="w-28 flex-shrink-0">
              <span className="text-[11px] font-mono text-gray-500">
                {item.time}
              </span>
            </div>

            {/* Icon + content */}
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-base">{item.icon}</span>
                <span className="font-medium text-white text-sm">{item.title}</span>
                {isLive && (
                  <span className="text-[9px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded-full bg-primary/20 text-primary border border-primary/30 animate-pulse">
                    LIVE
                  </span>
                )}
              </div>
              {item.speakers.length > 0 && (
                <p className="text-xs text-gray-500 mt-0.5 ml-6">
                  {item.speakers.join(" · ")}
                </p>
              )}
            </div>

            {/* Type pill */}
            <div
              className="flex-shrink-0 text-[9px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full border self-start mt-1"
              style={{
                backgroundColor: `${typeColor}22`,
                color: typeColor,
                borderColor: `${typeColor}44`,
              }}
            >
              {item.type}
            </div>
          </motion.div>
        );
      })}
    </div>
  );
}

/* ──────────────────────────────── page ────────────────────────────── */

export default function InnovationDay() {
  const [sidebarOpen, setSidebarOpen] = useState(false);

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar />

      <div className="flex-1 flex flex-col overflow-hidden">
        <Header
          title="Innovation Day — IL Site Q2 2026"
          onToggleSidebar={() => setSidebarOpen(!sidebarOpen)}
        />

        <main className="flex-1 overflow-y-auto bg-background-dark p-6">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
            className="max-w-5xl mx-auto space-y-6"
          >
            {/* ── Live indicator (dismissable) ── */}
            <LiveIndicator />

            {/* ── Hero Banner ── */}
            <div className="relative rounded-2xl overflow-hidden border border-white/10 bg-gradient-to-br from-[#1a0a2e] via-[#0D1117] to-[#0a1a2e] p-8">
              {/* decorative blobs */}
              <div className="absolute top-0 right-0 w-72 h-72 bg-primary/10 rounded-full blur-3xl pointer-events-none" />
              <div className="absolute bottom-0 left-0 w-56 h-56 bg-blue-600/10 rounded-full blur-3xl pointer-events-none" />
              <div className="absolute top-1/2 left-1/2 w-40 h-40 bg-amber-500/5 rounded-full blur-2xl pointer-events-none" />

              <div className="relative z-10">
                <div className="flex items-center gap-2 mb-3">
                  <span className="text-3xl">🚀</span>
                  <span className="text-xs font-bold uppercase tracking-widest text-primary/80 border border-primary/30 rounded-full px-3 py-1 bg-primary/10">
                    Red Hat · Internal Event
                  </span>
                  <span className="text-xs font-bold uppercase tracking-widest text-amber-400/80 border border-amber-400/30 rounded-full px-3 py-1 bg-amber-400/10">
                    Q2 2026
                  </span>
                </div>

                <h1 className="text-3xl md:text-4xl font-heading font-bold text-white leading-tight">
                  Red Hat Innovation Day
                  <br />
                  <span className="text-primary">Q2 2026 — IL Site</span>
                </h1>

                <p className="mt-3 text-gray-400 max-w-xl leading-relaxed">
                  A half-day gathering for the Israel site — focused on agentic
                  orchestration, ADLC, quality evaluation, and the journey from
                  AI ideation to real business value.
                </p>

                {/* Info chips */}
                <div className="mt-6 flex flex-wrap gap-3">
                  <InfoChip
                    icon={<FaCalendarAlt />}
                    label={EVENT_DATE}
                  />
                  <InfoChip
                    icon={<FaClock />}
                    label={`${EVENT_START} – ${EVENT_END}`}
                  />
                  <InfoChip icon={<FaMapMarkerAlt />} label="IL (Israel) Site" />
                </div>

                {/* Theme tags */}
                <div className="mt-4 flex flex-wrap gap-2">
                  {themeTags.map((t) => (
                    <ThemeTag key={t} label={t} />
                  ))}
                </div>
              </div>
            </div>

            {/* ── Stats bar ── */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              <StatPill
                value={agendaItems.filter((a) => a.type === "session").length}
                label="Sessions"
                icon={<FaMicrophone />}
              />
              <StatPill
                value={speakers.length}
                label="Speakers"
                icon={<FaUsers />}
              />
              <StatPill
                value="3h 45m"
                label="Duration"
                icon={<FaClock />}
              />
              <StatPill
                value={keyProjects.length}
                label="Key Projects"
                icon={<FaCode />}
              />
            </div>

            {/* ── Tabbed content ── */}
            <Tabs defaultValue="agenda" className="space-y-4">
              <TabsList className="bg-white/[.03] border border-white/10 p-1 rounded-xl flex gap-1 flex-wrap h-auto">
                {[
                  { value: "agenda", label: "📅 Agenda" },
                  { value: "sessions", label: "🎤 Sessions" },
                  { value: "projects", label: "🛠 Projects" },
                  { value: "speakers", label: "👥 Speakers" },
                  { value: "community", label: "🌐 Community" },
                ].map((tab) => (
                  <TabsTrigger
                    key={tab.value}
                    value={tab.value}
                    className="rounded-lg px-4 py-2 text-sm font-medium text-gray-400 data-[state=active]:bg-primary/20 data-[state=active]:text-primary transition-colors"
                  >
                    {tab.label}
                  </TabsTrigger>
                ))}
              </TabsList>

              {/* ── Tab: Agenda ── */}
              <TabsContent value="agenda" className="space-y-4 mt-0">
                <SectionHeading
                  icon={<FaCalendarAlt className="text-primary" />}
                  title="Full Agenda"
                  subtitle="All times are Israel Standard Time (IST / UTC+3). Live indicator updates every 30 seconds."
                />

                {/* Timeline view */}
                <div className="rounded-xl border border-white/10 bg-white/[.02] p-5">
                  <AgendaTimeline />
                </div>

                {/* Table view */}
                <div className="rounded-xl border border-white/10 bg-white/[.02] overflow-x-auto">
                  <table className="w-full text-left min-w-[600px]">
                    <thead>
                      <tr className="border-b border-white/10 bg-white/[.03]">
                        {["Time", "", "Session", "Type", "Speakers"].map(
                          (h) => (
                            <th
                              key={h}
                              className="py-3 px-4 text-xs font-semibold uppercase tracking-wider text-gray-500"
                            >
                              {h}
                            </th>
                          )
                        )}
                      </tr>
                    </thead>
                    <tbody>
                      {agendaItems.map((item, i) => {
                        const nowMin = getNowMinutes();
                        const liveIdx = getLiveSessionIndex(nowMin);
                        return (
                          <AgendaRow
                            key={i}
                            item={item}
                            index={i}
                            isLive={i === liveIdx}
                            isPast={liveIdx !== -1 && i < liveIdx}
                          />
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </TabsContent>

              {/* ── Tab: Sessions ── */}
              <TabsContent value="sessions" className="space-y-3 mt-0">
                <SectionHeading
                  icon={<FaMicrophone className="text-primary" />}
                  title="Session Details"
                  subtitle="Click any session to expand its description, key takeaways, and related technologies."
                />
                {sessionHighlights.map((s) => (
                  <SessionCard key={s.id} session={s} />
                ))}
              </TabsContent>

              {/* ── Tab: Projects ── */}
              <TabsContent value="projects" className="mt-0">
                <SectionHeading
                  icon={<FaCode className="text-primary" />}
                  title="Key Projects & Technologies"
                  subtitle="Tools and platforms covered across Innovation Day sessions."
                />
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                  {keyProjects.map((p) => (
                    <ProjectCard key={p.name} project={p} />
                  ))}
                </div>
              </TabsContent>

              {/* ── Tab: Speakers ── */}
              <TabsContent value="speakers" className="mt-0">
                <SectionHeading
                  icon={<FaUsers className="text-primary" />}
                  title="Speakers"
                  subtitle={`${speakers.length} presenters across ${sessionHighlights.length} sessions.`}
                />
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                  {speakers.map((s) => (
                    <SpeakerBadge key={s.name} speaker={s} />
                  ))}
                </div>

                {/* Session breakdown */}
                <div className="mt-6 space-y-3">
                  <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wider">
                    By Session
                  </h3>
                  {sessionHighlights.map((session) => (
                    <div
                      key={session.id}
                      className="flex items-center gap-3 rounded-xl border border-white/10 bg-white/[.02] p-3"
                    >
                      <div
                        className="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0"
                        style={{
                          backgroundColor: `${session.color}22`,
                          color: session.color,
                        }}
                      >
                        {session.icon}
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-white truncate">
                          {session.title}
                        </p>
                      </div>
                      <div className="flex -space-x-2">
                        {session.speakers.slice(0, 4).map((name) => {
                          const sp = speakers.find((s) => s.name === name);
                          return (
                            <div
                              key={name}
                              title={name}
                              className="w-7 h-7 rounded-full border-2 border-background-dark flex items-center justify-center text-white text-[9px] font-bold"
                              style={{ backgroundColor: sp?.color ?? "#6B7280" }}
                            >
                              {sp?.initials ?? name[0]}
                            </div>
                          );
                        })}
                        {session.speakers.length > 4 && (
                          <div className="w-7 h-7 rounded-full border-2 border-background-dark bg-gray-700 flex items-center justify-center text-white text-[9px] font-bold">
                            +{session.speakers.length - 4}
                          </div>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </TabsContent>

              {/* ── Tab: Community ── */}
              <TabsContent value="community" className="mt-0 space-y-6">
                <SectionHeading
                  icon={<FaBullhorn className="text-primary" />}
                  title="Community & Strategic Notes"
                  subtitle="Key focus areas and format changes for the IL AI community in Q2 2026."
                />

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  {communityNotes.map((note) => (
                    <CommunityNoteCard key={note.title} note={note} />
                  ))}
                </div>

                {/* Ambassador spotlight */}
                <div className="rounded-xl border border-blue-500/20 bg-blue-500/5 p-5">
                  <div className="flex items-start gap-4">
                    <div className="w-10 h-10 rounded-xl bg-blue-500/20 flex items-center justify-center text-blue-400 flex-shrink-0">
                      <FaStar className="w-5 h-5" />
                    </div>
                    <div>
                      <h3 className="font-semibold text-white mb-1">
                        AI IL Ambassador Program
                      </h3>
                      <p className="text-sm text-gray-400 leading-relaxed">
                        The IL Ambassador Program fosters cross-team AI knowledge
                        sharing. Ambassadors run internal workshops, publish
                        findings, and liaise with product and engineering
                        leadership to keep the community aligned with Red Hat's
                        AI strategy.
                      </p>
                      <p className="text-xs text-gray-500 mt-2">
                        Presented by{" "}
                        <span className="text-blue-400 font-medium">
                          Ilanit Stein
                        </span>{" "}
                        · 10 min · 12:50 – 13:00
                      </p>
                    </div>
                  </div>
                </div>

                {/* MCP Best Practices callout */}
                <div className="rounded-xl border border-amber-500/20 bg-amber-500/5 p-5">
                  <div className="flex items-start gap-4">
                    <div className="w-10 h-10 rounded-xl bg-amber-500/20 flex items-center justify-center text-amber-400 flex-shrink-0">
                      <FaBolt className="w-5 h-5" />
                    </div>
                    <div>
                      <h3 className="font-semibold text-white mb-1">
                        MCP Best Practices Adoption
                      </h3>
                      <p className="text-sm text-gray-400 leading-relaxed">
                        The IL community is adopting the Model Context Protocol
                        (MCP) as the standard interface for tool-augmented agents.
                        Teams are encouraged to publish MCP-compatible server
                        manifests for all internal tooling going forward.
                      </p>
                    </div>
                  </div>
                </div>
              </TabsContent>
            </Tabs>

            {/* ── Footer note ── */}
            <div className="rounded-xl border border-white/5 bg-white/[.02] p-5 text-center">
              <p className="text-sm text-gray-500">
                🌐 Red Hat Innovation Day is an internal community event bringing
                together engineers, PMs, and AI enthusiasts across the IL site —
                to share work, spark ideas, and build together.
              </p>
              <p className="text-xs text-gray-600 mt-2">
                Simulated page · Data sourced from Jira GENIE ticket ·{" "}
                <span className="text-primary/60">UnifAI IL Q2 2026</span>
              </p>
            </div>
          </motion.div>
        </main>

        <StatusBar />
      </div>
    </div>
  );
}
