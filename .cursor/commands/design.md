following this command please follow these steps:
1. if a jira case is available check if you have some way to connect to jira (either by mcp or any other way) - if not stop and notify the user that he needs to set jira integration.
2. getting the information from jira you need to understand what is needed in this case and prepare a design to close it

MANDATORY: Use the template structure from '.cursor/files/ADR - Architecture Review Template.md' to create 2 files one in markdown format and the 2nd in html format, both must have the same content so make sure you get the formatting right

DOCUMENT STRUCTURE - MUST FOLLOW EXACTLY the structure in '.cursor/files/ADR - Architecture Review Template.md'


CRITICAL RULES:
✅ DO: Use TABLE format for ALL sections (as in template)
✅ DO: Keep Section 1 to 3 table rows only
✅ DO: Put Success Metrics in Section 1, not elsewhere
✅ DO: List specific file paths in Section 2
✅ DO: Use exact section headers from template
✅ DO: Include diagrams in Section 3
❌ DON'T: Add prose paragraphs outside the table structure
❌ DON'T: Expand Section 1 with details (save for Section 3)
❌ DON'T: Skip any template sections
❌ DON'T: Create your own section structure

CONTENT FOCUS:
- 95% on the NEW solution
- Current state: 1-2 lines maximum (only in Problem Statement if needed)
- No migration analysis unless explicitly requested