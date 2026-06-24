# Cursor Commands

Custom Cursor IDE commands for the UnifAI project. Invoke with `/` in the Cursor chat.

## Primary Command

### `/pipeline` — Multi-Phase Development Pipeline

The unified development workflow featuring design, review, implementation, code review, QA, and debugging phases with automatic revision loops.

**Modes:**

| Mode | Usage | Phases |
|------|-------|--------|
| `full` (default) | `/pipeline <task or Jira ticket>` | Design → Review → Implement → Code Review → QA |
| `design-only` | `/pipeline design-only <task>` | Design only |
| `design-and-review` | `/pipeline design-and-review <task>` | Design → Design Review |
| `implement` | `/pipeline implement <design-file>` | Implement → Code Review → QA |
| `review-only` | `/pipeline review-only <design-file>` | Design Review only |
| `code-review-only` | `/pipeline code-review-only [files]` | Code Review only |
| `qa-only` | `/pipeline qa-only [files]` | QA only |
| `debug` | `/pipeline debug <error>` | Structured debugging |
| `arch-review` | `/pipeline arch-review [files]` | Architecture review (CI mode) |
| `review` | `/pipeline review [files]` | Architecture + Code Review (parallel judges, CI preferred) |

**Options:**
- `--adr` — Write design to ADR file at `docs/designs/<slug>-adr.md`

> **Note:** When passing a Jira ticket ID, requires Jira MCP server or API credentials (see [Setup Requirements](#setup-requirements)).

**Examples:**
```
/pipeline design-only --adr Add caching layer for vector search
/pipeline full GENIE-1234
/pipeline code-review-only rag/core/pipeline/
/pipeline implement docs/designs/caching-adr.md
/pipeline debug "PipelineExecutor fails with empty source list"
```

---

## Utility Commands

### `/review` — Quick Branch Review

Performs automated code reviews on your current branch with varying depth levels.

**Usage:**
```
/review [basic|deep] [files/folders]
```

**Parameters:**
- `basic` (default): Quick review focusing on obvious issues
- `deep`: Comprehensive review including design validation
- `files/folders` (optional): Specify particular files or folders to review

**Output:**
Creates a review file named `<branch_name>_<review_type>_review.md` containing:
1. Short overview of the feature and its purpose
2. Issues found, organized by area and severity
3. Design reference (for deep reviews or when architecture.md exists)

**Example:**
```
/review deep src/components/
```

---

### `/push` — Design Document Uploader

Uploads design files to specified Jira tickets.

**Prerequisites:**
- Jira MCP server configured in Cursor settings (or Jira API credentials in environment)
- Design file already created

**Usage:**
```
/push <jira-ticket> <file-name>
```

**Parameters:**
- `jira-ticket`: The Jira ticket ID to upload to
- `file-name`: Path to the design file to upload

**Example:**
```
/push GENIE-1163 GENIE-1163_design.html
```

---

## Setup Requirements

### Jira Integration

The `pipeline` (when given a Jira ticket), `design`, and `push` commands require Jira connectivity. Ensure you have one of the following configured:

1. **MCP Server** — Jira MCP server in your Cursor settings
2. **API Credentials** — Jira API tokens configured in your environment

If Jira integration is not available, the commands will notify you and stop execution.

### Template Files

The `design` phase requires:
- `.cursor/files/ADR - Architecture Review Template.md`

---

## Deprecated Commands

These commands are superseded by `/pipeline` modes. They remain functional but will be removed in a future cleanup pass.

| Legacy Command | Replaced By |
|---------------|-------------|
| `/Code.Review` | `/pipeline code-review-only` |
| `/Hexagonal.Gatekeeper` | `/pipeline code-review-only` or `arch-review` |
| `/Hexagonal.Refactor` | `/pipeline implement <design>` |
| `/PyTest.GateKeeper` | `/pipeline qa-only` |
| `/design` | `/pipeline design-only --adr` |

---

## Best Practices

### For Code Reviews

1. **Run basic reviews frequently** during development
2. **Run deep reviews** before:
   - Creating pull requests
   - Merging to main branches
   - Releasing features
3. **Target specific areas** when reviewing large changes
4. **Address all severity levels** in the review output

### For Design Documents

1. **Create designs early** in the feature development lifecycle
2. **Update designs** when significant changes occur
3. **Reference architecture.md files** in relevant folders
4. **Push designs to Jira** for team visibility and collaboration

---

## Troubleshooting

**Jira connection errors:**
- Verify Jira MCP server is running
- Check API credentials and permissions
- Confirm network connectivity to Jira instance

**Review file not generated:**
- Ensure you're on a git branch (not detached HEAD)
- Check write permissions in the current directory
- Verify there are changes to review on the branch

---

**Last Updated:** June 2026
**Project:** UnifAI
