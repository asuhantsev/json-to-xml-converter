"""Core conversion functions for Telegram JSON -> XML."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from jsontoxml import (
    normalize_text_content,
    extract_message_date,
    filter_messages,
    build_message_element,
    indent_xml,
    load_json_file,
    get_available_authors,
    get_date_range_from_messages,
    build_xml_tree,
    convert_json_to_xml_file,
    validate_telegram_export,
    anonymize_messages,
)

__all__ = [
    "normalize_text_content",
    "extract_message_date",
    "filter_messages",
    "build_message_element",
    "indent_xml",
    "load_json_file",
    "get_available_authors",
    "get_date_range_from_messages",
    "build_xml_tree",
    "convert_json_to_xml_file",
    "validate_telegram_export",
    "anonymize_messages",
]
