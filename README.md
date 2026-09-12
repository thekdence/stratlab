# StratLab

A frame-accurate Windows desktop utility for speedrunners to rapidly compare multiple attempts or strategies from a single recording.

## Key Features

- **Frame-Accurate Video Scrubbing**: Built with PyAV (direct FFmpeg bindings) with CFR frame-indexing and a bounded LRU cache for instantaneous single-frame stepping.
- **Speedrun Invariants**: Authoritative integer frame numbers prevent floating-point time drift across common fractional broadcast framerates (59.94, 29.97, 23.976 FPS).
- **Segment Management**: Create and track 2+ attempts, mark IN and OUT points, reorder, rename, and play segments in isolation.
- **Instant Comparison & Ranking**:
  - Automatically calculates rankings, fastest attempt, duration in seconds/ms/frames.
  - Computes exact deltas from fastest (`+0.084s / +5 frames / +2.01%`).
  - One-click copy formatted summary for Discord / notes.
- **Lightweight JSON Persistence**: Save and reopen sessions (`.stratlab`), with graceful handling of missing or relocated video files.
- **Zero-Flash Launchers**: Integrated with Windows Start Menu, Desktop, and Listary.

---

## Keyboard Shortcuts

| Shortcut | Action |
|---|---|
| `Left Arrow` | Step -1 Frame |
| `Right Arrow` | Step +1 Frame |
| `Shift + Left Arrow` | Step -10 Frames |
| `Shift + Right Arrow` | Step +10 Frames |
| `Space` | Play / Pause Toggle |
| `I` | Mark IN point for active attempt |
| `O` | Mark OUT point for active attempt |
| `Ctrl + N` | New Project |
| `Ctrl + O` | Open Video File |
| `Ctrl + S` | Save Project |
| `Ctrl + Shift + S` | Save Project As |
| `Ctrl + T` | Add New Attempt |

---

## Launching StratLab

### 1. Listary (Recommended)
Double-tap `Ctrl` to open Listary, type `StratLab`, and press `Enter`.

### 2. Desktop or Start Menu
Open the `StratLab` shortcut on your Desktop or under Start Menu -> Programs -> Python Tools.

### 3. Command-line Launcher
From the project root:
```powershell
.\stratlab.bat
```

---

## Development & Verification

### Install Dependencies
```powershell
uv sync
```

### Run Tests
```powershell
uv run pytest
```

### Run Full End-to-End Runtime Validation
```powershell
uv run python scripts/runtime_validation.py
```

### Install / Refresh Windows Launchers
```powershell
uv run python scripts/install_launchers.py
```
