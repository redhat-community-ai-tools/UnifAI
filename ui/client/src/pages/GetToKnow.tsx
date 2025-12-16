import { useState } from "react";
import { motion } from "framer-motion";

import Sidebar from "@/components/layout/Sidebar";
import Header from "@/components/layout/Header";
import StatusBar from "@/components/layout/StatusBar";

import PageHeader from "@/components/get-to-know/PageHeader";
import IntroVideoSection from "@/components/get-to-know/IntroVideoSection";
import ResourceLinksSection from "@/components/get-to-know/ResourceLinksSection";
import ReadmePreview from "@/components/get-to-know/ReadmePreview";
import TechStackSection from "@/components/get-to-know/TechStackSection";

export default function GetToKnow() {
  const [sidebarOpen, setSidebarOpen] = useState(false);

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar />

      <div className="flex-1 flex flex-col overflow-hidden">
        <Header
          title="Getting Started"
          onToggleSidebar={() => setSidebarOpen(!sidebarOpen)}
        />

        <main className="flex-1 overflow-y-auto p-6 bg-background-dark">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
            className="max-w-7xl mx-auto"
          >
            <PageHeader />
            <IntroVideoSection />
            <ResourceLinksSection />
            <ReadmePreview />
            <TechStackSection />
          </motion.div>
        </main>

        <StatusBar />
      </div>
    </div>
  );
}