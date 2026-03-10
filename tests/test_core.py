import os
import sys
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tgxml.core import (  # noqa: E402
    normalize_text_content,
    filter_messages,
    build_xml_tree,
    validate_telegram_export,
)


def test_normalize_text_content_handles_list_and_scalar():
    assert normalize_text_content(["a", {"text": "b"}, 3]) == "ab3"
    assert normalize_text_content(None) == ""
    assert normalize_text_content("x") == "x"


def test_filter_messages_with_service_and_dates():
    messages = [
        {"type": "service", "date": "2025-01-01T10:00:00", "text": ""},
        {"type": "message", "from": "Alice", "date": "2025-01-02T10:00:00", "text": "hello"},
        {"type": "message", "from": "Bob", "date": "2025-01-03T10:00:00", "text": "world"},
    ]
    filtered, stats = filter_messages(
        messages,
        selected_authors={"Alice"},
        start_date="2025-01-01",
        end_date="2025-01-02",
        use_date_range=True,
        include_service=True,
        return_stats=True,
    )
    assert len(filtered) == 2
    assert stats["included"] == 2


def test_build_xml_tree_creates_messages_root():
    messages = [
        {"id": 1, "type": "message", "date": "2025-01-01T00:00:00", "from": "A", "text": "Hi"}
    ]
    tree = build_xml_tree(messages, include_reactions=False, human_readable=False)
    root = tree.getroot()
    assert root.tag == "messages"
    assert len(root.findall("message")) == 1


def test_validate_telegram_export_reports_missing_messages():
    issues = validate_telegram_export({"name": "x"})
    assert any("messages" in issue for issue in issues)
