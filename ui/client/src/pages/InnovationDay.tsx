import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import Sidebar from "@/components/layout/Sidebar";
import Header from "@/components/layout/Header";
import StatusBar from "@/components/layout/StatusBar";
import GlassPanel from "@/components/ui/GlassPanel";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useTheme } from "@/contexts/ThemeContext";
import { cn } from "@/lib/utils";
import {
  Calendar,
  Clock,
  Users,
  ChevronDown,
  ChevronUp,
  MapPin,
  Rocket,
  Brain,
  Code2,
  FlaskConical,
  Bot,
  Layers,
  CheckCircle2,
  Circle,
  PlayCircle,
  Coffee,
  Mic2,
  Star,
  Tag,
  TrendingUp,
  Zap,
  BookOpen,
  Award,
} from "lucide-react";

// ─────────────────────────────────────────────
// Data
// ─────────────────────────────────────────────

interface Speaker {
  name: string;
  initials: string;
  color: string;
}

interface Session {
  id: string;
  startTime: string;
  endTime: string;
  title: string;
  speakers: Speaker[];
  type: "networking" | "intro" | "talk" | "demo" | "update" | "program";
  description: string;
  topics: string[];
  icon: React.ReactNode;
}

const SESSIONS: Session[] = [
  {
    id: "networking",
    startTime: "09:45",
    endTime: "10:00",
    title: "Coffee and Ma'affee",
    speakers: [],
    type: "networking",
    description:
      "Networking session over coffee and ma'affee — meet your fellow Red Hat engineers, share ideas, and kick off the day in true IL-site spirit.",
    topics: ["Networking", "Community"],
    icon: <Coffee className="w-4 h-4" />,
  },
  {
    id: "intro",
    startTime: "10:00",
    endTime: "10:05",
    title: "Intro to Innovation Day",
    speakers: [{ name: "Hofni Gartner", initials: "HG", color: "#8B5CF6" }],
    type: "intro",
    description:
      "Welcome and framing of the day's themes: Agentic orchestration, ADLC, Evaluation, and the journey from AI Ideation to real business value.",
    topics: ["ADLC", "Business Value", "AI Strategy"],
    icon: <Mic2 className="w-4 h-4" />,
  },
  {
    id: "orchestration",
    startTime: "10:05",
    endTime: "11:00",
    title: "Is Orchestration the Future?",
    speakers: [
      { name: "Vlad Luzin", initials: "VL", color: "#3B82F6" },
      { name: "Roy Nissim", initials: "RN", color: "#10B981" },
    ],
    type: "talk",
    description:
      "A deep-dive into agentic orchestration patterns and whether multi-agent orchestration is becoming the dominant paradigm for AI systems. Covers real-world learnings, trade-offs between orchestration frameworks, and what's next for the stack.",
    topics: ["Agentic Orchestration", "Multi-Agent", "LLM Systems", "Architecture"],
    icon: <Layers className="w-4 h-4" />,
  },
  {
    id: "fullsend",
    startTime: "11:00",
    endTime: "12:00",
    title: "Introduction to Fullsend",
    speakers: [{ name: "Barak Korren", initials: "BK", color: "#F59E0B" }],
    type: "demo",
    description:
      "Unveiling Fullsend — the MVP platform designed to accelerate AI-driven development. Live demo covering the core developer experience, integration points, and how it bridges the gap between prototyping and production-grade AI pipelines.",
    topics: ["Fullsend (MVP)", "Developer Experience", "AI Pipelines", "ADLC"],
    icon: <Rocket className="w-4 h-4" />,
  },
  {
    id: "evaluation",
    startTime: "12:00",
    endTime: "12:35",
    title: "Skill/Agents Related Quality and Evaluation",
    speakers: [
      { name: "Ella Shulman", initials: "ES", color: "#EC4899" },
      { name: "Benjamin Kapner", initials: "BK", color: "#6366F1" },
      { name: "Carmel Soceanu", initials: "CS", color: "#14B8A6" },
      { name: "Guy Ziv", initials: "GZ", color: "#F97316" },
      { name: "Sharon Dashet", initials: "SD", color: "#8B5CF6" },
    ],
    type: "talk",
    description:
      "A multi-presenter session covering the full evaluation lifecycle for AI skills and agents. Topics include the Code Agent Harness Evaluation framework, agent-eval-harness internals, eval-hub workflows, and sdg_hub for synthetic data generation.",
    topics: [
      "Code Agent Harness Evaluation",
      "agent-eval-harness",
      "eval-hub",
      "sdg_hub",
      "Quality Assurance",
    ],
    icon: <FlaskConical className="w-4 h-4" />,
  },
  {
    id: "unifai",
    startTime: "12:35",
    endTime: "12:50",
    title: "Updates from UnifAI",
    speakers: [
      { name: "Nir Rashti", initials: "NR", color: "#EF4444" },
      { name: "Odai Odeh", initials: "OO", color: "#3B82F6" },
    ],
    type: "update",
    description:
      "Latest product updates from the UnifAI team: new features, roadmap preview, and a showcase of the Compass Project — the internal initiative aligning AI tooling across Red Hat's IL site.",
    topics: ["UnifAI", "Compass Project", "Product Roadmap"],
    icon: <Bot className="w-4 h-4" />,
  },
  {
    id: "ambassador",
    startTime: "12:50",
    endTime: "13:00",
    title: "AI IL Ambassador Program",
    speakers: [{ name: "Ilanit Stein", initials: "IS", color: "#A855F7" }],
    type: "program",
    description:
      "Introduction to the AI IL Ambassador Program — a community-driven initiative to empower engineers across the IL site to champion AI adoption, share knowledge, and build a sustainable internal AI culture.",
    topics: ["Community", "AI Adoption", "Ambassador Program", "Culture"],
    icon: <Award className="w-4 h-4" />,
  },
];

const KEY_TOPICS = [
  { label: "Code Agent Harness Evaluation", icon: <Code2 className="w-3.5 h-3.5" />, color: "#6366F1" },
  { label: "agent-eval-harness", icon: <FlaskConical className="w-3.5 h-3.5" />, color: "#10B981" },
  { label: "eval-hub", icon: <TrendingUp className="w-3.5 h-3.5" />, color: "#F59E0B" },
  { label: "sdg_hub", icon: <Brain className="w-3.5 h-3.5" />, color: "#EC4899" },
  { label: "Fullsend (MVP)", icon: <Rocket className="w-3.5 h-3.5" />, color: "#EF4444" },
  { label: "UnifAI", icon: <Bot className="w-3.5 h-3.5" />, color: "#8B5CF6" },
  { label: "Compass Project", icon: <MapPin className="w-3.5 h-3.5" />, color: "#3B82F6" },
];

const SESSION_TYPE_STYLES: Record<Session["type"], { label: string; badgeClass: string }> = {
  networking: { label: "Networking", badgeClass: "bg-emerald-500/15 text-emerald-400 border-emerald-500/30" },
  intro:       { label: "Opening",    badgeClass: "bg-purple-500/15 text-purple-400 border-purple-500/30" },
  talk:        { label: "Talk",       badgeClass: "bg-blue-500/15 text-blue-400 border-blue-500/30" },
  demo:        { label: "Demo",       badgeClass: "bg-orange-500/15 text-orange-400 border-orange-500/30" },
  update:      { label: "Update",     badgeClass: "bg-red-500/15 text-red-400 border-red-500/30" },
  program:     { label: "Program",    badgeClass: "bg-pink-500/15 text-pink-400 border-pink-500/30" },
};

// ─────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────

function parseMinutes(time: string): number {
  const [h, m] = time.split(":").map(Number);
  return h * 60 + m;
}

function getSessionStatus(
  session: Session,
  nowMinutes: number,
  attended: Set<string>
): "completed" | "live" | "upcoming" | "attended" {
  if (attended.has(session.id)) return "attended";
  const start = parseMinutes(session.startTime);
  const end = parseMinutes(session.endTime);
  if (nowMinutes >= end) return "completed";
  if (nowMinutes >= start) return "live";
  return "upcoming";
}

// ─────────────────────────────────────────────
// Sub-components
// ─────────────────────────────────────────────

function SpeakerAvatar({ speaker, size = "md" }: { speaker: Speaker; size?: "sm" | "md" | "lg" }) {
  const sizeClass = size === "sm" ? "w-7 h-7 text-xs" : size === "lg" ? "w-12 h-12 text-sm" : "w-9 h-9 text-xs";
  return (
    <div
      className={cn("rounded-full flex items-center justify-center font-semibold text-white flex-shrink-0 ring-2 ring-background", sizeClass)}
      style={{ background: `linear-gradient(135deg, ${speaker.color}cc, ${speaker.color}55)`, boxShadow: `0 0 8px ${speaker.color}40` }}
      title={speaker.name}
    >
      {speaker.initials}
    </div>
  );
}

function StatusIndicator({ status }: { status: "completed" | "live" | "upcoming" | "attended" }) {
  if (status === "live")
    return (
      <span className="flex items-center gap-1.5 text-xs font-semibold text-emerald-400">
        <motion.span
          className="w-2 h-2 rounded-full bg-emerald-400"
          animate={{ opacity: [1, 0.3, 1] }}
          transition={{ duration: 1.2, repeat: Infinity }}
        />
        LIVE
      </span>
    );
  if (status === "attended")
    return (
      <span className="flex items-center gap-1.5 text-xs font-semibold text-purple-400">
        <CheckCircle2 className="w-3.5 h-3.5" />
        Attended
      </span>
    );
  if (status === "completed")
    return (
      <span className="flex items-center gap-1.5 text-xs text-gray-500">
        <CheckCircle2 className="w-3.5 h-3.5" />
        Ended
      </span>
    );
  return (
    <span className="flex items-center gap-1.5 text-xs text-gray-500">
      <Circle className="w-3.5 h-3.5" />
      Upcoming
    </span>
  );
}

// ─────────────────────────────────────────────
// Session Card
// ─────────────────────────────────────────────

interface SessionCardProps {
  session: Session;
  status: "completed" | "live" | "upcoming" | "attended";
  isExpanded: boolean;
  onToggle: () => void;
  onMarkAttended: () => void;
  onUnmarkAttended: () => void;
  index: number;
}

function SessionCard({ session, status, isExpanded, onToggle, onMarkAttended, onUnmarkAttended, index }: SessionCardProps) {
  const typeStyle = SESSION_TYPE_STYLES[session.type];
  const isLive = status === "live";
  const isAttended = status === "attended";

  return (
    <motion.div
      initial={{ opacity: 0, x: -20 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.4, delay: index * 0.07 }}
      className={cn(
        "relative rounded-xl border transition-all duration-300",
        isLive
          ? "border-emerald-500/50 bg-emerald-500/5 shadow-[0_0_20px_rgba(16,185,129,0.08)]"
          : isAttended
          ? "border-purple-500/40 bg-purple-500/5"
          : "border-gray-800 bg-card hover:border-gray-700"
      )}
    >
      {/* Live accent bar */}
      {isLive && (
        <div className="absolute left-0 top-0 bottom-0 w-1 rounded-l-xl bg-emerald-400" />
      )}
      {isAttended && (
        <div className="absolute left-0 top-0 bottom-0 w-1 rounded-l-xl bg-purple-500" />
      )}

      {/* Card Header — always visible */}
      <button
        className="w-full text-left p-4 pl-5 focus:outline-none"
        onClick={onToggle}
        aria-expanded={isExpanded}
      >
        <div className="flex items-start justify-between gap-3">
          {/* Time + Icon */}
          <div className="flex items-start gap-3 min-w-0">
            <div className="flex flex-col items-center flex-shrink-0 pt-0.5">
              <span className="text-xs font-mono text-gray-400 whitespace-nowrap">{session.startTime}</span>
              <div className="w-px h-3 bg-gray-700 my-0.5" />
              <span className="text-xs font-mono text-gray-500 whitespace-nowrap">{session.endTime}</span>
            </div>

            <div
              className="mt-0.5 p-2 rounded-lg flex-shrink-0"
              style={{ backgroundColor: "rgba(255,255,255,0.05)" }}
            >
              {session.icon}
            </div>

            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2 mb-1">
                <span
                  className={cn(
                    "inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold border",
                    typeStyle.badgeClass
                  )}
                >
                  {typeStyle.label}
                </span>
                <StatusIndicator status={status} />
              </div>
              <h3 className="font-semibold text-white text-sm leading-snug">{session.title}</h3>

              {/* Speakers preview */}
              {session.speakers.length > 0 && (
                <div className="flex items-center gap-2 mt-1.5">
                  <div className="flex -space-x-2">
                    {session.speakers.slice(0, 3).map((s) => (
                      <SpeakerAvatar key={s.name} speaker={s} size="sm" />
                    ))}
                    {session.speakers.length > 3 && (
                      <div className="w-7 h-7 rounded-full bg-gray-700 ring-2 ring-background flex items-center justify-center text-[10px] text-gray-400 font-medium">
                        +{session.speakers.length - 3}
                      </div>
                    )}
                  </div>
                  <span className="text-xs text-gray-400">
                    {session.speakers.map((s) => s.name).join(", ")}
                  </span>
                </div>
              )}
            </div>
          </div>

          {/* Chevron */}
          <div className="flex-shrink-0 mt-1 text-gray-500">
            {isExpanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
          </div>
        </div>
      </button>

      {/* Expanded Details */}
      <AnimatePresence>
        {isExpanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.25, ease: "easeInOut" }}
            className="overflow-hidden"
          >
            <div className="px-5 pb-4 pt-0 border-t border-gray-800/60">
              <div className="pt-3 space-y-4">
                {/* Description */}
                <p className="text-sm text-gray-300 leading-relaxed">{session.description}</p>

                {/* Speakers (detailed) */}
                {session.speakers.length > 0 && (
                  <div>
                    <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">
                      Speakers
                    </p>
                    <div className="flex flex-wrap gap-2">
                      {session.speakers.map((s) => (
                        <div
                          key={s.name}
                          className="flex items-center gap-2 px-3 py-1.5 rounded-full border border-gray-800 bg-background/50"
                        >
                          <SpeakerAvatar speaker={s} size="sm" />
                          <span className="text-xs text-gray-200 font-medium">{s.name}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Topics */}
                <div>
                  <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">
                    Topics
                  </p>
                  <div className="flex flex-wrap gap-1.5">
                    {session.topics.map((t) => (
                      <span
                        key={t}
                        className="inline-flex items-center gap-1 px-2 py-1 rounded-md text-xs bg-gray-800/70 text-gray-300 border border-gray-700/50"
                      >
                        <Tag className="w-3 h-3 text-gray-500" />
                        {t}
                      </span>
                    ))}
                  </div>
                </div>

                {/* Attend action */}
                <div className="flex items-center gap-2 pt-1">
                  {isAttended ? (
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={(e) => { e.stopPropagation(); onUnmarkAttended(); }}
                      className="text-xs h-7 border-purple-500/40 text-purple-400 hover:bg-purple-500/10"
                    >
                      <CheckCircle2 className="w-3 h-3 mr-1.5" />
                      Marked as Attended
                    </Button>
                  ) : (
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={(e) => { e.stopPropagation(); onMarkAttended(); }}
                      className="text-xs h-7 border-gray-700 text-gray-300 hover:bg-gray-800 hover:text-white"
                    >
                      <Circle className="w-3 h-3 mr-1.5" />
                      Mark as Attended
                    </Button>
                  )}
                  {isLive && (
                    <span className="text-xs text-emerald-400 flex items-center gap-1">
                      <PlayCircle className="w-3.5 h-3.5" />
                      Session in progress
                    </span>
                  )}
                </div>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}

// ─────────────────────────────────────────────
// Speakers Grid
// ─────────────────────────────────────────────

function SpeakersGrid() {
  const allSpeakers = SESSIONS.flatMap((s) =>
    s.speakers.map((sp) => ({ ...sp, sessionTitle: s.title, sessionId: s.id }))
  );
  // Deduplicate by name
  const uniqueSpeakers = allSpeakers.filter(
    (sp, idx, arr) => arr.findIndex((x) => x.name === sp.name) === idx
  );

  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4">
      {uniqueSpeakers.map((sp, i) => (
        <motion.div
          key={sp.name}
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.35, delay: i * 0.06 }}
        >
          <GlassPanel className="items-center text-center p-4 gap-3 hover:border-gray-700 transition-colors cursor-default border border-gray-800/60">
            <SpeakerAvatar speaker={sp} size="lg" />
            <div>
              <p className="font-semibold text-sm text-white mt-2">{sp.name}</p>
              <p className="text-xs text-gray-500 mt-0.5 leading-snug">{sp.sessionTitle}</p>
            </div>
          </GlassPanel>
        </motion.div>
      ))}
    </div>
  );
}

// ─────────────────────────────────────────────
// Topics Grid
// ─────────────────────────────────────────────

function TopicsGrid() {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
      {KEY_TOPICS.map((topic, i) => (
        <motion.div
          key={topic.label}
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.35, delay: i * 0.07 }}
        >
          <div
            className="flex items-center gap-3 p-4 rounded-xl border border-gray-800 bg-card hover:border-gray-700 transition-colors"
          >
            <div
              className="p-2.5 rounded-lg flex-shrink-0"
              style={{ backgroundColor: `${topic.color}20`, color: topic.color }}
            >
              {topic.icon}
            </div>
            <span className="text-sm font-medium text-gray-200">{topic.label}</span>
          </div>
        </motion.div>
      ))}
    </div>
  );
}

// ─────────────────────────────────────────────
// Progress Stats
// ─────────────────────────────────────────────

interface ProgressBarProps {
  label: string;
  value: number;
  max: number;
  color: string;
}

function ProgressBar({ label, value, max, color }: ProgressBarProps) {
  const pct = max === 0 ? 0 : Math.round((value / max) * 100);
  return (
    <div className="space-y-1">
      <div className="flex justify-between text-xs text-gray-400">
        <span>{label}</span>
        <span className="font-mono">
          {value}/{max}
        </span>
      </div>
      <div className="h-2 rounded-full bg-gray-800 overflow-hidden">
        <motion.div
          className="h-full rounded-full"
          style={{ backgroundColor: color }}
          initial={{ width: 0 }}
          animate={{ width: `${pct}%` }}
          transition={{ duration: 0.8, ease: "easeOut" }}
        />
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────
// Main Page
// ─────────────────────────────────────────────

export default function InnovationDay() {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [expandedSession, setExpandedSession] = useState<string | null>("orchestration");
  const [attended, setAttended] = useState<Set<string>>(new Set());
  const { primaryHex } = useTheme();

  // Simulate "current time" as 11:30 on event day for demo purposes
  // (June 16, 2026 is today, so the event is happening right now)
  const [simulatedMinutes, setSimulatedMinutes] = useState<number>(() => {
    const now = new Date();
    return now.getHours() * 60 + now.getMinutes();
  });

  // Advance simulated time every minute
  useEffect(() => {
    const id = setInterval(() => {
      setSimulatedMinutes((m) => m + 1);
    }, 60_000);
    return () => clearInterval(id);
  }, []);

  const markAttended = (id: string) => setAttended((prev) => new Set([...prev, id]));
  const unmarkAttended = (id: string) =>
    setAttended((prev) => {
      const next = new Set(prev);
      next.delete(id);
      return next;
    });

  const toggleSession = (id: string) =>
    setExpandedSession((prev) => (prev === id ? null : id));

  // Stats
  const totalSessions = SESSIONS.length;
  const attendedCount = attended.size;
  const sessionsCompleted = SESSIONS.filter((s) => {
    const st = getSessionStatus(s, simulatedMinutes, attended);
    return st === "completed" || st === "attended";
  }).length;
  const liveNow = SESSIONS.find((s) => getSessionStatus(s, simulatedMinutes, attended) === "live");

  // Hero time display
  const eventDateStr = "Tuesday, June 16th, 2026";
  const eventTimeStr = "09:30 – 13:15";

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar />

      <div className="flex-1 flex flex-col overflow-hidden">
        <Header
          title="Innovation Day · IL Site"
          onToggleSidebar={() => setSidebarOpen(!sidebarOpen)}
        />

        <main className="flex-1 overflow-y-auto bg-background-dark p-6">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
            className="max-w-5xl mx-auto space-y-8"
          >
            {/* ── Hero Section ── */}
            <GlassPanel strong className="relative overflow-hidden">
              {/* Background glow */}
              <div
                className="absolute -top-16 -right-16 w-64 h-64 rounded-full opacity-10 blur-3xl pointer-events-none"
                style={{ background: `radial-gradient(circle, ${primaryHex || "#A60000"}, transparent)` }}
              />
              <div
                className="absolute -bottom-12 -left-12 w-48 h-48 rounded-full opacity-8 blur-3xl pointer-events-none"
                style={{ background: `radial-gradient(circle, #3B82F6, transparent)` }}
              />

              <div className="relative z-10">
                {/* Red Hat badge */}
                <div className="flex items-center gap-2 mb-4">
                  <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-red-600/20 text-red-400 border border-red-600/30 tracking-wide">
                    <span className="w-2 h-2 rounded-full bg-red-500" />
                    RED HAT IL SITE
                  </span>
                  <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">
                    <motion.span
                      className="w-1.5 h-1.5 rounded-full bg-emerald-400"
                      animate={{ opacity: [1, 0.3, 1] }}
                      transition={{ duration: 1.5, repeat: Infinity }}
                    />
                    LIVE TODAY
                  </span>
                </div>

                <h1 className="text-3xl sm:text-4xl font-heading font-bold text-white mb-2 leading-tight">
                  🚀 Innovation Day <span className="text-primary">Q2 2026</span>
                </h1>

                <p className="text-base text-gray-300 mb-6 max-w-2xl leading-relaxed">
                  Agentic orchestration, ADLC, Evaluation, and transitioning from{" "}
                  <em className="text-white not-italic font-medium">AI Ideation to business value</em>.
                </p>

                {/* Meta row */}
                <div className="flex flex-wrap items-center gap-4 text-sm text-gray-400">
                  <span className="flex items-center gap-2">
                    <Calendar className="w-4 h-4 text-primary" />
                    {eventDateStr}
                  </span>
                  <span className="flex items-center gap-2">
                    <Clock className="w-4 h-4 text-primary" />
                    {eventTimeStr}
                  </span>
                  <span className="flex items-center gap-2">
                    <MapPin className="w-4 h-4 text-primary" />
                    IL Site
                  </span>
                  <span className="flex items-center gap-2">
                    <Users className="w-4 h-4 text-primary" />
                    {SESSIONS.flatMap((s) => s.speakers).filter(
                      (sp, i, arr) => arr.findIndex((x) => x.name === sp.name) === i
                    ).length}{" "}
                    speakers · {totalSessions} sessions
                  </span>
                </div>

                {/* Live session callout */}
                {liveNow && (
                  <motion.div
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="mt-5 flex items-center gap-3 px-4 py-3 rounded-xl border border-emerald-500/30 bg-emerald-500/8"
                  >
                    <motion.div
                      className="w-3 h-3 rounded-full bg-emerald-400 flex-shrink-0"
                      animate={{ scale: [1, 1.3, 1] }}
                      transition={{ duration: 1.5, repeat: Infinity }}
                    />
                    <div>
                      <span className="text-xs font-bold text-emerald-400 uppercase tracking-wider">
                        Now Live
                      </span>
                      <p className="text-sm text-white font-medium">{liveNow.title}</p>
                      <p className="text-xs text-gray-400">
                        {liveNow.startTime} – {liveNow.endTime} ·{" "}
                        {liveNow.speakers.map((s) => s.name).join(", ") || "All attendees"}
                      </p>
                    </div>
                  </motion.div>
                )}
              </div>
            </GlassPanel>

            {/* ── Stats Row ── */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
              {[
                {
                  label: "Sessions",
                  value: totalSessions,
                  icon: <BookOpen className="w-5 h-5" />,
                  color: primaryHex || "#8B5CF6",
                },
                {
                  label: "Speakers",
                  value: SESSIONS.flatMap((s) => s.speakers).filter(
                    (sp, i, arr) => arr.findIndex((x) => x.name === sp.name) === i
                  ).length,
                  icon: <Users className="w-5 h-5" />,
                  color: "#3B82F6",
                },
                {
                  label: "Topics",
                  value: KEY_TOPICS.length,
                  icon: <Tag className="w-5 h-5" />,
                  color: "#F59E0B",
                },
                {
                  label: "Attended",
                  value: attendedCount,
                  icon: <Star className="w-5 h-5" />,
                  color: "#10B981",
                },
              ].map((stat, i) => (
                <motion.div
                  key={stat.label}
                  initial={{ opacity: 0, y: 12 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.4, delay: i * 0.08 }}
                >
                  <div className="rounded-xl border border-gray-800 bg-card p-4 flex items-center gap-3">
                    <div
                      className="p-2 rounded-lg flex-shrink-0"
                      style={{ backgroundColor: `${stat.color}20`, color: stat.color }}
                    >
                      {stat.icon}
                    </div>
                    <div>
                      <p className="text-2xl font-bold text-white font-mono">{stat.value}</p>
                      <p className="text-xs text-gray-500">{stat.label}</p>
                    </div>
                  </div>
                </motion.div>
              ))}
            </div>

            {/* ── Tabs ── */}
            <Tabs defaultValue="agenda" className="w-full">
              <TabsList className="mb-6 bg-background-card border border-gray-800">
                <TabsTrigger
                  value="agenda"
                  className="data-[state=active]:bg-primary data-[state=active]:text-white"
                >
                  <Clock className="w-3.5 h-3.5 mr-1.5" />
                  Agenda
                </TabsTrigger>
                <TabsTrigger
                  value="speakers"
                  className="data-[state=active]:bg-primary data-[state=active]:text-white"
                >
                  <Users className="w-3.5 h-3.5 mr-1.5" />
                  Speakers
                </TabsTrigger>
                <TabsTrigger
                  value="topics"
                  className="data-[state=active]:bg-primary data-[state=active]:text-white"
                >
                  <Tag className="w-3.5 h-3.5 mr-1.5" />
                  Key Topics
                </TabsTrigger>
                <TabsTrigger
                  value="tracking"
                  className="data-[state=active]:bg-primary data-[state=active]:text-white"
                >
                  <TrendingUp className="w-3.5 h-3.5 mr-1.5" />
                  My Progress
                </TabsTrigger>
              </TabsList>

              {/* Agenda Tab */}
              <TabsContent value="agenda">
                <div className="space-y-3">
                  {SESSIONS.map((session, i) => {
                    const status = getSessionStatus(session, simulatedMinutes, attended);
                    return (
                      <SessionCard
                        key={session.id}
                        session={session}
                        status={status}
                        isExpanded={expandedSession === session.id}
                        onToggle={() => toggleSession(session.id)}
                        onMarkAttended={() => markAttended(session.id)}
                        onUnmarkAttended={() => unmarkAttended(session.id)}
                        index={i}
                      />
                    );
                  })}
                </div>
              </TabsContent>

              {/* Speakers Tab */}
              <TabsContent value="speakers">
                <SpeakersGrid />
              </TabsContent>

              {/* Topics Tab */}
              <TabsContent value="topics">
                <div className="space-y-6">
                  <p className="text-sm text-gray-400">
                    Key technology areas and projects featured across today's sessions.
                  </p>
                  <TopicsGrid />
                </div>
              </TabsContent>

              {/* Tracking Tab */}
              <TabsContent value="tracking">
                <div className="space-y-6">
                  <GlassPanel>
                    <h3 className="text-base font-semibold text-white mb-5">Session Tracker</h3>
                    <div className="space-y-4">
                      <ProgressBar
                        label="Sessions attended"
                        value={attendedCount}
                        max={totalSessions}
                        color="#8B5CF6"
                      />
                      <ProgressBar
                        label="Sessions completed (by time)"
                        value={sessionsCompleted}
                        max={totalSessions}
                        color="#10B981"
                      />
                    </div>

                    {/* Session status list */}
                    <div className="mt-6 space-y-2">
                      {SESSIONS.map((session) => {
                        const status = getSessionStatus(session, simulatedMinutes, attended);
                        return (
                          <div
                            key={session.id}
                            className="flex items-center justify-between py-2 border-b border-gray-800/60 last:border-0"
                          >
                            <div className="flex items-center gap-3 min-w-0">
                              <span className="text-xs font-mono text-gray-500 flex-shrink-0">
                                {session.startTime}
                              </span>
                              <span className="text-sm text-gray-300 truncate">{session.title}</span>
                            </div>
                            <div className="flex-shrink-0 ml-3">
                              <StatusIndicator status={status} />
                            </div>
                          </div>
                        );
                      })}
                    </div>

                    {/* CTA to mark all */}
                    <div className="mt-5 flex flex-wrap gap-2">
                      <Button
                        size="sm"
                        variant="outline"
                        className="text-xs border-gray-700 text-gray-300 hover:bg-gray-800"
                        onClick={() =>
                          SESSIONS.forEach((s) => markAttended(s.id))
                        }
                      >
                        <CheckCircle2 className="w-3.5 h-3.5 mr-1.5" />
                        Mark All Attended
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        className="text-xs text-gray-500 hover:text-gray-300"
                        onClick={() => setAttended(new Set())}
                      >
                        Clear All
                      </Button>
                    </div>
                  </GlassPanel>

                  {/* Quick summary card */}
                  {attendedCount > 0 && (
                    <motion.div
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                    >
                      <GlassPanel className="border border-purple-500/20 bg-purple-500/5">
                        <div className="flex items-start gap-4">
                          <div className="p-3 rounded-xl bg-purple-500/15 text-purple-400 flex-shrink-0">
                            <Zap className="w-5 h-5" />
                          </div>
                          <div>
                            <p className="font-semibold text-white text-sm">
                              You've tracked {attendedCount} of {totalSessions} sessions!
                            </p>
                            <p className="text-xs text-gray-400 mt-1">
                              Topics covered:{" "}
                              {[
                                ...new Set(
                                  SESSIONS.filter((s) => attended.has(s.id)).flatMap(
                                    (s) => s.topics
                                  )
                                ),
                              ].join(", ")}
                            </p>
                          </div>
                        </div>
                      </GlassPanel>
                    </motion.div>
                  )}
                </div>
              </TabsContent>
            </Tabs>
          </motion.div>
        </main>

        <StatusBar />
      </div>
    </div>
  );
}
