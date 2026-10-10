# Baldur

Local Windows posture watcher for desk workers. A webcam-based posture
score runs in the background; slouch too long and a fullscreen warning
takes the screen and parks the mouse until you sit tall again. No
account, no cloud, no recordings.

Two parts: **Recognition** (Python + YOLO pose scoring, headless) and
**Warning** (C# WPF tray app hosting the engine as a child process).

## How it works

- The engine scores your posture from the webcam, continuously.
- Slouch for **10 seconds** (score under 70) → fullscreen `STAND TALL!!!`
  warning plus mouse blocking.
- Sit tall for **3 seconds** (score 80 or higher) → the warning hides
  itself and the mouse is freed.
- No camera, no watching: a small dialog says `Camera is unavailable`,
  with Close (quits) and, mid-run, Continue (re-checks and resumes).
- The app lives in the system tray when all is well.

## Download and install

1. Open the [Releases page](https://github.com/semite91/Baldur/releases)
   and download the latest `BaldurSetup` installer.
2. Run it. Windows SmartScreen warns because the build is unsigned;
   choose to run it anyway.
3. Installs per user (no admin rights needed). Requires Windows 10/11
   64-bit and a webcam with camera permission enabled for desktop apps.

## Daily use

- Start Baldur from the Start Menu (it does not auto-start).
- While blocked: **ESC** quits the app completely, **ENTER** hides the
  warning and keeps watching, **q** quits the camera preview window.
- Right-click the tray icon and choose Quit to exit any time.
- Optional camera preview: run the engine with `--preview` for a live
  score window beside the tray app.
- Settings live in `%APPDATA%\Baldur\WarningConfig.json` (created on
  first run): warning closable, flashing, and the mouse-blocking flag.

## Privacy

Everything happens on your machine. No images, scores, or keypoints are
stored or sent anywhere (see `docs/adr/0002-no-persistence.md`).

## Uninstall

Remove via Add/Remove programs. The settings file above is kept; delete
it by hand for a fully clean slate.

## Troubleshooting

- **Nothing happens on launch:** a second copy may already run (single
  instance exits quietly — check the tray), or the engine is missing;
  run from a terminal to see the `baldur[boot]` reason line.
- **No camera window / camera dialog:** another app (browser, meetings,
  the dev notebook viewer) may hold the webcam; close it and press
  Continue. Covering the lens does not count — frames still arrive.
- **SmartScreen / antivirus warnings:** expected for the unsigned
  hook-based build; a signed release is planned.
- **Keys dead while blocked:** the warning window must own keyboard
  focus; Alt+Tab to it, then ESC/ENTER. Terminal lines starting with
  `baldur[host]` and `baldur[focus]` show what the app sees.

## For developers

Layout: `src/Warning/` (WPF app, `net8.0-windows`), `engine.py`
(recognition entry, thin composition over `notebooks/00`-`03` plus
`05` for preview), `notebooks/` (numbered Jupyter stages, single source
of truth), `tests/` + `tests/Warning.Tests/` (suites), `infrastructure/test/`
(scenario/result records), `installer/` (Inno Setup script), `docs/`.

Prerequisites: .NET 8 SDK, a Python 3.11 venv with the pinned packages,
YOLO pose weights. Build and test:

```powershell
dotnet build Baldur.sln
dotnet test Baldur.sln
B:\venvs\baldur\Scripts\python.exe -m pytest tests/
```

Contract between the halves: the engine prints only four frozen
JSON-lines events on stdout — `bad_posture`, `recovered`, `heartbeat`,
`error` — with the 10s / 3s / 5s dwell bars above; everything else goes
to stderr. `engine.py` defines no scoring logic itself; notebooks stay
the only definers (enforced by guard tests).

Work is tracked in [GitHub Issues](https://github.com/semite91/Baldur/issues)
with the five triage labels; coding process and standards live in
`instruction/standards.md` and `instruction/coding_standards.md`.

## Project status

Recognition scoring, Warning host (fullscreen modal, mouse block, tray,
recovery/error/heartbeat handling), the duplication-free engine with
live preview, production boot with side-by-side engine discovery, and a
working offline installer are done. Acceptance hardening, packaging
sign-off, and live-camera gates are tracked as open issues.
