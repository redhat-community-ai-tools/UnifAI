import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import InnovationDay from "@/pages/InnovationDay";
import EventHero from "@/components/innovation-day/EventHero";
import EventStatsBar from "@/components/innovation-day/EventStatsBar";
import AgendaSection from "@/components/innovation-day/AgendaSection";
import KeyTopicsSection from "@/components/innovation-day/KeyTopicsSection";
import SpeakersSection from "@/components/innovation-day/SpeakersSection";
import CommunityUpdatesSection from "@/components/innovation-day/CommunityUpdatesSection";

// Mock framer-motion to render plain elements without animation overhead or issues in jsdom
vi.mock("framer-motion", () => ({
  motion: {
    div: ({ children, className, style, onClick, ...props }: any) => (
      <div className={className} style={style} onClick={onClick} {...props}>
        {children}
      </div>
    ),
    span: ({ children, className, style, ...props }: any) => (
      <span className={className} style={style} {...props}>
        {children}
      </span>
    ),
  },
  AnimatePresence: ({ children }: any) => <>{children}</>,
}));

// Mock layout components to isolate the page test
vi.mock("@/components/layout/Sidebar", () => ({
  default: () => <div data-testid="sidebar">Sidebar Mock</div>,
}));

vi.mock("@/components/layout/Header", () => ({
  default: ({ title }: { title: string }) => (
    <div data-testid="header">
      <h1>{title}</h1>
    </div>
  ),
}));

describe("Red Hat Innovation Day Q2 2026 Page", () => {
  describe("EventHero Component", () => {
    it("renders the event title, subtitle, date, and location details", () => {
      render(<EventHero />);

      // Verify Title & Subtitle
      expect(screen.getByText("Red Hat Innovation Day")).toBeInTheDocument();
      expect(screen.getByText("Q2 2026")).toBeInTheDocument();
      expect(screen.getByText(/Agentic orchestration, ADLC/)).toBeInTheDocument();

      // Verify Meta Information
      expect(screen.getByText("Tuesday, June 16th, 2026")).toBeInTheDocument();
      expect(screen.getByText("09:30 – 13:15")).toBeInTheDocument();
      expect(screen.getByText("Red Hat IL Site")).toBeInTheDocument();
      expect(screen.getByText("IL Site")).toBeInTheDocument();
    });

    it("renders all key theme pills", () => {
      render(<EventHero />);

      const themes = [
        "Agentic Orchestration",
        "ADLC",
        "Multi-Agent Systems",
        "AI Evaluation",
        "Autonomous SDLC",
        "Business Value",
      ];

      themes.forEach((theme) => {
        expect(screen.getByText(theme)).toBeInTheDocument();
      });
    });
  });

  describe("EventStatsBar Component", () => {
    it("renders stats cards with correct values and labels", () => {
      render(<EventStatsBar />);

      expect(screen.getByText("5")).toBeInTheDocument();
      expect(screen.getByText("Talks & Sessions")).toBeInTheDocument();

      expect(screen.getByText("12")).toBeInTheDocument();
      expect(screen.getByText("Speakers")).toBeInTheDocument();

      expect(screen.getByText("3h 30m")).toBeInTheDocument();
      expect(screen.getByText("Duration")).toBeInTheDocument();

      expect(screen.getByText("6")).toBeInTheDocument();
      expect(screen.getByText("Key Projects")).toBeInTheDocument();
    });
  });

  describe("AgendaSection Component", () => {
    it("renders the agenda section with all sessions, times, and speakers", () => {
      render(<AgendaSection />);

      expect(screen.getByText("Full Agenda")).toBeInTheDocument();

      // Verify specific agenda items
      expect(screen.getByText("Coffee and Ma'affee")).toBeInTheDocument();
      expect(screen.getByText("Intro to Innovation Day")).toBeInTheDocument();
      expect(screen.getByText("Is Orchestration the Future?")).toBeInTheDocument();
      expect(screen.getByText("Introduction to Fullsend")).toBeInTheDocument();
      expect(screen.getByText("Skill/Agents Related Quality and Evaluation")).toBeInTheDocument();
      expect(screen.getByText("Updates from UnifAI")).toBeInTheDocument();
      expect(screen.getByText("AI IL Ambassador Program")).toBeInTheDocument();

      // Verify some speakers are rendered in the agenda
      expect(screen.getByText("Hofni Gartner")).toBeInTheDocument();
      expect(screen.getByText("Vlad Luzin")).toBeInTheDocument();
      expect(screen.getByText("Roy Nissim")).toBeInTheDocument();
      expect(screen.getByText("Barak Korren")).toBeInTheDocument();
      expect(screen.getByText("Ella Shulman")).toBeInTheDocument();
      expect(screen.getByText("Nir Rashti")).toBeInTheDocument();
      expect(screen.getByText("Odai Odeh")).toBeInTheDocument();
      expect(screen.getByText("Ilanit Stein")).toBeInTheDocument();
    });
  });

  describe("KeyTopicsSection Component", () => {
    it("renders key project cards and their descriptions", () => {
      render(<KeyTopicsSection />);

      expect(screen.getByText("Key Topics & Projects")).toBeInTheDocument();

      // Verify project titles
      expect(screen.getByText("Fullsend")).toBeInTheDocument();
      expect(screen.getByText("Eval-Hub")).toBeInTheDocument();
      expect(screen.getByText("agent-eval-harness")).toBeInTheDocument();
      expect(screen.getByText("sdg_hub")).toBeInTheDocument();
      expect(screen.getByText("Compass Project")).toBeInTheDocument();

      // Verify descriptions or parts of them
      expect(screen.getByText(/A living design corpus and shipping platform/)).toBeInTheDocument();
      expect(screen.getByText(/A lightweight REST API service/)).toBeInTheDocument();
      expect(screen.getByText(/A comprehensive evaluation framework/)).toBeInTheDocument();
      expect(screen.getByText(/A Python framework for building/)).toBeInTheDocument();
      expect(screen.getByText(/Tooling and frameworks designed to ensure/)).toBeInTheDocument();
    });
  });

  describe("SpeakersSection Component", () => {
    it("renders the list of speakers, their roles, initials, and total count", () => {
      render(<SpeakersSection />);

      expect(screen.getByText("Speakers & Presenters")).toBeInTheDocument();
      expect(screen.getByText("12 speakers")).toBeInTheDocument();

      // Verify speaker names
      expect(screen.getByText("Hofni Gartner")).toBeInTheDocument();
      expect(screen.getByText("Barak Korren")).toBeInTheDocument();
      expect(screen.getByText("Nir Rashti")).toBeInTheDocument();
      expect(screen.getByText("Odai Odeh")).toBeInTheDocument();

      // Verify speaker initials
      expect(screen.getByText("HG")).toBeInTheDocument();
      expect(screen.getByText("VL")).toBeInTheDocument();
      expect(screen.getByText("RN")).toBeInTheDocument();
      expect(screen.getAllByText("BK")).toHaveLength(2); // Barak Korren and Benjamin Kapner
      expect(screen.getByText("NR")).toBeInTheDocument();
      expect(screen.getByText("OO")).toBeInTheDocument();

      // Verify some roles
      expect(screen.getByText("Innovation Day Host")).toBeInTheDocument();
      expect(screen.getByText("Principal Software Engineer")).toBeInTheDocument();
      expect(screen.getByText("AI IL Ambassador Program Lead")).toBeInTheDocument();
    });
  });

  describe("CommunityUpdatesSection Component", () => {
    it("renders the community updates checklist", () => {
      render(<CommunityUpdatesSection />);

      expect(screen.getByText("Community Updates")).toBeInTheDocument();

      // Verify update titles
      expect(screen.getByText("From Presentations to Workshops")).toBeInTheDocument();
      expect(screen.getByText("Increasing Visibility")).toBeInTheDocument();
      expect(screen.getByText("MCP Best Practices")).toBeInTheDocument();
      expect(screen.getByText("AI Assisted Coding")).toBeInTheDocument();
      expect(screen.getByText("UnifAI – ADLC Adaptation")).toBeInTheDocument();
    });
  });

  describe("InnovationDay Page Component", () => {
    it("renders layout components and all page sections together", () => {
      render(<InnovationDay />);

      // Verify Layout
      expect(screen.getByTestId("sidebar")).toBeInTheDocument();
      expect(screen.getByTestId("header")).toBeInTheDocument();
      expect(screen.getByRole("heading", { name: "Innovation Day Q2 2026" })).toBeInTheDocument();
      expect(screen.getByText("System active")).toBeInTheDocument(); // from StatusBar

      // Verify presence of major sub-components
      expect(screen.getByText("Red Hat Innovation Day")).toBeInTheDocument();
      expect(screen.getByText("Full Agenda")).toBeInTheDocument();
      expect(screen.getByText("Key Topics & Projects")).toBeInTheDocument();
      expect(screen.getByText("Speakers & Presenters")).toBeInTheDocument();
      expect(screen.getByText("Community Updates")).toBeInTheDocument();
    });
  });
});
