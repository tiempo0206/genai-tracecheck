## Summary

Describe the smallest user-visible change and why it is needed.

## Evidence

Link the issue and any pinned upstream specification section. State explicitly when behavior is
recommended, experimental, provider-specific, or local policy rather than required.

## Verification

- [ ] `ruff check .`
- [ ] `ruff format --check .`
- [ ] `coverage run -m pytest && coverage report`
- [ ] New behavior has positive, negative, and boundary coverage.
- [ ] Fixtures and diagnostics contain no real prompts, credentials, personal data, or proprietary content.
- [ ] Public behavior, rule metadata, examples, and project log are updated where applicable.
- [ ] Distribution or dependency changes include a clean-install smoke test.

## Rule changes only

- [ ] The rule family and unused ID are correct.
- [ ] The implementation cites accepted evidence or is labeled as TraceCheck policy.
- [ ] The finding never copies sensitive attribute values.
- [ ] `rule_catalog.py`, README rule table, tests, and documentation agree.
