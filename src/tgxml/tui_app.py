"""Textual TUI application for Telegram JSON -> XML conversion."""

from __future__ import annotations

import os
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from jsontoxml import (  # noqa: E402
    load_json_file,
    get_available_authors,
    get_date_range_from_messages,
)
from src.tgxml.cli_flow import build_conversion_payload, write_xml  # noqa: E402


class TgXmlTextualApp:
    """Wrapper that lazily imports Textual only when needed."""

    def __init__(self):
        try:
            from textual.app import App, ComposeResult
            from textual.binding import Binding
            from textual.containers import Horizontal, Vertical, Container
            from textual.screen import ModalScreen
            from textual.widgets import Header, Footer, Input, Checkbox, Button, Static, Label
            from rich.console import Group
            from rich.panel import Panel
            from rich.table import Table
            from rich.text import Text
        except ModuleNotFoundError as exc:
            raise RuntimeError("Textual is not installed") from exc

        self._App = App
        self._ComposeResult = ComposeResult
        self._Binding = Binding
        self._Horizontal = Horizontal
        self._Vertical = Vertical
        self._Container = Container
        self._ModalScreen = ModalScreen
        self._Header = Header
        self._Footer = Footer
        self._Input = Input
        self._Checkbox = Checkbox
        self._Button = Button
        self._Static = Static
        self._Label = Label
        self._Group = Group
        self._Panel = Panel
        self._Table = Table
        self._Text = Text

    def build(self):
        App = self._App
        ComposeResult = self._ComposeResult
        Binding = self._Binding
        Horizontal = self._Horizontal
        Vertical = self._Vertical
        Container = self._Container
        ModalScreen = self._ModalScreen
        Header = self._Header
        Footer = self._Footer
        Input = self._Input
        Checkbox = self._Checkbox
        Button = self._Button
        Static = self._Static
        Label = self._Label
        Group = self._Group
        Panel = self._Panel
        Table = self._Table
        Text = self._Text

        class HelpScreen(ModalScreen):
            CSS = """
            HelpScreen {
                align: center middle;
                background: $surface 70%;
            }
            #help-box {
                width: 72;
                height: auto;
                border: round #46b3ff;
                background: #0c0f14;
                padding: 1 2;
            }
            #help-title { text-style: bold; color: #8bd5ff; }
            """

            def compose(self) -> ComposeResult:
                with Container(id="help-box"):
                    yield Label("Hotkeys", id="help-title")
                    yield Static(
                        "Ctrl+R  Dry Run\n"
                        "Ctrl+E  Export\n"
                        "Ctrl+I  Inspect\n"
                        "Ctrl+Q  Quit\n"
                        "F1      Help\n"
                        "H       Go to Hub\n"
                        "Esc     Close help"
                    )
                    yield Button("Close", id="close_help", variant="primary")

            def on_button_pressed(self, event: Button.Pressed) -> None:
                if event.button.id == "close_help":
                    self.app.pop_screen()

            def on_key(self, event) -> None:
                if event.key == "escape":
                    self.app.pop_screen()

        class ConverterApp(App):
            TITLE = "Telegram JSON -> XML"
            SUB_TITLE = "Operator Console"
            BINDINGS = [
                Binding("ctrl+r", "run_dry", "Dry Run", show=True),
                Binding("ctrl+e", "run_export", "Export", show=True),
                Binding("ctrl+i", "run_inspect", "Inspect", show=True),
                Binding("f1", "show_help", "Help", show=True),
                Binding("h", "go_hub", "Hub", show=True),
                Binding("ctrl+q", "quit", "Quit", show=True),
            ]

            CSS = """
            Screen { layout: vertical; background: #090b10; color: #e6edf3; }
            Header { background: #111827; color: #8bd5ff; }
            Footer { background: #111827; color: #9ca3af; }

            .hidden { display: none; }

            #hub {
                height: 1fr;
                align: center middle;
                content-align: center middle;
                border: round #30363d;
                margin: 1 2;
                background: #0d1117;
            }
            #hub-title { color: #8bd5ff; text-style: bold; }
            #hub-subtitle { color: #9ca3af; margin-bottom: 1; }
            #hub-buttons { width: 42; height: auto; }
            #hub-buttons Button { width: 1fr; margin: 0 0 1 0; }

            #workspace { height: 1fr; }
            #main { height: 3fr; }
            #left {
                width: 3fr;
                padding: 1 2;
                border: round #30363d;
                background: #0b1020;
            }
            #right {
                width: 2fr;
                padding: 1 2;
                border: round #2f4f76;
                background: #0a1528;
            }
            #bottom {
                height: 2fr;
                padding: 1 2;
                border: round #245b75;
                background: #071420;
                margin: 1 0 0 0;
            }
            .row { height: auto; margin: 0 0 1 0; }
            .section-title { text-style: bold; color: #7dd3fc; margin: 1 0 0 0; }
            #summary { height: 1fr; overflow: auto; }
            #activity { height: 1fr; overflow: auto; }
            #actions { height: auto; margin-top: 1; }
            Button { margin-right: 1; }
            """

            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.activity = []

            def compose(self) -> ComposeResult:
                yield Header(show_clock=False)

                with Container(id="hub"):
                    yield Label("TGXML OPERATOR", id="hub-title")
                    yield Label("Fast, deterministic Telegram JSON -> XML", id="hub-subtitle")
                    with Vertical(id="hub-buttons"):
                        yield Button("Open Workspace", id="hub_open", variant="primary")
                        yield Button("Quick Dry Run", id="hub_quick_dry", variant="warning")
                        yield Button("Inspect Source", id="hub_inspect", variant="default")
                        yield Button("Quit", id="hub_quit", variant="error")

                with Container(id="workspace", classes="hidden"):
                    with Horizontal(id="main"):
                        with Vertical(id="left"):
                            yield Label("Sources (comma-separated paths)", classes="section-title")
                            yield Input(placeholder="exports/ChatExport_2024-12-27/result.json", id="sources")

                            yield Label("Output path (optional)", classes="section-title")
                            yield Input(placeholder="auto: chat_name_(range)/chat_name_(range).xml", id="output")

                            yield Label("Authors CSV (optional)", classes="section-title")
                            yield Input(placeholder="Alice,Bob", id="authors")

                            yield Label("Date range", classes="section-title")
                            with Horizontal(classes="row"):
                                yield Input(placeholder="start YYYY-MM-DD", id="start_date")
                                yield Input(placeholder="end YYYY-MM-DD", id="end_date")

                            with Horizontal(classes="row"):
                                yield Checkbox("Use date filter", value=True, id="use_date_filter")
                                yield Checkbox("Human readable", value=True, id="human_readable")
                                yield Checkbox("Include reactions", value=True, id="include_reactions")

                            with Horizontal(classes="row"):
                                yield Checkbox("Include service", value=False, id="include_service")
                                yield Checkbox("Media metadata", value=False, id="include_media")
                                yield Checkbox("Text entities", value=False, id="include_entities")

                            with Horizontal(classes="row"):
                                yield Checkbox("Anonymize", value=False, id="anonymize")
                                yield Checkbox("Validate input", value=True, id="validate_input")

                            with Horizontal(id="actions"):
                                yield Button("Inspect", id="inspect", variant="default")
                                yield Button("Dry Run", id="dry_run", variant="warning")
                                yield Button("Export", id="export", variant="success")
                                yield Button("Hub", id="go_hub", variant="default")
                                yield Button("Quit", id="quit", variant="error")

                        with Vertical(id="right"):
                            yield Label("Summary", classes="section-title")
                            yield Static("Ready", id="summary")

                    with Vertical(id="bottom"):
                        yield Label("Activity", classes="section-title")
                        yield Static("No actions yet", id="activity")

                yield Footer()

            def on_mount(self) -> None:
                default_source = "exports/ChatExport_2024-12-27/result.json"
                if os.path.exists(default_source):
                    self.query_one("#sources", Input).value = default_source
                self._push_activity("Application started")
                self._summary_ready()

            def _show_hub(self):
                self.query_one("#hub", Container).remove_class("hidden")
                self.query_one("#workspace", Container).add_class("hidden")
                self._push_activity("Switched to hub")

            def _show_workspace(self):
                self.query_one("#hub", Container).add_class("hidden")
                self.query_one("#workspace", Container).remove_class("hidden")
                self._push_activity("Switched to workspace")

            def _is_workspace_visible(self):
                return not self.query_one("#workspace", Container).has_class("hidden")

            def _push_activity(self, message: str):
                ts = datetime.now().strftime("%H:%M:%S")
                self.activity.append(f"[{ts}] {message}")
                self.activity = self.activity[-30:]
                self.query_one("#activity", Static).update("\n".join(self.activity))

            def _sources(self):
                raw = self.query_one("#sources", Input).value
                return [p.strip() for p in raw.replace("\n", ",").split(",") if p.strip()]

            def _authors(self):
                raw = self.query_one("#authors", Input).value
                return {a.strip() for a in raw.split(",") if a.strip()}

            def _set_summary(self, content):
                self.query_one("#summary", Static).update(content)

            def _summary_ready(self):
                self._set_summary(
                    Panel(
                        Text("Choose an action: Inspect, Dry Run, or Export", style="#9ca3af"),
                        title="Status",
                        border_style="#2f4f76",
                    )
                )

            def _summary_error(self, exc: Exception):
                self._set_summary(
                    Panel(
                        Text(str(exc), style="bold #fecaca"),
                        title="Error",
                        border_style="#ef4444",
                    )
                )

            def _summary_inspect(self, result):
                overview = Table.grid(expand=True)
                overview.add_column(style="#9ca3af")
                overview.add_column(style="#e6edf3")
                date_start, date_end = result["date_range"]
                date_text = f"{date_start} .. {date_end}" if date_start and date_end else "n/a"
                overview.add_row("Sources", str(len(result["sources"])))
                overview.add_row("Authors", str(result["authors_count"]))
                overview.add_row("Date range", date_text)
                overview.add_row("Output", result["estimated_output"])

                authors_table = Table(show_header=True, header_style="bold #7dd3fc", box=None)
                authors_table.add_column("Top authors", overflow="fold")
                for author in result["authors"][:12]:
                    authors_table.add_row(author)
                if not result["authors"]:
                    authors_table.add_row("No message authors found")

                self._set_summary(
                    Group(
                        Panel(overview, title="Inspect", border_style="#22d3ee"),
                        Panel(authors_table, title="Author sample", border_style="#2f4f76"),
                    )
                )

            def _summary_dry_run(self, payload):
                stats = payload["stats"]
                stats_table = Table(show_header=True, header_style="bold #7dd3fc", box=None)
                stats_table.add_column("Metric")
                stats_table.add_column("Value", justify="right")
                stats_table.add_row("Included", str(stats["included"]))
                stats_table.add_row("Excluded non-message", str(stats["excluded_non_message"]))
                stats_table.add_row("Excluded service", str(stats["excluded_service"]))
                stats_table.add_row("Excluded by author", str(stats["excluded_author"]))
                stats_table.add_row("Excluded empty text", str(stats["excluded_empty_text"]))
                stats_table.add_row("Excluded by date", str(stats["excluded_date"]))

                validation = payload["validation_issues"]
                validation_text = "\n".join(validation[:8]) if validation else "No validation issues"
                self._set_summary(
                    Group(
                        Panel(stats_table, title="Dry Run", border_style="#f59e0b"),
                        Panel(
                            Text(f"Output: {payload['output_path']}\n\n{validation_text}", style="#cbd5e1"),
                            title="Output & Validation",
                            border_style="#2f4f76",
                        ),
                    )
                )

            def _summary_export(self, payload):
                exported = payload["stats"]["included"]
                self._set_summary(
                    Panel(
                        Text(
                            f"Export completed\nMessages: {exported}\nOutput: {payload['output_path']}",
                            style="bold #bbf7d0",
                        ),
                        title="Success",
                        border_style="#22c55e",
                    )
                )

            def _collect_data(self):
                sources = self._sources()
                if not sources:
                    raise ValueError("Add at least one source path")

                output_path = self.query_one("#output", Input).value.strip()
                selected_authors = self._authors()
                start_date = self.query_one("#start_date", Input).value.strip()
                end_date = self.query_one("#end_date", Input).value.strip()

                use_date_filter = self.query_one("#use_date_filter", Checkbox).value
                human_readable = self.query_one("#human_readable", Checkbox).value
                include_reactions = self.query_one("#include_reactions", Checkbox).value
                include_service = self.query_one("#include_service", Checkbox).value
                include_media = self.query_one("#include_media", Checkbox).value
                include_entities = self.query_one("#include_entities", Checkbox).value
                anonymize = self.query_one("#anonymize", Checkbox).value
                validate_input = self.query_one("#validate_input", Checkbox).value

                prepared = build_conversion_payload(
                    source_paths=sources,
                    output_path=output_path or None,
                    output_dir=None,
                    selected_authors=selected_authors,
                    start_date=start_date,
                    end_date=end_date,
                    use_date_range=use_date_filter,
                    include_service=include_service,
                    include_media_meta=include_media,
                    include_entities=include_entities,
                    include_reactions=include_reactions,
                    human_readable=human_readable,
                    anonymize=anonymize,
                    validate_input=validate_input,
                )
                return {
                    "sources": prepared["source_paths"],
                    "output_path": prepared["output_path"],
                    "include_reactions": include_reactions,
                    "include_media": include_media,
                    "include_entities": include_entities,
                    "human_readable": human_readable,
                    "validation_issues": prepared["validation_issues"],
                    "stats": prepared["filter_stats"],
                    "conversion_payload": prepared,
                }

            def _do_inspect(self):
                payload = self._collect_data()
                first = load_json_file(payload["sources"][0])
                authors = get_available_authors(first.get("messages", []))
                min_date, max_date = get_date_range_from_messages(first.get("messages", []))
                result = {
                    "sources": payload["sources"],
                    "authors_count": len(authors),
                    "authors": authors[:50],
                    "date_range": [min_date, max_date],
                    "estimated_output": payload["output_path"],
                }
                self._summary_inspect(result)
                self._push_activity("Inspect completed")

            def _do_dry_run(self):
                payload = self._collect_data()
                result = {
                    "output_path": payload["output_path"],
                    "included_messages": payload["stats"]["included"],
                    "stats": payload["stats"],
                    "validation_issues": payload["validation_issues"],
                }
                self._summary_dry_run(result)
                self._push_activity("Dry run completed")

            def _do_export(self):
                payload = self._collect_data()
                write_xml(payload["conversion_payload"])
                self._summary_export(payload)
                self._push_activity(f"Export completed -> {payload['output_path']}")

            def _run_workspace_action(self, action, label: str):
                if not self._is_workspace_visible():
                    self._show_workspace()
                try:
                    action()
                except Exception as exc:
                    self._summary_error(exc)
                    self._push_activity(f"{label} failed: {exc}")

            def on_button_pressed(self, event: Button.Pressed) -> None:
                button_id = event.button.id
                if button_id == "quit" or button_id == "hub_quit":
                    self.exit()
                    return
                if button_id == "go_hub":
                    self._show_hub()
                    return
                if button_id == "hub_open":
                    self._show_workspace()
                    return
                if button_id == "hub_quick_dry":
                    self._run_workspace_action(self._do_dry_run, "Dry run")
                    return
                if button_id == "hub_inspect":
                    self._run_workspace_action(self._do_inspect, "Inspect")
                    return
                if button_id == "inspect":
                    self._run_workspace_action(self._do_inspect, "Inspect")
                    return
                if button_id == "dry_run":
                    self._run_workspace_action(self._do_dry_run, "Dry run")
                    return
                if button_id == "export":
                    self._run_workspace_action(self._do_export, "Export")
                    return

            def action_run_dry(self):
                self._run_workspace_action(self._do_dry_run, "Dry run")

            def action_run_export(self):
                self._run_workspace_action(self._do_export, "Export")

            def action_run_inspect(self):
                self._run_workspace_action(self._do_inspect, "Inspect")

            def action_show_help(self):
                self.push_screen(HelpScreen())

            def action_go_hub(self):
                self._show_hub()

        return ConverterApp


def run_textual_tui():
    app = TgXmlTextualApp().build()()
    app.run()
