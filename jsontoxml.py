import json
import xml.etree.ElementTree as ET
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
import io
import copy
import subprocess

def indent(elem, level=0):
    """
    Функция для добавления отступов в XML для улучшения читаемости.
    """
    i = "\n" + level * "    "
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = i + "    "
        for child in elem:
            indent(child, level + 1)
        if not child.tail or not child.tail.strip():
            child.tail = i
    if level and (not elem.tail or not elem.tail.strip()):
        elem.tail = i

# Modify load_json to handle GUI errors
def load_json(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            return json.load(file)
    except FileNotFoundError:
        raise Exception(f"Файл '{file_path}' не найден.")
    except json.JSONDecodeError as e:
        raise Exception(f"Ошибка при разборе JSON файла: {e}")

# Modify process_group to update progress
def process_group(group, root, progress_var=None, status_var=None):
    if not isinstance(group, dict):
        if status_var:
            status_var.set(f"Пропущен элемент: {group} (не является словарём)")
        return
    
    group_name = group.get('name', 'Unnamed Group')
    group_id = group.get('id', 'unknown_id')
    
    if status_var:
        status_var.set(f"Обработка группы: {group_name} (ID: {group_id})")
    
    group_type = group.get('type', 'unknown_type')
    messages = group.get('messages', [])
    
    print(f"Обработка группы: {group_name} (ID: {group_id}) с {len(messages)} сообщениями.")
    
    # Создаём элемент <chat> для группы
    chat_elem = ET.SubElement(root, 'chat')
    
    # Добавляем информацию о группе
    name_elem = ET.SubElement(chat_elem, 'name')
    name_elem.text = group_name
    
    type_elem = ET.SubElement(chat_elem, 'type')
    type_elem.text = group_type
    
    id_elem = ET.SubElement(chat_elem, 'id')
    id_elem.text = str(group_id)
    
    # Создаём подэлемент для сообщений
    messages_elem = ET.SubElement(chat_elem, 'messages')
    
    included_messages = 0
    skipped_messages = 0
    
    # Обработка каждого сообщения
    for msg_index, msg in enumerate(messages):
        if isinstance(msg, dict) and msg.get('type') == 'message':
            # Обработка поля 'text'
            text = msg.get('text', '')
            if isinstance(text, list):
                # Если 'text' — список, объединяем все части в строку
                text = ''.join([part.get('text', '') if isinstance(part, dict) else str(part) for part in text])
            elif not isinstance(text, str):
                # Если 'text' не строка и не список, преобразуем в строку
                text = str(text)
            
            # Проверяем, не пустой ли текст
            if text.strip() == '':
                skipped_messages += 1
                continue  # Пропускаем это сообщение
            
            # Создаём элемент <message>
            message_elem = ET.SubElement(messages_elem, 'message')
            
            # Добавляем дату сообщения
            date_elem = ET.SubElement(message_elem, 'date')
            date_elem.text = msg.get('date', '')
            
            # Добавляем имя отправителя
            name_sender_elem = ET.SubElement(message_elem, 'name')
            name_sender_elem.text = msg.get('from', '')
            
            # Добавляем текст сообщения
            text_elem = ET.SubElement(message_elem, 'text')
            text_elem.text = text
            
            included_messages += 1
        else:
            # Пропускаем сообщения не типа 'message'
            skipped_messages += 1
    
    print(f"Сообщений включено: {included_messages}, пропущено: {skipped_messages}")

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
    
    def browse_source(self):
        filename = filedialog.askopenfilename(filetypes=[("JSON files", "*.json"), ("All files", "*.*")])
        if filename:
            self.source_path.set(filename)
    
    def browse_output(self):
        directory = filedialog.askdirectory()
        if directory:
            self.output_dir.set(directory)
    
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

    def get_reactions_summary(self, messages):
        """Count all unique reactions in the messages"""
        reaction_counts = {}
        for msg in messages:
            if isinstance(msg, dict) and 'reactions' in msg:
                for reaction in msg.get('reactions', []):
                    if isinstance(reaction, dict):
                        emoji = reaction.get('emoji', '')
                        count = reaction.get('count', 0)
                        if emoji and count > 0:
                            reaction_counts[emoji] = reaction_counts.get(emoji, 0) + count
        
        # Format the summary
        if not reaction_counts:
            return "No reactions found"
        
        summary = "Detected reactions: "
        reaction_items = [f"{emoji}({count})" for emoji, count in reaction_counts.items()]
        return summary + ", ".join(reaction_items)

    def get_file_stats(self, messages):
        """Get statistics about the file"""
        # Count messages
        total_messages = len(messages)
        
        # Get date range
        dates = []
        reaction_counts = {}
        
        for msg in messages:
            if isinstance(msg, dict):
                # Collect dates
                if 'date' in msg:
                    date = msg['date'].split()[0] if ' ' in msg['date'] else msg['date']
                    dates.append(date)
                
                # Count reactions
                if 'reactions' in msg:
                    for reaction in msg.get('reactions', []):
                        if isinstance(reaction, dict):
                            emoji = reaction.get('emoji', '')
                            count = reaction.get('count', 0)
                            if emoji and count > 0:
                                reaction_counts[emoji] = reaction_counts.get(emoji, 0) + count
        
        # Format date range
        date_range = ""
        if dates:
            dates.sort()
            if dates[0] == dates[-1]:
                date_range = dates[0]
            else:
                date_range = f"{dates[0]} to {dates[-1]}"
        
        # Format reactions
        reaction_str = ", ".join(f"{emoji}({count})" for emoji, count in reaction_counts.items())
        
        return f"Messages: {total_messages}\nDate range: {date_range}\nReactions: {reaction_str}"

    def update_output_filename(self, *args):
        """Update the output filename when source file is selected"""
        source = self.source_path.get()
        if source:
            source_dir = os.path.dirname(source)
            self.output_dir.set(source_dir)
            
            try:
                with open(source, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    messages = data.get('messages', [])
                    
                    # Detect if it's a private chat
                    self.is_private_chat = not data.get('name', '').startswith('@')
                    
                    # Collect unique authors
                    self.authors = {msg.get('from', '') for msg in messages if msg.get('from')}
                    self.authors.discard('')  # Remove empty author names
                    
                    # Update authors listbox
                    self.authors_listbox.delete(0, tk.END)
                    for author in sorted(self.authors):
                        self.authors_listbox.insert(tk.END, author)
                    
                    # Show/hide authors frame based on chat type
                    if self.is_private_chat and self.authors:
                        self.authors_frame.pack(fill="x", pady=2)
                        self.authors_listbox.selection_set(0, tk.END)  # Select all by default
                        self.selected_authors = set(self.authors)  # Initialize with all authors
                    else:
                        self.authors_frame.pack_forget()
                        self.selected_authors = set(self.authors)  # All authors for non-private chats
                    
                    # Get chat name and date range for filename
                    chat_name = data.get('name', 'chat').replace('/', '_')
                    date_range = self.get_message_dates_range(messages)
                    
                    # Set output filename
                    if date_range:
                        self.output_filename.set(f"{chat_name}_{date_range}.xml")
                    else:
                        self.output_filename.set(f"{chat_name}.xml")
                    
                    # Update status to ready state
                    self.status_var.set("Ready to convert")
                    
                    # Update counters after a small delay
                    self.window.after(1, self.update_all_counters)
                    
                    # Update available dates after loading file
                    self.update_available_dates()
                    
            except Exception as e:
                print(f"Error processing file: {str(e)}")
                self.status_var.set(f"Error: {str(e)}")
                self.stats_var.set("")
                self.format_info.set("")
                self.reactions_info.set("")
                self.output_filename.set("output.xml")

    def process_message(self, message, root):
        """Process message with strict author filtering and text-only content check"""
        # Skip message processing if no authors are selected
        if not self.selected_authors:
            return None
        
        author = message.get('from', '')
        if author in self.selected_authors:
            # Handle text content which can be string or list
            text = message.get('text', '')
            if isinstance(text, list):
                # If text is a list, join all text elements
                text = ''.join(item.get('text', '') if isinstance(item, dict) else str(item) for item in text)
            text = text.strip()
            
            # Skip messages without text content
            if not text:
                return None
            
            msg_element = ET.SubElement(root, "message")
            
            # Add message attributes
            msg_element.set('id', str(message.get('id', '')))
            msg_element.set('date', message.get('date', ''))
            msg_element.set('sender', author)
            
            # Process message text
            text_element = ET.SubElement(msg_element, "text")
            text_element.text = text
            
            # Process reply if exists
            reply_to = message.get('reply_to_message_id')
            if reply_to:
                msg_element.set('reply_to', str(reply_to))
            
            # Process reactions if enabled
            if self.include_reactions.get() and 'reactions' in message:
                reactions_element = ET.SubElement(msg_element, "reactions")
                for reaction in message['reactions']:
                    reaction_element = ET.SubElement(reactions_element, "reaction")
                    reaction_element.set('emoji', reaction.get('emoji', ''))
                    reaction_element.set('count', str(reaction.get('count', 0)))
            
            return msg_element
        return None

    def convert_json_to_xml(self):
        try:
            if not self.source_path.get() or not self.output_filename.get():
                self.status_var.set("Error: Please select source and output files")
                return
            
            with open(self.source_path.get(), 'r', encoding='utf-8') as f:
                data = json.load(f)
                messages = data.get('messages', [])
                
                # Filter messages by selected authors and text content
                filtered_messages = []
                for msg in messages:
                    if msg.get('from', '') in self.selected_authors:
                        text = msg.get('text', '')
                        if isinstance(text, list):
                            text = ''.join(item.get('text', '') if isinstance(item, dict) else str(item) for item in text)
                        if text.strip():
                            filtered_messages.append(msg)
                
                # Apply date range filter
                messages = self.filter_messages_by_date(filtered_messages)
                
                if not messages:
                    self.status_var.set("Error: No messages to export")
                    self.progress_var.set(0)
                    return
                
                root = ET.Element("messages")
                total_messages = len(messages)
                processed = 0
                
                for message in messages:
                    self.process_message(message, root)
                    processed += 1
                    progress = (processed / total_messages) * 100
                    self.progress_var.set(progress)
                    self.window.update_idletasks()
                
                # Create XML tree and save
                tree = ET.ElementTree(root)
                
                # Format XML if human readable option is selected
                if self.human_readable.get():
                    self.indent(root)
                
                output_path = os.path.join(self.output_dir.get(), self.output_filename.get())
                tree.write(output_path, encoding='utf-8', xml_declaration=True)
                
                self.status_var.set(f"Converted successfully: {processed:,} messages")
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
        i = "\n" + level*"  "
        if len(elem):
            if not elem.text or not elem.text.strip():
                elem.text = i + "  "
            if not elem.tail or not elem.tail.strip():
                elem.tail = i
            for subelem in elem:
                self.indent(subelem, level+1)
            if not elem.tail or not elem.tail.strip():
                elem.tail = i
        else:
            if level and (not elem.tail or not elem.tail.strip()):
                elem.tail = i

    def select_file(self):
        """Open file dialog to select JSON file"""
        filetypes = [
            ('JSON files', '*.json'),
            ('All files', '*.*')
        ]
        
        filename = filedialog.askopenfilename(
            title="Select JSON file",
            filetypes=filetypes
        )
        
        if filename:
            self.source_path.set(filename)

    def select_output_dir(self):
        """Open directory dialog to select output location"""
        directory = filedialog.askdirectory(
            title="Select Output Directory"
        )
        
        if directory:
            self.output_dir.set(directory)

    def handle_reactions_toggle(self):
        """Handle reactions checkbox toggle"""
        # Force update of the BooleanVar
        current_state = self.include_reactions.get()
        self.include_reactions.set(current_state)
        # Update format info with new state
        self.update_format_info()

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
            
            with open(self.source_path.get(), 'r', encoding='utf-8') as f:
                data = json.load(f)
                messages = data.get('messages', [])
                
                # Filter messages by selected authors
                dates = []
                for msg in messages:
                    if msg.get('from', '') in self.selected_authors:
                        date_str = msg.get('date', '').split('T')[0]
                        if date_str:
                            dates.append(date_str)
                
                if dates:
                    # Sort dates and get min/max
                    dates.sort()
                    min_date = dates[0]
                    max_date = dates[-1]
                    
                    # Update date range
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
            
            # Handle non-zero state
            with open(self.source_path.get(), 'r', encoding='utf-8') as f:
                data = json.load(f)
                messages = data.get('messages', [])
                
                # Filter messages by selected authors and text content
                filtered_messages = []
                for msg in messages:
                    if msg.get('from', '') in self.selected_authors:
                        text = msg.get('text', '')
                        if isinstance(text, list):
                            text = ''.join(item.get('text', '') if isinstance(item, dict) else str(item) for item in text)
                        if text.strip():
                            filtered_messages.append(msg)
                
                # Apply date range filter
                messages = self.filter_messages_by_date(filtered_messages)
                
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
                
                # Update reactions counter
                reactions_count = {}
                for message in messages:
                    if 'reactions' in message:
                        for reaction in message['reactions']:
                            emoji = reaction.get('emoji', '')
                            count = reaction.get('count', 0)
                            if emoji and count > 0:
                                reactions_count[emoji] = reactions_count.get(emoji, 0) + count
                
                if reactions_count:
                    # Sort reactions by count (descending) and then by emoji
                    reactions_list = sorted(reactions_count.items(), key=lambda x: (-x[1], x[0]))
                    
                    # Get window width and calculate optimal layout
                    window_width = self.window.winfo_width()
                    available_width = window_width - 40  # Account for padding
                    
                    # Calculate optimal items per row based on available width
                    avg_item_width = 12  # Average width of "emoji: number" in characters
                    min_spacing = 3  # Minimum spaces between items
                    
                    # Calculate how many items can fit in one row
                    items_per_row = max(4, available_width // ((avg_item_width + min_spacing) * 8))
                    
                    # Calculate number of rows needed
                    total_items = len(reactions_list)
                    num_rows = min(6, (total_items + items_per_row - 1) // items_per_row)
                    
                    # Recalculate items per row to distribute items evenly
                    items_per_row = (total_items + num_rows - 1) // num_rows
                    
                    # Create rows with dynamic spacing
                    reactions_rows = []
                    for row_start in range(0, total_items, items_per_row):
                        row_items = reactions_list[row_start:row_start + items_per_row]
                        # Calculate spacing for this row to fill available width
                        spacing = " " * max(3, (available_width // 8 - len(row_items) * avg_item_width) // (len(row_items) - 1 if len(row_items) > 1 else 1))
                        row = spacing.join(f"{emoji}: {count}" for emoji, count in row_items)
                        reactions_rows.append(row)
                    
                    reactions_text = "Reactions:\n" + "\n".join(reactions_rows)
                else:
                    reactions_text = "No reactions found"
                
                self.reactions_var.set(reactions_text)
                
                # Update other counters
                date_range = self.get_message_dates_range(messages)
                stats = f"Messages: {len(messages)}\nDate range: {date_range}"
                self.stats_var.set(stats)
                
                # Update format info and status
                self.update_format_info()
                self.status_var.set("Ready to convert")
                
                # Force window to update and resize if needed
                self.window.update_idletasks()
                
                # Get required height and resize window if needed
                required_height = self.main_container.winfo_reqheight() + 40
                current_height = self.window.winfo_height()
                if required_height > current_height:
                    self.window.geometry(f"{window_width}x{required_height}")
                
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
        if not self.use_date_range.get():
            return messages
        
        try:
            start = self.get_date_string(self.start_year, self.start_month, self.start_day)
            end = self.get_date_string(self.end_year, self.end_month, self.end_day)
            
            if not start and not end:
                return messages
            
            filtered = []
            for msg in messages:
                date_str = msg.get('date', '').split('T')[0]  # Get date part only
                
                if start and date_str < start:
                    continue
                if end and date_str > end:
                    continue
                
                filtered.append(msg)
            
            return filtered
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
                with open(self.source_path.get(), 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    messages = data.get('messages', [])
                    
                    # Extract all dates from messages
                    dates = []
                    for msg in messages:
                        date_str = msg.get('date', '').split('T')[0]  # YYYY-MM-DD
                        if date_str:
                            dates.append(date_str)
                    
                    if dates:
                        # Sort dates and get min/max
                        dates.sort()
                        min_date = dates[0]
                        max_date = dates[-1]
                        
                        # Extract unique years
                        self.years = sorted(list(set(d[:4] for d in dates)))
                        
                        # Update dropdowns with available years
                        for dropdown in [self.start_year_cb, self.end_year_cb]:
                            dropdown['values'] = [''] + self.years
                        
                        # Set default date range to full range
                        self.start_year.set(min_date[:4])
                        self.start_month.set(min_date[5:7])
                        self.start_day.set(min_date[8:10])
                        
                        self.end_year.set(max_date[:4])
                        self.end_month.set(max_date[5:7])
                        self.end_day.set(max_date[8:10])
                        
                        # Enable date range by default
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
            
            with open(self.source_path.get(), 'r', encoding='utf-8') as f:
                data = json.load(f)
                messages = data.get('messages', [])
                
                # Extract dates only from selected authors' messages
                dates = []
                for msg in messages:
                    if msg.get('from', '') in self.selected_authors:
                        text = msg.get('text', '')
                        if isinstance(text, list):
                            text = ''.join(item.get('text', '') if isinstance(item, dict) else str(item) for item in text)
                        if text.strip():  # Only consider messages with text content
                            date_str = msg.get('date', '').split('T')[0]  # YYYY-MM-DD
                            if date_str:
                                dates.append(date_str)
                
                if dates:
                    # Sort dates and get min/max
                    dates.sort()
                    min_date = dates[0]
                    max_date = dates[-1]
                    
                    # Set date range to available range
                    self.start_year.set(min_date[:4])
                    self.start_month.set(min_date[5:7])
                    self.start_day.set(min_date[8:10])
                    
                    self.end_year.set(max_date[:4])
                    self.end_month.set(max_date[5:7])
                    self.end_day.set(max_date[8:10])
                    
                    # Enable date range if it was disabled
                    self.use_date_range.set(True)
                    
                    # Update counters
                    self.update_all_counters()
    
        except Exception as e:
            print(f"Error resetting date range: {str(e)}")

    def calculate_total_chars(self, human_readable=False, with_reactions=False):
        """Calculate total characters based on current settings"""
        try:
            if not self.source_path.get():
                return 0
            
            with open(self.source_path.get(), 'r', encoding='utf-8') as f:
                data = json.load(f)
                messages = data.get('messages', [])
                
                # Filter messages by selected authors and text content
                filtered_messages = []
                for msg in messages:
                    if msg.get('from', '') in self.selected_authors:
                        text = msg.get('text', '')
                        if isinstance(text, list):
                            text = ''.join(item.get('text', '') if isinstance(item, dict) else str(item) for item in text)
                        if text.strip():
                            filtered_messages.append(msg)
                
                # Apply date range filter
                messages = self.filter_messages_by_date(filtered_messages)
                
                if not messages:
                    return 0
                
                # Calculate format size
                total_chars = 0
                
                for message in messages:
                    # Base XML structure
                    total_chars += len(f'<message id="{message.get("id", "")}" '
                                     f'date="{message.get("date", "")}" '
                                     f'sender="{message.get("from", "")}"')
                    
                    # Text content
                    text = message.get('text', '')
                    if isinstance(text, list):
                        text = ''.join(item.get('text', '') if isinstance(item, dict) else str(item) for item in text)
                    if text.strip():
                        total_chars += len('<text>') + len(text) + len('</text>')
                    
                    # Reply reference
                    if message.get('reply_to_message_id'):
                        total_chars += len(f' reply_to="{message["reply_to_message_id"]}"')
                    
                    total_chars += len('/>') if not text else len('</message>')
                    
                    # Reactions if enabled
                    if with_reactions and 'reactions' in message:
                        total_chars += len('<reactions>')
                        for reaction in message['reactions']:
                            total_chars += len('<reaction ') + \
                                         len(f'emoji="{reaction.get("emoji", "")}" ') + \
                                         len(f'count="{reaction.get("count", 0)}"') + \
                                         len('/>')
                        total_chars += len('</reactions>')
                
                # Add root element and XML declaration
                total_chars += len('<?xml version="1.0" encoding="utf-8"?><messages></messages>')
                
                # Add newlines and indentation if human readable
                if human_readable:
                    total_chars += len(messages) * 2  # Newlines for each message
                    if text:
                        total_chars += len(messages) * 2  # Indentation for text elements
                    if with_reactions:
                        reactions_count = sum(1 for m in messages if 'reactions' in m)
                        total_chars += reactions_count * 4  # Indentation for reactions
                
                return total_chars
                
        except Exception as e:
            print(f"Error calculating total chars: {str(e)}")
            return 0

    def calculate_reaction_chars(self):
        """Calculate characters used by reactions"""
        try:
            if not self.source_path.get():
                return 0
            
            with open(self.source_path.get(), 'r', encoding='utf-8') as f:
                data = json.load(f)
                messages = data.get('messages', [])
                
                # Filter messages
                filtered_messages = []
                for msg in messages:
                    if msg.get('from', '') in self.selected_authors:
                        text = msg.get('text', '')
                        if isinstance(text, list):
                            text = ''.join(item.get('text', '') if isinstance(item, dict) else str(item) for item in text)
                        if text.strip():
                            filtered_messages.append(msg)
                
                # Apply date range filter
                messages = self.filter_messages_by_date(filtered_messages)
                
                # Calculate reactions size
                reactions_chars = 0
                for message in messages:
                    if 'reactions' in message:
                        reactions_chars += len('<reactions>')
                        for reaction in message['reactions']:
                            reactions_chars += len('<reaction ') + \
                                            len(f'emoji="{reaction.get("emoji", "")}" ') + \
                                            len(f'count="{reaction.get("count", 0)}"') + \
                                            len('/>')
                        reactions_chars += len('</reactions>')
                
                return reactions_chars
                
        except Exception as e:
            print(f"Error calculating reaction chars: {str(e)}")
            return 0

# Modify main function
def main():
    gui = ConversionGUI()
    gui.run()

if __name__ == "__main__":
    main()     