# 検証 / 验证 / Validation

## Transcript workspace — 2026-10-31

- Python syntax/import checks passed for the macOS source, shared workspace modules and Windows source. Windows source imports resolve the shared backend and static resources from the repository root.
- `python -m unittest discover -s tests -v`: 11 tests passed. Coverage includes version conflicts, persisted edited results and snapshots, canonical Markdown export, credential masking (including invalid requests), cross-origin/Host restrictions, cancellation, input limits, ASR result import and timestamp identity after reordering/deleting repeated paragraphs.
- JavaScript syntax and `git diff --check` passed.
- In-browser workflow passed against a real local HTTP fixture: import text, configure a compatible endpoint, generate, locate sources, edit, save, reload and retain source links. HTTP checks also verified the original transcription entry and canonical download content. The fixture runs outside the repository; no test model result or connection is hard-coded in the application.
- Two-axis code review completed. Standards: canonical Markdown duplication resolved. Spec: cancellation/document isolation, audio identity, citations after editing and audio continuity were corrected; no outstanding findings remained in follow-up review.
- No real third-party model credentials or personal recordings were used. Live model quality, Whisper accuracy and macOS/Windows binary packaging were not retested. Browser inspection covered the current narrow preview viewport, not a full device/accessibility matrix.

## Publication preparation — 2026-10-20

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
