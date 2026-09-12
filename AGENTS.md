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

## Canonical Verification Commands
```powershell
# Run full automated test suite (unit + Qt integration)
uv run pytest

# Run end-to-end runtime validation script (synthetic video, seek/step/mark/persist)
uv run python scripts/runtime_validation.py

# Reinstall Windows desktop & start menu shortcuts for Listary
uv run python scripts/install_launchers.py
```
