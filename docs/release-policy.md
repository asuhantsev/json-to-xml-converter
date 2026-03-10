# Release Policy

## Versioning
- Use SemVer: `MAJOR.MINOR.PATCH`.
- `PATCH`: bugfixes, no CLI contract breaks.
- `MINOR`: backwards-compatible features/flags.
- `MAJOR`: breaking changes in output schema or CLI behavior.

## Release checklist
1. Run tests: `PYTHONPATH=src pytest -q`.
2. Run smoke test: `./scripts/smoke_test.sh`.
3. Run benchmark: `python3 scripts/benchmark_large_export.py --multiplier 20`.
4. Update `readme.md` and changelog section.
5. Tag release: `git tag vX.Y.Z`.
6. Push tag and publish release notes.

## Notes format
- Added
- Changed
- Fixed
- Deprecated
- Removed

## Quality gate
A release is allowed only when CI is green and smoke test passes on current main branch.
