# AGENTS.md

## Project Purpose
StratLab is a Windows desktop application for speedrunners to rapidly compare 2 or more gameplay attempts/strategies from a single video recording. It provides frame-accurate scrubbing, IN/OUT marking, and automatic ranking with exact deltas in seconds, milliseconds, frames, and percentages slower.

## Environment & Tooling
- **OS**: Windows 11
- **Runtime**: Python >= 3.11 with `uv`
- **Frameworks**: PySide6 (Qt Widgets), PyAV (`av`)
- **System Tools**: FFmpeg, ffprobe
- **Launchers**: `stratlab.bat` and `stratlab.vbs` in project root; shortcuts in `%APPDATA%\Microsoft\Windows\Start Menu\Programs\Python Tools\` and `%USERPROFILE%\Desktop\`.

## Architectural Invariants
1. **Authoritative Timing**:
   - Frame number is the authoritative timing source (`duration_frames = out_frame - in_frame`).
   - Timestamps and durations derive from `frames / fps`.
   - Frame rates are represented as exact `fractions.Fraction` (e.g. `Fraction(60000, 1001)` for 59.94 FPS) to prevent floating-point drift.
2. **Segment Validation**:
   - OUT must be strictly greater than IN (`OUT > IN`).
   - Segments with `OUT <= IN` or missing IN/OUT points are marked invalid/incomplete and excluded from ranking.
3. **Speedrun Comparison Formulas**:
   - `delta_seconds = attempt_duration - fastest_duration`
   - `delta_frames = attempt_frames - fastest_frames`
   - `percent_slower = ((attempt_duration - fastest_duration) / fastest_duration) * 100.0`
4. **Threading**:
   - PyAV decoding and playback loops execute on `VideoWorker` (`QThread`), never on the Qt GUI thread.
   - All worker communication uses Qt Signals and Slots (`QueuedConnection`).
5. **Frame Caching**:
   - `FrameCache` provides bounded LRU caching of decoded `QImage` objects for instantaneous (<1ms) forward/backward frame stepping.
6. **Input Request Coalescing**:
   - Frame navigation maintains immediate UI responsiveness by updating `_desired_frame` synchronously and coalescing decode requests sent to background workers (`_seek_in_flight`). Rapid repeated keypresses or slider drags never accumulate a FIFO decode backlog.
7. **Authoritative Shortcut Routing**:
   - Frame navigation, playhead stepping, and IN/OUT marking are authoritatively routed via `MainWindow.eventFilter` (ignoring active `QLineEdit` inputs) to eliminate duplicate shortcut collisions and dropped key events.
8. **Synchronized Comparison Engine**:
   - Side-by-side strategy comparison operates dual independent `VideoReader` instances on `CompareWorker` (`QThread`), synchronously aligned from relative frame 0. When the shorter attempt reaches its OUT frame, it cleanly freezes on that frame while the longer attempt continues.
9. **Playback / Navigation Separation**:
   - During playback, the worker's wall-clock position is authoritative and the UI mirrors emitted frames without seeking toward stale navigation targets. User seeks and steps pause playback before entering the coalesced paused-navigation path.
10. **Decoded Pixel Memory Bound**:
   - `FrameCache` is bounded by both frame count and expanded `QImage` byte size so high-resolution recordings cannot grow the RGB cache without limit.

## Canonical Verification Commands
```powershell
# Run full automated test suite (unit + Qt integration)
uv run pytest

# Run end-to-end runtime validation script (synthetic video, seek/step/mark/persist)
uv run python scripts/runtime_validation.py

# Run heavy stress validation (1440p60 profile, coalescing, compare mode, persistence)
uv run python scripts/stress_validation.py

# Reinstall Windows desktop & start menu shortcuts for Listary
uv run python scripts/install_launchers.py
```
