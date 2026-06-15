import { useState } from "react";
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
} from "react-icons/fa";

import Sidebar from "@/components/layout/Sidebar";
import Header from "@/components/layout/Header";
import StatusBar from "@/components/layout/StatusBar";

/* ─────────────────────────────── data ─────────────────────────────── */

const agendaItems = [
  {
    time: "09:30–10:00",
    title: "Coffee and Ma'affee",
    speakers: [],
    icon: "☕",
  },
  {
    time: "10:00–10:05",
    title: "Intro to Innovation Day",
    speakers: ["Hofni Gartner"],
    icon: "👋",
  },
  {
    time: "10:05–11:00",
    title: "Is Orchestration the Future?",
    speakers: ["Vlad Luzin", "Roy Nissim"],
    icon: "🔗",
  },
  {
    time: "11:00–12:00",
    title: "Introduction to Fullsend",
    speakers: ["Barak Korren"],
    icon: "🚀",
  },
  {
    time: "12:00–12:35",
    title: "Skill/Agents Related Quality and Evaluation",
    speakers: [
      "Ella Shulman",
      "Benjamin Kapner",
      "Carmel Soceanu",
      "Guy Ziv",
      "Sharon Dashet",
    ],
    icon: "🧪",
  },
  {
    time: "12:35–12:50",
    title: "Updates from UnifAI",
    speakers: ["Nir Rashti", "Odai Odeh"],
    icon: "🤖",
  },
  {
    time: "12:50–13:00",
    title: "AI IL Ambassador Program",
    speakers: ["Ilanit Stein"],
    icon: "🌟",
  },
];

interface SessionDetail {
  id: number;
  title: string;
  speakers: string[];
  icon: React.ReactNode;
  color: string;
  points: string[];
}

const sessionHighlights: SessionDetail[] = [
  {
    id: 1,
    title: "Is Orchestration the Future?",
    speakers: ["Vlad Luzin", "Roy Nissim"],
    icon: <FaProjectDiagram className="w-5 h-5" />,
    color: "#8B5CF6",
    points: [
      "A2A (Agent-to-Agent) Communications for multi-agent systems",
      "Peer-to-peer collaboration between agents",
      "Overcoming the limits of current multi-agent SDLCs",
    ],
  },
  {
    id: 2,
    title: "Introduction to Fullsend",
    speakers: ["Barak Korren"],
    icon: <FaRocket className="w-5 h-5" />,
    color: "#F59E0B",
    points: [
      "A living design corpus and shipping platform (MVP)",
      "Designed for fully autonomous agentic SDLC on Git forges",
    ],
  },
  {
    id: 3,
    title: "Skill/Agents Related Quality and Evaluation",
    speakers: [
      "Ella Shulman",
      "Benjamin Kapner",
      "Carmel Soceanu",
      "Guy Ziv",
      "Sharon Dashet",
    ],
    icon: <FaFlask className="w-5 h-5" />,
    color: "#10B981",
    points: [
      "Why quality estimation matters in agentic workflows",
      "Intro to Eval-Hub, agent-eval-harness, and the Compass project",
    ],
  },
  {
    id: 4,
    title: "Updates from UnifAI",
    speakers: ["Nir Rashti", "Odai Odeh"],
    icon: <FaCode className="w-5 h-5" />,
    color: "#EF4444",
    points: [
      "Adapting to ADLC flows",
      "Focusing on automation and quick setup for individuals and teams",
    ],
  },
  {
    id: 5,
    title: "AI IL Ambassador Program",
    speakers: ["Ilanit Stein"],
    icon: <FaStar className="w-5 h-5" />,
    color: "#3B82F6",
    points: ["Success stories and community updates"],
  },
];

interface KeyProject {
  name: string;
  description: string;
  icon: React.ReactNode;
  tag: string;
}

const keyProjects: KeyProject[] = [
  {
    name: "Code Agent Harness Evaluation",
    description:
      "Tools to check if code agent setups are working, safe, and internally consistent.",
    icon: <FaCode className="w-4 h-4" />,
    tag: "Evaluation",
  },
  {
    name: "agent-eval-harness",
    description:
      "Evaluation framework for AI agent skills against test datasets.",
    icon: <FaFlask className="w-4 h-4" />,
    tag: "Framework",
  },
  {
    name: "eval-hub",
    description:
      "Lightweight REST API service for orchestrating AI model evaluations.",
    icon: <FaProjectDiagram className="w-4 h-4" />,
    tag: "API",
  },
  {
    name: "sdg_hub",
    description:
      "Python framework for building synthetic data generation pipelines.",
    icon: <FaLightbulb className="w-4 h-4" />,
    tag: "Framework",
  },
  {
    name: "Community Updates",
    description:
      "Shifting from presentations to workshops and open office hours.",
    icon: <FaUsers className="w-4 h-4" />,
    tag: "Community",
  },
];

const themeTags = [
  "Agentic Orchestration",
  "ADLC",
  "Evaluation",
  "AI to Business Value",
];

/* ─────────────────────────── components ───────────────────────────── */

function InfoChip({
  icon,
  label,
}: {
  icon: React.ReactNode;
  label: string;
}) {
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

function AgendaRow({
  item,
  index,
}: {
  item: (typeof agendaItems)[0];
  index: number;
}) {
  return (
    <motion.tr
      initial={{ opacity: 0, x: -20 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.3, delay: index * 0.05 }}
      className="border-b border-white/5 hover:bg-white/[.03] transition-colors"
    >
      <td className="py-3 px-4 text-xs font-mono text-gray-400 whitespace-nowrap">
        {item.time}
      </td>
      <td className="py-3 px-4 text-lg">{item.icon}</td>
      <td className="py-3 px-4 font-medium text-white">{item.title}</td>
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
      >
        <div
          className="flex-shrink-0 w-9 h-9 rounded-lg flex items-center justify-center"
          style={{ backgroundColor: `${session.color}22`, color: session.color }}
        >
          {session.icon}
        </div>
        <div className="flex-1 min-w-0">
          <p className="font-semibold text-white truncate">{session.title}</p>
          <p className="text-xs text-gray-500 mt-0.5">
            {session.speakers.join(" · ")}
          </p>
        </div>
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
            <ul className="px-5 pb-4 space-y-2">
              {session.points.map((pt, i) => (
                <li key={i} className="flex items-start gap-2 text-sm text-gray-400">
                  <span
                    className="mt-1.5 w-1.5 h-1.5 rounded-full flex-shrink-0"
                    style={{ backgroundColor: session.color }}
                  />
                  {pt}
                </li>
              ))}
            </ul>
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
      className="rounded-xl border border-white/10 bg-white/[.03] p-4 flex flex-col gap-2 hover:border-primary/40 transition-colors"
    >
      <div className="flex items-center justify-between">
        <div className="w-8 h-8 rounded-lg bg-primary/15 flex items-center justify-center text-primary">
          {project.icon}
        </div>
        <span className="text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full bg-white/5 text-gray-500 border border-white/10">
          {project.tag}
        </span>
      </div>
      <p className="font-semibold text-white text-sm">{project.name}</p>
      <p className="text-xs text-gray-500 leading-relaxed">{project.description}</p>
    </motion.div>
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
            className="max-w-5xl mx-auto space-y-8"
          >
            {/* ── Hero Banner ── */}
            <div className="relative rounded-2xl overflow-hidden border border-white/10 bg-gradient-to-br from-[#1a0a2e] via-[#0D1117] to-[#0a1a2e] p-8">
              {/* decorative blobs */}
              <div className="absolute top-0 right-0 w-64 h-64 bg-primary/10 rounded-full blur-3xl pointer-events-none" />
              <div className="absolute bottom-0 left-0 w-48 h-48 bg-blue-600/10 rounded-full blur-3xl pointer-events-none" />

              <div className="relative z-10">
                <div className="flex items-center gap-2 mb-3">
                  <span className="text-3xl">🚀</span>
                  <span className="text-xs font-bold uppercase tracking-widest text-primary/70 border border-primary/30 rounded-full px-3 py-1 bg-primary/10">
                    Red Hat Event
                  </span>
                </div>

                <h1 className="text-3xl md:text-4xl font-heading font-bold text-white leading-tight">
                  Red Hat Innovation Day
                  <br />
                  <span className="text-primary">Q2 2026 — IL Site</span>
                </h1>

                <p className="mt-3 text-gray-400 max-w-xl">
                  A half-day gathering for the Israel site focused on agentic
                  orchestration, ADLC, quality evaluation, and the journey from
                  AI ideation to real business value.
                </p>

                {/* Info chips */}
                <div className="mt-6 flex flex-wrap gap-3">
                  <InfoChip
                    icon={<FaCalendarAlt />}
                    label="Tuesday, June 16th, 2026"
                  />
                  <InfoChip icon={<FaClock />} label="09:30 – 13:15" />
                  <InfoChip
                    icon={<FaMapMarkerAlt />}
                    label="IL (Israel) Site"
                  />
                </div>

                {/* Theme tags */}
                <div className="mt-4 flex flex-wrap gap-2">
                  {themeTags.map((t) => (
                    <ThemeTag key={t} label={t} />
                  ))}
                </div>
              </div>
            </div>

            {/* ── Agenda ── */}
            <section>
              <SectionHeading
                icon={<FaCalendarAlt className="text-primary" />}
                title="Agenda"
              />
              <div className="rounded-xl border border-white/10 bg-white/[.02] overflow-hidden">
                <table className="w-full text-left">
                  <thead>
                    <tr className="border-b border-white/10 bg-white/[.03]">
                      <th className="py-3 px-4 text-xs font-semibold uppercase tracking-wider text-gray-500">
                        Time
                      </th>
                      <th className="py-3 px-4 text-xs font-semibold uppercase tracking-wider text-gray-500">
                        &nbsp;
                      </th>
                      <th className="py-3 px-4 text-xs font-semibold uppercase tracking-wider text-gray-500">
                        Session
                      </th>
                      <th className="py-3 px-4 text-xs font-semibold uppercase tracking-wider text-gray-500">
                        Speakers
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {agendaItems.map((item, i) => (
                      <AgendaRow key={i} item={item} index={i} />
                    ))}
                  </tbody>
                </table>
              </div>
            </section>

            {/* ── Session Highlights ── */}
            <section>
              <SectionHeading
                icon={<FaMicrophone className="text-primary" />}
                title="Session Highlights"
              />
              <div className="space-y-3">
                {sessionHighlights.map((s) => (
                  <SessionCard key={s.id} session={s} />
                ))}
              </div>
            </section>

            {/* ── Key Topics & Projects ── */}
            <section>
              <SectionHeading
                icon={<FaLightbulb className="text-primary" />}
                title="Key Topics & Projects"
              />
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                {keyProjects.map((p) => (
                  <ProjectCard key={p.name} project={p} />
                ))}
              </div>
            </section>

            {/* ── Footer note ── */}
            <div className="rounded-xl border border-white/5 bg-white/[.02] p-5 text-center">
              <p className="text-sm text-gray-500">
                🌐 Red Hat Innovation Day is an internal community event that
                brings together engineers, PMs, and AI enthusiasts across the IL
                site to share work, spark ideas, and build together.
              </p>
            </div>
          </motion.div>
        </main>

        <StatusBar />
      </div>
    </div>
  );
}

function SectionHeading({
  icon,
  title,
}: {
  icon: React.ReactNode;
  title: string;
}) {
  return (
    <div className="flex items-center gap-2 mb-4">
      {icon}
      <h2 className="text-lg font-heading font-bold text-white">{title}</h2>
    </div>
  );
}
