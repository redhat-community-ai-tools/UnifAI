import { useState } from "react";
import { motion } from "framer-motion";

import Sidebar from "@/components/layout/Sidebar";
import Header from "@/components/layout/Header";
import StatusBar from "@/components/layout/StatusBar";

import EventHero from "@/components/innovation-day/EventHero";
import EventStatsBar from "@/components/innovation-day/EventStatsBar";
import AgendaSection from "@/components/innovation-day/AgendaSection";
import SpeakersSection from "@/components/innovation-day/SpeakersSection";
import KeyTopicsSection from "@/components/innovation-day/KeyTopicsSection";
import CommunityUpdatesSection from "@/components/innovation-day/CommunityUpdatesSection";

export default function InnovationDay() {
  const [sidebarOpen, setSidebarOpen] = useState(false);

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar />

      <div className="flex-1 flex flex-col overflow-hidden">
        <Header
          title="Innovation Day Q2 2026"
          onToggleSidebar={() => setSidebarOpen(!sidebarOpen)}
        />

        <main className="flex-1 overflow-y-auto p-6 bg-background-dark">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
            className="max-w-7xl mx-auto"
          >
            <EventHero />
            <EventStatsBar />
            <AgendaSection />
            <KeyTopicsSection />
            <SpeakersSection />
            <CommunityUpdatesSection />
          </motion.div>
        </main>

        <StatusBar />
      </div>
    </div>
  );
}
