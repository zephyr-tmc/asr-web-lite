# 検証 / 验证 / Validation

Date: 2026-10-20. Platform: macOS arm64. Runtime: Python 3.12.8, using the existing ASR development environment.

## Checks performed

- Parsed all 17 Python and PyInstaller spec files across the macOS and Windows source variants.
- Started the source application on `127.0.0.1:8765`.
- Verified HTTP 200 responses from `/`, `/api/health`, `/api/tasks`, `/static/app.js` and `/static/style.css`.
- Verified an empty task list in the clean publication copy.
- Verified HTTP 404 for missing-task lookup and result download.
- Submitted a synthetic unsupported `.exe` filename and verified HTTP 400 without creating a task.
- Inspected the browser interface with no personal recording or transcript loaded; [the screenshot](images/app.jpg) captures this empty state.

## Not performed

No real audio inference, accuracy benchmarking, macOS package build, signing/notarization or Windows hardware test was performed during publication preparation. The checks above establish source syntax, basic startup, static assets and selected API behavior.

## Publication changes

The two existing platform variants were collected in one repository. The macOS spec now resolves FFmpeg from PATH and the model cache from the current user's home directory instead of a workstation-specific path. This spec was parsed but not built. No recording, transcript, task history, model weight or installer is included.
