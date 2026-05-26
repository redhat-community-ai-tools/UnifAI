import { useEffect, useState } from "react";
import {
  FaInfoCircle,
  FaSun,
  FaMoon,
  FaSyncAlt,
  FaUser,
  FaSlack,
  FaExternalLinkAlt,
  FaBook,
} from "react-icons/fa";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Separator } from "@/components/ui/separator";
import SimpleTooltip from "@/components/shared/SimpleTooltip";
import { useTheme } from "@/contexts/ThemeContext";
import { api } from "@/http/queryClient";
import { api as apiAuth } from "@/http/authClient";
import axios from "@/http/axiosAgentConfig";
import { backendApi } from "@/http/backendClient";

interface AboutDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

const MODULE_NAMES = ["Backend", "MultiAgent", "RAG", "Identity", "UI"];

const COLOR_OPTIONS = [
  { hex: "#A60000", name: "Red" },
  { hex: "#147878", name: "Teal" },
  { hex: "#707070", name: "Gray" },
  { hex: "#8A2BE2", name: "Purple" },
];

const QUICK_LINKS = [
  { label: "Getting Started", href: "/get-to-know", icon: FaInfoCircle },
  { label: "How-To Guides", href: "/guides", icon: FaBook },
  { label: "Repository", href: "https://github.com/redhat-community-ai-tools/UnifAI", icon: FaExternalLinkAlt },
];

export default function AboutDialog({ open, onOpenChange }: AboutDialogProps) {
  const { theme, toggleTheme, primaryHex, setPrimaryHex } = useTheme();

  const [versions, setVersions] = useState<Record<string, string>>({});
  const [versionLoading, setVersionLoading] = useState(false);
  const [teamMembers, setTeamMembers] = useState<string[]>([]);
  const [supportLink, setSupportLink] = useState("");

  const clientMap: Record<string, typeof api> = {
    RAG: api,
    MultiAgent: axios,
    Identity: apiAuth,
    Backend: backendApi,
  };

  const fetchAppConfig = async () => {
    try {
      const res = await fetch("/config.json");
      const config = await res.json();

      const members = (config?.teamMembers || "")
        .split(",")
        .map((m: string) => m.trim())
        .filter(Boolean);
      setTeamMembers(members);
      setSupportLink(config?.supportLink || "");

      return config?.version || "N/A";
    } catch (err) {
      console.error("Failed to fetch UI config", err);
      return "N/A";
    }
  };

  const fetchVersions = async () => {
    setVersionLoading(true);
    try {
      const results: Record<string, string> = {};

      await Promise.all(
        MODULE_NAMES.map(async (name) => {
          if (name === "UI") {
            results[name] = await fetchAppConfig();
            return;
          }

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
    } finally {
      setVersionLoading(false);
    }
  };

  useEffect(() => {
    if (open) {
      fetchVersions();
    }
  }, [open]);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md max-h-[85vh] flex flex-col p-0 gap-0">
        <DialogHeader className="px-6 pt-6 pb-4">
          <DialogTitle className="flex items-center gap-2">
            <div className="w-6 h-6 rounded-md bg-gradient-to-r from-primary to-gray-500 flex items-center justify-center flex-shrink-0">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M3 12H7M17 12H21M12 3V7M12 17V21M5 19L8 16M16 8L19 5M19 19L16 16M5 5L8 8" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            </div>
            About UnifAI
          </DialogTitle>
        </DialogHeader>

        <div className="flex-1 overflow-y-auto px-6 space-y-5">
          {/* App Description */}
          <p className="text-sm text-muted-foreground leading-relaxed">
            AI-powered unified platform for Agentic AI workflows and RAG pipelines.
          </p>

          <Separator />

          {/* Preferences */}
          <div className="space-y-3">
            <h3 className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Preferences</h3>

            <div className="flex items-center justify-between mb-1">
              <span className="text-sm text-foreground">Theme</span>
              <div className="flex items-center rounded-md border border-border overflow-hidden">
                <button
                  onClick={() => theme === "dark" && toggleTheme()}
                  className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium transition-colors ${
                    theme === "light"
                      ? "bg-primary text-primary-foreground"
                      : "bg-transparent text-muted-foreground hover:text-foreground"
                  }`}
                >
                  <FaSun className="w-3 h-3" />
                  Light
                </button>
                <button
                  onClick={() => theme === "light" && toggleTheme()}
                  className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium transition-colors ${
                    theme === "dark"
                      ? "bg-primary text-primary-foreground"
                      : "bg-transparent text-muted-foreground hover:text-foreground"
                  }`}
                >
                  <FaMoon className="w-3 h-3" />
                  Dark
                </button>
              </div>
            </div>

            <div className="flex items-center justify-between">
              <span className="text-sm text-foreground">Accent Color</span>
              <div className="flex items-center gap-1.5">
                {COLOR_OPTIONS.map(({ hex, name }) => (
                  <SimpleTooltip key={hex} content={<p>{name}</p>}>
                    <button
                      onClick={() => setPrimaryHex(hex)}
                      className={`w-4 h-4 rounded-sm transition-all ${
                        primaryHex === hex
                          ? "ring-2 ring-offset-1 ring-offset-background ring-foreground scale-110"
                          : "hover:scale-110"
                      }`}
                      style={{ backgroundColor: hex }}
                    />
                  </SimpleTooltip>
                ))}
              </div>
            </div>
          </div>

          <Separator />

          {/* Contact Team */}
          <div className="space-y-3">
            <h3 className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Contact Team</h3>

            <div className="grid grid-cols-2 gap-x-4 gap-y-1.5">
              {teamMembers.map((name) => (
                <div key={name} className="flex items-center gap-2">
                  <FaUser className="w-3 h-3 text-muted-foreground flex-shrink-0" />
                  <span className="text-sm text-foreground">{name}</span>
                </div>
              ))}
            </div>
            {supportLink && (
              <div className="flex items-center gap-2 pt-1">
                <FaSlack className="w-3.5 h-3.5 text-muted-foreground flex-shrink-0" />
                <span className="text-sm text-foreground">
                  Reach us on Slack:{" "}
                  <a
                    href={supportLink}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="font-medium text-primary hover:underline"
                  >
                    Support
                  </a>
                </span>
              </div>
            )}
          </div>

          <Separator />

          {/* Quick Links */}
          <div className="space-y-3 pb-4">
            <h3 className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Quick Links</h3>

            <div className="grid grid-cols-2 gap-2">
              {QUICK_LINKS.map(({ label, href, icon: Icon }) => (
                <a
                  key={label}
                  href={href}
                  className="flex items-center gap-2 text-sm text-foreground hover:text-primary transition-colors p-2 rounded-md hover:bg-accent"
                >
                  <Icon className="w-3.5 h-3.5" />
                  {label}
                </a>
              ))}
            </div>
          </div>
        </div>

        {/* Version Footer */}
        <div className="border-t border-border px-6 py-3">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Versions</span>
            <SimpleTooltip content={<p>Refresh versions</p>}>
              <button
                onClick={fetchVersions}
                disabled={versionLoading}
                className="p-1 rounded-full hover:bg-accent text-muted-foreground hover:text-foreground transition-colors"
              >
                <FaSyncAlt className={`w-3 h-3 ${versionLoading ? "animate-spin" : ""}`} />
              </button>
            </SimpleTooltip>
          </div>
          {versionLoading ? (
            <div className="text-xs text-muted-foreground">Loading versions...</div>
          ) : (
            <div className="space-y-1">
              {MODULE_NAMES.map((name) => (
                <div key={name} className="flex items-center justify-between text-xs">
                  <span className="text-muted-foreground">{name}</span>
                  <span className="text-foreground font-mono">{versions[name] ?? "N/A"}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
