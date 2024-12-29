# JSON to XML Telegram Chat Converter

A GUI application to convert Telegram chat JSON exports to XML format with filtering options.

## Prerequisites

- Python 3.7 or higher
- Tkinter (usually comes with Python)

## Installation

1. First, ensure you have Python installed:
```bash
python3 --version
```

2. If Python is not installed, install it using Homebrew:
```bash
brew install python
```

3. Verify Tkinter is installed (it usually comes with Python):
```python
python3 -c "import tkinter; tkinter._test()"
```

If you see a test window appear, Tkinter is installed correctly.

4. If Tkinter is missing, you can install it with:
```bash
brew install python-tk
```

## Running the Application

There are several ways to run the application:

### 1. Double-Click Method (Easiest)
Simply double-click the `Run Converter.command` file in Finder.

### 2. Shell Script
Double-click or run the `run.sh` script.

### 3. Terminal Method
1. Open Terminal and navigate to the project directory:
```bash
cd path/to/json-to-xml-tgchat
```

2. Run the script:
```bash
python3 jsontoxml.py
```

## Usage

1. Click "Select JSON file" to choose your Telegram chat export file
2. The output location will automatically be set to the source file directory
3. Adjust export options as needed:
   - Enable/disable human-readable format
   - Include/exclude reactions
   - Filter by date range
   - Select specific authors (for private chats)
4. Click "CONVERT" to process the file
5. The converted XML file will be saved in the selected output directory

## Troubleshooting

If you encounter any issues:

1. Verify Python installation:
```bash
which python3
```

2. Check Tkinter installation:
```bash
python3 -c "import tkinter; print(tkinter.TkVersion)"
```

3. If you see permission errors, you might need to run:
```bash
chmod +x jsontoxml.py
chmod +x run.sh
chmod +x "Run Converter.command"
```

4. If the double-click methods don't work:
   - Right-click the file
   - Select "Open With" → "Terminal"
   - Click "Open" if prompted about security

For additional help, click the "HELP" button in the application interface.


