# Desktop Packaging

The desktop app packages the Web UI with an Electron shell and connects it to the backend runtime.

## Scope

Desktop changes usually affect:

- `apps/dsa-desktop/`
- `apps/dsa-web/`
- desktop build scripts under `scripts/`
- release workflow packaging steps

## Build Order

1. Build the Web app.
2. Build the Electron desktop app.
3. Verify the packaged app can start the backend and load the Web UI.
4. Confirm runtime data and user configuration paths are not bundled as secrets.

## Validation

Run the closest available local build command for the platform. If a platform-specific package cannot be built locally, state which part was verified and which part relies on CI or release workflow validation.

## Release Notes

When changing desktop packaging behavior, document startup impact, bundled assets, configuration migration, and rollback path.