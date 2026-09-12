# StratLab

A frame-accurate Windows desktop utility for speedrunners to rapidly compare multiple attempts or strategies from a single recording.

## Key Features

- **Frame-Accurate Video Scrubbing & Coalescing**: Built with PyAV with CFR frame-indexing, bounded LRU caching, and request coalescing for lag-free rapid stepping and dragging.
- **Speedrun Invariants**: Authoritative integer frame numbers prevent floating-point time drift across common fractional broadcast framerates (59.94, 29.97, 23.976 FPS).
- **Streamlined Workflow with Auto-Attempt Creation**:
  - Press `I` at run start (auto-creates Attempt 1 if none exists).
  - Press `O` at run end to complete Attempt 1.
  - Seek to next run and press `I` — StratLab automatically creates Attempt 2 and sets its IN point!
- **Unified Attempt & Results Dashboard**: Real-time ranking, durations, frame counts, and deltas (`+0.084s / +5 frames / +2.01%`) in a clean, compact panel.
- **Side-by-Side Synchronized Comparison Mode**:
  - Compare any two attempts side-by-side with synchronized relative playback from relative frame 0.
  - The shorter attempt freezes on its OUT frame when it completes, clearly showing how far behind the other attempt is.
  - Relative timeline slider, synchronized stepping, and one-click restart.
- **Lightweight JSON Persistence**: Save and reopen sessions (`.stratlab`), with graceful handling of missing or relocated video files.
- **Zero-Flash Launchers**: Integrated with Windows Start Menu, Desktop, and Listary.

---

## Keyboard Shortcuts

| Shortcut | Action |
|---|---|
| `Left Arrow` | Step -1 Frame (or -1 relative frame in Compare Mode) |
| `Right Arrow` | Step +1 Frame (or +1 relative frame in Compare Mode) |
| `Shift + Left Arrow` | Step -10 Frames (or -10 relative frames in Compare Mode) |
| `Shift + Right Arrow` | Step +10 Frames (or +10 relative frames in Compare Mode) |
| `Space` | Play / Pause Toggle (Single player or Compare Mode) |
| `I` | Mark IN (auto-creates next attempt when current is complete) |
| `O` | Mark OUT for active attempt |
| `Esc` | Exit Side-by-Side Compare Mode |
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
