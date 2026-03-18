"""
Admin privilege check for Windows 11.
The assistant requires administrator rights so it can read activity from
all desktop windows and write to protected paths.
"""

import sys
import os
import subprocess
import platform


def is_admin() -> bool:
    """
    Return True when the current process is running with administrator
    privileges on Windows, or as root on Unix-like systems.
    """
    if platform.system() == "Windows":
        try:
            import ctypes
            return bool(ctypes.windll.shell32.IsUserAnAdmin())
        except Exception:
            return False
    else:
        # On Linux/macOS (useful for development/testing)
        return os.geteuid() == 0


def relaunch_as_admin() -> None:
    """
    Re-launch the current script with administrator privileges using the
    Windows UAC prompt (ShellExecuteW with 'runas').  This function never
    returns; it exits the current process after requesting elevation.

    On non-Windows systems the function is a no-op (useful for testing).
    """
    if platform.system() != "Windows":
        print("Admin re-launch is only supported on Windows.")
        return

    try:
        import ctypes
        ctypes.windll.shell32.ShellExecuteW(
            None,
            "runas",
            sys.executable,
            " ".join(f'"{arg}"' for arg in sys.argv),
            None,
            1,
        )
    except Exception as exc:
        print(f"Failed to re-launch as admin: {exc}", file=sys.stderr)
    sys.exit(0)


def require_admin(auto_relaunch: bool = True) -> None:
    """
    Ensure the process has admin rights.

    Parameters
    ----------
    auto_relaunch:
        When True (default) and the process is *not* running as admin on
        Windows, automatically trigger UAC elevation and exit.
        When False, raise a PermissionError instead.
    """
    if is_admin():
        return

    if auto_relaunch and platform.system() == "Windows":
        relaunch_as_admin()
    else:
        raise PermissionError(
            "This application must be run as Administrator.\n"
            "Right-click the launcher and choose 'Run as administrator'."
        )
