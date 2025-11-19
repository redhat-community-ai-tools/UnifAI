import React, { useRef, useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  FaTimes,
  FaInfoCircle,
  FaCube,
  FaCodeBranch,
  FaSyncAlt,
} from "react-icons/fa";
import { Badge } from "@/components/ui/badge";
import { useTheme } from "@/contexts/ThemeContext";
import { api } from "@/http/queryClient";
import { api as apiAuth } from "@/http/authClient";
import axios from "@/http/axiosAgentConfig";

// 🔹 Fixed list of modules
const MODULE_NAMES = ["Dataflow", "MultiAgent", "UI", "SSO"];

export default function HelpPanel({ isOpen, onClose }: any) {
  const panelRef = useRef<HTMLDivElement>(null);
  const { primaryHex } = useTheme();

  // 🔹 Only track versions in state
  const [versions, setVersions] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const clientMap: Record<string, typeof api> = {
    Dataflow: api,
    MultiAgent: axios,
    SSO: apiAuth,
  };

  const fetchVersions = async () => {
    setLoading(true);
    try {
      const results: Record<string, string> = {};

      await Promise.all(
        MODULE_NAMES.map(async (name) => {
          // UI version from config.json
          if (name === "UI") {
            try {
              const res = await fetch("/config.json");
              const config = await res.json();
              results[name] = config?.version || "N/A";
            } catch (err) {
              console.error("Failed to fetch UI version", err);
              results[name] = "N/A";
            }
            return;
          }

          // Other services -> /health/version
          const client = clientMap[name];
          if (!client) {
            results[name] = "N/A";
            return;
          }

          try {
            const res = await client.get("/health/version");
            results[name] =
              res?.data?.version && res.data.version !== "1.0.0"
                ? res.data.version
                : "1.0.0";
          } catch (err) {
            console.error(`Failed to fetch version for ${name}`, err);
            results[name] = "N/A";
          }
        })
      );

      setVersions(results);
    } catch (err) {
      console.error(err);
      setError("Failed to fetch module versions");
    } finally {
      setLoading(false);
    }
  };

  // Auto-refresh every 10 seconds **only when panel is open**
  useEffect(() => {
    let interval: number | null = null;

    if (isOpen) {
      fetchVersions();
      interval = setInterval(() => {
        fetchVersions();
      }, 10000);
    }

    return () => {
      if (interval) clearInterval(interval);
    };
  }, [isOpen]);

  if (!isOpen) return null;

  return (
    <AnimatePresence>
      <motion.div
        ref={panelRef}
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: -10 }}
        transition={{ duration: 0.2 }}
        className="absolute top-full right-0 z-50 mt-2 w-80 sm:w-96 bg-background-dark border border-border rounded-lg shadow-2xl overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between p-3 border-b border-border bg-background-dark rounded-t-lg">
          <div className="flex items-center gap-2">
            <FaInfoCircle className="text-foreground w-5 h-5" />
            <h2 className="text-lg font-semibold text-foreground">Module Version Overview</h2>
          </div>
          <div className="flex items-center gap-2">
            {/* Refresh Button */}
            <button
              onClick={fetchVersions}
              className="p-1 rounded-full hover:bg-accent text-foreground transition-colors duration-200"
              title="Refresh"
            >
              <FaSyncAlt className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
            </button>
            <button
              onClick={onClose}
              className="p-1 rounded-full hover:bg-accent text-foreground transition-colors duration-200"
            >
              <FaTimes className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="p-4 max-h-80 overflow-y-auto no-scrollbar">
          {loading ? (
            <div className="text-center text-muted-foreground">Loading...</div>
          ) : error ? (
            <div className="text-center text-destructive">{error}</div>
          ) : (
            <div className="space-y-2">
              {MODULE_NAMES.map((name) => (
                <div
                  key={name}
                  className="flex items-center justify-between p-3 border border-border rounded-lg bg-card transition-colors duration-200"
                >
                  <div className="flex items-center gap-3">
                    <FaCube className="text-card-foreground w-5 h-5" />
                    <span className="text-card-foreground font-medium">{name}</span>
                  </div>
                  <Badge
                    variant="secondary"
                    className="flex items-center gap-1 shadow-sm px-2.5 py-1 text-sm font-medium rounded-md"
                    style={{
                      backgroundColor: primaryHex || "hsl(var(--primary))",
                      color: "hsl(var(--primary-foreground))",
                    }}
                  >
                    <FaCodeBranch className="w-3 h-3" />
                    {versions[name] ?? "n/a"}
                  </Badge>
                </div>
              ))}
            </div>
          )}
        </div>
      </motion.div>
    </AnimatePresence>
  );
}
