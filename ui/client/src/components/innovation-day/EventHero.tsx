import { motion } from "framer-motion";
import { Calendar, Clock, MapPin, Zap } from "lucide-react";

export default function EventHero() {
  return (
    <motion.div
      initial={{ opacity: 0, y: -10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
      className="mb-10"
    >
      {/* Hero banner */}
      <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-[#A60000]/30 via-[#1a1a2e] to-[#0D1117] border border-red-900/30 p-8 mb-6">
        {/* Background decorative elements */}
        <div className="absolute top-0 right-0 w-64 h-64 bg-primary/5 rounded-full blur-3xl -translate-y-1/2 translate-x-1/2" />
        <div className="absolute bottom-0 left-0 w-48 h-48 bg-secondary/5 rounded-full blur-3xl translate-y-1/2 -translate-x-1/2" />

        <div className="relative z-10">
          {/* Badge */}
          <div className="flex items-center gap-2 mb-4">
            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-primary/20 border border-primary/30 text-primary text-xs font-semibold tracking-wider uppercase">
              <Zap className="w-3 h-3" />
              Innovation Day Q2 2026
            </span>
            <span className="inline-flex items-center px-3 py-1 rounded-full bg-green-500/10 border border-green-500/20 text-green-400 text-xs font-medium">
              IL Site
            </span>
          </div>

          {/* Title */}
          <h1 className="text-4xl font-bold text-white mb-3 leading-tight">
            Red Hat Innovation Day
            <br />
            <span className="text-primary">Q2 2026</span>
          </h1>
          <p className="text-gray-300 text-lg max-w-3xl mb-6">
            Agentic orchestration, ADLC, Evaluation, and transitioning from{" "}
            <span className="text-white font-medium">"AI Ideation to Business Value"</span>.
            A half-day of cutting-edge talks and live demos from the IL engineering community.
          </p>

          {/* Event meta */}
          <div className="flex flex-wrap gap-6">
            <div className="flex items-center gap-2 text-gray-300">
              <Calendar className="w-4 h-4 text-primary" />
              <span className="text-sm font-medium">Tuesday, June 16th, 2026</span>
            </div>
            <div className="flex items-center gap-2 text-gray-300">
              <Clock className="w-4 h-4 text-primary" />
              <span className="text-sm font-medium">09:30 – 13:15</span>
            </div>
            <div className="flex items-center gap-2 text-gray-300">
              <MapPin className="w-4 h-4 text-primary" />
              <span className="text-sm font-medium">Red Hat IL Site</span>
            </div>
          </div>
        </div>
      </div>

      {/* Theme pills */}
      <div className="flex flex-wrap gap-2">
        {[
          "Agentic Orchestration",
          "ADLC",
          "Multi-Agent Systems",
          "AI Evaluation",
          "Autonomous SDLC",
          "Business Value",
        ].map((theme) => (
          <span
            key={theme}
            className="px-3 py-1 rounded-full bg-background-card border border-gray-700 text-gray-300 text-sm"
          >
            {theme}
          </span>
        ))}
      </div>
    </motion.div>
  );
}
