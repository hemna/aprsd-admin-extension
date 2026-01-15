"""Terminal UI for APRSD admin interface using textual library."""

import importlib.metadata as imp
import io
import json
import logging
from datetime import datetime

import aprsd
import click

try:
    from textual_plotext import PlotextPlot

    PLOTEXT_AVAILABLE = True
except ImportError:
    PLOTEXT_AVAILABLE = False
    PlotextPlot = None
from aprsd import cli_helper, conf
from aprsd import threads as aprsd_threads
from aprsd.packets.core import AckPacket, RejectPacket
from aprsd.threads import service
from aprsd.threads import stats as stats_threads
from oslo_config import cfg, generator
from rich.console import RenderableType
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
    OverviewHeader,
    fetch_config_from_url,
    fetch_stats_from_url,
)
from aprsd_admin_extension.threads import log_monitor

CONF = cfg.CONF
LOG = logging.getLogger("APRSD")

# Chart classes - only define if plotext is available
if PLOTEXT_AVAILABLE:

    class PacketsChart(PlotextPlot):
        """Chart for displaying APRS packet totals (TX/RX)."""

        def on_mount(self) -> None:
            """Initialize the plot."""
            self.plt.xlabel("Time")
            self.plt.ylabel("Count")

        def update(self, tx_data: list, rx_data: list) -> None:
            """Update the plot with new data."""
            self.plt.clear_data()
            if len(tx_data) > 1:
                x = list(range(len(tx_data)))
                self.plt.plot(x, tx_data, label="TX", color="red")
                self.plt.plot(x, rx_data, label="RX", color="green")
            elif len(tx_data) == 1:
                # Need at least 2 points for line plot
                x = [0, 1]
                self.plt.plot(x, [tx_data[0], tx_data[0]], label="TX", color="red")
                self.plt.plot(x, [rx_data[0], rx_data[0]], label="RX", color="green")
            # Set Y-axis to show only whole numbers
            max_val = max(
                max(tx_data) if tx_data else 0, max(rx_data) if rx_data else 0
            )
            if max_val > 0:
                # Create integer tick marks
                num_ticks = 5
                tick_step = max(1, int(max_val / num_ticks))
                y_ticks = list(range(0, int(max_val) + tick_step + 1, tick_step))
                self.plt.yticks(y_ticks, [str(int(y)) for y in y_ticks])
            widget_size = self.size
            if widget_size.width > 0 and widget_size.height > 0:
                # Use a fixed smaller height instead of widget size
                # Original would be ~15-20, reduced to ~7-10 (49% of original)
                height = max(7, int((widget_size.height - 4) * 0.49))
                self.plt.plotsize(widget_size.width - 4, height)
            else:
                self.plt.plotsize(80, 7)  # Reduced fallback height
            self.refresh()

    class ThreadsChart(PlotextPlot):
        """Chart for displaying active thread count."""

        def on_mount(self) -> None:
            """Initialize the plot."""
            self.plt.xlabel("Time")
            self.plt.ylabel("Count")

        def update(self, count_data: list) -> None:
            """Update the plot with new data."""
            self.plt.clear_data()
            if len(count_data) > 1:
                x = list(range(len(count_data)))
                self.plt.plot(x, count_data, label="Threads", color="blue")
            elif len(count_data) == 1:
                x = [0, 1]
                self.plt.plot(
                    x, [count_data[0], count_data[0]], label="Threads", color="blue"
                )
            widget_size = self.size
            if widget_size.width > 0 and widget_size.height > 0:
                # Use a fixed smaller height instead of widget size
                # Original would be ~15-20, reduced to ~7-10 (49% of original)
                height = max(7, int((widget_size.height - 4) * 0.49))
                self.plt.plotsize(widget_size.width - 4, height)
            else:
                self.plt.plotsize(80, 7)  # Reduced fallback height
            self.refresh()

    class MemoryChart(PlotextPlot):
        """Chart for displaying memory usage."""

        def on_mount(self) -> None:
            """Initialize the plot."""
            self.plt.xlabel("Time")
            self.plt.ylabel("MB")

        def update(self, current_data: list, peak_data: list) -> None:
            """Update the plot with new data."""
            self.plt.clear_data()
            if len(current_data) > 1:
                x = list(range(len(current_data)))
                self.plt.plot(x, current_data, label="Current", color="blue")
                self.plt.plot(x, peak_data, label="Peak", color="red")
            elif len(current_data) == 1:
                x = [0, 1]
                self.plt.plot(
                    x, [current_data[0], current_data[0]], label="Current", color="blue"
                )
                self.plt.plot(
                    x, [peak_data[0], peak_data[0]], label="Peak", color="red"
                )
            widget_size = self.size
            if widget_size.width > 0 and widget_size.height > 0:
                # Use a fixed smaller height instead of widget size
                # Original would be ~15-20, reduced to ~7-10 (49% of original)
                height = max(7, int((widget_size.height - 4) * 0.49))
                self.plt.plotsize(widget_size.width - 4, height)
            else:
                self.plt.plotsize(80, 7)  # Reduced fallback height
            self.refresh()

    class PacketTypesChart(PlotextPlot):
        """Chart for displaying packet types as a bar chart."""

        def on_mount(self) -> None:
            """Initialize the plot."""
            self.plt.xlabel("Packet Type")
            self.plt.ylabel("Count")

        def update(self, types: list, rx_values: list, tx_values: list) -> None:
            """Update the plot with new data."""
            self.plt.clear_data()
            if (
                types
                and len(types) > 0
                and len(rx_values) == len(types)
                and len(tx_values) == len(types)
            ):
                # Create x positions for each packet type group
                # Each group will have 2 bars (RX and TX) side by side
                bar_width = 0.35  # Width of each bar
                x_base = list(range(len(types)))  # Base positions for each packet type
                x_rx = [x - bar_width / 2 for x in x_base]  # RX bars offset left
                x_tx = [x + bar_width / 2 for x in x_base]  # TX bars offset right

                # Plot RX bars in green
                self.plt.bar(
                    x_rx, rx_values, width=bar_width, label="RX", color="green"
                )
                # Plot TX bars in red
                self.plt.bar(x_tx, tx_values, width=bar_width, label="TX", color="red")
                # Set x-axis labels at the center of each group
                self.plt.xticks(x_base, types)
                # Set Y-axis to show only whole numbers
                max_val = max(
                    max(rx_values) if rx_values else 0,
                    max(tx_values) if tx_values else 0,
                )
                if max_val > 0:
                    # Create integer tick marks
                    num_ticks = 5
                    tick_step = max(1, int(max_val / num_ticks))
                    y_ticks = list(range(0, int(max_val) + tick_step + 1, tick_step))
                    self.plt.yticks(y_ticks, [str(int(y)) for y in y_ticks])
                widget_size = self.size
                if widget_size.width > 0 and widget_size.height > 0:
                    # Use a fixed smaller height instead of widget size
                    # Original would be ~20, reduced to ~10 (49% of original)
                    height = max(10, int((widget_size.height - 4) * 0.49))
                    self.plt.plotsize(widget_size.width - 4, height)
                else:
                    self.plt.plotsize(100, 10)  # Reduced fallback height
            # Always refresh, even if no data
            self.refresh()

else:
    # Dummy classes when plotext is not available
    PacketsChart = None
    ThreadsChart = None
    MemoryChart = None
    PacketTypesChart = None


class StatsTab(ScrollableContainer):
    """Stats tab showing APRSD statistics."""

    DEFAULT_CSS = """
    .chart_container {
        border: solid $primary;
        padding: 1;
        margin: 1;
        height: auto;
    }
    .chart_title {
        text-align: center;
        margin-bottom: 1;
    }
    PlotextPlot {
        height: auto;
        min-height: 7;
        max-height: 20;
    }
    """

    def __init__(self, aprsd_url: str = None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.aprsd_url = aprsd_url
        self.stats_store = stats_threads.StatsStore() if not aprsd_url else None
        # Track historical data for time-series charts
        self.history = {
            "packets": {"tx": [], "rx": [], "time": []},
            "threads": {"count": [], "time": []},
            "memory": {"current": [], "peak": [], "time": []},
        }
        self.max_history = 50  # Keep last 50 data points

    def compose(self) -> ComposeResult:
        if PLOTEXT_AVAILABLE:
            yield Container(
                Static(
                    "[bold cyan]APRS Packet Totals[/bold cyan]", classes="chart_title"
                ),
                PacketsChart(id="packets_chart"),
                classes="chart_container",
            )
            yield Container(
                Static(
                    "[bold bright_cyan]Packet Types[/bold bright_cyan]",
                    classes="chart_title",
                ),
                PacketTypesChart(id="packet_types_chart"),
                classes="chart_container",
            )
            yield Container(
                Static("[bold blue]Active Threads[/bold blue]", classes="chart_title"),
                ThreadsChart(id="threads_chart"),
                classes="chart_container",
            )
            yield Container(
                Static(
                    "[bold magenta]Memory Usage[/bold magenta]", classes="chart_title"
                ),
                MemoryChart(id="memory_chart"),
                classes="chart_container",
            )

    def on_mount(self) -> None:
        # Initial refresh after a short delay to ensure widgets are mounted
        self.set_timer(0.1, self.refresh_stats)
        self.set_interval(5.0, self.refresh_stats)

    def refresh_stats(self) -> None:
        try:
            if self.aprsd_url:
                stats = fetch_stats_from_url(self.aprsd_url)
            else:
                self.stats_store.load()
                stats = self.stats_store.data
            # Update history for time-series charts
            self._update_history(stats)
            # Update charts if available
            if PLOTEXT_AVAILABLE:
                self._update_charts(stats)
            # No longer need to update stats_content since we removed the text blocks
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

    def _update_charts(self, stats: dict) -> None:
        """Update all chart widgets with current data."""
        if not PLOTEXT_AVAILABLE:
            return

        try:
            # Packets chart
            if len(self.history["packets"]["time"]) >= 1:
                try:
                    chart = self.query_one("#packets_chart", PacketsChart)
                    chart.update(
                        self.history["packets"]["tx"],
                        self.history["packets"]["rx"],
                    )
                except Exception as e:
                    LOG.error(f"Error updating packets chart: {e}", exc_info=True)

            # Threads chart
            if len(self.history["threads"]["time"]) >= 1:
                try:
                    chart = self.query_one("#threads_chart", ThreadsChart)
                    chart.update(self.history["threads"]["count"])
                except Exception as e:
                    LOG.error(f"Error updating threads chart: {e}", exc_info=True)

            # Memory chart
            try:
                chart = self.query_one("#memory_chart", MemoryChart)
                if len(self.history["memory"]["time"]) >= 1:
                    chart.update(
                        self.history["memory"]["current"],
                        self.history["memory"]["peak"],
                    )
            except Exception as e:
                LOG.error(f"Error updating memory chart: {e}", exc_info=True)

            # Packet types chart
            try:
                chart = self.query_one("#packet_types_chart", PacketTypesChart)
                packet_list = stats.get("PacketList", {})
                types = []
                rx_values = []
                tx_values = []

                if packet_list:
                    # Try "types" first (used by web version), fall back to "packets"
                    packet_types = packet_list.get(
                        "types", packet_list.get("packets", {})
                    )
                    if isinstance(packet_types, dict) and packet_types:
                        for packet_type, data in sorted(packet_types.items()):
                            if isinstance(data, dict):
                                rx = data.get("rx", 0)
                                tx = data.get("tx", 0)
                                # Only include packet types with non-zero counts
                                if rx > 0 or tx > 0:
                                    types.append(packet_type[:15])
                                    rx_values.append(rx)
                                    tx_values.append(tx)

                # Always update the chart
                chart.update(types, rx_values, tx_values)
            except Exception as e:
                LOG.error(f"Error updating packet types chart: {e}", exc_info=True)
        except Exception as e:
            LOG.debug(f"Error updating charts: {e}")

    def _update_history(self, stats: dict) -> None:
        """Update historical data for time-series charts."""
        from datetime import datetime

        now = datetime.now()
        time_str = now.strftime("%H:%M:%S")

        # Packets
        packet_list = stats.get("PacketList", {})
        if packet_list:
            tx = packet_list.get("tx", 0)
            rx = packet_list.get("rx", 0)
            self.history["packets"]["tx"].append(tx)
            self.history["packets"]["rx"].append(rx)
            self.history["packets"]["time"].append(time_str)
            if len(self.history["packets"]["time"]) > self.max_history:
                self.history["packets"]["tx"].pop(0)
                self.history["packets"]["rx"].pop(0)
                self.history["packets"]["time"].pop(0)

        # Threads
        thread_list = stats.get("APRSDThreadList", {})
        if thread_list:
            thread_count = len(thread_list) if isinstance(thread_list, dict) else 0
            self.history["threads"]["count"].append(thread_count)
            self.history["threads"]["time"].append(time_str)
            if len(self.history["threads"]["time"]) > self.max_history:
                self.history["threads"]["count"].pop(0)
                self.history["threads"]["time"].pop(0)
        else:
            # If no thread list, append 0
            self.history["threads"]["count"].append(0)
            self.history["threads"]["time"].append(time_str)
            if len(self.history["threads"]["time"]) > self.max_history:
                self.history["threads"]["count"].pop(0)
                self.history["threads"]["time"].pop(0)

        # Memory
        aprsd_stats = stats.get("APRSDStats", {})
        if aprsd_stats:
            # Try to get memory values - could be numeric or string
            mem_current = aprsd_stats.get("memory_current", 0.0)
            mem_peak = aprsd_stats.get("memory_peak", 0.0)

            # If they're strings, parse them
            if isinstance(mem_current, str):
                try:
                    # Handle both MB and KB units
                    mem_current_val = (
                        mem_current.replace(" MB", "").replace(" KB", "").strip()
                    )
                    mem_current = float(mem_current_val) if mem_current_val else 0.0
                    # Convert KB to MB if needed
                    if " KB" in mem_current:
                        mem_current = mem_current / 1024.0
                except (ValueError, AttributeError):
                    mem_current = 0.0

            if isinstance(mem_peak, str):
                try:
                    # Handle both MB and KB units
                    mem_peak_val = (
                        mem_peak.replace(" MB", "").replace(" KB", "").strip()
                    )
                    mem_peak = float(mem_peak_val) if mem_peak_val else 0.0
                    # Convert KB to MB if needed
                    if " KB" in mem_peak:
                        mem_peak = mem_peak / 1024.0
                except (ValueError, AttributeError):
                    mem_peak = 0.0

            # Ensure they're floats
            try:
                mem_current = float(mem_current) if mem_current else 0.0
                mem_peak = float(mem_peak) if mem_peak else 0.0
            except (ValueError, TypeError):
                mem_current = 0.0
                mem_peak = 0.0

            self.history["memory"]["current"].append(mem_current)
            self.history["memory"]["peak"].append(mem_peak)
            self.history["memory"]["time"].append(time_str)
            if len(self.history["memory"]["time"]) > self.max_history:
                self.history["memory"]["current"].pop(0)
                self.history["memory"]["peak"].pop(0)
                self.history["memory"]["time"].pop(0)
        else:
            # If no APRSDStats, append 0
            self.history["memory"]["current"].append(0.0)
            self.history["memory"]["peak"].append(0.0)
            self.history["memory"]["time"].append(time_str)
            if len(self.history["memory"]["time"]) > self.max_history:
                self.history["memory"]["current"].pop(0)
                self.history["memory"]["peak"].pop(0)
                self.history["memory"]["time"].pop(0)

    def _format_stats(self, stats: dict) -> RenderableType:
        """Format stats as a rich renderable - now just returns empty since charts are widgets."""
        # Charts are now widgets, so we don't need to format anything here
        return Static("")


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


class ThreadsTab(ScrollableContainer):
    """Threads tab showing thread information."""

    def __init__(self, aprsd_url: str = None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.aprsd_url = aprsd_url
        self.stats_store = stats_threads.StatsStore() if not aprsd_url else None

    def compose(self) -> ComposeResult:
        yield Static(id="threads_content")

    def on_mount(self) -> None:
        self.refresh_threads()
        self.set_interval(5.0, self.refresh_threads)

    def refresh_threads(self) -> None:
        try:
            if self.aprsd_url:
                stats = fetch_stats_from_url(self.aprsd_url)
            else:
                self.stats_store.load()
                stats = self.stats_store.data
            content = self._format_threads(stats)
            self.query_one("#threads_content", Static).update(content)
        except Exception as e:
            LOG.error(f"Error refreshing threads: {e}")
            self.query_one("#threads_content", Static).update(
                Panel(
                    Text(f"Error loading threads: {e}", style="bold red"),
                    title="[bold red]Error[/bold red]",
                    border_style="red",
                )
            )

    def _format_threads(self, stats: dict) -> RenderableType:
        """Format threads as a rich renderable with panels."""
        threads_data = stats.get("APRSDThreadList", {})
        if not threads_data or not isinstance(threads_data, dict):
            return Panel(
                Text("No threads data available", style="dim"),
                title="[dim]Threads[/dim]",
                border_style="dim",
            )

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

        return panel


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
            # Try to get human_info - it might be a property or attribute
            human_info = None
            try:
                # Try accessing human_info directly (works for both properties and attributes)
                human_info = pkt.human_info
            except (AttributeError, TypeError):
                # If that fails, try message_text directly
                try:
                    message_text = getattr(pkt, "message_text", None)
                    if message_text:
                        # Simple filtering: limit length and strip newlines
                        human_info = message_text[:67].rstrip("\n")
                except Exception:
                    pass

            if human_info:
                text.append(" : ", style="default")
                text.append(str(human_info), style=f"bold {MESSAGE_COLOR}")

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
                                # Store original data for human_info property
                                self._data = data

                            @property
                            def human_info(self):
                                """Get human-readable message info, handling both dict and object cases."""
                                # If human_info is already in the dict, use it
                                if "human_info" in self._data:
                                    return self._data["human_info"]
                                # Otherwise, try to build it from message_text (for MessagePacket)
                                message_text = self._data.get("message_text")
                                if message_text:
                                    # Filter for send (remove control characters and limit length) like MessagePacket does
                                    # _filter_for_send limits to 67 chars and removes control chars
                                    filtered = message_text[:67] if message_text else ""
                                    # Remove common control characters (simplified version of _filter_for_send)
                                    for char in [
                                        "\x00",
                                        "\x01",
                                        "\x02",
                                        "\x03",
                                        "\x04",
                                        "\x05",
                                        "\x06",
                                        "\x07",
                                        "\x08",
                                        "\x0b",
                                        "\x0c",
                                        "\x0e",
                                        "\x0f",
                                        "\x10",
                                        "\x11",
                                        "\x12",
                                        "\x13",
                                        "\x14",
                                        "\x15",
                                        "\x16",
                                        "\x17",
                                        "\x18",
                                        "\x19",
                                        "\x1a",
                                        "\x1b",
                                        "\x1c",
                                        "\x1d",
                                        "\x1e",
                                        "\x1f",
                                    ]:
                                        filtered = filtered.replace(char, "")
                                    return filtered.rstrip("\n")
                                return None

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
    Header {
        dock: top;
    }
    #overview_header {
        height: 4;
        min-height: 4;
        max-height: 4;
        border-bottom: solid $primary;
    }
    #main_tabs {
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

    def __init__(self, aprsd_url: str = None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.server_threads = None
        self.aprsd_url = aprsd_url
        self.url_error_shown = False

    def compose(self) -> ComposeResult:
        """Create child widgets for the app."""
        yield Header(show_clock=True)
        yield OverviewHeader(
            aprsd_url=self.aprsd_url, app_name="APRSD Admin", id="overview_header"
        )
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
            TabPane("Threads", ThreadsTab(aprsd_url=self.aprsd_url), id="threads_tab")
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
