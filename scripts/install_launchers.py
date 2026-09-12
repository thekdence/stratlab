"""Install Windows shortcuts for StratLab in Start Menu and Desktop."""

import os
import subprocess
from pathlib import Path


def create_shortcut(target_vbs: Path, working_dir: Path, shortcut_path: Path, description: str = "StratLab"):
    shortcut_path.parent.mkdir(parents=True, exist_ok=True)

    ps_script = (
        f'$WshShell = New-Object -ComObject WScript.Shell; '
        f'$Shortcut = $WshShell.CreateShortcut("{shortcut_path}"); '
        f'$Shortcut.TargetPath = "{target_vbs}"; '
        f'$Shortcut.WorkingDirectory = "{working_dir}"; '
        f'$Shortcut.Description = "{description}"; '
        f'$Shortcut.Save()'
    )

    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", ps_script],
        capture_output=True,
        text=True,
    )
    if shortcut_path.exists():
        print(f"Created shortcut: {shortcut_path}")
    else:
        print(f"Failed to create shortcut: {shortcut_path}, error: {result.stderr}")


def main():
    project_root = Path(__file__).resolve().parent.parent
    vbs_path = project_root / "stratlab.vbs"

    if not vbs_path.exists():
        print(f"Error: {vbs_path} does not exist.")
        return

    # Start Menu Programs / Python Tools
    appdata = os.environ.get("APPDATA", "")
    if appdata:
        start_menu_dir = Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Python Tools"
        create_shortcut(vbs_path, project_root, start_menu_dir / "StratLab.lnk")

    # Desktop
    userprofile = os.environ.get("USERPROFILE", "")
    if userprofile:
        desktop_dir = Path(userprofile) / "Desktop"
        create_shortcut(vbs_path, project_root, desktop_dir / "StratLab.lnk")


if __name__ == "__main__":
    main()
