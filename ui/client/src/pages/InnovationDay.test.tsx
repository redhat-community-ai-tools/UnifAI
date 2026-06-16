import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import InnovationDay from './InnovationDay';

// Mock components that might cause issues in jsdom
vi.mock('@/components/layout/Sidebar', () => ({
  default: () => <div data-testid="sidebar">Sidebar</div>,
}));

vi.mock('@/components/layout/Header', () => ({
  default: ({ title }: { title: string }) => <div data-testid="header">{title}</div>,
}));

vi.mock('@/components/layout/StatusBar', () => ({
  default: () => <div data-testid="statusbar">StatusBar</div>,
}));

vi.mock('@/contexts/ThemeContext', () => ({
  useTheme: () => ({ theme: 'dark', setTheme: vi.fn() }),
}));

describe('InnovationDay Page', () => {
  it('renders correctly with header, date, and agenda items', () => {
    render(<InnovationDay />);
    
    // Test 1: Page Rendering
    // Verify header
    expect(screen.getByTestId('header')).toHaveTextContent('Innovation Day · IL Site');
    
    // Verify title and date
    expect(screen.getAllByText(/Innovation Day/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Q2 2026/i).length).toBeGreaterThan(0);
    
    // Verify extracted agenda items
    expect(screen.getAllByText("Coffee and Ma'affee").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Intro to Innovation Day").length).toBeGreaterThan(0);
  });

  it('allows interacting with session cards (expanding and marking attended)', () => {
    render(<InnovationDay />);
    
    // Test 2: Component Interaction
    // Find the first session card (Coffee and Ma'affee) - we want the h3 tag
    const firstSessionTitles = screen.getAllByText("Coffee and Ma'affee");
    const h3Title = firstSessionTitles.find(el => el.tagName.toLowerCase() === 'h3');
    const sessionCard = h3Title?.closest('button');
    
    expect(sessionCard).toBeInTheDocument();
    
    // Initially the description might be hidden or aria-expanded is false
    expect(sessionCard).toHaveAttribute('aria-expanded', 'false');
    
    // Click to expand
    fireEvent.click(sessionCard!);
    
    // Now it should be expanded
    expect(sessionCard).toHaveAttribute('aria-expanded', 'true');
    
    // Find the "Mark as Attended" button inside the expanded area
    const markAttendedBtns = screen.getAllByRole('button', { name: /Mark as Attended/i });
    const markAttendedBtn = markAttendedBtns[0];
    
    expect(markAttendedBtn).toBeInTheDocument();
    
    // Click "Mark as Attended"
    fireEvent.click(markAttendedBtn);
    
    // Button should change to "Marked as Attended"
    const markedAttendedBtn = screen.getAllByRole('button', { name: /Marked as Attended/i })[0];
    expect(markedAttendedBtn).toBeInTheDocument();
  });
});
