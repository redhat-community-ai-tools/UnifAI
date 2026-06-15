import { motion } from "framer-motion";
import { Clock, Coffee, Mic, Users } from "lucide-react";

interface AgendaItem {
  time: string;
  title: string;
  speakers: string[];
  description?: string;
  type: "break" | "talk" | "panel" | "update" | "program";
}

const agendaItems: AgendaItem[] = [
  {
    time: "09:30 – 10:00",
    title: "Coffee and Ma'affee",
    speakers: [],
    type: "break",
  },
  {
    time: "10:00 – 10:05",
    title: "Intro to Innovation Day",
    speakers: ["Hofni Gartner"],
    type: "talk",
  },
  {
    time: "10:05 – 11:00",
    title: "Is Orchestration the Future?",
    speakers: ["Vlad Luzin", "Roy Nissim"],
    description:
      "A2A Communications for multi-agent systems, peer-to-peer collaboration, and overcoming the limits of current multi-agent SDLCs.",
    type: "talk",
  },
  {
    time: "11:00 – 12:00",
    title: "Introduction to Fullsend",
    speakers: ["Barak Korren"],
    description:
      "A living design corpus and shipping platform (MVP) for fully autonomous agentic SDLC on Git forges.",
    type: "talk",
  },
  {
    time: "12:00 – 12:35",
    title: "Skill/Agents Related Quality and Evaluation",
    speakers: [
      "Ella Shulman",
      "Benjamin Kapner",
      "Carmel Soceanu",
      "Guy Ziv",
      "Sharon Dashet",
    ],
    description:
      "Why quality estimation is important. Introduction to Eval-Hub, agent-eval-harness, and the Compass project.",
    type: "panel",
  },
  {
    time: "12:35 – 12:50",
    title: "Updates from UnifAI",
    speakers: ["Nir Rashti", "Odai Odeh"],
    description:
      "Adapting to ADLC flows, focusing on automation and quick setup for individuals and teams.",
    type: "update",
  },
  {
    time: "12:50 – 13:00",
    title: "AI IL Ambassador Program",
    speakers: ["Ilanit Stein"],
    description:
      "Success stories and community updates. Shifting from presentations to workshops and open office hours.",
    type: "program",
  },
];

const typeConfig: Record<
  AgendaItem["type"],
  { color: string; bg: string; border: string; icon: React.ReactNode; label: string }
> = {
  break: {
    color: "text-amber-400",
    bg: "bg-amber-400/10",
    border: "border-amber-400/30",
    icon: <Coffee className="w-4 h-4" />,
    label: "Break",
  },
  talk: {
    color: "text-blue-400",
    bg: "bg-blue-400/10",
    border: "border-blue-400/30",
    icon: <Mic className="w-4 h-4" />,
    label: "Talk",
  },
  panel: {
    color: "text-purple-400",
    bg: "bg-purple-400/10",
    border: "border-purple-400/30",
    icon: <Users className="w-4 h-4" />,
    label: "Panel",
  },
  update: {
    color: "text-primary",
    bg: "bg-primary/10",
    border: "border-primary/30",
    icon: <Mic className="w-4 h-4" />,
    label: "Update",
  },
  program: {
    color: "text-green-400",
    bg: "bg-green-400/10",
    border: "border-green-400/30",
    icon: <Users className="w-4 h-4" />,
    label: "Program",
  },
};

export default function AgendaSection() {
  return (
    <section className="mb-10">
      <div className="flex items-center gap-3 mb-6">
        <Clock className="w-5 h-5 text-primary" />
        <h2 className="text-xl font-semibold text-white">Full Agenda</h2>
      </div>

      <div className="relative">
        {/* Timeline line */}
        <div className="absolute left-[5.5rem] top-0 bottom-0 w-px bg-gradient-to-b from-primary/50 via-gray-700 to-transparent hidden sm:block" />

        <div className="space-y-4">
          {agendaItems.map((item, index) => {
            const config = typeConfig[item.type];
            return (
              <motion.div
                key={index}
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ duration: 0.3, delay: index * 0.06 }}
                className="flex gap-4 sm:gap-6"
              >
                {/* Time column */}
                <div className="flex-shrink-0 w-20 sm:w-[5rem] text-right hidden sm:block">
                  <span className="text-xs text-gray-500 font-mono leading-5 block pt-4">
                    {item.time.split(" – ")[0]}
                  </span>
                  <span className="text-xs text-gray-600 font-mono">
                    {item.time.split(" – ")[1]}
                  </span>
                </div>

                {/* Dot */}
                <div className="relative hidden sm:flex flex-col items-center">
                  <div
                    className={`w-3 h-3 rounded-full border-2 mt-4 flex-shrink-0 z-10 ${config.border} ${config.bg}`}
                  />
                </div>

                {/* Content card */}
                <div
                  className={`flex-1 rounded-xl border p-4 ${config.bg} ${config.border} bg-background-card/60`}
                >
                  {/* Mobile time */}
                  <div className="flex items-center gap-2 mb-2 sm:hidden">
                    <Clock className="w-3 h-3 text-gray-500" />
                    <span className="text-xs text-gray-500 font-mono">{item.time}</span>
                  </div>

                  <div className="flex flex-wrap items-start justify-between gap-2 mb-1">
                    <h3 className="text-white font-semibold text-sm sm:text-base">
                      {item.title}
                    </h3>
                    <span
                      className={`inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full ${config.bg} ${config.color} ${config.border} border`}
                    >
                      {config.icon}
                      {config.label}
                    </span>
                  </div>

                  {item.speakers.length > 0 && (
                    <div className="flex flex-wrap gap-1.5 mb-2">
                      {item.speakers.map((speaker) => (
                        <span
                          key={speaker}
                          className="text-xs px-2 py-0.5 rounded-full bg-gray-800 text-gray-300 border border-gray-700"
                        >
                          {speaker}
                        </span>
                      ))}
                    </div>
                  )}

                  {item.description && (
                    <p className="text-gray-400 text-sm leading-relaxed">
                      {item.description}
                    </p>
                  )}
                </div>
              </motion.div>
            );
          })}
        </div>
      </div>
    </section>
  );
}
