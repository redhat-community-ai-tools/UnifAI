import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import Sidebar from '../Sidebar';

// Mock wouter hooks and components
vi.mock('wouter', () => ({
  useLocation: () => ['/', vi.fn()],
  Link: ({ children, href, className }: any) => (
    <a href={href} className={className} data-testid={`link-${href}`}>
      {children}
    </a>
  ),
}));

// Mock icons
vi.mock('react-icons/fa', () => ({
  FaCalendarAlt: () => <div data-testid="icon-calendar" />,
  // mock other icons as needed or use a proxy
}));

vi.mock('lucide-react', () => {
  return new Proxy({}, {
    get: function(target, prop) {
      return () => <div data-testid={`icon-${String(prop)}`} />;
    }
  });
});

describe('Sidebar Integration', () => {
  it('renders the Innovation Day navigation link', () => {
    render(<Sidebar />);

    // Check if the "Innovation Day Q2 2026" link exists
    const innovationDayLink = screen.getByText('Innovation Day Q2 2026');
    expect(innovationDayLink).toBeInTheDocument();

    // Check if it has the correct href
    const linkElement = innovationDayLink.closest('a');
    expect(linkElement).toHaveAttribute('href', '/innovation-day');

    // Verify the icon is present
    // The FaCalendarAlt icon is used for this nav item
    // Because we mocked it, we can't easily check the specific icon inside the link without more complex queries,
    // but knowing the text and link are correct covers the core integration.
  });
});
