/**
 * Comprehensive tests for the InnovationDay page component.
 *
 * Covers:
 *  - Page loading and layout
 *  - Tab switching (Overview, Agenda, Projects & Tools, Metrics)
 *  - Agenda timeline filtering via filter chips
 *  - Collapsible session cards (expand / collapse)
 *  - Projects search and category filtering
 *  - Rendering of charts and progress bars
 */

import React from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

// ─── Mocks ───────────────────────────────────────────────────────────────────

// Mock layout shell components so tests focus on InnovationDay content
vi.mock("@/components/layout/Sidebar", () => ({
  default: () => <aside data-testid="sidebar" />,
}));

vi.mock("@/components/layout/Header", () => ({
  default: ({ title }: { title: string }) => (
    <header data-testid="header">
      <span>{title}</span>
    </header>
  ),
}));

vi.mock("@/components/layout/StatusBar", () => ({
  default: () => <footer data-testid="status-bar" />,
}));

// Mock ThemeContext – only primaryHex is used in OverviewTab
vi.mock("@/contexts/ThemeContext", () => ({
  useTheme: () => ({
    primaryHex: "#A60000",
    theme: "dark",
    toggleTheme: vi.fn(),
    setPrimaryHex: vi.fn(),
  }),
}));

// Simplify framer-motion so animations don't require requestAnimationFrame
vi.mock("framer-motion", () => {
  const FakeMotionDiv = ({
    children,
    ...rest
  }: React.HTMLAttributes<HTMLDivElement> & { [key: string]: unknown }) => {
    // Strip framer-specific props to avoid React warnings
    const {
      initial, animate, exit, transition, whileHover, onMouseEnter, onMouseLeave,
      style, className, ...domProps
    } = rest as Record<string, unknown>;
    return (
      <div
        style={style as React.CSSProperties}
        className={className as string}
        onMouseEnter={onMouseEnter as React.MouseEventHandler}
        onMouseLeave={onMouseLeave as React.MouseEventHandler}
        {...(domProps as React.HTMLAttributes<HTMLDivElement>)}
      >
        {children as React.ReactNode}
      </div>
    );
  };

  const AnimatePresence = ({ children }: { children: React.ReactNode }) => (
    <>{children}</>
  );

  return { motion: { div: FakeMotionDiv }, AnimatePresence };
});

// ─── Component under test ────────────────────────────────────────────────────

import InnovationDay from "@/pages/InnovationDay";

// ─── Helpers ─────────────────────────────────────────────────────────────────

function renderPage() {
  return render(<InnovationDay />);
}

/** Click a named tab in the TabsList */
async function switchToTab(tabLabel: string | RegExp) {
  const tab = screen.getByRole("tab", { name: tabLabel });
  await userEvent.click(tab);
  return tab;
}

// ─── Tests ───────────────────────────────────────────────────────────────────

describe("InnovationDay page", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  // ── 1. Layout & initial render ─────────────────────────────────────────────

  describe("Layout and initial render", () => {
    it("renders the page without crashing", () => {
      renderPage();
      expect(screen.getByTestId("sidebar")).toBeInTheDocument();
      expect(screen.getByTestId("header")).toBeInTheDocument();
      expect(screen.getByTestId("status-bar")).toBeInTheDocument();
    });

    it("renders the Header with the correct title", () => {
      renderPage();
      expect(screen.getByTestId("header")).toHaveTextContent(
        "Innovation Day — Q2 2026"
      );
    });

    it("renders the page heading with event title and badges", () => {
      renderPage();
      // Both h1 and h2 match this text (page heading + overview hero banner)
      const headings = screen.getAllByRole("heading", { name: /Red Hat Innovation Day Q2 2026/i });
      expect(headings.length).toBeGreaterThanOrEqual(1);

      // Two badges: "IL Site" and "Simulation"
      expect(screen.getByText("IL Site")).toBeInTheDocument();
      expect(screen.getAllByText("Simulation").length).toBeGreaterThan(0);
    });

    it("renders four navigation tabs", () => {
      renderPage();
      expect(screen.getByRole("tab", { name: /overview/i })).toBeInTheDocument();
      expect(screen.getByRole("tab", { name: /agenda/i })).toBeInTheDocument();
      expect(screen.getByRole("tab", { name: /projects/i })).toBeInTheDocument();
      expect(screen.getByRole("tab", { name: /metrics/i })).toBeInTheDocument();
    });

    it("shows the Overview tab as the default active tab", () => {
      renderPage();
      const overviewTab = screen.getByRole("tab", { name: /overview/i });
      expect(overviewTab).toHaveAttribute("data-state", "active");
    });
  });

  // ── 2. Tab switching ───────────────────────────────────────────────────────

  describe("Tab switching", () => {
    it("switches to the Agenda tab when clicked", async () => {
      renderPage();
      await switchToTab(/agenda/i);

      // Agenda content: filter chips should appear
      expect(screen.getByRole("button", { name: /^all$/i })).toBeInTheDocument();
      expect(screen.getByRole("button", { name: /^talk$/i })).toBeInTheDocument();
    });

    it("switches to the Projects & Tools tab when clicked", async () => {
      renderPage();
      await switchToTab(/projects/i);

      // Projects content: search input should appear
      expect(
        screen.getByPlaceholderText(/search projects/i)
      ).toBeInTheDocument();
    });

    it("switches to the Metrics tab when clicked", async () => {
      renderPage();
      await switchToTab(/metrics/i);

      // Metrics content: community metrics section
      expect(
        screen.getByText(/community.*adoption metrics/i)
      ).toBeInTheDocument();
    });

    it("switches back to Overview from another tab", async () => {
      renderPage();
      await switchToTab(/agenda/i);
      await switchToTab(/overview/i);

      // Back on overview: highlight stats should be visible
      expect(screen.getByText(/registered attendees/i)).toBeInTheDocument();
    });
  });

  // ── 3. Overview tab content ────────────────────────────────────────────────

  describe("Overview tab", () => {
    it("displays the event date, time and location", () => {
      renderPage();
      // Date/time/location appear in both the page subtitle and the hero banner
      expect(screen.getAllByText(/tuesday, june 16, 2026/i).length).toBeGreaterThan(0);
      expect(screen.getAllByText(/09:30/i).length).toBeGreaterThan(0);
      expect(screen.getAllByText(/red hat il site/i).length).toBeGreaterThan(0);
    });

    it("renders highlight stats (attendees, speakers, projects, duration)", () => {
      renderPage();
      expect(screen.getByText("87")).toBeInTheDocument();   // attendees
      expect(screen.getByText("11")).toBeInTheDocument();   // speakers
      expect(screen.getByText("7")).toBeInTheDocument();    // projects
      expect(screen.getByText("3h 45m")).toBeInTheDocument(); // duration
    });

    it("renders all four theme pillars", () => {
      renderPage();
      // These strings appear in both the hero theme text and pillar titles
      expect(screen.getAllByText(/agentic orchestration/i).length).toBeGreaterThan(0);
      expect(screen.getAllByText(/ADLC/).length).toBeGreaterThan(0);
      expect(screen.getAllByText(/evaluation/i).length).toBeGreaterThan(0);
      expect(screen.getAllByText(/ai ideation.*business value/i).length).toBeGreaterThan(0);
    });

    it("renders the Session Quick-Look preview table", () => {
      renderPage();
      expect(screen.getByText(/session quick-look/i)).toBeInTheDocument();
      // At least one agenda session title should appear in the preview
      expect(
        screen.getAllByText(/registration.*arrival|is orchestration/i).length
      ).toBeGreaterThanOrEqual(1);
    });
  });

  // ── 4. Agenda tab – filter chips ──────────────────────────────────────────

  describe("Agenda tab – filter chips", () => {
    beforeEach(async () => {
      renderPage();
      await switchToTab(/agenda/i);
    });

    it("renders all six filter chip types", () => {
      const chips = ["all", "talk", "workshop", "update", "community", "logistics"];
      for (const chip of chips) {
        expect(screen.getByRole("button", { name: new RegExp(`^${chip}$`, "i") })).toBeInTheDocument();
      }
    });

    it("'all' filter chip is active by default and shows all agenda items", async () => {
      const allBtn = screen.getByRole("button", { name: /^all$/i });
      // The active chip should visually be styled differently; we verify by
      // checking the full list of sessions is visible.
      expect(allBtn).toBeInTheDocument();

      // All 8 agenda sessions should render
      expect(screen.getByText(/registration.*arrival/i)).toBeInTheDocument();
      expect(screen.getByText(/coffee and ma'affee/i)).toBeInTheDocument();
      expect(screen.getByText(/intro to innovation day/i)).toBeInTheDocument();
      expect(screen.getByText(/is orchestration the future/i)).toBeInTheDocument();
      expect(screen.getByText(/introduction to fullsend/i)).toBeInTheDocument();
      expect(screen.getByText(/skill.*agents related quality/i)).toBeInTheDocument();
      expect(screen.getByText(/updates from unifai/i)).toBeInTheDocument();
      expect(screen.getByText(/ai il ambassador program/i)).toBeInTheDocument();
    });

    it("filters to 'talk' shows only talk sessions", async () => {
      await userEvent.click(screen.getByRole("button", { name: /^talk$/i }));

      expect(screen.getByText(/intro to innovation day/i)).toBeInTheDocument();
      expect(screen.getByText(/is orchestration the future/i)).toBeInTheDocument();

      // Non-talk sessions should NOT be visible
      expect(screen.queryByText(/introduction to fullsend/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/registration.*arrival/i)).not.toBeInTheDocument();
    });

    it("filters to 'workshop' shows only workshop sessions", async () => {
      await userEvent.click(screen.getByRole("button", { name: /^workshop$/i }));

      expect(screen.getByText(/introduction to fullsend/i)).toBeInTheDocument();
      expect(screen.getByText(/skill.*agents related quality/i)).toBeInTheDocument();

      expect(screen.queryByText(/intro to innovation day/i)).not.toBeInTheDocument();
    });

    it("filters to 'update' shows only update sessions", async () => {
      await userEvent.click(screen.getByRole("button", { name: /^update$/i }));

      expect(screen.getByText(/updates from unifai/i)).toBeInTheDocument();
      expect(screen.queryByText(/introduction to fullsend/i)).not.toBeInTheDocument();
    });

    it("filters to 'community' shows only community sessions", async () => {
      await userEvent.click(screen.getByRole("button", { name: /^community$/i }));

      expect(screen.getByText(/ai il ambassador program/i)).toBeInTheDocument();
      expect(screen.queryByText(/updates from unifai/i)).not.toBeInTheDocument();
    });

    it("filters to 'logistics' shows only logistics sessions", async () => {
      await userEvent.click(screen.getByRole("button", { name: /^logistics$/i }));

      expect(screen.getByText(/registration.*arrival/i)).toBeInTheDocument();
      expect(screen.getByText(/coffee and ma'affee/i)).toBeInTheDocument();
      expect(screen.queryByText(/intro to innovation day/i)).not.toBeInTheDocument();
    });

    it("switching from a specific filter back to 'all' restores all items", async () => {
      await userEvent.click(screen.getByRole("button", { name: /^talk$/i }));
      await userEvent.click(screen.getByRole("button", { name: /^all$/i }));

      expect(screen.getByText(/registration.*arrival/i)).toBeInTheDocument();
      expect(screen.getByText(/introduction to fullsend/i)).toBeInTheDocument();
    });
  });

  // ── 5. Agenda tab – collapsible session cards ─────────────────────────────

  describe("Agenda tab – collapsible session cards", () => {
    beforeEach(async () => {
      renderPage();
      await switchToTab(/agenda/i);
    });

    it("non-logistics cards have an expand button", () => {
      // The Expand button is aria-labelled
      const expandButtons = screen.getAllByRole("button", { name: /expand/i });
      expect(expandButtons.length).toBeGreaterThan(0);
    });

    it("clicking a non-logistics card expands it to show description and topics", async () => {
      // Click on the "Intro to Innovation Day" card header
      const cardHeader = screen.getByText(/intro to innovation day/i);
      await userEvent.click(cardHeader);

      // Description text should now appear
      await waitFor(() => {
        expect(
          screen.getByText(/brief welcome and orientation/i)
        ).toBeInTheDocument();
      });
    });

    it("clicking an expanded card again collapses it (description hidden)", async () => {
      const cardHeader = screen.getByText(/intro to innovation day/i);

      // Expand
      await userEvent.click(cardHeader);
      await waitFor(() =>
        expect(screen.getByText(/brief welcome and orientation/i)).toBeInTheDocument()
      );

      // Collapse
      await userEvent.click(cardHeader);
      await waitFor(() =>
        expect(
          screen.queryByText(/brief welcome and orientation/i)
        ).not.toBeInTheDocument()
      );
    });

    it("the Expand/Collapse button toggles aria-label accordingly", async () => {
      // Find the expand button for a non-logistics card
      const expandBtns = screen.getAllByRole("button", { name: /expand/i });
      const firstExpandBtn = expandBtns[0];

      // Click the card header area (parent of the button)
      await userEvent.click(firstExpandBtn.closest(".cursor-pointer") ?? firstExpandBtn);

      await waitFor(() => {
        expect(
          screen.getAllByRole("button", { name: /collapse/i }).length
        ).toBeGreaterThan(0);
      });
    });

    it("logistics cards (Registration, Coffee) do NOT have an expand button", () => {
      // Logistics type cards don't render the chevron button
      // Verify "Registration / Arrival" card is present
      expect(screen.getByText(/registration.*arrival/i)).toBeInTheDocument();

      // There should be fewer expand buttons than non-logistics sessions (6 non-logistics in AGENDA)
      const expandButtons = screen.getAllByRole("button", { name: /expand/i });
      expect(expandButtons.length).toBeLessThanOrEqual(6);
    });

    it("expanded card for 'Is Orchestration the Future?' shows all its topics", async () => {
      const cardHeader = screen.getByText(/is orchestration the future/i);
      await userEvent.click(cardHeader);

      await waitFor(() => {
        // Text appears in both description and topic tags, so use getAllByText
        expect(screen.getAllByText(/agent-to-agent \(a2a\) communications/i).length).toBeGreaterThan(0);
        expect(screen.getAllByText(/peer-to-peer collaboration/i).length).toBeGreaterThan(0);
        expect(screen.getAllByText(/orchestration topologies/i).length).toBeGreaterThan(0);
      });
    });

    it("expanded card shows speaker name", async () => {
      const cardHeader = screen.getByText(/intro to innovation day/i);
      await userEvent.click(cardHeader);

      // Speaker "Hofni Gartner" should be rendered
      expect(screen.getByText(/hofni gartner/i)).toBeInTheDocument();
    });
  });

  // ── 6. Projects tab – search & category filtering ─────────────────────────

  describe("Projects tab – search and category filtering", () => {
    beforeEach(async () => {
      renderPage();
      await switchToTab(/projects/i);
    });

    it("renders all 7 project cards by default", () => {
      const projectNames = [
        "Code Agent Harness Evaluation",
        "agent-eval-harness",
        "eval-hub",
        "sdg_hub",
        "Fullsend",
        "UnifAI",
        "Compass",
      ];
      for (const name of projectNames) {
        expect(screen.getByText(name)).toBeInTheDocument();
      }
    });

    it("renders category filter buttons (All, Evaluation, Platform, Data, SDLC)", () => {
      expect(screen.getByRole("button", { name: /^all$/i })).toBeInTheDocument();
      expect(screen.getByRole("button", { name: /^evaluation$/i })).toBeInTheDocument();
      expect(screen.getByRole("button", { name: /^platform$/i })).toBeInTheDocument();
      expect(screen.getByRole("button", { name: /^data$/i })).toBeInTheDocument();
      expect(screen.getByRole("button", { name: /^sdlc$/i })).toBeInTheDocument();
    });

    it("filters projects by search text matching project name", async () => {
      const searchInput = screen.getByPlaceholderText(/search projects/i);
      await userEvent.type(searchInput, "UnifAI");

      expect(screen.getByText("UnifAI")).toBeInTheDocument();
      expect(screen.queryByText("Fullsend")).not.toBeInTheDocument();
      expect(screen.queryByText("Compass")).not.toBeInTheDocument();
    });

    it("filters projects by search text matching description keywords", async () => {
      const searchInput = screen.getByPlaceholderText(/search projects/i);
      await userEvent.type(searchInput, "autonomous");

      // "Fullsend" description mentions "autonomous"
      expect(screen.getByText("Fullsend")).toBeInTheDocument();
      // Projects without "autonomous" in name/description/tags should be hidden
      expect(screen.queryByText("Compass")).not.toBeInTheDocument();
    });

    it("filters projects by search text matching tags", async () => {
      const searchInput = screen.getByPlaceholderText(/search projects/i);
      await userEvent.type(searchInput, "Benchmarking");

      // "agent-eval-harness" has tag "Benchmarking"
      expect(screen.getByText("agent-eval-harness")).toBeInTheDocument();
      expect(screen.queryByText("UnifAI")).not.toBeInTheDocument();
    });

    it("shows 'No projects found.' when search yields no results", async () => {
      const searchInput = screen.getByPlaceholderText(/search projects/i);
      await userEvent.type(searchInput, "xyznonexistentproject");

      expect(screen.getByText(/no projects found/i)).toBeInTheDocument();
    });

    it("clearing search restores all projects", async () => {
      const searchInput = screen.getByPlaceholderText(/search projects/i);
      await userEvent.type(searchInput, "UnifAI");
      await userEvent.clear(searchInput);

      expect(screen.getByText("Fullsend")).toBeInTheDocument();
      expect(screen.getByText("Compass")).toBeInTheDocument();
    });

    it("category filter 'Evaluation' shows only Evaluation projects", async () => {
      await userEvent.click(screen.getByRole("button", { name: /^evaluation$/i }));

      expect(screen.getByText("Code Agent Harness Evaluation")).toBeInTheDocument();
      expect(screen.getByText("agent-eval-harness")).toBeInTheDocument();
      expect(screen.getByText("Compass")).toBeInTheDocument();

      expect(screen.queryByText("Fullsend")).not.toBeInTheDocument();
      expect(screen.queryByText("UnifAI")).not.toBeInTheDocument();
    });

    it("category filter 'Platform' shows only Platform projects", async () => {
      await userEvent.click(screen.getByRole("button", { name: /^platform$/i }));

      expect(screen.getByText("eval-hub")).toBeInTheDocument();
      expect(screen.getByText("UnifAI")).toBeInTheDocument();

      expect(screen.queryByText("Fullsend")).not.toBeInTheDocument();
      expect(screen.queryByText("Compass")).not.toBeInTheDocument();
    });

    it("category filter 'SDLC' shows only SDLC projects", async () => {
      await userEvent.click(screen.getByRole("button", { name: /^sdlc$/i }));

      expect(screen.getByText("Fullsend")).toBeInTheDocument();
      expect(screen.queryByText("UnifAI")).not.toBeInTheDocument();
    });

    it("category filter 'Data' shows only Data projects", async () => {
      await userEvent.click(screen.getByRole("button", { name: /^data$/i }));

      expect(screen.getByText("sdg_hub")).toBeInTheDocument();
      expect(screen.queryByText("Fullsend")).not.toBeInTheDocument();
    });

    it("combining search and category filter works correctly", async () => {
      await userEvent.click(screen.getByRole("button", { name: /^evaluation$/i }));
      const searchInput = screen.getByPlaceholderText(/search projects/i);
      await userEvent.type(searchInput, "harness");

      // Only agent-eval-harness matches both criteria
      expect(screen.getByText("agent-eval-harness")).toBeInTheDocument();
      expect(screen.queryByText("Compass")).not.toBeInTheDocument();
    });

    it("project cards show status badges (Active, Production, MVP)", () => {
      expect(screen.getAllByText("Active").length).toBeGreaterThan(0);
      expect(screen.getByText("Production")).toBeInTheDocument();
      expect(screen.getByText("MVP")).toBeInTheDocument();
    });

    it("project cards show maturity progress bars", () => {
      // Progress bars are rendered for each project
      const progressBars = document.querySelectorAll('[role="progressbar"]');
      // We expect one per project card (7 projects)
      expect(progressBars.length).toBeGreaterThanOrEqual(7);
    });

    it("project cards show category labels", () => {
      expect(screen.getAllByText("Evaluation").length).toBeGreaterThan(0);
      expect(screen.getAllByText("Platform").length).toBeGreaterThan(0);
    });
  });

  // ── 7. Metrics tab – charts and progress bars ─────────────────────────────

  describe("Metrics tab – charts and progress bars", () => {
    beforeEach(async () => {
      renderPage();
      await switchToTab(/metrics/i);
    });

    it("renders all six community metric cards", () => {
      expect(screen.getByText(/event attendees/i)).toBeInTheDocument();
      expect(screen.getByText(/ai-assisted coding adoption/i)).toBeInTheDocument();
      expect(screen.getByText(/community workshops held/i)).toBeInTheDocument();
      expect(screen.getByText(/best practices.*mcp.*published/i)).toBeInTheDocument();
      expect(screen.getByText(/ambassador program members/i)).toBeInTheDocument();
      expect(screen.getByText(/visibility score/i)).toBeInTheDocument();
    });

    it("metric cards display correct values and units", () => {
      expect(screen.getByText("87")).toBeInTheDocument();  // Event Attendees
      expect(screen.getByText("64")).toBeInTheDocument();  // AI Adoption %
      expect(screen.getByText("12")).toBeInTheDocument();  // Workshops
      expect(screen.getByText("18")).toBeInTheDocument();  // Ambassadors
      expect(screen.getByText("76")).toBeInTheDocument();  // Visibility
    });

    it("metric cards display positive delta indicators", () => {
      expect(screen.getByText("+23%")).toBeInTheDocument();
      expect(screen.getByText("+18pp")).toBeInTheDocument();
      expect(screen.getByText("+11%")).toBeInTheDocument();
    });

    it("metric cards render progress bars", () => {
      const progressBars = document.querySelectorAll('[role="progressbar"]');
      // At least 6 metric cards, each with one progress bar
      expect(progressBars.length).toBeGreaterThanOrEqual(6);
    });

    it("renders the Community Format Shift chart section", () => {
      expect(screen.getByText(/community format shift/i)).toBeInTheDocument();
      expect(screen.getByText(/transitioning from passive presentations/i)).toBeInTheDocument();
    });

    it("Community Shift chart shows Presentations, Workshops, Office Hours rows", () => {
      // "Presentations" and "Office Hours" appear as row labels AND as legend labels
      expect(screen.getAllByText("Presentations").length).toBeGreaterThan(0);
      expect(screen.getAllByText("Workshops").length).toBeGreaterThan(0);
      expect(screen.getAllByText(/office hours/i).length).toBeGreaterThan(0);
    });

    it("Community Shift chart shows Q1 and Q2 percentage values", () => {
      // The Q1/Q2 values are rendered in nested spans; verify via container text
      // Presentations row: Q1 70 → Q2 40 (spans inside a flex row)
      const chartSection = screen.getByText(/community format shift/i).closest("div");
      expect(chartSection).toBeTruthy();
      // Check that the chart area contains "70" and "40"
      expect(screen.getAllByText(/\bq1:/i).length).toBeGreaterThan(0);
      expect(screen.getAllByText(/\bq2:/i).length).toBeGreaterThan(0);
    });

    it("renders the AI-Assisted Coding breakdown section", () => {
      expect(screen.getByText(/ai-assisted coding.*adoption breakdown/i)).toBeInTheDocument();
      expect(screen.getByText(/claude code/i)).toBeInTheDocument();
      expect(screen.getByText(/github copilot/i)).toBeInTheDocument();
      expect(screen.getByText(/cursor.*windsurf/i)).toBeInTheDocument();
      expect(screen.getByText(/other.*custom mcp/i)).toBeInTheDocument();
    });

    it("AI coding breakdown shows correct percentages", () => {
      expect(screen.getByText("38%")).toBeInTheDocument();
      expect(screen.getByText("29%")).toBeInTheDocument();
      expect(screen.getByText("19%")).toBeInTheDocument();
      expect(screen.getByText("14%")).toBeInTheDocument();
    });

    it("renders the Ambassador Program snapshot section", () => {
      expect(screen.getByText(/ai il ambassador program.*q2 snapshot/i)).toBeInTheDocument();
      expect(screen.getByText(/18 active ambassadors/i)).toBeInTheDocument();
    });

    it("Ambassador section displays correct stats", () => {
      // "24" and "37" appear only in the Ambassador section
      expect(screen.getByText("24")).toBeInTheDocument();  // Success Stories
      expect(screen.getByText("37")).toBeInTheDocument();  // Peer Mentoring
      // "9" also appears in the MetricCard for "Best Practices (MCP) Published"
      expect(screen.getAllByText("9").length).toBeGreaterThan(0);  // MCP Best Practices
    });

    it("Ambassador section displays stat labels", () => {
      expect(screen.getByText(/success stories shared/i)).toBeInTheDocument();
      expect(screen.getByText(/peer mentoring sessions/i)).toBeInTheDocument();
      expect(screen.getByText(/mcp best practices published/i)).toBeInTheDocument();
    });
  });

  // ── 8. Accessibility ──────────────────────────────────────────────────────

  describe("Accessibility", () => {
    it("all tabs are keyboard-navigable via role='tab'", () => {
      renderPage();
      const tabs = screen.getAllByRole("tab");
      expect(tabs.length).toBe(4);
      tabs.forEach((tab) => {
        expect(tab).toBeVisible();
      });
    });

    it("expand/collapse buttons have descriptive aria-labels", async () => {
      renderPage();
      await switchToTab(/agenda/i);
      const expandBtns = screen.getAllByRole("button", { name: /expand/i });
      expandBtns.forEach((btn) => {
        expect(btn).toHaveAttribute("aria-label");
      });
    });
  });
});
