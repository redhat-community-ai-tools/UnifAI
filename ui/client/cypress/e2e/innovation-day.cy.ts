describe('Innovation Day Page E2E', () => {
  beforeEach(() => {
    // Visit the home page first to test navigation
    cy.visit('/');
  });

  it('navigates to the Innovation Day page via the sidebar', () => {
    // Find the link in the sidebar and click it
    cy.contains('Innovation Day Q2 2026').click();

    // Verify the URL changes
    cy.url().should('include', '/innovation-day');

    // Verify the page title
    cy.get('h1').contains('Red Hat Innovation Day').should('be.visible');
  });

  it('displays all sections on the Innovation Day page', () => {
    cy.visit('/innovation-day');

    // Hero Banner
    cy.contains('Q2 2026 — IL Site').should('be.visible');
    cy.contains('Tuesday, June 16th, 2026').should('be.visible');
    cy.contains('09:30 – 13:15').should('be.visible');
    cy.contains('IL (Israel) Site').should('be.visible');

    // Agenda Section (Default Tab)
    cy.contains('h2', 'Agenda').should('be.visible');
    cy.get('table').within(() => {
      cy.contains('Coffee and Ma\'affee').should('be.visible');
      cy.contains('Is Orchestration the Future?').should('be.visible');
      cy.contains('Updates from UnifAI').should('be.visible');
    });

    // Session Highlights Section
    cy.contains('button[role="tab"]', 'Sessions').click();
    cy.contains('h2', 'Session Details').should('be.visible');

    // Test accordion/collapsible behavior for a session card
    cy.contains('Is Orchestration the Future?').parents('button').as('sessionBtn');
    cy.get('@sessionBtn').click();

    // Verify the content is revealed
    cy.contains('A2A (Agent-to-Agent) Communications for multi-agent systems').should('be.visible');
    cy.contains('Peer-to-peer collaboration patterns between autonomous agents').should('be.visible');

    // Key Topics & Projects Section
    cy.contains('button[role="tab"]', 'Projects').click();
    cy.contains('h2', 'Key Projects & Technologies').should('be.visible');
    cy.contains('Code Agent Harness Evaluation').should('be.visible');
    cy.contains('agent-eval-harness').should('be.visible');
    cy.contains('eval-hub').should('be.visible');
    cy.contains('sdg_hub').should('be.visible');
    
    // Speakers Section
    cy.contains('button[role="tab"]', 'Speakers').click();
    cy.contains('h2', 'Speakers').should('be.visible');
    cy.contains('Hofni Gartner').should('be.visible');
    
    // Community Section
    cy.contains('button[role="tab"]', 'Community').click();
    cy.contains('h2', 'Community & Strategic Notes').should('be.visible');
    cy.contains('Format Shift').should('be.visible');
  });
});
