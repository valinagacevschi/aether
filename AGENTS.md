# Repository Guidelines

## Project Structure & Module Organization
This repo follows a specification-first approach with native implementations:

**Repository Structure:**
```
aether-protocol/
├── spec/                    # Source of truth
│   ├── schema.fbs           # FlatBuffers schema
│   ├── test-vectors/        # YAML test cases (conformance)
│   └── protocol.md          # Protocol specification
│
├── implementations/
│   ├── relay/               # Python (asyncio-native)
│   ├── python-sdk/          # Pure Python (shares code with relay)
│   └── typescript-sdk/      # TypeScript + WASM
│
└── integration-tests/       # Cross-language tests
```

Files at the root:
- `README.md`: overview, usage examples, and installation instructions.
- `RFC.txt`: protocol specification.
- `AETHER.md`/`PRD.md`: design and planning notes.

## Build, Test, and Development Commands

### Python (Relay & SDK)
```bash
# Install dependencies
cd implementations/relay  # or python-sdk
pip install -e ".[dev]"

# Run tests
pytest

# Format code
black .
ruff check --fix .

# Type checking
mypy .
```

### TypeScript SDK
```bash
# Install dependencies
cd implementations/typescript-sdk
npm install

# Run tests
npm test

# Build
npm run build

# Lint
npm run lint
```

## Coding Style & Naming Conventions

### Python
- Follow PEP 8 conventions.
- Indentation: 4 spaces.
- Naming: `snake_case` for functions/variables, `PascalCase` for classes, `SCREAMING_SNAKE_CASE` for constants.
- Type hints: Use type annotations (`typing` module or built-in types).
- Formatting: Use `black` for formatting, `ruff` for linting.
- Async: Use `asyncio` for all I/O operations.

### TypeScript
- Follow TypeScript/ESLint conventions.
- Indentation: 2 spaces.
- Naming: `camelCase` for functions/variables, `PascalCase` for classes/types, `SCREAMING_SNAKE_CASE` for constants.
- Type safety: Strict mode enabled, avoid `any`.
- Formatting: Use Prettier, ESLint for linting.

## Testing Guidelines

### Python
- Use `pytest` for all tests.
- Unit tests live in `tests/` directory or alongside code as `test_*.py`.
- Integration tests in `tests/integration/`.
- Test names should be descriptive, e.g., `test_rejects_invalid_signature`.
- Run `pytest` before submitting changes.
- All implementations must pass 100% of test vectors from `spec/test-vectors/`.

### TypeScript
- Use Jest or Vitest for testing.
- Unit tests in `src/**/*.test.ts`.
- Integration tests in `tests/`.
- Test names should be descriptive, e.g., `rejectsInvalidSignature`.
- Run `npm test` before submitting changes.
- All implementations must pass 100% of test vectors from `spec/test-vectors/`.

## Commit & Pull Request Guidelines
Git history shows short, sentence-case summaries (e.g., "Add initial implementation…"). Use the same style:
- Imperative, present tense, no trailing period.

Pull requests should include:
- A short summary of changes and motivation.
- References to relevant issues, PRD sections, or RFC sections.
- Notes on tests run (or why not applicable).
- For protocol changes, update `RFC.txt`, `PRD.md`, and relevant docs.
- Ensure conformance tests pass (Python relay, Python SDK, TypeScript SDK all pass test vectors).

## Conformance & Interoperability
- **Shared Test Vectors:** All implementations must pass 100% of test vectors from `spec/test-vectors/`.
- **Interoperability:** Weekly "plug-fest" testing ensures Python client ↔ Python relay ↔ TypeScript client work together.
- **CI/CD:** All implementations are tested against the same test vectors in CI.

## Security & Configuration Tips
- Do not commit secrets or keys.
- Security-sensitive changes (crypto, signing, identity) must include rationale and tests.
- Use only established cryptographic libraries:
  - Python: PyNaCl (Ed25519), blake3
  - TypeScript: @noble/ed25519 or tweetnacl, blake3 (WASM)

## Implementation Strategy
**"Python for infrastructure, idiomatic SDKs for developers"**
- **Relay:** Python (asyncio-native, debuggable by ML engineers)
- **Python SDK:** Native Python (shares codebase with relay)
- **TypeScript SDK:** Native TypeScript with WASM crypto bundle

This ensures `pip install` and `npm install` work immediately while maintaining debuggability and ecosystem alignment.

## Agent-Specific Instructions
- Keep changes small and reviewable.
- If you introduce new tooling or dependencies, explain why and update this document.
- When adding features, ensure both Python and TypeScript SDKs are updated (or document why only one is needed).
- Follow the spec-first approach: update `spec/` before implementing.
