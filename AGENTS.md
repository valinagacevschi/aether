# Repository Guidelines

Aether Protocol: Decentralized binary messaging for autonomous AI agents.

## Project Structure

This repo follows a specification-first approach with native implementations:

Files at the root:
- `README.md`: overview, usage examples, and installation instructions.
- `RFC.txt`: formal protocol specification (authoritative).
- `AETHER.md`: high-level protocol overview and architectural philosophy.
- `PRD.md`: product requirements document with implementation details.

## Development Guidelines

- **Python Development**: [Python guidelines](.cursor/rules/python-development.mdc)
- **TypeScript Development**: [TypeScript guidelines](.cursor/rules/typescript-development.mdc)
- **Git Workflow**: [Commit and PR guidelines](.cursor/rules/git-workflow.mdc)
- **Security**: [Security guidelines](.cursor/rules/security.mdc)
- **Conformance**: [Conformance and interoperability](.cursor/rules/conformance.mdc)
- **Implementation Strategy**: [Architecture decisions](.cursor/rules/implementation-strategy.mdc)

## Core Principles

- **Spec-first approach**: Update `spec/` before implementing.
- **Small, reviewable changes**: Keep PRs focused and easy to review.
- **Tooling changes**: If you introduce new tooling or dependencies, explain why and update relevant documentation.

## Lessons Learned

- Normalize cross-protocol aliases at adapter boundaries (`id` vs `event_id`) before validation to prevent subtle interoperability failures.
