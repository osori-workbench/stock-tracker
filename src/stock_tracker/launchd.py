from __future__ import annotations

from pathlib import Path

SCHEDULES = {
    "morning": {"hour": 8, "minute": 0},
    "open": {"hour": 9, "minute": 10},
    "noon": {"hour": 12, "minute": 0},
    "close": {"hour": 15, "minute": 40},
}
WEEKDAYS = [1, 2, 3, 4, 5]
DOMAIN_PREFIX = "com.osori.stock-tracker"


def build_launch_agent_plists(project_dir: str) -> dict[str, str]:
    project_path = Path(project_dir)
    script_path = project_path / "scripts" / "run_briefing.sh"
    log_dir = project_path / "logs"
    plists: dict[str, str] = {}

    for mode, schedule in SCHEDULES.items():
        label = f"{DOMAIN_PREFIX}.{mode}"
        plist = _render_plist(
            label=label,
            script_path=str(script_path),
            mode=mode,
            hour=schedule["hour"],
            minute=schedule["minute"],
            stdout_path=str(log_dir / f"launchd-{mode}.log"),
            stderr_path=str(log_dir / f"launchd-{mode}.log"),
        )
        plists[label] = plist
    return plists


def _render_plist(
    *,
    label: str,
    script_path: str,
    mode: str,
    hour: int,
    minute: int,
    stdout_path: str,
    stderr_path: str,
) -> str:
    calendar_entries = "\n".join(
        f"""      <dict>
        <key>Weekday</key>
        <integer>{weekday}</integer>
        <key>Hour</key>
        <integer>{hour}</integer>
        <key>Minute</key>
        <integer>{minute}</integer>
      </dict>"""
        for weekday in WEEKDAYS
    )
    return f"""<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<!DOCTYPE plist PUBLIC \"-//Apple//DTD PLIST 1.0//EN\" \"http://www.apple.com/DTDs/PropertyList-1.0.dtd\">
<plist version=\"1.0\">
<dict>
  <key>Label</key>
  <string>{label}</string>
  <key>ProgramArguments</key>
  <array>
    <string>{script_path}</string>
    <string>{mode}</string>
  </array>
  <key>WorkingDirectory</key>
  <string>{Path(script_path).parent.parent}</string>
  <key>RunAtLoad</key>
  <false/>
  <key>StandardOutPath</key>
  <string>{stdout_path}</string>
  <key>StandardErrorPath</key>
  <string>{stderr_path}</string>
  <key>StartCalendarInterval</key>
  <array>
{calendar_entries}
  </array>
</dict>
</plist>
"""


def write_launch_agent_plists(project_dir: str, output_dir: str) -> list[Path]:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for label, content in build_launch_agent_plists(project_dir).items():
        target = output_path / f"{label}.plist"
        target.write_text(content)
        written.append(target)
    return written
