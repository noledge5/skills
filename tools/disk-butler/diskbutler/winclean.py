"""Windows system hygiene: installed programs, leftovers, autostart,
services and scheduled tasks.

Everything here is **report-first**: the functions enumerate and
classify, they never change the system. The one mutating helper
(`disable_startup_entry`) only handles registry Run keys and Startup
folder items — the two safest categories — and quarantines rather than
deletes where possible. Services and scheduled tasks are never touched;
for those the report includes the exact command an administrator can
review and run.

On non-Windows platforms every function raises NotSupported, which the
API layer turns into a clear error message.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys


class NotSupported(RuntimeError):
    pass


def _require_windows() -> None:
    if sys.platform != "win32":
        raise NotSupported("This feature is only available on Windows.")


def _powershell(script: str, timeout: int = 60) -> str:
    out = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
        capture_output=True, text=True, timeout=timeout,
    )
    if out.returncode != 0:
        raise RuntimeError(out.stderr.strip() or "powershell failed")
    return out.stdout


def _ps_json(script: str) -> list[dict]:
    raw = _powershell(script + " | ConvertTo-Json -Depth 3").strip()
    if not raw:
        return []
    data = json.loads(raw)
    return data if isinstance(data, list) else [data]


# --- Installed programs & leftovers -----------------------------------

_UNINSTALL_KEYS = [
    (r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall", "HKLM"),
    (r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall", "HKLM"),
    (r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall", "HKCU"),
]


def installed_programs() -> list[dict]:
    _require_windows()
    import winreg

    hives = {"HKLM": winreg.HKEY_LOCAL_MACHINE, "HKCU": winreg.HKEY_CURRENT_USER}
    programs = []
    for key_path, hive_name in _UNINSTALL_KEYS:
        try:
            key = winreg.OpenKey(hives[hive_name], key_path)
        except OSError:
            continue
        with key:
            for i in range(winreg.QueryInfoKey(key)[0]):
                try:
                    sub = winreg.OpenKey(key, winreg.EnumKey(key, i))
                except OSError:
                    continue
                with sub:
                    def val(name: str) -> str:
                        try:
                            return str(winreg.QueryValueEx(sub, name)[0])
                        except OSError:
                            return ""
                    name = val("DisplayName")
                    if not name:
                        continue
                    programs.append({
                        "name": name,
                        "version": val("DisplayVersion"),
                        "publisher": val("Publisher"),
                        "install_location": val("InstallLocation"),
                        "uninstall_string": val("UninstallString"),
                        "hive": hive_name,
                    })
    return programs


def leftover_dirs() -> list[dict]:
    """Directories under Program Files / AppData that no installed
    program claims — likely remnants of uninstalled software."""
    _require_windows()
    programs = installed_programs()
    known_tokens: set[str] = set()
    for p in programs:
        for source in (p["name"], p["publisher"], p["install_location"]):
            for token in source.replace("\\", " ").split():
                if len(token) >= 3:
                    known_tokens.add(token.lower())
        loc = p["install_location"].rstrip("\\").lower()
        if loc:
            known_tokens.add(os.path.basename(loc))

    scan_dirs = [
        os.environ.get("ProgramFiles", r"C:\Program Files"),
        os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), ""),
        os.path.join(os.environ.get("APPDATA", ""), ""),
    ]
    # Vendors whose folders are expected even without an uninstall entry.
    expected = {
        "microsoft", "windows", "windowsapps", "common files", "internet explorer",
        "windows defender", "windows mail", "windows media player",
        "windows nt", "windowspowershell", "modifiablewindowsapps", "dotnet",
        "msbuild", "reference assemblies", "packages", "temp", "intel", "nvidia",
        "amd", "realtek",
    }

    results = []
    for base in scan_dirs:
        if not base or not os.path.isdir(base):
            continue
        try:
            entries = list(os.scandir(base))
        except OSError:
            continue
        for entry in entries:
            if not entry.is_dir(follow_symlinks=False):
                continue
            name = entry.name.lower()
            if name in expected:
                continue
            tokens = [t for t in name.replace("_", " ").replace("-", " ").split()
                      if len(t) >= 3]
            claimed = name in known_tokens or any(t in known_tokens for t in tokens)
            if claimed:
                continue
            try:
                mtime = entry.stat().st_mtime
            except OSError:
                mtime = 0
            results.append({
                "path": entry.path,
                "base": base,
                "mtime": mtime,
                "confidence": "medium",
                "note": "No installed program references this folder. "
                        "Verify before quarantining.",
            })
    return results


# --- Autostart ---------------------------------------------------------

_RUN_KEYS = [
    ("HKCU", r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run"),
    ("HKLM", r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run"),
    ("HKLM", r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Run"),
]


def _classify_command(name: str, command: str) -> tuple[str, str]:
    """Return (assessment, note) for an autostart/service command line."""
    lowered = command.lower()
    exe = lowered.split(".exe")[0] + ".exe" if ".exe" in lowered else lowered
    exe = exe.strip('"')
    if exe and not os.path.exists(exe.strip('"')):
        # Try without quotes/args
        candidate = command.strip('"').split('"')[0].strip()
        if candidate and not os.path.exists(candidate):
            return ("broken",
                    "Target executable not found — leftover of an "
                    "uninstalled program, safe to remove.")
    if "update" in lowered or "updater" in lowered:
        return ("optional",
                "Auto-updater. Usually safe to disable; the program "
                "updates when launched manually.")
    if any(t in lowered for t in ("\\windows\\", "\\microsoft\\", "securityhealth")):
        return ("keep", "Part of Windows / Microsoft — leave enabled.")
    return ("review", "Third-party autostart. Disable if you do not "
                      "need it immediately at boot.")


def startup_entries() -> list[dict]:
    _require_windows()
    import winreg

    hives = {"HKCU": winreg.HKEY_CURRENT_USER, "HKLM": winreg.HKEY_LOCAL_MACHINE}
    entries = []
    for hive_name, key_path in _RUN_KEYS:
        try:
            key = winreg.OpenKey(hives[hive_name], key_path)
        except OSError:
            continue
        with key:
            for i in range(winreg.QueryInfoKey(key)[1]):
                try:
                    name, value, _ = winreg.EnumValue(key, i)
                except OSError:
                    continue
                assessment, note = _classify_command(name, str(value))
                entries.append({
                    "kind": "registry_run",
                    "location": f"{hive_name}\\{key_path}",
                    "name": name,
                    "command": str(value),
                    "assessment": assessment,
                    "note": note,
                })

    startup_dirs = [
        os.path.join(os.environ.get("APPDATA", ""),
                     r"Microsoft\Windows\Start Menu\Programs\Startup"),
        os.path.join(os.environ.get("ProgramData", ""),
                     r"Microsoft\Windows\Start Menu\Programs\Startup"),
    ]
    for d in startup_dirs:
        if not os.path.isdir(d):
            continue
        for entry in os.scandir(d):
            if entry.name.lower() == "desktop.ini":
                continue
            assessment, note = _classify_command(entry.name, entry.path)
            entries.append({
                "kind": "startup_folder",
                "location": d,
                "name": entry.name,
                "command": entry.path,
                "assessment": assessment,
                "note": note,
            })
    return entries


def disable_startup_entry(kind: str, location: str, name: str,
                          quarantine=None) -> dict:
    """Disable a single autostart entry found by startup_entries().

    Registry values are exported to the data dir before deletion so
    they can be re-imported; Startup-folder items go through the
    normal quarantine.
    """
    _require_windows()
    import winreg

    if kind == "startup_folder":
        path = os.path.join(location, name)
        if quarantine is None:
            raise ValueError("quarantine required for startup_folder entries")
        return quarantine.quarantine([path], reason=f"autostart: {name}")

    if kind != "registry_run":
        raise ValueError(f"unknown kind: {kind}")
    hive_name, _, key_path = location.partition("\\")
    hives = {"HKCU": winreg.HKEY_CURRENT_USER, "HKLM": winreg.HKEY_LOCAL_MACHINE}
    key = winreg.OpenKey(hives[hive_name], key_path, 0,
                         winreg.KEY_READ | winreg.KEY_SET_VALUE)
    with key:
        value, vtype = winreg.QueryValueEx(key, name)
        winreg.DeleteValue(key, name)
    return {
        "disabled": name,
        "backup": {"hive": hive_name, "key": key_path, "name": name,
                   "value": str(value), "type": vtype},
        "restore_hint": "Re-create this registry value to undo.",
    }


# --- Services & scheduled tasks (report-only) --------------------------

def services() -> list[dict]:
    _require_windows()
    rows = _ps_json(
        "Get-CimInstance Win32_Service |"
        " Select-Object Name, DisplayName, State, StartMode, PathName, Description"
    )
    out = []
    for r in rows:
        path = r.get("PathName") or ""
        assessment, note = _classify_command(r.get("Name", ""), path)
        if r.get("StartMode") == "Disabled":
            assessment, note = "disabled", "Already disabled."
        out.append({
            "name": r.get("Name", ""),
            "display_name": r.get("DisplayName", ""),
            "state": r.get("State", ""),
            "start_mode": r.get("StartMode", ""),
            "path": path,
            "description": (r.get("Description") or "")[:300],
            "assessment": assessment,
            "note": note,
            "disable_command":
                f'sc config "{r.get("Name", "")}" start= disabled',
        })
    return out


def scheduled_tasks() -> list[dict]:
    _require_windows()
    rows = _ps_json(
        "Get-ScheduledTask | Where-Object {$_.TaskPath -notlike '\\Microsoft\\*'} |"
        " Select-Object TaskName, TaskPath, State,"
        " @{n='Action';e={($_.Actions | ForEach-Object {$_.Execute + ' ' +"
        " $_.Arguments}) -join '; '}}"
    )
    out = []
    for r in rows:
        action = r.get("Action") or ""
        assessment, note = _classify_command(r.get("TaskName", ""), action)
        out.append({
            "name": r.get("TaskName", ""),
            "path": r.get("TaskPath", ""),
            "state": str(r.get("State", "")),
            "action": action,
            "assessment": assessment,
            "note": note,
            "disable_command":
                f'schtasks /Change /TN "{r.get("TaskPath", "")}'
                f'{r.get("TaskName", "")}" /Disable',
        })
    return out
