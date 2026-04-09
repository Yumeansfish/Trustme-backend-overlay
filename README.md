# Trustme backend overlay

This repository tracks the Trust-me browser/backend overlay extracted from the historical backend work.
It is not a full ActivityWatch backend fork. It keeps the Trust-me specific browser modules,
tooling, and release glue while upstream runtime, watchers, and desktop shell code are pulled from
the upstream ActivityWatch monorepo during build.

## Workspace contract

The local workspace is expected to look like:

```text
trust-me/
  backend/
  frontend/
  upstream/
    activitywatch/
```

All build outputs are written under `upstream/build`.

## Local entrypoints

From inside `backend/`:

```bash
make build-bundle
make sync-app
```

Or from the workspace root:

```bash
./make-sync
```

For repo-local Python imports and test runs, the overlay now exposes a standard package definition:

```bash
python3 -m pip install -e .
python3 -m pytest
```

`make build-bundle` assembles a portable browser-line bundle from:

- `frontend/` for the static UI artifact
- `upstream/activitywatch` for `aw-core`, `aw-client`, `aw-qt`, and the watcher packages
- `backend/` for the Trust-me overlay modules and release glue

The resulting bundle and archive land in `upstream/build/dist`.

## Release shape

The release artifact is a portable `browser-line` bundle directory plus a tarball built from the
same directory. Local `make-sync` uses the exact same bundle and only changes the final deployment
step by syncing the built contents into `/Applications/trust-me.app`.

Historical note: the commits in this repository were reconstructed from the original backend history
and dated to the original work windows so the development sequence stays readable.
