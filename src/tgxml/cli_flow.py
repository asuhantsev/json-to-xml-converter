"""Shared CLI flow helpers for conversion payload/report orchestration."""

from __future__ import annotations

import json
import os
import shlex
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from jsontoxml import (  # noqa: E402
    anonymize_messages,
    build_export_label,
    build_xml_tree,
    filter_messages,
    load_json_file,
    validate_telegram_export,
)


def build_conversion_payload(
    *,
    source_paths: list[str],
    output_path: str | None,
    output_dir: str | None,
    selected_authors: set[str],
    start_date: str,
    end_date: str,
    use_date_range: bool,
    include_service: bool,
    include_media_meta: bool,
    include_entities: bool,
    include_reactions: bool,
    human_readable: bool,
    anonymize: bool,
    validate_input: bool,
) -> dict[str, Any]:
    """Load sources, apply filters, and prepare conversion payload."""
    all_messages = []
    validation_issues = []
    first_chat_name = "chat"

    for idx, src in enumerate(source_paths):
        data = load_json_file(src)
        if idx == 0:
            first_chat_name = data.get("name", "chat")
        if validate_input:
            validation_issues.extend([f"{src}: {x}" for x in validate_telegram_export(data)])
        all_messages.extend(data.get("messages", []))

    if anonymize:
        all_messages = anonymize_messages(all_messages)

    filtered_messages, filter_stats = filter_messages(
        all_messages,
        selected_authors=selected_authors,
        start_date=start_date,
        end_date=end_date,
        use_date_range=use_date_range,
        require_text=True,
        return_stats=True,
        include_service=include_service,
    )

    resolved_output = output_path
    if not resolved_output:
        export_label = build_export_label(first_chat_name, filtered_messages)
        if output_dir:
            resolved_output = os.path.join(output_dir, f"{export_label}.xml")
        else:
            source_dir = os.path.dirname(source_paths[0]) or "."
            resolved_output = os.path.join(source_dir, export_label, f"{export_label}.xml")

    return {
        "source_paths": source_paths,
        "output_path": resolved_output,
        "filtered_messages": filtered_messages,
        "filter_stats": filter_stats,
        "validation_issues": validation_issues,
        "selected_authors": selected_authors,
        "use_date_range": use_date_range,
        "start_date": start_date,
        "end_date": end_date,
        "include_reactions": include_reactions,
        "include_service": include_service,
        "include_media_meta": include_media_meta,
        "include_entities": include_entities,
        "anonymize": anonymize,
        "validate_input": validate_input,
        "human_readable": human_readable,
    }


def create_report(payload: dict[str, Any], *, dry_run: bool) -> dict[str, Any]:
    """Build structured report for dry-run/export output."""
    return {
        "source_paths": payload["source_paths"],
        "output_path": payload["output_path"],
        "dry_run": dry_run,
        "use_date_range": payload["use_date_range"],
        "start_date": payload["start_date"],
        "end_date": payload["end_date"],
        "include_reactions": payload["include_reactions"],
        "include_service": payload["include_service"],
        "include_media_meta": payload["include_media_meta"],
        "include_entities": payload["include_entities"],
        "anonymize": payload["anonymize"],
        "validate_input": payload["validate_input"],
        "human_readable": payload["human_readable"],
        "selected_authors_count": len(payload["selected_authors"]),
        "filter_stats": payload["filter_stats"],
        "validation_issues": payload["validation_issues"],
    }


def format_dry_run_report(report: dict[str, Any]) -> str:
    """Render dry-run report in human-readable text."""
    stats = report["filter_stats"]
    lines = [
        "Dry run report:",
        f"  Sources: {', '.join(report['source_paths'])}",
        f"  Output: {report['output_path']}",
        f"  Included messages: {stats['included']}",
        f"  Excluded non-message: {stats['excluded_non_message']}",
        f"  Excluded service: {stats['excluded_service']}",
        f"  Excluded by author: {stats['excluded_author']}",
        f"  Excluded empty text: {stats['excluded_empty_text']}",
        f"  Excluded by date: {stats['excluded_date']}",
    ]
    if report["validation_issues"]:
        lines.append("  Validation issues:")
        lines.extend([f"    - {issue}" for issue in report["validation_issues"]])
    return "\n".join(lines)


def write_xml(payload: dict[str, Any]) -> None:
    """Write XML output using prepared payload."""
    tree = build_xml_tree(
        payload["filtered_messages"],
        include_reactions=payload["include_reactions"],
        human_readable=payload["human_readable"],
        include_media_meta=payload["include_media_meta"],
        include_entities=payload["include_entities"],
    )
    os.makedirs(os.path.dirname(payload["output_path"]) or ".", exist_ok=True)
    tree.write(payload["output_path"], encoding="utf-8", xml_declaration=True)


def build_replay_command(payload: dict[str, Any], *, no_color: bool, plain: bool) -> str:
    """Build reproducible one-shot CLI command."""
    parts = ["python3", "jsontoxml.py", "--cli", "--run"]
    for src in payload["source_paths"]:
        parts.extend(["--source", src])
    parts.extend(["--output", payload["output_path"]])

    for author in sorted(payload["selected_authors"]):
        parts.extend(["--author", author])

    if payload["use_date_range"]:
        if payload["start_date"]:
            parts.extend(["--start-date", payload["start_date"]])
        if payload["end_date"]:
            parts.extend(["--end-date", payload["end_date"]])
    else:
        parts.append("--no-date-filter")

    if not payload["include_reactions"]:
        parts.append("--no-reactions")
    if not payload["human_readable"]:
        parts.append("--compact")
    if payload["include_service"]:
        parts.append("--include-service")
    if payload["include_media_meta"]:
        parts.append("--include-media-meta")
    if payload["include_entities"]:
        parts.append("--include-entities")
    if payload["anonymize"]:
        parts.append("--anonymize")
    if payload["validate_input"]:
        parts.append("--validate-input")
    if no_color:
        parts.append("--no-color")
    if plain:
        parts.append("--plain")

    return " ".join(shlex.quote(part) for part in parts)


def report_as_json(report: dict[str, Any]) -> str:
    return json.dumps(report, ensure_ascii=False, indent=2)
