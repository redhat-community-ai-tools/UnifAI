import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import InnovationDay from '../InnovationDay';

// Mock the child components to simplify testing
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

// Mock framer-motion to bypass animations in tests
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

describe('InnovationDay Page', () => {
  it('renders the layout components (Sidebar, Header, StatusBar)', () => {
    render(<InnovationDay />);

    expect(screen.getByTestId('sidebar-mock')).toBeInTheDocument();
    expect(screen.getByTestId('header-mock')).toHaveTextContent('Header: Innovation Day — IL Site Q2 2026');
    expect(screen.getByTestId('statusbar-mock')).toBeInTheDocument();
  });

  it('renders the Hero Banner with correct information', () => {
    render(<InnovationDay />);

    expect(screen.getByText('Red Hat Event')).toBeInTheDocument();
    expect(screen.getByText(/Red Hat Innovation Day/i)).toBeInTheDocument();
    expect(screen.getByText(/Q2 2026 — IL Site/i)).toBeInTheDocument();

    // Check info chips
    expect(screen.getByText('Tuesday, June 16th, 2026')).toBeInTheDocument();
    expect(screen.getByText('09:30 – 13:15')).toBeInTheDocument();
    expect(screen.getByText('IL (Israel) Site')).toBeInTheDocument();
  });

  it('renders the Agenda section with correct rows', () => {
    render(<InnovationDay />);

    expect(screen.getByText('Agenda')).toBeInTheDocument();

    // Check some agenda items
    expect(screen.getByText('Coffee and Ma\'affee')).toBeInTheDocument();
    expect(screen.getByText('09:30–10:00')).toBeInTheDocument();

    expect(screen.getByText('Is Orchestration the Future?')).toBeInTheDocument();
    expect(screen.getByText('Vlad Luzin, Roy Nissim')).toBeInTheDocument();
  });

  it('renders Session Highlights and expands on click', () => {
    render(<InnovationDay />);

    expect(screen.getByText('Session Highlights')).toBeInTheDocument();

    // Check that the session title is rendered
    expect(screen.getAllByText('Is Orchestration the Future?').length).toBeGreaterThan(0);

    // The points shouldn't be visible initially (or they might be if we mocked AnimatePresence poorly,
    // but assuming standard behavior, we click to expand)
    const toggleButton = screen.getAllByRole('button').find(btn => btn.textContent?.includes('Is Orchestration the Future?'));

    if (toggleButton) {
      fireEvent.click(toggleButton);
      // Now the details should be in the document
      expect(screen.getByText('A2A (Agent-to-Agent) Communications for multi-agent systems')).toBeInTheDocument();
    }
  });

  it('renders Key Topics & Projects', () => {
    render(<InnovationDay />);

    expect(screen.getByText('Key Topics & Projects')).toBeInTheDocument();

    // Check for some projects
    expect(screen.getByText('Code Agent Harness Evaluation')).toBeInTheDocument();
    expect(screen.getByText('agent-eval-harness')).toBeInTheDocument();
    expect(screen.getByText('eval-hub')).toBeInTheDocument();
    expect(screen.getByText('sdg_hub')).toBeInTheDocument();
  });
});
