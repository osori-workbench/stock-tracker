from stock_tracker.launchd import build_launch_agent_plists


def test_build_launch_agent_plists_contains_expected_labels_and_schedules() -> None:
    plists = build_launch_agent_plists(project_dir="/Users/osori/workbench/stock-tracker")

    assert set(plists) == {
        "com.osori.stock-tracker.morning",
        "com.osori.stock-tracker.open",
        "com.osori.stock-tracker.noon",
        "com.osori.stock-tracker.close",
    }
    assert "<key>Minute</key>\n        <integer>0</integer>" in plists["com.osori.stock-tracker.morning"]
    assert "<key>Hour</key>\n        <integer>8</integer>" in plists["com.osori.stock-tracker.morning"]
    assert "scripts/run_briefing.sh</string>\n    <string>morning</string>" in plists["com.osori.stock-tracker.morning"]
    assert "<key>Minute</key>\n        <integer>10</integer>" in plists["com.osori.stock-tracker.open"]
    assert "<key>Hour</key>\n        <integer>9</integer>" in plists["com.osori.stock-tracker.open"]
    assert "scripts/run_briefing.sh</string>\n    <string>open</string>" in plists["com.osori.stock-tracker.open"]
    assert "<key>Minute</key>\n        <integer>0</integer>" in plists["com.osori.stock-tracker.noon"]
    assert "<key>Hour</key>\n        <integer>12</integer>" in plists["com.osori.stock-tracker.noon"]
    assert "<key>Minute</key>\n        <integer>40</integer>" in plists["com.osori.stock-tracker.close"]
    assert "<key>Hour</key>\n        <integer>15</integer>" in plists["com.osori.stock-tracker.close"]
