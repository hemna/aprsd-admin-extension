"""Terminal UI for APRSD admin interface using textual library."""

import importlib.metadata as imp
import io
import json
import logging
from datetime import datetime

import aprsd
import click
from aprsd import cli_helper, conf
from aprsd import threads as aprsd_threads
from aprsd.packets.core import AckPacket, RejectPacket
from aprsd.threads import service
from aprsd.threads import stats as stats_threads
from oslo_config import cfg, generator
from rich.console import Group, RenderableType
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text
from textual.app import App, ComposeResult
from textual.containers import Container, ScrollableContainer
from textual.widgets import (
    DataTable,
    Footer,
    Header,
    Static,
    TabbedContent,
    TabPane,
)

from aprsd_admin_extension import cmds
from aprsd_admin_extension.cmds.ui_common import (
    ErrorDialog,
    fetch_config_from_url,
    fetch_stats_from_url,
)
from aprsd_admin_extension.threads import log_monitor

CONF = cfg.CONF
LOG = logging.getLogger("APRSD")


class StatsTab(ScrollableContainer):
    """Stats tab showing APRSD statistics."""

    def __init__(self, aprsd_url: str = None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.aprsd_url = aprsd_url
        self.stats_store = stats_threads.StatsStore() if not aprsd_url else None

    def compose(self) -> ComposeResult:
        yield Static(id="stats_content")

    def on_mount(self) -> None:
        self.refresh_stats()
        self.set_interval(5.0, self.refresh_stats)

    def refresh_stats(self) -> None:
        try:
            if self.aprsd_url:
                stats = fetch_stats_from_url(self.aprsd_url)
            else:
                self.stats_store.load()
                stats = self.stats_store.data
            content = self._format_stats(stats)
            self.query_one("#stats_content", Static).update(content)
        except Exception as e:
            LOG.error(f"Error refreshing stats: {e}")
            # Show error in the stats tab
            error_msg = Panel(
                Text(
                    f"Error fetching stats from URL:\n\n{self.aprsd_url}\n\n{str(e)}",
                    style="bold red",
                ),
                title="[bold red]Connection Error[/bold red]",
                border_style="red",
            )
            self.query_one("#stats_content", Static).update(error_msg)

    def _format_stats(self, stats: dict) -> RenderableType:
        """Format stats as a rich renderable with enhanced colorization and panels."""
        output = []

        # APRSD Stats
        aprsd_stats = stats.get("APRSDStats", {})
        if aprsd_stats:
            table = Table(show_header=True, box=None)
            table.add_column("Key", style="bold cyan", header_style="bold cyan")
            table.add_column("Value", style="bold green", header_style="bold green")
            for key, value in sorted(aprsd_stats.items()):
                table.add_row(
                    Text(str(key), style="cyan"), Text(str(value), style="green")
                )
            panel = Panel(
                table,
                title="[bold cyan]APRSD Stats[/bold cyan]",
                border_style="cyan",
                padding=(1, 2),
            )
            output.append(panel)

        # Threads
        threads_data = stats.get("APRSDThreadList", {})
        if threads_data and isinstance(threads_data, dict):
            thread_count = len(threads_data)
            table = Table(show_header=True, box=None)
            table.add_column("Name", style="bold cyan", header_style="bold cyan")
            table.add_column("Class", style="yellow", header_style="bold yellow")
            table.add_column("Alive", style="bold green", header_style="bold green")
            table.add_column("Loop Count", style="magenta", header_style="bold magenta")
            for name, value in sorted(threads_data.items()):
                if isinstance(value, dict):
                    alive = value.get("alive", False)
                    alive_str = (
                        Text("✓", style="bold green")
                        if alive
                        else Text("✗", style="bold red")
                    )
                    table.add_row(
                        Text(name, style="cyan"),
                        Text(value.get("class", "N/A"), style="yellow"),
                        alive_str,
                        Text(str(value.get("loop_count", 0)), style="magenta"),
                    )
            panel = Panel(
                table,
                title=f"[bold yellow]Threads[/bold yellow] [dim]({thread_count})[/dim]",
                border_style="yellow",
                padding=(1, 2),
            )
            output.append(panel)

        # Plugins
        plugins_data = stats.get("PluginManager", {})
        if plugins_data and isinstance(plugins_data, dict):
            plugin_count = len(plugins_data)
            table = Table(show_header=True, box=None)
            table.add_column("Name", style="bold cyan", header_style="bold cyan")
            table.add_column("Enabled", style="bold green", header_style="bold green")
            table.add_column("Version", style="yellow", header_style="bold yellow")
            table.add_column("TX", style="bold magenta", header_style="bold magenta")
            table.add_column("RX", style="bold blue", header_style="bold blue")
            for name, value in sorted(plugins_data.items()):
                if isinstance(value, dict):
                    enabled = value.get("enabled", False)
                    enabled_str = (
                        Text("✓", style="bold green")
                        if enabled
                        else Text("✗", style="bold red")
                    )
                    table.add_row(
                        Text(name, style="cyan"),
                        enabled_str,
                        Text(value.get("version", "N/A"), style="yellow"),
                        Text(str(value.get("tx", 0)), style="magenta"),
                        Text(str(value.get("rx", 0)), style="blue"),
                    )
            panel = Panel(
                table,
                title=f"[bold blue]Plugins[/bold blue] [dim]({plugin_count})[/dim]",
                border_style="blue",
                padding=(1, 2),
            )
            output.append(panel)

        # Packet List
        packet_list = stats.get("PacketList", {})
        if packet_list:
            table = Table(show_header=True, box=None)
            table.add_column("Type", style="bold cyan", header_style="bold cyan")
            table.add_column("RX", style="bold green", header_style="bold green")
            table.add_column("TX", style="bold yellow", header_style="bold yellow")

            # Total row with special styling
            total_rx = packet_list.get("rx", 0)
            total_tx = packet_list.get("tx", 0)
            table.add_row(
                Text("Total", style="bold white"),
                Text(str(total_rx), style="bold green"),
                Text(str(total_tx), style="bold yellow"),
            )

            packets = packet_list.get("packets", {})
            if isinstance(packets, dict):
                for packet_type, data in sorted(packets.items()):
                    if isinstance(data, dict):
                        rx = data.get("rx", 0)
                        tx = data.get("tx", 0)
                    else:
                        rx = tx = 0
                    table.add_row(
                        Text(str(packet_type), style="cyan"),
                        Text(str(rx), style="green"),
                        Text(str(tx), style="yellow"),
                    )
            panel = Panel(
                table,
                title="[bold green]Packet Statistics[/bold green]",
                border_style="green",
                padding=(1, 2),
            )
            output.append(panel)

        if not output:
            return Panel(
                Text("No stats data available", style="dim"),
                title="[dim]Stats[/dim]",
                border_style="dim",
            )

        # Return Rich Group to preserve colors and spacing
        return Group(*output)


class ConfigTab(ScrollableContainer):
    """Configuration tab showing APRSD configuration."""

    def __init__(self, aprsd_url: str = None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.aprsd_url = aprsd_url

    def compose(self) -> ComposeResult:
        yield Static(id="config_content")

    def on_mount(self) -> None:
        self.refresh_config()

    def _get_namespaces(self):
        """Get namespaces for oslo config generator (same as wsgi.py _get_namespaces)."""
        args = []
        all_entries = imp.entry_points()
        selected = []
        if "oslo.config.opts" in all_entries:
            for x in all_entries["oslo.config.opts"]:
                if x.group == "oslo.config.opts":
                    selected.append(x)
        for entry in selected:
            if "aprsd" in entry.name:
                args.append("--namespace")
                args.append(entry.name)
        return args

    def _generate_oslo(self):
        """Generate oslo config (same code as wsgi.py generate_oslo)."""
        CONF.namespace = self._get_namespaces()
        string_out = io.StringIO()
        generator.generate(CONF, string_out)
        return string_out.getvalue()

    def refresh_config(self) -> None:
        try:
            if self.aprsd_url:
                # Fetch config from remote URL
                config_content = fetch_config_from_url(self.aprsd_url)
            else:
                # Use same approach as wsgi.py generate_oslo()
                # Save and restore CONF.namespace to avoid conflicts
                original_namespace = getattr(CONF, "namespace", None)
                try:
                    config_content = self._generate_oslo()
                finally:
                    # Restore original namespace if it existed
                    if original_namespace is not None:
                        CONF.namespace = original_namespace
                    elif hasattr(CONF, "namespace"):
                        # Try to clear it if it was set by _generate_oslo
                        try:
                            delattr(CONF, "namespace")
                        except (AttributeError, TypeError):
                            pass

            # Display as config file format (same as generate_oslo produces)
            syntax = Syntax(config_content, "ini", theme="monokai", line_numbers=True)
            self.query_one("#config_content", Static).update(syntax)
        except Exception as e:
            LOG.error(f"Error refreshing config: {e}", exc_info=True)
            # Fallback to JSON format if generator fails (only for local config)
            if not self.aprsd_url:
                try:
                    entries = conf.conf_to_dict()
                    config_json = json.dumps(
                        entries,
                        indent=4,
                        sort_keys=True,
                        default=str,
                    )
                    syntax = Syntax(
                        config_json, "json", theme="monokai", line_numbers=True
                    )
                    self.query_one("#config_content", Static).update(syntax)
                except Exception as e2:
                    LOG.error(f"Error in fallback config display: {e2}", exc_info=True)
                    self.query_one("#config_content", Static).update(
                        f"Error loading config: {e}\nFallback also failed: {e2}"
                    )
            else:
                # For remote URL, show error message
                error_msg = Panel(
                    Text(
                        f"Error fetching config from URL:\n\n{self.aprsd_url}\n\n{str(e)}",
                        style="bold red",
                    ),
                    title="[bold red]Connection Error[/bold red]",
                    border_style="red",
                )
                self.query_one("#config_content", Static).update(error_msg)


class PluginsTab(ScrollableContainer):
    """Plugins tab showing plugin information."""

    def __init__(self, aprsd_url: str = None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.aprsd_url = aprsd_url
        self.stats_store = stats_threads.StatsStore() if not aprsd_url else None

    def compose(self) -> ComposeResult:
        yield Static(id="plugins_content")

    def on_mount(self) -> None:
        self.refresh_plugins()
        self.set_interval(10.0, self.refresh_plugins)

    def refresh_plugins(self) -> None:
        try:
            if self.aprsd_url:
                stats = fetch_stats_from_url(self.aprsd_url)
            else:
                self.stats_store.load()
                stats = self.stats_store.data
            content = self._format_plugins(stats)
            self.query_one("#plugins_content", Static).update(content)
        except Exception as e:
            LOG.error(f"Error refreshing plugins: {e}")
            self.query_one("#plugins_content", Static).update(
                Panel(
                    Text(f"Error loading plugins: {e}", style="bold red"),
                    title="[bold red]Error[/bold red]",
                    border_style="red",
                )
            )

    def _format_plugins(self, stats: dict) -> RenderableType:
        """Format plugins as a rich renderable with enhanced colorization and panels."""
        plugins_data = stats.get("PluginManager", {})

        if not isinstance(plugins_data, dict) or not plugins_data:
            return Panel(
                Text("No plugins data available", style="dim"),
                title="[dim]Plugins[/dim]",
                border_style="dim",
            )

        plugin_count = len(plugins_data)
        table = Table(show_header=True, box=None)
        table.add_column("Name", style="bold cyan", header_style="bold cyan")
        table.add_column("Enabled", style="bold green", header_style="bold green")
        table.add_column("Version", style="yellow", header_style="bold yellow")
        table.add_column("TX", style="bold magenta", header_style="bold magenta")
        table.add_column("RX", style="bold blue", header_style="bold blue")

        for name, value in sorted(plugins_data.items()):
            if isinstance(value, dict):
                enabled = value.get("enabled", False)
                enabled_str = (
                    Text("✓", style="bold green")
                    if enabled
                    else Text("✗", style="bold red")
                )
                table.add_row(
                    Text(name, style="cyan"),
                    enabled_str,
                    Text(value.get("version", "N/A"), style="yellow"),
                    Text(str(value.get("tx", 0)), style="magenta"),
                    Text(str(value.get("rx", 0)), style="blue"),
                )

        panel = Panel(
            table,
            title=f"[bold blue]Plugins[/bold blue] [dim]({plugin_count})[/dim]",
            border_style="blue",
            padding=(1, 2),
        )

        return panel


class MessagesTab(Container):
    """Messages tab showing packet tracking from StatsStore."""

    def __init__(self, aprsd_url: str = None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.aprsd_url = aprsd_url
        self.stats_store = stats_threads.StatsStore() if not aprsd_url else None

    def compose(self) -> ComposeResult:
        yield DataTable(id="messages_table", zebra_stripes=True)

    def on_mount(self) -> None:
        # Don't add column here - let refresh_messages handle it with count
        self.refresh_messages()
        self.set_interval(5.0, self.refresh_messages)

    def _format_packet_compact(self, pkt) -> Text:
        """Format a packet in compact format like log.py and web UI with Rich colors."""
        # Color constants matching log.py
        FROM_COLOR = "#C70039"
        TO_COLOR = "#D033FF"
        TX_COLOR = "red"
        RX_COLOR = "#1AA730"
        PACKET_COLOR = "cyan"
        MESSAGE_COLOR = "light_yellow"

        # Determine if packet is TX or RX
        from_call = getattr(pkt, "from_call", None) or ""
        our_callsign = CONF.callsign or ""
        is_tx = from_call == our_callsign

        # Get packet type name
        packet_type = pkt.__class__.__name__

        # Build Rich Text object
        text = Text()

        # Add TX/RX indicator
        if is_tx:
            text.append("TX↑", style=TX_COLOR)
        else:
            text.append("RX↓", style=RX_COLOR)

        # Add packet type (cyan)
        text.append(" ", style="default")
        text.append(packet_type, style=PACKET_COLOR)

        # Add message number
        msg_no = getattr(pkt, "msgNo", None)
        if msg_no:
            text.append(f":{msg_no}", style=PACKET_COLOR)

        # Add send count for TX packets
        if is_tx:
            if isinstance(pkt, AckPacket):
                max_send_count = CONF.default_ack_send_count
            else:
                max_send_count = CONF.default_packet_send_count
            send_count = getattr(pkt, "send_count", 0) + 1
            text.append(f" ({send_count} of {max_send_count})", style="default")

        # Add from_call → path → to_call
        to_call = getattr(pkt, "to_call", None) or ""
        text.append(" ", style="default")
        text.append(from_call, style=FROM_COLOR)
        text.append(" →", style=TX_COLOR if is_tx else RX_COLOR)

        # Add path if available
        path = getattr(pkt, "path", None)
        if path and isinstance(path, (list, tuple)) and len(path) > 0:
            path_str = "→".join(str(p) for p in path)
            text.append(f" {path_str}", style="default")
            text.append(" →", style=TX_COLOR if is_tx else RX_COLOR)

        text.append(" ", style="default")
        text.append(to_call, style=TO_COLOR)

        # Add message if available (not for Ack or Reject packets)
        if not isinstance(pkt, AckPacket) and not isinstance(pkt, RejectPacket):
            human_info = getattr(pkt, "human_info", None)
            if human_info:
                text.append(" : ", style="default")
                text.append(human_info, style=f"bold {MESSAGE_COLOR}")

        return text

    def refresh_messages(self) -> None:
        try:
            table = self.query_one("#messages_table", DataTable)

            # Load stats from disk (written by the running aprsd process) or URL
            if self.aprsd_url:
                stats = fetch_stats_from_url(self.aprsd_url)
            else:
                self.stats_store.load()
                stats = self.stats_store.data

            # Get PacketList which contains the actual packet objects
            packet_list_stats = stats.get("PacketList", {})
            packets_data = (
                packet_list_stats.get("packets", {})
                if isinstance(packet_list_stats, dict)
                else {}
            )

            # Determine packet count first
            packet_count = 0
            packet_list = []

            if packets_data:
                # Handle both list and dict cases
                # When packet_list_stats_maxlen >= 0, packets is a list
                # Otherwise it's a dict
                if isinstance(packets_data, list):
                    packet_items = enumerate(packets_data)
                else:
                    packet_items = packets_data.items()

                # Handle both packet objects and dicts
                for packet_id, pkt_data in packet_items:
                    # Check if pkt_data is already a packet object or a dict
                    if isinstance(pkt_data, dict):
                        # Convert dict to object-like structure
                        class PacketObj:
                            def __init__(self, data):
                                # Copy all attributes from the dict
                                for key, value in data.items():
                                    setattr(self, key, value)
                                # Ensure __class__.__name__ is set for packet type
                                self._type = data.get(
                                    "_type", data.get("format", "Packet")
                                )

                        pkt = PacketObj(pkt_data)
                        pkt.__class__.__name__ = pkt._type
                    else:
                        # Already a packet object, use it directly
                        pkt = pkt_data

                    # Get timestamp for sorting
                    timestamp = getattr(pkt, "timestamp", None)
                    if timestamp is None:
                        # Fallback to 0 if no timestamp
                        timestamp = 0

                    packet_list.append((timestamp, pkt))

                packet_count = len(packet_list)

                # Sort by timestamp (oldest first, so newest appears at bottom)
                # This matches the natural order where newer packets are added later
                packet_list.sort(key=lambda x: x[0])

            # Clear rows (clear() removes rows but keeps columns)
            table.clear()

            # Update or add column with packet count
            # Check if columns exist - columns is a dict-like object
            column_keys = list(table.columns.keys())
            if len(column_keys) > 0:
                # Column exists, update its label
                first_key = column_keys[0]
                table.columns[first_key].label = f"Packet ({packet_count})"
            else:
                # No column exists, add it
                table.add_columns(f"Packet ({packet_count})")

            # Add rows to table in sorted order
            for timestamp, pkt in packet_list:
                # Format packet in compact format
                compact_format = self._format_packet_compact(pkt)
                table.add_row(compact_format)
        except Exception as e:
            LOG.error(f"Error refreshing messages: {e}")
            import traceback

            LOG.error(traceback.format_exc())
            # Add error message to table so user knows something went wrong
            try:
                table = self.query_one("#messages_table", DataTable)
                table.clear()
                table.add_columns("Packet (Error)")
                table.add_row(Text(f"Error: {e}", style="bold red"))
            except Exception:
                pass


class SeenListTab(ScrollableContainer):
    """Seen List tab showing callsigns that have been seen."""

    def __init__(self, aprsd_url: str = None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.aprsd_url = aprsd_url
        self.stats_store = stats_threads.StatsStore() if not aprsd_url else None

    def compose(self) -> ComposeResult:
        yield Static(id="seenlist_content")

    def on_mount(self) -> None:
        self.refresh_seenlist()
        self.set_interval(5.0, self.refresh_seenlist)

    def refresh_seenlist(self) -> None:
        try:
            if self.aprsd_url:
                stats = fetch_stats_from_url(self.aprsd_url)
            else:
                self.stats_store.load()
                stats = self.stats_store.data
            content = self._format_seenlist(stats)
            self.query_one("#seenlist_content", Static).update(content)
        except Exception as e:
            LOG.error(f"Error refreshing seen list: {e}")

    def _format_seenlist(self, stats: dict) -> RenderableType:
        """Format seen list as a rich renderable with panels."""
        seen_data = stats.get("SeenList", {})

        if not seen_data or not isinstance(seen_data, dict):
            return Panel(
                Text("No seen list data available", style="dim"),
                title="[dim]Seen List[/dim]",
                border_style="dim",
            )

        # Create table
        table = Table(show_header=True, box=None)
        table.add_column("Callsign", style="bold cyan", header_style="bold cyan")
        table.add_column("Packet Count", style="bold green", header_style="bold green")
        table.add_column("Last Seen", style="bold yellow", header_style="bold yellow")

        # Sort by packet count (descending) then by callsign
        sorted_items = sorted(
            seen_data.items(),
            key=lambda x: (x[1].get("count", 0) if isinstance(x[1], dict) else 0, x[0]),
            reverse=True,
        )

        for callsign, data in sorted_items:
            if isinstance(data, dict):
                count = data.get("count", 0)
                last_seen = data.get("last", None)

                # Format last seen time
                if last_seen:
                    if isinstance(last_seen, str):
                        # Already serialized as ISO format string
                        try:
                            dt = datetime.fromisoformat(
                                last_seen.replace("Z", "+00:00")
                            )
                            last_seen_str = dt.strftime("%Y-%m-%d %H:%M:%S")
                        except Exception:
                            last_seen_str = str(last_seen)
                    else:
                        last_seen_str = str(last_seen)
                else:
                    last_seen_str = "Never"

                table.add_row(
                    Text(callsign, style="cyan"),
                    Text(str(count), style="green"),
                    Text(last_seen_str, style="yellow"),
                )

        panel = Panel(
            table,
            title=f"[bold magenta]Seen List[/bold magenta] [dim]({len(seen_data)} callsigns)[/dim]",
            border_style="magenta",
            padding=(1, 2),
        )

        return panel


class WatchListTab(ScrollableContainer):
    """Watch List tab showing callsigns being watched."""

    def __init__(self, aprsd_url: str = None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.aprsd_url = aprsd_url
        self.stats_store = stats_threads.StatsStore() if not aprsd_url else None

    def compose(self) -> ComposeResult:
        yield Static(id="watchlist_content")

    def on_mount(self) -> None:
        self.refresh_watchlist()
        self.set_interval(5.0, self.refresh_watchlist)

    def refresh_watchlist(self) -> None:
        try:
            if self.aprsd_url:
                stats = fetch_stats_from_url(self.aprsd_url)
            else:
                self.stats_store.load()
                stats = self.stats_store.data
            content = self._format_watchlist(stats)
            self.query_one("#watchlist_content", Static).update(content)
        except Exception as e:
            LOG.error(f"Error refreshing watch list: {e}")

    def _format_watchlist(self, stats: dict) -> RenderableType:
        """Format watch list as a rich renderable with panels."""
        watch_data = stats.get("WatchList", {})

        if not watch_data or not isinstance(watch_data, dict):
            return Panel(
                Text("No watch list data available", style="dim"),
                title="[dim]Watch List[/dim]",
                border_style="dim",
            )

        # Create table
        table = Table(show_header=True, box=None)
        table.add_column("Callsign", style="bold cyan", header_style="bold cyan")
        table.add_column("Last Seen", style="bold yellow", header_style="bold yellow")
        table.add_column("Age", style="bold blue", header_style="bold blue")
        table.add_column("Status", style="bold green", header_style="bold green")

        # Sort by callsign
        sorted_items = sorted(watch_data.items())

        for callsign, data in sorted_items:
            if isinstance(data, dict):
                last_seen = data.get("last", None)
                age = data.get("age", None)
                was_old = data.get("was_old_before_update", False)

                # Format last seen time
                if last_seen:
                    if isinstance(last_seen, str):
                        # Already serialized as ISO format string
                        try:
                            dt = datetime.fromisoformat(
                                last_seen.replace("Z", "+00:00")
                            )
                            last_seen_str = dt.strftime("%Y-%m-%d %H:%M:%S")
                        except Exception:
                            last_seen_str = str(last_seen)
                    else:
                        last_seen_str = str(last_seen)
                else:
                    last_seen_str = "Never"

                # Format age
                age_str = str(age) if age else "N/A"

                # Status based on was_old_before_update
                if was_old:
                    status = Text("Old", style="bold red")
                else:
                    status = Text("Active", style="bold green")

                table.add_row(
                    Text(callsign, style="cyan"),
                    Text(last_seen_str, style="yellow"),
                    Text(age_str, style="blue"),
                    status,
                )

        panel = Panel(
            table,
            title=f"[bold bright_cyan]Watch List[/bold bright_cyan] [dim]({len(watch_data)} callsigns)[/dim]",
            border_style="bright_cyan",
            padding=(1, 2),
        )

        return panel


class APRSDAdminApp(App):
    """A Textual application for APRSD admin interface."""

    CSS = """
    Screen {
        layout: vertical;
    }
    """

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("r", "refresh", "Refresh"),
    ]

    def __init__(self, aprsd_url: str = None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.server_threads = None
        self.aprsd_url = aprsd_url
        self.url_error_shown = False

    def compose(self) -> ComposeResult:
        """Create child widgets for the app."""
        yield Header(show_clock=True)
        yield TabbedContent(id="main_tabs")
        yield Footer()

    def on_mount(self) -> None:
        """Called when app starts."""
        # Test URL connection if provided
        if self.aprsd_url:
            try:
                fetch_stats_from_url(self.aprsd_url)
            except Exception as e:
                self._show_url_error(str(e))
                return

        # Add all tabs in the specified order
        tabbed_content = self.query_one("#main_tabs", TabbedContent)
        tabbed_content.add_pane(
            TabPane("Stats", StatsTab(aprsd_url=self.aprsd_url), id="stats_tab")
        )
        tabbed_content.add_pane(
            TabPane(
                "Messages", MessagesTab(aprsd_url=self.aprsd_url), id="messages_tab"
            )
        )
        tabbed_content.add_pane(
            TabPane(
                "Seen List", SeenListTab(aprsd_url=self.aprsd_url), id="seenlist_tab"
            )
        )
        tabbed_content.add_pane(
            TabPane(
                "Watch List", WatchListTab(aprsd_url=self.aprsd_url), id="watchlist_tab"
            )
        )
        tabbed_content.add_pane(
            TabPane("Plugins", PluginsTab(aprsd_url=self.aprsd_url), id="plugins_tab")
        )
        tabbed_content.add_pane(
            TabPane("Config", ConfigTab(aprsd_url=self.aprsd_url), id="config_tab")
        )
        tabbed_content.active = "stats_tab"

        # Start log monitor thread if web is enabled
        if CONF.aprsd_admin_extension.web_enabled:
            LOG.info("Starting LogMonitorThread")
            self.server_threads = service.ServiceThreads()
            self.server_threads.register(log_monitor.LogMonitorThread())

    def _show_url_error(self, error_message: str) -> None:
        """Show error dialog for URL fetch failure."""
        if self.url_error_shown:
            return
        self.url_error_shown = True

        # Create error message
        message = f"Failed to fetch stats from URL:\n\n{self.aprsd_url}\n\nError: {error_message}\n\nPlease check the URL and try again."
        dialog = ErrorDialog(message, title="URL Connection Error")

        # Mount as a screen overlay
        from textual.screen import Screen

        error_screen = Screen()
        error_screen.mount(dialog)
        self.push_screen(error_screen)

    def action_refresh(self) -> None:
        """Action to refresh all tabs."""
        # Trigger refresh on current tab
        pass

    def action_quit(self) -> None:
        """Action to quit the application."""
        # Stop all APRSD threads
        aprsd_threads.APRSDThreadList().stop_all()
        self.exit()


@cmds.admin.command()
@cli_helper.add_options(cli_helper.common_options)
@click.option(
    "--url",
    "aprsd_url",
    default=None,
    help="URL to fetch stats and config from (e.g., http://localhost:8080). If not provided, stats are loaded from local StatsStore.",
)
@click.pass_context
@cli_helper.process_standard_options
def admin_ui(ctx, aprsd_url):
    """Display APRSD admin interface in a terminal UI."""
    LOG.info(f"APRSD Admin UI started version: {aprsd.__version__}")
    if aprsd_url:
        LOG.info(f"Fetching stats and config from remote URL: {aprsd_url}")

    app = APRSDAdminApp(aprsd_url=aprsd_url)
    app.run()
