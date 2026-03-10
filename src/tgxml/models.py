from dataclasses import dataclass
from typing import Optional, List, Set, Dict, Any


@dataclass
class ConversionOptions:
    source_paths: List[str]
    output_path: str
    selected_authors: Optional[Set[str]] = None
    start_date: str = ""
    end_date: str = ""
    use_date_range: bool = False
    include_reactions: bool = True
    human_readable: bool = True
    include_service: bool = False
    include_media_meta: bool = False
    include_entities: bool = False
    anonymize: bool = False
    validate_input: bool = False


@dataclass
class ConversionResult:
    messages: int
    output_path: str
    filter_stats: Dict[str, Any]
    validation_issues: Optional[List[str]] = None
