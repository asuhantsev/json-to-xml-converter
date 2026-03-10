import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "jsontoxml.py"
SOURCE = ROOT / "exports" / "ChatExport_2024-12-27" / "result.json"


def run_cmd(args, input_text=None):
    return subprocess.run(
        args,
        input=input_text,
        text=True,
        capture_output=True,
        cwd=ROOT,
        check=True,
    )


def test_cli_command_mode_writes_xml(tmp_path):
    out = tmp_path / "out.xml"
    res = run_cmd([
        "python3", str(SCRIPT), "--cli", "--run",
        "--source", str(SOURCE),
        "--output", str(out),
        "--compact",
        "--no-date-filter",
    ])
    assert out.exists()
    assert "Converted successfully" in res.stdout


def test_cli_dry_run_json_report():
    res = run_cmd([
        "python3", str(SCRIPT), "--cli", "--run",
        "--source", str(SOURCE),
        "--dry-run", "--report-json",
    ])
    body = res.stdout[res.stdout.find("{"):res.stdout.rfind("}") + 1]
    payload = json.loads(body)
    assert payload["dry_run"] is True
    assert payload["filter_stats"]["included"] > 0


def test_cli_interactive_fallback_flow(tmp_path):
    # Menu selection "Inspect source" in non-TTY fallback.
    user_input = "3\n"
    res = run_cmd([
        "python3", str(SCRIPT), "--interactive", "--source", str(SOURCE), "--plain"
    ], input_text=user_input)
    assert "Raw items:" in res.stdout
