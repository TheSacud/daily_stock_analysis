# Run Diagnostics P0

P0 diagnostics cover the highest-priority runtime checks that determine whether the application can start and produce a basic analysis.

## Scope

- Required configuration presence.
- Model provider availability.
- Core data-provider reachability.
- Writable runtime directories.
- Basic report generation path.

## Expected Behavior

Diagnostics should return structured status, reason codes, and remediation hints. They should avoid hiding failures behind silent fallbacks.