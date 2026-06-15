import { motion } from "framer-motion";
import { Users } from "lucide-react";

interface Speaker {
  name: string;
  role: string;
  talks: string[];
  initials: string;
  color: string;
}

const speakers: Speaker[] = [
  {
    name: "Hofni Gartner",
    role: "Innovation Day Host",
    talks: ["Intro to Innovation Day"],
    initials: "HG",
    color: "from-blue-500 to-blue-700",
  },
  {
    name: "Vlad Luzin",
    role: "AI/ML Engineer",
    talks: ["Is Orchestration the Future?"],
    initials: "VL",
    color: "from-violet-500 to-violet-700",
  },
  {
    name: "Roy Nissim",
    role: "AI/ML Engineer",
    talks: ["Is Orchestration the Future?"],
    initials: "RN",
    color: "from-indigo-500 to-indigo-700",
  },
  {
    name: "Barak Korren",
    role: "Principal Software Engineer",
    talks: ["Introduction to Fullsend"],
    initials: "BK",
    color: "from-cyan-500 to-cyan-700",
  },
  {
    name: "Ella Shulman",
    role: "QE Engineer",
    talks: ["Skill/Agents Related Quality and Evaluation"],
    initials: "ES",
    color: "from-purple-500 to-purple-700",
  },
  {
    name: "Benjamin Kapner",
    role: "QE Engineer",
    talks: ["Skill/Agents Related Quality and Evaluation"],
    initials: "BK",
    color: "from-pink-500 to-pink-700",
  },
  {
    name: "Carmel Soceanu",
    role: "Software Engineer",
    talks: ["Skill/Agents Related Quality and Evaluation"],
    initials: "CS",
    color: "from-rose-500 to-rose-700",
  },
  {
    name: "Guy Ziv",
    role: "Software Engineer",
    talks: ["Skill/Agents Related Quality and Evaluation"],
    initials: "GZ",
    color: "from-orange-500 to-orange-700",
  },
  {
    name: "Sharon Dashet",
    role: "Software Engineer",
    talks: ["Skill/Agents Related Quality and Evaluation"],
    initials: "SD",
    color: "from-amber-500 to-amber-700",
  },
  {
    name: "Nir Rashti",
    role: "Software Engineer – UnifAI",
    talks: ["Updates from UnifAI"],
    initials: "NR",
    color: "from-primary to-red-700",
  },
  {
    name: "Odai Odeh",
    role: "Software Engineer – UnifAI",
    talks: ["Updates from UnifAI"],
    initials: "OO",
    color: "from-red-600 to-red-900",
  },
  {
    name: "Ilanit Stein",
    role: "AI IL Ambassador Program Lead",
    talks: ["AI IL Ambassador Program"],
    initials: "IS",
    color: "from-green-500 to-green-700",
  },
];

export default function SpeakersSection() {
  return (
    <section className="mb-10">
      <div className="flex items-center gap-3 mb-6">
        <Users className="w-5 h-5 text-primary" />
        <h2 className="text-xl font-semibold text-white">Speakers & Presenters</h2>
        <span className="ml-auto text-sm text-gray-500">{speakers.length} speakers</span>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
        {speakers.map((speaker, index) => (
          <motion.div
            key={speaker.name}
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.25, delay: index * 0.04 }}
            className="bg-background-card border border-gray-800 rounded-xl p-4 hover:border-gray-600 transition-colors"
          >
            <div className="flex items-center gap-3 mb-3">
              <div
                className={`w-10 h-10 rounded-full bg-gradient-to-br ${speaker.color} flex items-center justify-center text-white text-sm font-bold flex-shrink-0`}
              >
                {speaker.initials}
              </div>
              <div className="min-w-0">
                <p className="text-white font-medium text-sm truncate">{speaker.name}</p>
                <p className="text-gray-500 text-xs truncate">{speaker.role}</p>
              </div>
            </div>
            <div className="space-y-1">
              {speaker.talks.map((talk) => (
                <p
                  key={talk}
                  className="text-xs text-gray-400 bg-gray-800/50 rounded-lg px-2 py-1 truncate"
                  title={talk}
                >
                  {talk}
                </p>
              ))}
            </div>
          </motion.div>
        ))}
      </div>
    </section>
  );
}
