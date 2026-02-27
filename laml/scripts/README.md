# LAML Scripts

## Start dashboard and HTTP API at login (macOS)

To have the **LAML Dashboard** and **LAML HTTP API** start automatically when you log in (so they are already running when you open Cursor):

```bash
# From repo root
./laml/scripts/install-launch-agents.sh
```

This installs two LaunchAgents:

- **com.laml.http-api** – LAML HTTP API on port 8082 (dashboard backend)
- **com.laml.dashboard** – LAML Dashboard (Vite) on port 5173

They start at login and restart if they exit. Logs: `~/Library/Logs/LAML/`.

To stop or disable:

```bash
launchctl unload ~/Library/LaunchAgents/com.laml.http-api.plist
launchctl unload ~/Library/LaunchAgents/com.laml.dashboard.plist
```

To start again:

```bash
launchctl load ~/Library/LaunchAgents/com.laml.http-api.plist
launchctl load ~/Library/LaunchAgents/com.laml.dashboard.plist
```

## Manual start (no LaunchAgents)

- **HTTP API:** `./laml/scripts/start-laml-http-api.sh` (or `cd laml/laml-server && PYTHONPATH=. .venv/bin/python -m src.http_api`)
- **Dashboard:** `./laml/scripts/start-laml-dashboard.sh` or `./laml/dashboard/start-dashboard.sh`
