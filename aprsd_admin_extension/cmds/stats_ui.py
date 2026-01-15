"""Terminal UI for displaying APRSD stats using textual library."""

import logging
import time

import aprsd
import click
from aprsd import cli_helper
from aprsd.threads.stats import StatsStore
from oslo_config import cfg
from rich.console import RenderableType
from rich.table import Table
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Footer, Header, Static

from aprsd_admin_extension import cmds
from aprsd_admin_extension.cmds.ui_common import (
    ErrorDialog,
    OverviewHeader,
    fetch_stats_from_url,
)

CONF = cfg.CONF
LOG = logging.getLogger("APRSD")


class StatsPanel(Static):
    """A panel widget that displays stats in a table format."""

    def __init__(self, title: str, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.title = title
        self.stats_data = {}

    def update_stats(self, stats: dict):
        """Update the stats data and refresh the display."""
        self.stats_data = stats
        self.refresh()

    def render(self) -> RenderableType:
        """Render the stats as a rich table."""
        if not self.stats_data:
            return f"{self.title}\n\nNo data available"

        table = Table(title=self.title, show_header=True, box=None)
        if isinstance(self.stats_data, dict):
            # Determine if it's a key-value table or a list of rows
            if all(
                isinstance(v, (str, int, float, bool)) for v in self.stats_data.values()
            ):
                # Simple key-value table
                table.add_column("Key", style="cyan")
                table.add_column("Value", style="green")
                for key, value in sorted(self.stats_data.items()):
                    table.add_row(str(key), str(value))
            else:
                # Complex nested structure - show keys
                table.add_column("Key", style="cyan")
                table.add_column("Details", style="green")
                for key, value in sorted(self.stats_data.items()):
                    if isinstance(value, dict):
                        details = f"{len(value)} items"
                    else:
                        details = str(value)
                    table.add_row(str(key), details)
        else:
            table.add_column("Value", style="green")
            table.add_row(str(self.stats_data))

        return table


class ThreadsPanel(Static):
    """A panel widget that displays thread information."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.threads_data = {}

    def update_stats(self, stats: dict):
        """Update the threads data and refresh the display."""
        threads = stats.get("APRSDThreadList", {})
        # Ensure it's a dict, not a list
        if isinstance(threads, dict):
            self.threads_data = threads
        else:
            self.threads_data = {}
        self.refresh()

    def render(self) -> RenderableType:
        """Render the threads as a rich table."""
        if not self.threads_data or not isinstance(self.threads_data, dict):
            return "Threads\n\nNo thread data available"

        table = Table(
            title=f"Threads ({len(self.threads_data)})",
            show_header=True,
            box=None,
        )
        table.add_column("Name", style="cyan")
        table.add_column("Class", style="yellow")
        table.add_column("Alive", style="green")
        table.add_column("Loop Count", style="magenta")
        table.add_column("Age", style="blue")

        for name, value in sorted(self.threads_data.items()):
            if isinstance(value, dict):
                alive_str = "✓" if value.get("alive", False) else "✗"
                class_name = value.get("class", "N/A")
                loop_count = value.get("loop_count", 0)
                age = value.get("age", "N/A")
            else:
                alive_str = "?"
                class_name = "N/A"
                loop_count = 0
                age = "N/A"
            table.add_row(
                name,
                class_name,
                alive_str,
                str(loop_count),
                str(age),
            )

        return table


class PacketsPanel(Static):
    """A panel widget that displays packet statistics with rates."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.packet_data = {}
        self.last_rx = 0
        self.last_tx = 0
        self.last_time = None
        self.rx_rate = 0.0
        self.tx_rate = 0.0

    def update_stats(self, stats: dict):
        """Update the packet data and refresh the display."""
        packet_data = stats.get("PacketList", {})
        current_rx = packet_data.get("rx", 0)
        current_tx = packet_data.get("tx", 0)
        current_time = time.time()

        # Calculate rates if we have previous data
        if self.last_time is not None:
            time_delta = current_time - self.last_time
            if time_delta > 0:
                self.rx_rate = (current_rx - self.last_rx) / time_delta
                self.tx_rate = (current_tx - self.last_tx) / time_delta

        self.last_rx = current_rx
        self.last_tx = current_tx
        self.last_time = current_time
        self.packet_data = packet_data
        self.refresh()

    def render(self) -> RenderableType:
        """Render the packet stats as a rich table."""
        if not self.packet_data:
            return "Packets\n\nNo packet data available"

        table = Table(title="Packet Statistics", show_header=True, box=None)
        table.add_column("Type", style="cyan")
        table.add_column("RX", style="green")
        table.add_column("TX", style="yellow")
        table.add_column("RX Rate", style="green")
        table.add_column("TX Rate", style="yellow")

        # Add totals with rates
        rx_total = self.packet_data.get("rx", 0)
        tx_total = self.packet_data.get("tx", 0)
        rx_rate_str = f"{self.rx_rate:.2f}/s" if self.rx_rate >= 0 else "N/A"
        tx_rate_str = f"{self.tx_rate:.2f}/s" if self.tx_rate >= 0 else "N/A"
        table.add_row("Total", str(rx_total), str(tx_total), rx_rate_str, tx_rate_str)

        return table


class PluginsPanel(Static):
    """A panel widget that displays plugin information."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.plugins_data = {}

    def update_stats(self, stats: dict):
        """Update the plugins data and refresh the display."""
        plugins = stats.get("PluginManager", {})
        # Ensure it's a dict, not a list
        if isinstance(plugins, dict):
            self.plugins_data = plugins
        else:
            self.plugins_data = {}
        self.refresh()

    def render(self) -> RenderableType:
        """Render the plugins as a rich table."""
        if not self.plugins_data or not isinstance(self.plugins_data, dict):
            return "Plugins\n\nNo plugin data available"

        table = Table(
            title=f"Plugins ({len(self.plugins_data)})",
            show_header=True,
            box=None,
        )
        table.add_column("Name", style="cyan")
        table.add_column("Enabled", style="green")
        table.add_column("Version", style="yellow")
        table.add_column("TX", style="magenta")
        table.add_column("RX", style="blue")

        for name, value in sorted(self.plugins_data.items()):
            if isinstance(value, dict):
                enabled_str = "✓" if value.get("enabled", False) else "✗"
                version = value.get("version", "N/A")
                tx = value.get("tx", 0)
                rx = value.get("rx", 0)
            else:
                enabled_str = "?"
                version = "N/A"
                tx = 0
                rx = 0
            table.add_row(
                name,
                enabled_str,
                version,
                str(tx),
                str(rx),
            )

        return table


class SeenListPanel(Static):
    """A panel widget that displays seen list information."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.seen_data = {}

    def update_stats(self, stats: dict):
        """Update the seen list data and refresh the display."""
        seen = stats.get("SeenList", {})
        # Ensure it's a dict, not a list
        if isinstance(seen, dict):
            self.seen_data = seen
        else:
            self.seen_data = {}
        self.refresh()

    def render(self) -> RenderableType:
        """Render the seen list as a rich table."""
        if not self.seen_data or not isinstance(self.seen_data, dict):
            return "Seen List\n\nNo seen list data available"

        # Sort by last heard time (most recent first)
        def sort_key(item):
            if not isinstance(item[1], dict):
                return ""  # Empty string sorts last
            last = item[1].get("last")
            if last is None:
                return ""  # Empty string sorts last
            # Handle datetime objects by converting to ISO format string for comparison
            if hasattr(last, "isoformat"):
                return last.isoformat()
            # Convert everything else to string for consistent comparison
            return str(last)

        sorted_seen = sorted(
            self.seen_data.items(),
            key=sort_key,
            reverse=True,
        )[:20]  # Show top 20

        table = Table(
            title=f"Seen List (showing {len(sorted_seen)} of {len(self.seen_data)})",
            show_header=True,
            box=None,
        )
        table.add_column("Callsign", style="cyan")
        table.add_column("Count", style="green")
        table.add_column("Last Heard", style="yellow")

        for callsign, value in sorted_seen:
            if isinstance(value, dict):
                count = value.get("count", 0)
                last = value.get("last", "N/A")
            else:
                count = 0
                last = "N/A"
            table.add_row(
                callsign,
                str(count),
                str(last),
            )

        return table


class WatchListPanel(Static):
    """A panel widget that displays watch list information."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.watch_data = {}

    def update_stats(self, stats: dict):
        """Update the watch list data and refresh the display."""
        watch = stats.get("WatchList", {})
        # Ensure it's a dict, not a list
        if isinstance(watch, dict):
            self.watch_data = watch
        else:
            self.watch_data = {}
        self.refresh()

    def render(self) -> RenderableType:
        """Render the watch list as a rich table."""
        if not self.watch_data or not isinstance(self.watch_data, dict):
            return "Watch List\n\nNo watch list data available"

        def sort_key(item):
            if not isinstance(item[1], dict):
                return ""  # Empty string sorts last
            last = item[1].get("last")
            if last is None:
                return ""  # Empty string sorts last
            # Handle datetime objects by converting to ISO format string for comparison
            if hasattr(last, "isoformat"):
                return last.isoformat()
            # Convert everything else to string for consistent comparison
            return str(last)

        sorted_watch = sorted(
            self.watch_data.items(),
            key=sort_key,
            reverse=True,
        )

        table = Table(
            title=f"Watch List ({len(self.watch_data)})",
            show_header=True,
            box=None,
        )
        table.add_column("Callsign", style="cyan")
        table.add_column("Last Heard", style="yellow")

        for callsign, value in sorted_watch:
            if isinstance(value, dict):
                last = value.get("last", "N/A")
            else:
                last = "N/A"
            table.add_row(callsign, str(last))

        return table


class PacketTypesPanel(Static):
    """A panel widget that displays packet type breakdown with percentages."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.packet_data = {}

    def update_stats(self, stats: dict):
        """Update the packet data and refresh the display."""
        self.packet_data = stats.get("PacketList", {})
        self.refresh()

    def render(self) -> RenderableType:
        """Render the packet types breakdown as a rich table."""
        if not self.packet_data:
            return "Packet Types\n\nNo packet data available"

        # Try 'packets' first, then 'types' as fallback
        packets = self.packet_data.get("packets")
        if packets is None:
            packets = self.packet_data.get("types", {})

        if not isinstance(packets, dict):
            packets = {}

        total_rx = self.packet_data.get("rx", 0) or 0
        total_tx = self.packet_data.get("tx", 0) or 0
        total_all = total_rx + total_tx

        if not packets:
            return f"Packet Types\n\nNo packet type data available\nTotal RX: {total_rx}, Total TX: {total_tx}"

        if total_all == 0:
            return "Packet Types\n\nNo packets received or sent"

        table = Table(title="Packet Types Breakdown", show_header=True, box=None)
        table.add_column("Type", style="cyan")
        table.add_column("RX", style="green")
        table.add_column("TX", style="yellow")
        table.add_column("Total", style="magenta")
        table.add_column("% of Total", style="blue")

        # Collect and sort by total count
        packet_list = []
        for packet_type, data in packets.items():
            # Skip if packet_type is None
            if packet_type is None:
                continue
            if isinstance(data, dict):
                rx = data.get("rx")
                tx = data.get("tx")
            else:
                rx = tx = None
            # Ensure rx and tx are numbers
            try:
                rx = int(rx) if rx is not None else 0
                tx = int(tx) if tx is not None else 0
            except (ValueError, TypeError):
                rx = tx = 0
            total = rx + tx
            packet_list.append((str(packet_type), rx, tx, total))

        if not packet_list:
            return f"Packet Types\n\nNo packet types found\nTotal RX: {total_rx}, Total TX: {total_tx}\nPackets dict has {len(packets)} keys"

        # Sort by total count descending, ensuring total is always a number
        packet_list.sort(
            key=lambda x: (x[3] if x[3] is not None else 0, x[0]), reverse=True
        )

        for packet_type, rx, tx, total in packet_list:
            percentage = (total / total_all * 100) if total_all > 0 else 0.0
            table.add_row(
                packet_type,
                str(rx),
                str(tx),
                str(total),
                f"{percentage:.1f}%",
            )

        return table


class APRSDStatsApp(App):
    """A Textual application for displaying APRSD stats."""

    CSS = """
    Screen {
        background: $surface;
        layout: vertical;
    }

    Header {
        dock: top;
    }

    #overview_header {
        height: 4;
        min-height: 4;
        max-height: 4;
        border-bottom: solid $primary;
    }

    Container {
        height: 1fr;
        layout: vertical;
    }

    StatsPanel, ThreadsPanel, PacketsPanel, PluginsPanel, SeenListPanel, WatchListPanel, PacketTypesPanel {
        height: 1fr;
        padding: 1;
        border: solid $primary;
        overflow-y: auto;
    }

    Horizontal {
        height: 1fr;
    }

    Horizontal > SeenListPanel,
    Horizontal > WatchListPanel {
        width: 1fr;
    }

    Vertical {
        width: 1fr;
        height: 1fr;
    }

    Footer {
        dock: bottom;
    }
    """

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("r", "refresh", "Refresh"),
    ]

    def __init__(
        self, refresh_interval: float = 5.0, aprsd_url: str = None, *args, **kwargs
    ):
        super().__init__(*args, **kwargs)
        self.aprsd_url = aprsd_url
        self.stats_store = StatsStore() if not aprsd_url else None
        self.stats_data = {}
        self.refresh_interval = refresh_interval
        self.url_error_shown = False

    def compose(self) -> ComposeResult:
        """Create child widgets for the app."""
        yield Header(show_clock=True)
        yield OverviewHeader(
            aprsd_url=self.aprsd_url, app_name="APRSD Stats", id="overview_header"
        )
        with Container():
            with Horizontal():
                with Vertical():
                    yield StatsPanel("APRSD Stats", id="aprsd_stats")
                    yield ThreadsPanel(id="threads")
                with Vertical():
                    yield PacketsPanel(id="packets")
                    yield PluginsPanel(id="plugins")
            with Horizontal():
                yield SeenListPanel(id="seen_list")
                yield WatchListPanel(id="watch_list")
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

        self.refresh_stats()
        self.set_interval(self.refresh_interval, self.refresh_stats)

    def _show_url_error(self, error_message: str) -> None:
        """Show error dialog for URL fetch failure."""
        if self.url_error_shown:
            return
        self.url_error_shown = True

        # Create error message
        message = f"Failed to fetch stats from URL:\n\n{self.aprsd_url}\n\nError: {error_message}\n\nPlease check the URL and try again."

        # Schedule showing the error dialog after the app is fully mounted
        # Use a small delay to ensure the app is ready
        def show_error():
            from textual.screen import Screen

            class ErrorScreen(Screen):
                """Screen that displays an error dialog."""

                DEFAULT_CSS = """
                ErrorScreen {
                    align: center middle;
                }
                """

                def compose(self):
                    """Compose the error screen with dialog."""
                    yield ErrorDialog(message, title="URL Connection Error")

            self.push_screen(ErrorScreen())

        # Use set_timer to schedule after mount is complete
        self.set_timer(0.1, show_error)

    def refresh_stats(self) -> None:
        """Refresh stats from the stats store or URL."""
        try:
            if self.aprsd_url:
                self.stats_data = fetch_stats_from_url(self.aprsd_url)
            else:
                self.stats_store.load()
                self.stats_data = self.stats_store.data

            # Update all panels
            self.query_one("#aprsd_stats", StatsPanel).update_stats(
                self.stats_data.get("APRSDStats", {})
            )
            self.query_one("#threads", ThreadsPanel).update_stats(self.stats_data)
            self.query_one("#packets", PacketsPanel).update_stats(self.stats_data)
            self.query_one("#plugins", PluginsPanel).update_stats(self.stats_data)
            self.query_one("#seen_list", SeenListPanel).update_stats(self.stats_data)
            self.query_one("#watch_list", WatchListPanel).update_stats(self.stats_data)
        except Exception as e:
            LOG.error(f"Error refreshing stats: {e}")
            # Show error dialog if URL fetch fails
            if self.aprsd_url and not self.url_error_shown:
                self._show_url_error(str(e))

    def action_refresh(self) -> None:
        """Action to refresh stats manually."""
        self.refresh_stats()

    def action_quit(self) -> None:
        """Action to quit the application."""
        self.exit()


@cmds.admin.command()
@cli_helper.add_options(cli_helper.common_options)
@click.option(
    "--refresh-interval",
    type=float,
    default=5.0,
    help="Refresh interval in seconds (default: 5.0)",
)
@click.option(
    "--url",
    "aprsd_url",
    default=None,
    help="URL to fetch stats from (e.g., http://localhost:8080). If not provided, stats are loaded from local StatsStore.",
)
@click.pass_context
@cli_helper.process_standard_options
def stats_ui(ctx, refresh_interval, aprsd_url):
    """Display APRSD stats in a terminal UI."""
    LOG.info(f"APRSD Stats UI started version: {aprsd.__version__}")
    LOG.info(f"Refresh interval: {refresh_interval} seconds")
    if aprsd_url:
        LOG.info(f"Fetching stats from remote URL: {aprsd_url}")

    app = APRSDStatsApp(refresh_interval=refresh_interval, aprsd_url=aprsd_url)
    app.run()
