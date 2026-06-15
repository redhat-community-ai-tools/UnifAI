import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import InnovationDay from '../InnovationDay';

// Mock layout components
vi.mock('@/components/layout/Sidebar', () => ({
  default: () => <div data-testid="sidebar-mock">Sidebar</div>,
}));

vi.mock('@/components/layout/Header', () => ({
  default: ({ title, onToggleSidebar }: any) => (
    <div data-testid="header-mock">
      Header: {title}
      <button onClick={onToggleSidebar} data-testid="header-toggle-btn">Toggle</button>
    </div>
  ),
}));

vi.mock('@/components/layout/StatusBar', () => ({
  default: () => <div data-testid="statusbar-mock">StatusBar</div>,
}));

// Mock framer-motion to bypass animations
vi.mock('framer-motion', async () => {
  const actual = await vi.importActual('framer-motion');
  return {
    ...actual,
    motion: {
      div: ({ children, ...props }: any) => <div {...props}>{children}</div>,
      tr: ({ children, ...props }: any) => <tr {...props}>{children}</tr>,
    },
    AnimatePresence: ({ children }: any) => <>{children}</>,
  };
});

// Mock Tabs to render all tab content simultaneously (no JS state needed in tests)
vi.mock('@/components/ui/tabs', () => ({
  Tabs: ({ children }: any) => <div>{children}</div>,
  TabsList: ({ children }: any) => <div role="tablist">{children}</div>,
  TabsTrigger: ({ children, value }: any) => (
    <button role="tab" data-value={value}>{children}</button>
  ),
  TabsContent: ({ children }: any) => <div role="tabpanel">{children}</div>,
}));

describe('InnovationDay Page', () => {
  it('renders layout shell (Sidebar, Header, StatusBar)', () => {
    render(<InnovationDay />);
    expect(screen.getByTestId('sidebar-mock')).toBeInTheDocument();
    expect(screen.getByTestId('header-mock')).toHaveTextContent(
      'Innovation Day — IL Site Q2 2026'
    );
    expect(screen.getByTestId('statusbar-mock')).toBeInTheDocument();
  });

  it('renders the Hero Banner with correct event metadata', () => {
    render(<InnovationDay />);

    // Event title
    expect(screen.getByText(/Red Hat Innovation Day/i)).toBeInTheDocument();
    expect(screen.getByText(/Q2 2026 — IL Site/i)).toBeInTheDocument();

    // Info chips
    expect(screen.getByText('Tuesday, June 16th, 2026')).toBeInTheDocument();
    expect(screen.getByText('09:30 – 13:15')).toBeInTheDocument();
    expect(screen.getByText('IL (Israel) Site')).toBeInTheDocument();

    // Theme tags
    expect(screen.getByText('Agentic Orchestration')).toBeInTheDocument();
    expect(screen.getByText('ADLC')).toBeInTheDocument();
    expect(screen.getByText('Evaluation')).toBeInTheDocument();
    expect(screen.getByText('AI to Business Value')).toBeInTheDocument();
  });

  it('renders stats bar labels', () => {
    render(<InnovationDay />);
    expect(screen.getByText('Sessions')).toBeInTheDocument();
    expect(screen.getByText('Speakers')).toBeInTheDocument();
    expect(screen.getByText('3h 45m')).toBeInTheDocument();
    expect(screen.getByText('Key Projects')).toBeInTheDocument();
  });

  it('renders the full agenda with all sessions', () => {
    render(<InnovationDay />);

    expect(screen.getByText('Full Agenda')).toBeInTheDocument();

    // Spot-check agenda items (they appear in both timeline and table views)
    expect(screen.getAllByText(/Coffee and Ma'affee/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Is Orchestration the Future\?/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Introduction to Fullsend/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Skill\/Agents Related Quality/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Updates from UnifAI/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/AI IL Ambassador Program/i).length).toBeGreaterThan(0);
  });

  it('renders session details section heading', () => {
    render(<InnovationDay />);
    expect(screen.getByText('Session Details')).toBeInTheDocument();
  });

  it('expands a session card and shows detailed content', () => {
    render(<InnovationDay />);

    // Find the expand button for the Orchestration session
    const buttons = screen.getAllByRole('button');
    const orchestrationBtn = buttons.find((btn) =>
      btn.textContent?.includes('Is Orchestration the Future?')
    );

    expect(orchestrationBtn).toBeDefined();
    if (orchestrationBtn) {
      fireEvent.click(orchestrationBtn);
      // Check expanded bullet points are visible
      expect(
        screen.getByText(/A2A \(Agent-to-Agent\) Communications for multi-agent systems/i)
      ).toBeInTheDocument();
      expect(
        screen.getByText(/Peer-to-peer collaboration patterns between autonomous agents/i)
      ).toBeInTheDocument();
    }
  });

  it('expands Fullsend session and shows its unique description', () => {
    render(<InnovationDay />);

    const buttons = screen.getAllByRole('button');
    const fullsendBtn = buttons.find((btn) =>
      btn.textContent?.includes('Introduction to Fullsend')
    );

    expect(fullsendBtn).toBeDefined();
    if (fullsendBtn) {
      fireEvent.click(fullsendBtn);
      expect(
        screen.getByText(/living design corpus and shipping platform/i)
      ).toBeInTheDocument();
    }
  });

  it('renders all 6 key projects', () => {
    render(<InnovationDay />);

    expect(screen.getByText('Key Projects & Technologies')).toBeInTheDocument();
    expect(screen.getByText('Code Agent Harness Evaluation')).toBeInTheDocument();
    expect(screen.getByText('agent-eval-harness')).toBeInTheDocument();
    expect(screen.getByText('eval-hub')).toBeInTheDocument();
    expect(screen.getByText('sdg_hub')).toBeInTheDocument();
    expect(screen.getByText('Fullsend')).toBeInTheDocument();
    // UnifAI appears in multiple places; just confirm presence
    expect(screen.getAllByText('UnifAI').length).toBeGreaterThan(0);
  });

  it('renders all 12 speakers', () => {
    render(<InnovationDay />);

    expect(screen.getByText('Hofni Gartner')).toBeInTheDocument();
    expect(screen.getByText('Vlad Luzin')).toBeInTheDocument();
    expect(screen.getByText('Roy Nissim')).toBeInTheDocument();
    expect(screen.getByText('Barak Korren')).toBeInTheDocument();
    expect(screen.getByText('Ella Shulman')).toBeInTheDocument();
    expect(screen.getByText('Benjamin Kapner')).toBeInTheDocument();
    expect(screen.getByText('Carmel Soceanu')).toBeInTheDocument();
    expect(screen.getByText('Guy Ziv')).toBeInTheDocument();
    expect(screen.getByText('Sharon Dashet')).toBeInTheDocument();
    expect(screen.getByText('Nir Rashti')).toBeInTheDocument();
    expect(screen.getByText('Odai Odeh')).toBeInTheDocument();
    expect(screen.getByText('Ilanit Stein')).toBeInTheDocument();
  });

  it('renders Community & Strategic Notes section', () => {
    render(<InnovationDay />);

    expect(screen.getByText('Community & Strategic Notes')).toBeInTheDocument();
    expect(screen.getByText('Format Shift')).toBeInTheDocument();
    expect(screen.getByText('Community Visibility')).toBeInTheDocument();
    expect(screen.getByText('MCP Best Practices')).toBeInTheDocument();
    expect(screen.getByText('AI Assisted Coding')).toBeInTheDocument();
    expect(screen.getByText('MCP Best Practices Adoption')).toBeInTheDocument();
  });

  it('renders the footer attribution note', () => {
    render(<InnovationDay />);
    expect(
      screen.getByText(/Simulated page · Data sourced from Jira GENIE ticket/i)
    ).toBeInTheDocument();
  });
});
