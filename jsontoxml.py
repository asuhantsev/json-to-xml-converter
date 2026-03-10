import json
import xml.etree.ElementTree as ET
import os
import io
import subprocess
import argparse
import sys
import logging
import copy
from dataclasses import dataclass, asdict
from typing import Optional, List

try:
    import tkinter as tk
    from tkinter import ttk, filedialog
except ModuleNotFoundError:
    tk = None
    ttk = None
    filedialog = None

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("tgxml")


@dataclass
class ConversionOptions:
    source_paths: List[str]
    output_path: str
    selected_authors: Optional[set] = None
    start_date: str = ""
    end_date: str = ""
    use_date_range: bool = False
    include_reactions: bool = True
    human_readable: bool = True
    include_service: bool = False
    include_media_meta: bool = False
    include_entities: bool = False
    anonymize: bool = False


@dataclass
class ConversionResult:
    messages: int
    output_path: str
    filter_stats: dict
    validation_issues: Optional[list] = None


def validate_telegram_export(data):
    issues = []
    if not isinstance(data, dict):
        return ["Root JSON must be an object"]
    if 'messages' not in data:
        issues.append("Missing required field: messages")
    elif not isinstance(data.get('messages'), list):
        issues.append("Field 'messages' must be an array")
    for i, msg in enumerate(data.get('messages', [])):
        if not isinstance(msg, dict):
            issues.append(f"messages[{i}] is not an object")
            continue
        if 'type' not in msg:
            issues.append(f"messages[{i}] missing field 'type'")
        if 'date' not in msg:
            issues.append(f"messages[{i}] missing field 'date'")
    return issues


def anonymize_messages(messages):
    user_map = {}
    counter = 1

    def alias(name):
        nonlocal counter
        if not name:
            return name
        if name not in user_map:
            user_map[name] = f"user_{counter:03d}"
            counter += 1
        return user_map[name]

    out = []
    for msg in messages:
        cp = copy.deepcopy(msg)
        cp['from'] = alias(cp.get('from', ''))
        if 'actor' in cp:
            cp['actor'] = alias(cp.get('actor', ''))
        if 'from_id' in cp and cp.get('from_id'):
            cp['from_id'] = f"id_{abs(hash(str(cp['from_id']))) % 10_000_000}"
        if 'actor_id' in cp and cp.get('actor_id'):
            cp['actor_id'] = f"id_{abs(hash(str(cp['actor_id']))) % 10_000_000}"
        out.append(cp)
    return out

def normalize_text_content(text):
    """Normalize Telegram text field (string/list/misc) into plain string."""
    if isinstance(text, list):
        return ''.join(
            part.get('text', '') if isinstance(part, dict) else str(part)
            for part in text
        )
    if isinstance(text, str):
        return text
    if text is None:
        return ''
    return str(text)


def extract_message_date(message):
    return str(message.get('date', '')).split('T')[0]


def filter_messages(messages, selected_authors=None, start_date='', end_date='',
                    use_date_range=False, require_text=True, return_stats=False,
                    include_service=False):
    """Single filtering pipeline used by counters and export."""
    selected_authors = selected_authors or set()
    filtered = []
    stats = {
        "total_items": len(messages),
        "excluded_non_message": 0,
        "excluded_author": 0,
        "excluded_empty_text": 0,
        "excluded_date": 0,
        "excluded_service": 0,
        "included": 0,
    }

    for msg in messages:
        if not isinstance(msg, dict):
            stats["excluded_non_message"] += 1
            continue

        msg_type = msg.get('type')
        if msg_type != 'message':
            if include_service and msg_type == 'service':
                pass
            else:
                if msg_type == 'service':
                    stats["excluded_service"] += 1
                else:
                    stats["excluded_non_message"] += 1
                continue

        author = msg.get('from', '')
        if selected_authors and author and author not in selected_authors:
            stats["excluded_author"] += 1
            continue

        text = normalize_text_content(msg.get('text', ''))
        if require_text and msg_type == 'message' and not text.strip():
            stats["excluded_empty_text"] += 1
            continue

        if use_date_range:
            date_str = extract_message_date(msg)
            if start_date and date_str < start_date:
                stats["excluded_date"] += 1
                continue
            if end_date and date_str > end_date:
                stats["excluded_date"] += 1
                continue

        filtered.append(msg)
        stats["included"] += 1

    if return_stats:
        return filtered, stats
    return filtered


def build_message_element(root, message, include_reactions=True,
                          include_media_meta=False, include_entities=False):
    msg_element = ET.SubElement(root, "message")
    msg_type = message.get('type', 'message')
    msg_element.set('kind', msg_type)
    msg_element.set('id', str(message.get('id', '')))
    msg_element.set('date', message.get('date', ''))
    msg_element.set('sender', message.get('from', ''))

    if msg_type == 'service':
        if message.get('action'):
            msg_element.set('action', str(message.get('action')))
        if message.get('actor'):
            msg_element.set('actor', str(message.get('actor')))

    text_element = ET.SubElement(msg_element, "text")
    text_element.text = normalize_text_content(message.get('text', '')).strip()

    reply_to = message.get('reply_to_message_id')
    if reply_to:
        msg_element.set('reply_to', str(reply_to))

    if include_reactions and 'reactions' in message:
        reactions_element = ET.SubElement(msg_element, "reactions")
        for reaction in message.get('reactions', []):
            reaction_element = ET.SubElement(reactions_element, "reaction")
            reaction_element.set('emoji', reaction.get('emoji', ''))
            reaction_element.set('count', str(reaction.get('count', 0)))

    if include_media_meta:
        media_keys = [
            "photo", "photo_file_size", "file", "file_name", "file_size", "mime_type",
            "media_type", "width", "height", "duration_seconds", "thumbnail"
        ]
        media_payload = {k: message.get(k) for k in media_keys if k in message}
        if media_payload:
            media_element = ET.SubElement(msg_element, "media")
            for key, value in media_payload.items():
                media_element.set(key, str(value))

    if include_entities and isinstance(message.get('text_entities'), list):
        entities_element = ET.SubElement(msg_element, "entities")
        for entity in message.get('text_entities', []):
            if not isinstance(entity, dict):
                continue
            entity_element = ET.SubElement(entities_element, "entity")
            entity_element.set("type", str(entity.get("type", "")))
            if "text" in entity:
                entity_element.set("text", str(entity.get("text", "")))

    return msg_element


def indent_xml(elem, level=0):
    i = "\n" + level * "  "
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = i + "  "
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
        for subelem in elem:
            indent_xml(subelem, level + 1)
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
    elif level and (not elem.tail or not elem.tail.strip()):
        elem.tail = i


def load_json_file(file_path):
    with open(file_path, 'r', encoding='utf-8') as file:
        return json.load(file)


def get_available_authors(messages):
    return sorted({
        msg.get('from', '')
        for msg in messages
        if isinstance(msg, dict) and msg.get('type') == 'message' and msg.get('from')
    })


def get_date_range_from_messages(messages):
    dates = sorted([extract_message_date(msg) for msg in messages if extract_message_date(msg)])
    if not dates:
        return '', ''
    return dates[0], dates[-1]


def get_message_dates_range_label(messages):
    start_date, end_date = get_date_range_from_messages(messages)
    if not start_date:
        return ""
    if start_date == end_date:
        return f"({start_date})"
    return f"({start_date}_to_{end_date})"


def sanitize_path_component(value):
    text = (value or "chat").strip()
    for ch in ['/', '\\', ':', '*', '?', '"', '<', '>', '|']:
        text = text.replace(ch, "_")
    return text or "chat"


def build_export_label(chat_name, messages):
    safe_chat_name = sanitize_path_component(chat_name)
    date_range = get_message_dates_range_label(messages)
    if date_range:
        return f"{safe_chat_name}_{date_range}"
    return safe_chat_name


def build_xml_tree(messages, include_reactions=True, human_readable=True,
                   include_media_meta=False, include_entities=False):
    root = ET.Element("messages")
    for message in messages:
        build_message_element(
            root,
            message,
            include_reactions=include_reactions,
            include_media_meta=include_media_meta,
            include_entities=include_entities,
        )
    if human_readable:
        indent_xml(root)
    return ET.ElementTree(root)


def convert_json_to_xml_file(source_path, output_path, selected_authors=None,
                             start_date='', end_date='', use_date_range=False,
                             include_reactions=True, human_readable=True,
                             include_service=False, include_media_meta=False,
                             include_entities=False, anonymize=False,
                             validate_input=False):
    source_paths = source_path if isinstance(source_path, list) else [source_path]
    merged_messages = []
    validation_issues = []

    for path in source_paths:
        data = load_json_file(path)
        if validate_input:
            validation_issues.extend([f"{path}: {issue}" for issue in validate_telegram_export(data)])
        merged_messages.extend(data.get('messages', []))

    if anonymize:
        merged_messages = anonymize_messages(merged_messages)

    messages, filter_stats = filter_messages(
        merged_messages,
        selected_authors=selected_authors or set(),
        start_date=start_date,
        end_date=end_date,
        use_date_range=use_date_range,
        require_text=True,
        return_stats=True,
        include_service=include_service,
    )
    tree = build_xml_tree(
        messages,
        include_reactions=include_reactions,
        human_readable=human_readable,
        include_media_meta=include_media_meta,
        include_entities=include_entities,
    )
    tree.write(output_path, encoding='utf-8', xml_declaration=True)
    return {
        'messages': len(messages),
        'output_path': output_path,
        'filter_stats': filter_stats,
        'validation_issues': validation_issues,
    }

class ConversionGUI:
    def __init__(self):
        self.window = tk.Tk()
        self.window.title("JSON to XML Converter")
        
        # Set initial size but allow vertical growth
        self.window.geometry("600x750")
        self.window.minsize(600, 650)
        
        # Create main container that will control minimum width
        self.main_container = ttk.Frame(self.window)
        self.main_container.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Allow vertical growth
        self.window.grid_rowconfigure(0, weight=1)
        self.window.grid_columnconfigure(0, weight=1)
        
        # Variables
        self.source_path = tk.StringVar()
        self.source_path.trace_add('write', self.update_output_filename)
        self.output_dir = tk.StringVar()
        self.output_filename = tk.StringVar(value="output.xml")
        self.status_var = tk.StringVar()
        self.stats_var = tk.StringVar()
        self.reactions_var = tk.StringVar()
        self.progress_var = tk.DoubleVar()
        self.human_readable = tk.BooleanVar(value=True)
        self.include_reactions = tk.BooleanVar(value=True)
        self.format_info = tk.StringVar()
        self.reactions_info = tk.StringVar()  # New variable for reactions savings
        self.summary_info = tk.StringVar()    # New variable for summary
        
        # Add new variables for author filtering
        self.authors = set()  # Store unique authors
        self.selected_authors = set()  # Store selected authors
        self.is_private_chat = False
        self.authors_var = tk.StringVar(value="All authors")  # For display purposes
        
        # Replace string vars with separate vars for year, month, day
        self.start_year = tk.StringVar()
        self.start_month = tk.StringVar()
        self.start_day = tk.StringVar()
        self.end_year = tk.StringVar()
        self.end_month = tk.StringVar()
        self.end_day = tk.StringVar()
        self.use_date_range = tk.BooleanVar(value=False)
        
        # Initialize with empty values
        self.years = []
        self.months = [str(i).zfill(2) for i in range(1, 13)]
        self.days = [str(i).zfill(2) for i in range(1, 32)]
        
        self.create_widgets()
        
    def create_widgets(self):
        # Create content frame first
        self.content_frame = ttk.Frame(self.main_container)
        self.content_frame.pack(fill="both", expand=True)
        
        # File selection frame
        file_frame = ttk.Frame(self.content_frame)
        file_frame.pack(fill="x", pady=5)
        
        # Source file selection
        source_label = ttk.Label(file_frame, text="Source JSON file:")
        source_label.pack(side="left", padx=(0, 10))
        
        source_entry = ttk.Entry(file_frame, textvariable=self.source_path)
        source_entry.pack(side="left", fill="x", expand=True)
        
        source_button = ttk.Button(
            file_frame,
            text="Select JSON file",
            command=self.select_source_file
        )
        source_button.pack(side="left", padx=(10, 0))
        
        # Output file frame
        output_frame = ttk.Frame(self.content_frame)
        output_frame.pack(fill="x", pady=5)
        
        # Output directory
        output_dir_label = ttk.Label(output_frame, text="Output directory:")
        output_dir_label.pack(side="left", padx=(0, 10))
        
        output_dir_entry = ttk.Entry(output_frame, textvariable=self.output_dir)
        output_dir_entry.pack(side="left", fill="x", expand=True)
        
        output_dir_button = ttk.Button(
            output_frame,
            text="Select directory",
            command=self.select_output_dir
        )
        output_dir_button.pack(side="left", padx=(10, 0))
        
        # Output filename frame
        filename_frame = ttk.Frame(self.content_frame)
        filename_frame.pack(fill="x", pady=5)
        
        filename_label = ttk.Label(filename_frame, text="Output filename:")
        filename_label.pack(side="left", padx=(0, 10))
        
        filename_entry = ttk.Entry(filename_frame, textvariable=self.output_filename)
        filename_entry.pack(side="left", fill="x", expand=True)
        
        # Options group frame
        options_frame = ttk.LabelFrame(self.content_frame, text="Export Options", padding=(10, 5, 10, 10))
        options_frame.pack(fill="x", pady=5)
        
        # Human readable format option
        human_readable = ttk.Checkbutton(
            options_frame, 
            text="Human readable format", 
            variable=self.human_readable,
            command=self.update_format_info
        )
        human_readable.pack(anchor="w", pady=2)
        
        # Include reactions option
        include_reactions = ttk.Checkbutton(
            options_frame, 
            text="Include reactions", 
            variable=self.include_reactions,
            command=self.update_format_info
        )
        include_reactions.pack(anchor="w", pady=2)
        
        # Date range frame
        date_range_frame = ttk.Frame(options_frame)
        date_range_frame.pack(fill="x", pady=2)
        
        # Date range enable checkbox
        date_range_check = ttk.Checkbutton(
            date_range_frame,
            text="Filter by date range",
            variable=self.use_date_range,
            command=self.update_all_counters
        )
        date_range_check.pack(anchor="w", padx=(0, 10))
        
        # Date selectors container
        date_selectors_frame = ttk.Frame(date_range_frame)
        date_selectors_frame.pack(fill="x", padx=20)
        
        # Start date selector
        self.start_year_cb, self.start_month_cb, self.start_day_cb = self.create_date_selector(
            date_selectors_frame,
            self.start_year,
            self.start_month,
            self.start_day,
            "From:"
        )
        
        # End date selector
        self.end_year_cb, self.end_month_cb, self.end_day_cb = self.create_date_selector(
            date_selectors_frame,
            self.end_year,
            self.end_month,
            self.end_day,
            "To:"
        )
        
        # Reset button container
        reset_frame = ttk.Frame(date_range_frame)
        reset_frame.pack(fill="x", padx=20, pady=(5, 0))
        
        # Reset button
        reset_button = ttk.Button(
            reset_frame,
            text="Reset to Full Range",
            command=self.reset_date_range,
            width=20
        )
        reset_button.pack(side="left")
        
        # Add date format hint
        date_hint = ttk.Label(
            date_range_frame,
            text="Format: Year-Month-Day, partial dates allowed",
            font=('TkDefaultFont', 8),
            foreground='gray'
        )
        date_hint.pack(anchor="w", padx=20, pady=(2, 0))
        
        # Authors filter section (moved into options frame)
        self.authors_frame = ttk.Frame(options_frame)
        self.authors_frame.pack(fill="x", pady=(10, 2))
        
        authors_label = ttk.Label(self.authors_frame, text="Filter authors:")
        authors_label.pack(side="left", padx=(0, 5))
        
        # Authors listbox with scrollbar in a container frame
        authors_list_frame = ttk.Frame(self.authors_frame)
        authors_list_frame.pack(fill="x", expand=True)
        
        self.authors_listbox = tk.Listbox(
            authors_list_frame, 
            selectmode=tk.MULTIPLE, 
            height=3,
            exportselection=False
        )
        self.authors_listbox.pack(side="left", fill="x", expand=True)
        
        authors_scrollbar = ttk.Scrollbar(
            authors_list_frame, 
            orient="vertical", 
            command=self.authors_listbox.yview
        )
        authors_scrollbar.pack(side="right", fill="y")
        self.authors_listbox.configure(yscrollcommand=authors_scrollbar.set)
        
        # Bind selection event
        self.authors_listbox.bind('<<ListboxSelect>>', self.on_author_selection)
        
        # Summary frame
        summary_frame = ttk.LabelFrame(self.content_frame, text="Export Summary", padding=(10, 5, 10, 10))
        summary_frame.pack(fill="x", pady=5)
        
        summary_label = ttk.Label(summary_frame, textvariable=self.summary_info)
        summary_label.pack(fill="x")
        
        # Status group frame
        status_frame = ttk.LabelFrame(self.content_frame, text="Status", padding=(10, 5, 10, 10))
        status_frame.pack(fill="x", pady=5)
        
        # Create a clickable label with custom style
        status_label = ttk.Label(
            status_frame, 
            textvariable=self.status_var,
            cursor="hand2"  # Change cursor to hand when hovering
        )
        status_label.pack(fill="x")
        
        # Bind click event
        status_label.bind('<Button-1>', self.copy_status_to_clipboard)
        
        # Add tooltip hint
        self.create_tooltip(status_label, "Click to copy status to clipboard")
        
        # Create status section with two main parts
        status_section = ttk.Frame(self.content_frame, padding=10)
        status_section.pack(fill="x", padx=10)
        
        # Status and Stats frames (side by side)
        stats_frame = ttk.Frame(status_section)
        stats_frame.pack(fill="x")
        
        # Right stats (including reactions)
        right_stats_frame = ttk.Frame(stats_frame)
        right_stats_frame.pack(side="right", fill="x", expand=True)
        
        reactions_label = ttk.Label(right_stats_frame, textvariable=self.reactions_var)
        reactions_label.pack(fill="x")
        
        stats_label = ttk.Label(right_stats_frame, textvariable=self.stats_var)
        stats_label.pack(fill="x")
        
        # Progress bar
        progress_bar = ttk.Progressbar(
            self.content_frame,
            variable=self.progress_var,
            maximum=100
        )
        progress_bar.pack(fill="x", padx=10, pady=5)
        
        # Buttons
        button_frame = ttk.Frame(self.content_frame, padding=10)
        button_frame.pack(fill="x", padx=10, pady=5)
        
        # Convert button
        convert_btn = tk.Button(
            button_frame, 
            text="CONVERT", 
            command=self.start_conversion,
            font=('Arial', 12, 'bold'),
            width=15,
            height=2
        )
        convert_btn.pack(side="left", padx=5)
        convert_btn.name = "convert_button"
        
        # Help button
        help_btn = tk.Button(
            button_frame, 
            text="HELP", 
            command=self.show_help,
            font=('Arial', 12, 'bold'),
            width=15,
            height=2
        )
        help_btn.pack(side="left", padx=5)
        help_btn.name = "help_button"
        
        # Exit button
        close_btn = tk.Button(
            button_frame, 
            text="EXIT", 
            command=self.window.quit,
            font=('Arial', 12, 'bold'),
            width=15,
            height=2
        )
        close_btn.pack(side="right", padx=5)
        close_btn.name = "close_button"
        
        # Bind window resize event
        self.window.bind('<Configure>', self.on_window_resize)
    
    def start_conversion(self):
        if not self.source_path.get() or not self.output_dir.get():
            self.status_var.set("Please select source file and output directory")
            return
        
        self.status_var.set("Converting...")
        self.progress_var.set(0)
        
        # Run conversion
        self.convert_json_to_xml()
    
    def run(self):
        self.window.mainloop()

    def _load_source_data(self):
        source = self.source_path.get()
        if not source:
            raise ValueError("Source file is not selected")
        with open(source, 'r', encoding='utf-8') as f:
            return json.load(f)

    def _current_date_bounds(self):
        if not self.use_date_range.get():
            return '', ''
        return (
            self.get_date_string(self.start_year, self.start_month, self.start_day),
            self.get_date_string(self.end_year, self.end_month, self.end_day),
        )

    def _get_filtered_messages(self, data=None, use_selected_date_range=True):
        data = data if data is not None else self._load_source_data()
        start_date, end_date = ('', '')
        if use_selected_date_range:
            start_date, end_date = self._current_date_bounds()

        return filter_messages(
            data.get('messages', []),
            selected_authors=self.selected_authors,
            start_date=start_date,
            end_date=end_date,
            use_date_range=use_selected_date_range and self.use_date_range.get(),
            require_text=True,
        )

    def _build_xml_tree(self, messages, include_reactions, human_readable):
        root = ET.Element("messages")
        for message in messages:
            build_message_element(root, message, include_reactions=include_reactions)
        if human_readable:
            self.indent(root)
        return ET.ElementTree(root)

    def _xml_size_for_settings(self, messages, human_readable, include_reactions):
        tree = self._build_xml_tree(messages, include_reactions, human_readable)
        with io.BytesIO() as bio:
            tree.write(bio, encoding='utf-8', xml_declaration=True)
            return len(bio.getvalue())

    def get_message_dates_range(self, messages):
        """Get date range for filtered messages"""
        if not messages:
            return ""
        
        dates = [msg.get('date', '') for msg in messages if msg.get('date')]
        if not dates:
            return ""
        
        dates.sort()
        start_date = dates[0].split('T')[0]
        end_date = dates[-1].split('T')[0]
        
        if start_date == end_date:
            return f"({start_date})"
        return f"({start_date}_to_{end_date})"

    def update_output_filename(self, *args):
        """Update the output filename when source file is selected"""
        source = self.source_path.get()
        if source:
            source_dir = os.path.dirname(source)
            
            try:
                data = self._load_source_data()
                messages = data.get('messages', [])

                self.is_private_chat = data.get('type') == 'personal_chat'

                self.authors = {
                    msg.get('from', '')
                    for msg in messages
                    if isinstance(msg, dict) and msg.get('type') == 'message' and msg.get('from')
                }
                self.authors.discard('')

                self.authors_listbox.delete(0, tk.END)
                for author in sorted(self.authors):
                    self.authors_listbox.insert(tk.END, author)

                if self.is_private_chat and self.authors:
                    self.authors_frame.pack(fill="x", pady=2)
                else:
                    self.authors_frame.pack_forget()

                self.authors_listbox.selection_set(0, tk.END)
                self.selected_authors = set(self.authors)

                export_label = build_export_label(data.get('name', 'chat'), messages)
                self.output_dir.set(os.path.join(source_dir, export_label))
                self.output_filename.set(f"{export_label}.xml")

                self.status_var.set("Ready to convert")
                self.window.after(1, self.update_all_counters)
                self.update_available_dates()
            except Exception as e:
                print(f"Error processing file: {str(e)}")
                self.status_var.set(f"Error: {str(e)}")
                self.stats_var.set("")
                self.format_info.set("")
                self.reactions_info.set("")
                self.output_filename.set("output.xml")

    def process_message(self, message, root):
        """Append one already-filtered message to XML root."""
        return build_message_element(root, message, include_reactions=self.include_reactions.get())

    def convert_json_to_xml(self):
        try:
            if not self.source_path.get() or not self.output_filename.get():
                self.status_var.set("Error: Please select source file and output filename")
                return

            data = self._load_source_data()
            messages = self._get_filtered_messages(data=data, use_selected_date_range=True)

            if not messages:
                self.status_var.set("Error: No messages to export")
                self.progress_var.set(0)
                return

            total_messages = len(messages)
            root = ET.Element("messages")
            for index, message in enumerate(messages, start=1):
                self.process_message(message, root)
                self.progress_var.set((index / total_messages) * 100)
                self.window.update_idletasks()

            tree = ET.ElementTree(root)
            if self.human_readable.get():
                self.indent(root)

            output_path = os.path.join(self.output_dir.get(), self.output_filename.get())
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            tree.write(output_path, encoding='utf-8', xml_declaration=True)

            self.status_var.set(f"Converted successfully: {total_messages:,} messages")
            self.progress_var.set(100)
        except Exception as e:
            print(f"Error converting file: {str(e)}")
            self.status_var.set(f"Error: {str(e)}")
            self.progress_var.set(0)

    def show_help(self):
        help_window = tk.Toplevel(self.window)
        help_window.title("About JSON to XML Converter")
        help_window.geometry("500x400")
        
        # Make the window modal
        help_window.transient(self.window)
        help_window.grab_set()
        
        # Create text widget
        text_widget = tk.Text(help_window, wrap=tk.WORD, padx=10, pady=10)
        text_widget.pack(fill=tk.BOTH, expand=True)
        
        # Add scrollbar
        scrollbar = ttk.Scrollbar(help_window, orient=tk.VERTICAL, command=text_widget.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        text_widget.configure(yscrollcommand=scrollbar.set)
        
        # Updated help content
        help_text = """JSON to XML Converter

Usage Instructions:

1. Source File Selection:
   • Click 'Select JSON file' to choose your Telegram chat export
   • Output location will be automatically set to source file directory
   • Output filename will be generated based on chat name and date range

2. Export Options:
   a) Format Options:
      • Human Readable Format:
        - Adds proper indentation and line breaks
        - Makes XML easier to read
        - Shows character impact in real-time
      • Include Reactions:
        - Option to include or skip reaction data
        - Shows character impact in real-time
        - Helps optimize output file size

   b) Date Range Filter:
      • Enable/disable date range filtering
      • Select dates using Year/Month/Day dropdowns
      • From: Select start date of the range
      • To: Select end date of the range
      • Reset to Full Range button available
      • Partial dates supported (year only, year-month)
      • Updates counters automatically
      • Default: Full date range selected

   c) Author Selection:
      • Select one or multiple authors to include
      • Deselect authors to exclude their messages
      • All counters update automatically
      • No authors selected = no messages in export

3. Status Information:
   • Reactions counter shows emoji usage statistics
   • Message count and date range display
   • Character count and token estimation
   • Click status text to copy to clipboard
   • Progress bar shows conversion status
   • Real-time updates for all changes

4. Converting:
   • Review export options and selections
   • Check estimated size and token count
   • Click 'CONVERT' to process the file
   • Progress bar will show conversion status
   • Status will update with results

5. Additional Features:
   • Real-time counter updates
   • Automatic window sizing
   • Clipboard support for status
   • Error handling and feedback
   • Smart date range selection
   • Flexible filtering options

Note: The converter will maintain proper XML structure regardless of selected options. Date range and author filters can be combined to precisely select the messages you want to export.

Click 'Close' to return to the converter."""
        
        # Insert help text and make read-only
        text_widget.insert('1.0', help_text)
        text_widget.configure(state='disabled')
        
        # Add close button
        close_button = ttk.Button(help_window, text="Close", command=help_window.destroy)
        close_button.pack(pady=10)
        
        # Center the window relative to the main window
        help_window.update_idletasks()
        x = self.window.winfo_x() + (self.window.winfo_width() // 2) - (help_window.winfo_width() // 2)
        y = self.window.winfo_y() + (self.window.winfo_height() // 2) - (help_window.winfo_height() // 2)
        help_window.geometry(f"+{x}+{y}")

    def update_format_info(self, *args):
        """Update format information based on current settings and selection"""
        try:
            if not self.source_path.get():
                return
            
            # Calculate both formatted and unformatted sizes
            formatted_chars = self.calculate_total_chars(human_readable=True, with_reactions=True)
            unformatted_chars = self.calculate_total_chars(human_readable=False, with_reactions=False)
            current_chars = self.calculate_total_chars(
                human_readable=self.human_readable.get(),
                with_reactions=self.include_reactions.get()
            )
            
            # Calculate savings
            max_chars = formatted_chars
            saved_chars = max_chars - current_chars
            saved_tokens = saved_chars // 4
            
            # Update info labels with savings
            if self.human_readable.get():
                self.format_info.set(f"(+{saved_chars:,} characters, +{saved_tokens:,} tokens)")
            else:
                self.format_info.set(f"(-{saved_chars:,} characters, -{saved_tokens:,} tokens)")
            
            if self.include_reactions.get():
                reaction_chars = self.calculate_reaction_chars()
                self.reactions_info.set(f"(+{reaction_chars:,} characters, +{reaction_chars//4:,} tokens)")
            else:
                reaction_chars = self.calculate_reaction_chars()
                self.reactions_info.set(f"(-{reaction_chars:,} characters, -{reaction_chars//4:,} tokens)")
            
            # Update total summary
            self.summary_info.set(
                f"Total characters: {current_chars:,}\n"
                f"Estimated tokens: {current_chars//4:,}"
            )
            
        except Exception as e:
            print(f"Error updating format info: {str(e)}")
            self.format_info.set("(error)")
            self.reactions_info.set("(error)")
            self.summary_info.set("Error calculating size")

    def get_xml_size(self, tree):
        """Calculate size of XML"""
        with io.BytesIO() as bio:
            tree.write(bio, encoding='utf-8', xml_declaration=True)
            return len(bio.getvalue())

    def indent(self, elem, level=0):
        """Add proper indentation to XML elements"""
        indent_xml(elem, level)

    def copy_status_to_clipboard(self, event=None):
        """Copy status text to clipboard and show feedback using pbcopy"""
        status_text = self.status_var.get()
        if status_text:
            try:
                # Use pbcopy for macOS clipboard
                process = subprocess.Popen(['pbcopy'], stdin=subprocess.PIPE)
                process.communicate(status_text.encode('utf-8'))
                
                # Show feedback
                original_text = status_text
                self.status_var.set("Copied to clipboard!")
                
                # Schedule restoration of original text after 1 second
                self.window.after(1000, lambda: self.status_var.set(original_text))
            except Exception as e:
                print(f"Error copying to clipboard: {str(e)}")

    def create_tooltip(self, widget, text):
        """Create a tooltip for a given widget"""
        def show_tooltip(event):
            tooltip = tk.Toplevel()
            tooltip.wm_overrideredirect(True)
            tooltip.wm_geometry(f"+{event.x_root+10}+{event.y_root+10}")
            
            label = ttk.Label(tooltip, text=text, background="#ffffe0", relief="solid", borderwidth=1)
            label.pack()
            
            def hide_tooltip():
                tooltip.destroy()
            
            widget.tooltip = tooltip
            widget.bind('<Leave>', lambda e: hide_tooltip())
            tooltip.bind('<Leave>', lambda e: hide_tooltip())
        
        widget.bind('<Enter>', show_tooltip)

    def on_author_selection(self, event=None):
        """Handle author selection changes"""
        selection = self.authors_listbox.curselection()
        previous_authors = self.selected_authors.copy()
        self.selected_authors = {self.authors_listbox.get(i) for i in selection}
        
        # Only update if the selection actually changed
        if previous_authors != self.selected_authors:
            self.update_all_counters()
            # Update date range based on selected authors
            self.update_date_range_for_authors()

    def update_date_range_for_authors(self):
        """Update date range based on selected authors"""
        try:
            if not self.source_path.get() or not self.selected_authors:
                return

            data = self._load_source_data()
            messages = filter_messages(
                data.get('messages', []),
                selected_authors=self.selected_authors,
                use_date_range=False,
                require_text=True,
            )
            dates = sorted([extract_message_date(msg) for msg in messages if extract_message_date(msg)])

            if dates:
                min_date = dates[0]
                max_date = dates[-1]

                self.start_year.set(min_date[:4])
                self.start_month.set(min_date[5:7])
                self.start_day.set(min_date[8:10])

                self.end_year.set(max_date[:4])
                self.end_month.set(max_date[5:7])
                self.end_day.set(max_date[8:10])
            
        except Exception as e:
            print(f"Error updating date range for authors: {str(e)}")

    def update_all_counters(self):
        """Update all counters based on current selection"""
        try:
            if not self.source_path.get():
                return
            
            if not self.selected_authors:
                # Handle zero state
                self.reactions_var.set("No messages selected")
                self.stats_var.set("Messages: 0\nDate range: (no messages)")
                self.format_info.set("(0 characters)")
                self.reactions_info.set("(0 characters)")
                self.summary_info.set(
                    "Total characters: 0\n"
                    "Estimated tokens: 0"
                )
                self.status_var.set("No authors selected")
                return
            
            data = self._load_source_data()
            messages = self._get_filtered_messages(data=data, use_selected_date_range=True)

            if not messages:
                self.reactions_var.set("No messages found")
                self.stats_var.set("Messages: 0\nDate range: (no messages)")
                self.format_info.set("(0 characters)")
                self.reactions_info.set("(0 characters)")
                self.summary_info.set(
                    "Total characters: 0\n"
                    "Estimated tokens: 0"
                )
                self.status_var.set("No messages to export")
                return

            reactions_count = {}
            for message in messages:
                for reaction in message.get('reactions', []):
                    emoji = reaction.get('emoji', '')
                    count = reaction.get('count', 0)
                    if emoji and count > 0:
                        reactions_count[emoji] = reactions_count.get(emoji, 0) + count

            if reactions_count:
                reactions_list = sorted(reactions_count.items(), key=lambda x: (-x[1], x[0]))
                window_width = self.window.winfo_width()
                available_width = window_width - 40
                avg_item_width = 12
                min_spacing = 3
                items_per_row = max(4, available_width // ((avg_item_width + min_spacing) * 8))
                total_items = len(reactions_list)
                num_rows = min(6, (total_items + items_per_row - 1) // items_per_row)
                items_per_row = (total_items + num_rows - 1) // num_rows

                reactions_rows = []
                for row_start in range(0, total_items, items_per_row):
                    row_items = reactions_list[row_start:row_start + items_per_row]
                    spacing = " " * max(
                        3,
                        (available_width // 8 - len(row_items) * avg_item_width) //
                        (len(row_items) - 1 if len(row_items) > 1 else 1),
                    )
                    row = spacing.join(f"{emoji}: {count}" for emoji, count in row_items)
                    reactions_rows.append(row)
                reactions_text = "Reactions:\n" + "\n".join(reactions_rows)
            else:
                reactions_text = "No reactions found"

            self.reactions_var.set(reactions_text)
            date_range = self.get_message_dates_range(messages)
            self.stats_var.set(f"Messages: {len(messages)}\nDate range: {date_range}")
            self.update_format_info()
            self.status_var.set("Ready to convert")

            self.window.update_idletasks()
            required_height = self.main_container.winfo_reqheight() + 40
            current_height = self.window.winfo_height()
            if required_height > current_height:
                self.window.geometry(f"{self.window.winfo_width()}x{required_height}")
                
        except Exception as e:
            print(f"Error updating counters: {str(e)}")
            self.reactions_var.set("")
            self.stats_var.set("")
            self.format_info.set("")
            self.reactions_info.set("")
            self.summary_info.set("")
            self.status_var.set(f"Error: {str(e)}")

    def on_window_resize(self, event=None):
        """Handle window resize events"""
        if event.widget == self.window:
            # Update counters to adjust to new size
            self.update_all_counters()

    def filter_messages_by_date(self, messages):
        """Filter messages by date range if enabled"""
        try:
            start, end = self._current_date_bounds()
            return filter_messages(
                messages,
                selected_authors=set(),
                start_date=start,
                end_date=end,
                use_date_range=self.use_date_range.get(),
                require_text=False,
            )
        except Exception as e:
            print(f"Date filtering error: {str(e)}")
            return messages

    def select_source_file(self):
        """Open file dialog to select source JSON file"""
        filename = filedialog.askopenfilename(
            title="Select JSON file",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if filename:
            self.source_path.set(filename)

    def select_output_dir(self):
        """Open directory dialog to select output location"""
        directory = filedialog.askdirectory(
            title="Select output directory",
            initialdir=self.output_dir.get() if self.output_dir.get() else None
        )
        if directory:
            self.output_dir.set(directory)

    def update_available_dates(self):
        """Update available dates based on the loaded file"""
        try:
            if self.source_path.get():
                data = self._load_source_data()
                messages = filter_messages(
                    data.get('messages', []),
                    selected_authors=set(),
                    use_date_range=False,
                    require_text=False,
                )
                dates = sorted([extract_message_date(msg) for msg in messages if extract_message_date(msg)])

                if dates:
                    min_date = dates[0]
                    max_date = dates[-1]
                    self.years = sorted(list(set(d[:4] for d in dates)))

                    for dropdown in [self.start_year_cb, self.end_year_cb]:
                        dropdown['values'] = [''] + self.years

                    self.start_year.set(min_date[:4])
                    self.start_month.set(min_date[5:7])
                    self.start_day.set(min_date[8:10])

                    self.end_year.set(max_date[:4])
                    self.end_month.set(max_date[5:7])
                    self.end_day.set(max_date[8:10])

                    self.use_date_range.set(True)
                
        except Exception as e:
            print(f"Error updating dates: {str(e)}")

    def get_date_string(self, year, month, day):
        """Convert year, month, day variables to YYYY-MM-DD format"""
        if not year.get():
            return ''
        
        date_parts = [year.get()]
        
        if month.get():
            date_parts.append(month.get())
            if day.get():
                date_parts.append(day.get())
        
        return '-'.join(date_parts)

    def create_date_selector(self, parent, year_var, month_var, day_var, label_text):
        """Create a date selector with year, month, and day dropdowns"""
        frame = ttk.Frame(parent)
        frame.pack(fill="x", pady=2)
        
        ttk.Label(frame, text=label_text, width=8).pack(side="left", padx=(0, 5))
        
        def on_date_change(*args):
            self.update_all_counters()
        
        # Year dropdown
        year_cb = ttk.Combobox(
            frame,
            textvariable=year_var,
            values=[''] + self.years,
            width=6,
            state="readonly"
        )
        year_cb.pack(side="left", padx=(0, 2))
        
        # Month dropdown
        month_cb = ttk.Combobox(
            frame,
            textvariable=month_var,
            values=[''] + self.months,
            width=4,
            state="readonly"
        )
        month_cb.pack(side="left", padx=(0, 2))
        
        # Day dropdown
        day_cb = ttk.Combobox(
            frame,
            textvariable=day_var,
            values=[''] + self.days,
            width=4,
            state="readonly"
        )
        day_cb.pack(side="left")
        
        # Bind change events
        year_var.trace_add('write', on_date_change)
        month_var.trace_add('write', on_date_change)
        day_var.trace_add('write', on_date_change)
        
        return year_cb, month_cb, day_cb

    def reset_date_range(self):
        """Reset date range to the available range based on selected authors"""
        try:
            if not self.source_path.get() or not self.selected_authors:
                return

            data = self._load_source_data()
            messages = filter_messages(
                data.get('messages', []),
                selected_authors=self.selected_authors,
                use_date_range=False,
                require_text=True,
            )
            dates = sorted([extract_message_date(msg) for msg in messages if extract_message_date(msg)])

            if dates:
                min_date = dates[0]
                max_date = dates[-1]

                self.start_year.set(min_date[:4])
                self.start_month.set(min_date[5:7])
                self.start_day.set(min_date[8:10])

                self.end_year.set(max_date[:4])
                self.end_month.set(max_date[5:7])
                self.end_day.set(max_date[8:10])

                self.use_date_range.set(True)
                self.update_all_counters()
    
        except Exception as e:
            print(f"Error resetting date range: {str(e)}")

    def calculate_total_chars(self, human_readable=False, with_reactions=False):
        """Calculate total characters based on current settings"""
        try:
            if not self.source_path.get():
                return 0

            data = self._load_source_data()
            messages = self._get_filtered_messages(data=data, use_selected_date_range=True)
            if not messages:
                return 0

            return self._xml_size_for_settings(
                messages,
                human_readable=human_readable,
                include_reactions=with_reactions,
            )
                
        except Exception as e:
            print(f"Error calculating total chars: {str(e)}")
            return 0

    def calculate_reaction_chars(self):
        """Calculate characters used by reactions"""
        try:
            if not self.source_path.get():
                return 0

            data = self._load_source_data()
            messages = self._get_filtered_messages(data=data, use_selected_date_range=True)
            if not messages:
                return 0

            with_reactions = self._xml_size_for_settings(
                messages,
                human_readable=self.human_readable.get(),
                include_reactions=True,
            )
            without_reactions = self._xml_size_for_settings(
                messages,
                human_readable=self.human_readable.get(),
                include_reactions=False,
            )
            return max(0, with_reactions - without_reactions)
                
        except Exception as e:
            print(f"Error calculating reaction chars: {str(e)}")
            return 0

def _prompt_yes_no(prompt, default=True):
    suffix = "[Y/n]" if default else "[y/N]"
    value = input(f"{prompt} {suffix}: ").strip().lower()
    if not value:
        return default
    return value in {"y", "yes", "1", "true"}


def _arrow_ui_available():
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        return False
    try:
        import curses  # noqa: F401
        return True
    except Exception:
        return False


def _menu_single_select(title, options, default_index=0):
    if not options:
        raise ValueError("Options list is empty")

    if not _arrow_ui_available():
        print(title)
        for idx, option in enumerate(options, start=1):
            print(f"  {idx}. {option}")
        raw = input(f"Select [1-{len(options)}] (default {default_index + 1}): ").strip()
        if raw.isdigit():
            chosen = int(raw) - 1
            if 0 <= chosen < len(options):
                return chosen
        return default_index

    import curses

    def _draw(stdscr):
        curses.curs_set(0)
        stdscr.keypad(True)
        index = max(0, min(default_index, len(options) - 1))

        while True:
            stdscr.clear()
            stdscr.addstr(0, 0, title)
            stdscr.addstr(1, 0, "Use arrows, Enter to select")
            for i, option in enumerate(options):
                prefix = "➤ " if i == index else "  "
                stdscr.addstr(i + 3, 0, f"{prefix}{option}")
            stdscr.refresh()
            key = stdscr.getch()

            if key in (curses.KEY_UP, ord('k')):
                index = (index - 1) % len(options)
            elif key in (curses.KEY_DOWN, ord('j')):
                index = (index + 1) % len(options)
            elif key in (10, 13, curses.KEY_ENTER):
                return index
            elif key in (27, ord('q')):
                return default_index

    return curses.wrapper(_draw)


def _menu_multi_select(title, options, default_selected=None):
    default_selected = set(default_selected or [])
    if not options:
        return set()

    if not _arrow_ui_available():
        print(title)
        for idx, option in enumerate(options, start=1):
            mark = "x" if option in default_selected else " "
            print(f"  [{mark}] {idx}. {option}")
        raw = input("Select numbers comma-separated (empty = defaults): ").strip()
        if not raw:
            return set(default_selected) if default_selected else set(options)
        indexes = []
        for chunk in raw.split(","):
            chunk = chunk.strip()
            if chunk.isdigit():
                indexes.append(int(chunk))
        return {options[i - 1] for i in indexes if 1 <= i <= len(options)}

    import curses

    def _draw(stdscr):
        curses.curs_set(0)
        stdscr.keypad(True)
        index = 0
        selected = {i for i, opt in enumerate(options) if opt in default_selected}

        if not selected:
            selected = set(range(len(options)))

        while True:
            stdscr.clear()
            stdscr.addstr(0, 0, title)
            stdscr.addstr(1, 0, "Arrows navigate, Space toggle, a=all, Enter confirm")
            for i, option in enumerate(options):
                cursor = "➤" if i == index else " "
                mark = "x" if i in selected else " "
                stdscr.addstr(i + 3, 0, f"{cursor} [{mark}] {option}")
            stdscr.refresh()
            key = stdscr.getch()

            if key in (curses.KEY_UP, ord('k')):
                index = (index - 1) % len(options)
            elif key in (curses.KEY_DOWN, ord('j')):
                index = (index + 1) % len(options)
            elif key == ord(' '):
                if index in selected:
                    selected.remove(index)
                else:
                    selected.add(index)
            elif key in (ord('a'), ord('A')):
                selected = set(range(len(options)))
            elif key in (10, 13, curses.KEY_ENTER):
                if not selected:
                    selected = set(range(len(options)))
                return {options[i] for i in sorted(selected)}
            elif key in (27, ord('q')):
                return {options[i] for i in sorted(selected)}

    return curses.wrapper(_draw)


def _menu_yes_no(title, default=True):
    options = ["Yes", "No"]
    default_index = 0 if default else 1
    selected = _menu_single_select(title, options, default_index=default_index)
    return selected == 0


def _preset_store_path():
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), ".tgxml_presets.json")


def _load_presets():
    path = _preset_store_path()
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save_presets(presets):
    path = _preset_store_path()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(presets, f, ensure_ascii=False, indent=2)


def _print_banner(use_plain=False):
    if use_plain:
        return
    print("=" * 56)
    print(" Telegram JSON -> XML Converter (Interactive CLI) ".center(56, "="))
    print("=" * 56)


def _parse_cli_args(argv):
    examples = (
        "Quick start:\n"
        "  python3 jsontoxml.py --cli\n\n"
        "One-shot run (no menu):\n"
        "  python3 jsontoxml.py --cli --run --source chat.json --output out.xml\n\n"
        "Textual TUI:\n"
        "  python3 jsontoxml.py --tui\n\n"
        "Interactive wizard:\n"
        "  python3 jsontoxml.py --interactive --source chat.json\n\n"
        "Filter by author/date:\n"
        "  python3 jsontoxml.py --cli --run --source chat.json --author Alice --start-date 2025-01-01 --end-date 2025-02-01\n\n"
        "Dry run (no file write):\n"
        "  python3 jsontoxml.py --cli --run --source chat.json --dry-run --report-json"
    )
    parser = argparse.ArgumentParser(
        description="Convert Telegram JSON export to XML (GUI and CLI).",
        epilog=examples,
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument("--cli", action="store_true", help="Force CLI mode")
    parser.add_argument("--run", action="store_true", help="Run one-shot conversion (skip menu)")
    parser.add_argument("--tui", action="store_true", help="Run modern Textual TUI mode")
    parser.add_argument("--interactive", action="store_true", help="Run interactive CLI wizard")
    parser.add_argument("--source", help="Path to source Telegram JSON")
    parser.add_argument("--sources", nargs="+", help="Multiple source JSON files to merge")
    parser.add_argument("--output", help="Output XML file path")
    parser.add_argument("--output-dir", help="Output directory (if --output is not set)")
    parser.add_argument("--author", action="append", default=[], help="Author to include (repeatable)")
    parser.add_argument("--start-date", default="", help="Start date (YYYY, YYYY-MM, or YYYY-MM-DD)")
    parser.add_argument("--end-date", default="", help="End date (YYYY, YYYY-MM, or YYYY-MM-DD)")
    parser.add_argument("--no-date-filter", action="store_true", help="Disable date filtering")
    parser.add_argument("--no-reactions", action="store_true", help="Exclude reactions from XML")
    parser.add_argument("--compact", action="store_true", help="Write compact XML (no pretty indentation)")
    parser.add_argument("--dry-run", action="store_true", help="Evaluate filters and report stats without writing XML")
    parser.add_argument("--report-json", action="store_true", help="Print dry-run/conversion report as JSON")
    parser.add_argument("--include-service", action="store_true", help="Include Telegram service messages")
    parser.add_argument("--include-media-meta", action="store_true", help="Include media metadata in XML")
    parser.add_argument("--include-entities", action="store_true", help="Include text_entities in XML")
    parser.add_argument("--anonymize", action="store_true", help="Anonymize authors and identifiers in output")
    parser.add_argument("--validate-input", action="store_true", help="Validate input JSON structure before conversion")
    parser.add_argument("--plain", action="store_true", help="Plain interactive output (no TUI decorations)")
    parser.add_argument("--no-color", action="store_true", help="Disable ANSI colors in CLI output")
    parser.add_argument("--preset", help="Load conversion preset by name")
    parser.add_argument("--save-preset", help="Save current options as preset name")
    return parser.parse_args(argv)


def run_cli(args):
    from src.tgxml.cli_flow import (
        build_conversion_payload,
        create_report,
        format_dry_run_report,
        write_xml,
        build_replay_command,
        report_as_json,
    )

    source_path = args.source
    source_paths = list(args.sources or [])
    if source_path and source_path not in source_paths:
        source_paths.append(source_path)

    output_path = args.output
    output_dir = args.output_dir
    selected_authors = set(args.author or [])
    use_date_range = not args.no_date_filter
    start_date = args.start_date
    end_date = args.end_date
    include_reactions = not args.no_reactions
    human_readable = not args.compact
    dry_run = args.dry_run
    include_service = args.include_service
    include_media_meta = args.include_media_meta
    include_entities = args.include_entities
    anonymize = args.anonymize
    validate_input = args.validate_input
    plain = args.plain
    no_color = args.no_color

    _print_banner(use_plain=plain)

    presets = _load_presets()
    if args.preset:
        preset_data = presets.get(args.preset)
        if not preset_data:
            raise ValueError(f"Preset not found: {args.preset}")
        selected_authors = set(preset_data.get("selected_authors", list(selected_authors)))
        use_date_range = bool(preset_data.get("use_date_range", use_date_range))
        start_date = preset_data.get("start_date", start_date)
        end_date = preset_data.get("end_date", end_date)
        include_reactions = bool(preset_data.get("include_reactions", include_reactions))
        human_readable = bool(preset_data.get("human_readable", human_readable))
        include_service = bool(preset_data.get("include_service", include_service))
        include_media_meta = bool(preset_data.get("include_media_meta", include_media_meta))
        include_entities = bool(preset_data.get("include_entities", include_entities))
        anonymize = bool(preset_data.get("anonymize", anonymize))
        validate_input = bool(preset_data.get("validate_input", validate_input))

    if args.interactive:
        if not source_paths:
            single_source = input("Source JSON path: ").strip()
            source_paths = [single_source]

        data = load_json_file(source_paths[0])
        messages = data.get('messages', [])
        available_authors = get_available_authors(messages)
        min_date, max_date = get_date_range_from_messages(messages)

        mode_index = _menu_single_select(
            "Interactive CLI",
            [
                "Quick convert (defaults)",
                "Wizard (full options)",
                "Inspect source",
                "Presets",
                "Exit",
            ],
            default_index=1,
        )

        if mode_index == 2:
            print(f"Source: {source_paths[0]}")
            print(f"Raw items: {len(messages)}")
            print(f"Message authors: {len(available_authors)}")
            if min_date and max_date:
                print(f"Date range: {min_date} .. {max_date}")
            print("Authors:")
            for author in available_authors:
                print(f"  - {author}")
            return

        if mode_index == 3:
            if not presets:
                print("No presets found.")
                return
            preset_names = sorted(list(presets.keys()))
            idx = _menu_single_select("Choose preset", preset_names, default_index=0)
            selected = presets[preset_names[idx]]
            selected_authors = set(selected.get("selected_authors", []))
            use_date_range = bool(selected.get("use_date_range", True))
            start_date = selected.get("start_date", "")
            end_date = selected.get("end_date", "")
            include_reactions = bool(selected.get("include_reactions", True))
            human_readable = bool(selected.get("human_readable", True))
            include_service = bool(selected.get("include_service", False))
            include_media_meta = bool(selected.get("include_media_meta", False))
            include_entities = bool(selected.get("include_entities", False))
            anonymize = bool(selected.get("anonymize", False))
            validate_input = bool(selected.get("validate_input", False))
            dry_run = bool(selected.get("dry_run", False))
            output_dir = selected.get("output_dir", output_dir)
            output_path = selected.get("output_path", output_path)
        elif mode_index == 4:
            print("Aborted by user")
            return

        if mode_index == 0:
            selected_authors = set(available_authors)
            use_date_range = True if (min_date or max_date) else False
            start_date = min_date
            end_date = max_date
            include_reactions = True
            human_readable = True
        else:
            print(f"Detected {len(available_authors)} authors and {len(messages)} raw messages.")
            if min_date and max_date:
                print(f"Detected date range: {min_date} .. {max_date}")

            if available_authors:
                selected_authors = _menu_multi_select(
                    "Select authors",
                    available_authors,
                    default_selected=set(available_authors),
                )
            else:
                selected_authors = set()

            use_date_range = _menu_yes_no("Enable date filter?", default=True)
            if use_date_range:
                default_start = min_date if min_date else ""
                default_end = max_date if max_date else ""
                while True:
                    start_input = input(f"Start date [{default_start}] (h/? help, s skip, q quit): ").strip()
                    if start_input in {"h", "?"}:
                        print("Use YYYY, YYYY-MM or YYYY-MM-DD. Empty keeps default.")
                        continue
                    if start_input == "q":
                        print("Aborted by user")
                        return
                    if start_input == "s":
                        start_input = ""
                    break
                while True:
                    end_input = input(f"End date [{default_end}] (h/? help, s skip, b back, q quit): ").strip()
                    if end_input in {"h", "?"}:
                        print("Use YYYY, YYYY-MM or YYYY-MM-DD. Empty keeps default.")
                        continue
                    if end_input == "q":
                        print("Aborted by user")
                        return
                    if end_input == "b":
                        start_input = input(f"Start date [{default_start}]: ").strip()
                        continue
                    if end_input == "s":
                        end_input = ""
                    break
                start_date = start_input or default_start
                end_date = end_input or default_end
            else:
                start_date = ""
                end_date = ""

            include_reactions = _menu_yes_no("Include reactions?", default=True)
            human_readable = _menu_yes_no("Human-readable XML?", default=True)
            include_service = _menu_yes_no("Include service messages?", default=False)
            include_media_meta = _menu_yes_no("Include media metadata?", default=False)
            include_entities = _menu_yes_no("Include text entities?", default=False)
            anonymize = _menu_yes_no("Anonymize authors/ids?", default=False)
            validate_input = _menu_yes_no("Validate input structure?", default=True)
            dry_run = _menu_yes_no("Dry run (do not write XML)?", default=False)

        if not output_dir:
            output_dir = input("Output directory (empty = auto chat folder): ").strip() or None

        if _menu_yes_no("Save these options as preset?", default=False):
            preset_name = input("Preset name: ").strip()
            if preset_name:
                presets[preset_name] = {
                    "selected_authors": sorted(list(selected_authors)),
                    "use_date_range": use_date_range,
                    "start_date": start_date,
                    "end_date": end_date,
                    "include_reactions": include_reactions,
                    "human_readable": human_readable,
                    "include_service": include_service,
                    "include_media_meta": include_media_meta,
                    "include_entities": include_entities,
                    "anonymize": anonymize,
                    "validate_input": validate_input,
                    "dry_run": dry_run,
                    "output_dir": output_dir,
                    "output_path": output_path,
                }
                _save_presets(presets)
                print(f"Preset saved: {preset_name}")
    else:
        if not source_paths:
            raise ValueError("CLI mode requires --source")

    payload = build_conversion_payload(
        source_paths=source_paths,
        output_path=output_path,
        output_dir=output_dir,
        selected_authors=selected_authors,
        start_date=start_date,
        end_date=end_date,
        use_date_range=use_date_range,
        include_service=include_service,
        include_media_meta=include_media_meta,
        include_entities=include_entities,
        include_reactions=include_reactions,
        human_readable=human_readable,
        anonymize=anonymize,
        validate_input=validate_input,
    )
    output_path = payload["output_path"]
    report = create_report(payload, dry_run=dry_run)

    if args.save_preset:
        presets[args.save_preset] = {
            "selected_authors": sorted(list(selected_authors)),
            "use_date_range": use_date_range,
            "start_date": start_date,
            "end_date": end_date,
            "include_reactions": include_reactions,
            "human_readable": human_readable,
            "include_service": include_service,
            "include_media_meta": include_media_meta,
            "include_entities": include_entities,
            "anonymize": anonymize,
            "validate_input": validate_input,
            "dry_run": dry_run,
            "output_dir": output_dir,
            "output_path": output_path,
        }
        _save_presets(presets)

    if dry_run:
        if args.report_json:
            print(report_as_json(report))
        else:
            print(format_dry_run_report(report))
        return

    write_xml(payload)
    filter_stats = payload["filter_stats"]
    validation_issues = payload["validation_issues"]

    if args.report_json:
        print(report_as_json(report))
    else:
        print(f"Converted successfully: {filter_stats['included']} messages")
        print(f"Output: {output_path}")
        if validation_issues:
            print("Validation issues:")
            for issue in validation_issues:
                print(f"  - {issue}")
        replay = build_replay_command(payload, no_color=no_color, plain=plain)
        print("Replay command:")
        print("  " + replay)


def main():
    args = _parse_cli_args(sys.argv[1:])

    # If user passed direct sources without explicit mode, keep one-shot behavior.
    if (args.source or args.sources) and not args.cli and not args.tui and not args.interactive:
        args.run = True

    if args.tui:
        try:
            from src.tgxml.tui_app import run_textual_tui
            run_textual_tui()
        except Exception as exc:
            raise SystemExit(
                f"Textual TUI is not available: {exc}. "
                "Install it with: python3 -m pip install textual"
            ) from exc
        return

    # Default CLI mode should open a menu-first experience, not auto-run conversion.
    if args.cli and not args.run:
        try:
            from src.tgxml.tui_app import run_textual_tui
            run_textual_tui()
            return
        except Exception:
            args.interactive = True

    run_in_cli = args.cli or args.interactive or args.run

    if run_in_cli:
        run_cli(args)
        return

    if tk is None:
        raise RuntimeError(
            "Tkinter is not available in this Python environment. "
            "Use CLI mode (--cli) or one-shot (--cli --run --source ...), or install Tkinter to run GUI."
        )

    gui = ConversionGUI()
    gui.run()

if __name__ == "__main__":
    main()     
