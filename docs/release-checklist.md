# Release Checklist

## Pre-release

1. Run `npm run typecheck`
2. Run `npm run test`
3. Run `python -m build sdk/python`
4. Run `pnpm -C sdk/typescript build && pnpm -C sdk/typescript pack`

## Tags

- Python package tag: `py-vX.Y.Z`
- TypeScript package tag: `ts-vX.Y.Z`

## Publish Pipelines

- `publish-pypi.yml` triggers on `py-v*`
- `publish-npm.yml` triggers on `ts-v*`

## Post-release smoke checks

1. `pip install aether-protocol`
2. `python -c "import aether"`
3. `npm install @aether-protocol/sdk`
4. `node -e "require('@aether-protocol/sdk')"`
