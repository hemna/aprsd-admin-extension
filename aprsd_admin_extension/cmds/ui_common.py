"""Common UI utilities for admin and stats UI commands."""

import base64
import json
import logging
import urllib.request

from aprsd import client
from aprsd.threads import stats as stats_threads
from oslo_config import cfg
from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Container
from textual.widgets import Button, Static

import aprsd_admin_extension

CONF = cfg.CONF
LOG = logging.getLogger("APRSD")


def _make_authenticated_request(url: str) -> urllib.request.Request:
    """Create an authenticated request for a URL."""
    req = urllib.request.Request(url)

    # Add basic auth if configured in CONF
    if hasattr(CONF, "aprsd_admin_extension") and hasattr(
        CONF.aprsd_admin_extension, "web_username"
    ):
        username = getattr(CONF.aprsd_admin_extension, "web_username", None)
        password = getattr(CONF.aprsd_admin_extension, "web_password", None)
        if username and password:
            credentials = f"{username}:{password}".encode()
            encoded = base64.b64encode(credentials).decode()
            req.add_header("Authorization", f"Basic {encoded}")

    return req


def fetch_stats_from_url(url: str) -> dict:
    """Fetch stats from a remote URL endpoint."""
    try:
        # Ensure URL ends with /stats if not already
        if not url.endswith("/stats"):
            url = url.rstrip("/") + "/stats"

        req = _make_authenticated_request(url)

        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode())
            # The /stats endpoint returns {"time": ..., "stats": ...}
            # Return just the stats part to match StatsStore.data format
            return data.get("stats", {})
    except Exception as e:
        LOG.error(f"Error fetching stats from URL {url}: {e}")
        raise


def fetch_config_from_url(url: str) -> str:
    """Fetch config from a remote URL endpoint (/oslo)."""
    try:
        # Ensure URL ends with /oslo if not already
        if not url.endswith("/oslo"):
            url = url.rstrip("/") + "/oslo"

        req = _make_authenticated_request(url)

        with urllib.request.urlopen(req, timeout=5) as response:
            # The /oslo endpoint returns the config file content as text
            return response.read().decode()
    except Exception as e:
        LOG.error(f"Error fetching config from URL {url}: {e}")
        raise


class ErrorDialog(Container):
    """Error dialog widget for displaying URL fetch errors."""

    DEFAULT_CSS = """
    ErrorDialog {
        align: center middle;
        width: 70;
        height: 12;
        border: solid red;
        background: $surface;
    }
    #error_title {
        text-align: center;
        width: 100%;
        padding: 1;
        text-style: bold;
        color: red;
    }
    #error_message {
        padding: 1 2;
        width: 100%;
    }
    #error_ok {
        width: 100%;
        margin: 1;
    }
    """

    def __init__(self, message: str, title: str = "Error", *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.message = message
        self.title = title

    def compose(self):
        """Compose the error dialog widgets."""
        yield Static(f"[bold red]{self.title}[/bold red]", id="error_title")
        yield Static(self.message, id="error_message")
        yield Button("OK", id="error_ok")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle OK button press."""
        if event.button.id == "error_ok":
            self.app.pop_screen()


class OverviewHeader(Container):
    """Overview header showing app name, callsign, version, and uptime."""

    DEFAULT_CSS = """
    OverviewHeader {
        height: 4;
        min-height: 4;
        max-height: 4;
        border-bottom: solid $primary;
        padding: 1;
    }
    #overview_content {
        width: 100%;
        height: 100%;
    }
    """

    def __init__(self, aprsd_url: str = None, app_name: str = "APRSD", *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.aprsd_url = aprsd_url
        self.app_name = app_name
        self.stats_store = stats_threads.StatsStore() if not aprsd_url else None

    def compose(self) -> ComposeResult:
        yield Static(id="overview_content")

    def on_mount(self) -> None:
        self.refresh_overview()
        self.set_interval(5.0, self.refresh_overview)

    def refresh_overview(self) -> None:
        try:
            # Get stats for uptime and connection info
            if self.aprsd_url:
                stats = fetch_stats_from_url(self.aprsd_url)
            else:
                self.stats_store.load()
                stats = self.stats_store.data

            # Get version info - admin version is always local
            admin_version = aprsd_admin_extension.__version__

            # Get callsign - from remote stats if available, otherwise local config
            aprsd_stats = stats.get("APRSDStats", {})
            callsign = aprsd_stats.get("callsign", CONF.callsign or "N/A")

            # Get uptime
            uptime = aprsd_stats.get("uptime", "N/A")

            # Get connection info
            # If remote, try to get pre-formatted connection string from stats
            # Otherwise build it from stats data
            client_stats = stats.get("APRSClientStats", {})
            if self.aprsd_url:
                # For remote, try to get the formatted connection string first
                connection = client_stats.get("aprs_connection", "")
                if not connection:
                    # Fallback: build from available stats data
                    if client_stats.get("server_string"):
                        connection = (
                            f"APRS-IS Server: {client_stats.get('server_string')}"
                        )
                    elif client_stats.get("transport"):
                        transport = client_stats.get("transport", "Unknown")
                        if transport == "tcpkiss":
                            connection = f"TCPKISS://{client_stats.get('host', 'unknown')}:{client_stats.get('port', 'unknown')}"
                        elif transport == "serialkiss":
                            connection = f"SerialKISS://{client_stats.get('device', 'unknown')}@{client_stats.get('baudrate', 'unknown')} baud"
                        else:
                            connection = transport
                    else:
                        connection = "Unknown"
            else:
                # For local, use config (same logic as wsgi.py)
                if CONF.aprs_network.enabled:
                    transport = "aprs-is"
                    if client_stats:
                        server_string = client_stats.get("server_string", "")
                        connection = (
                            f"APRS-IS Server: {server_string}"
                            if server_string
                            else "APRS-IS"
                        )
                    else:
                        connection = "APRS-IS"
                else:
                    # We might be connected to a KISS socket?
                    if client.KISSClient.kiss_enabled():
                        transport = client.KISSClient.transport()
                        if transport == client.TRANSPORT_TCPKISS:
                            connection = (
                                f"TCPKISS://{CONF.kiss_tcp.host}:{CONF.kiss_tcp.port}"
                            )
                        elif transport == client.TRANSPORT_SERIALKISS:
                            connection = f"SerialKISS://{CONF.kiss_serial.device}@{CONF.kiss_serial.baudrate} baud"
                        else:
                            connection = transport or "Unknown"
                    else:
                        connection = "Unknown"

            # Format overview similar to web interface
            overview_text = Text()
            overview_text.append(f"{self.app_name} ", style="bold white")
            overview_text.append(f"v{admin_version} ", style="dim cyan")
            overview_text.append(f"{callsign} ", style="bold cyan")
            overview_text.append("connected to ", style="dim")
            overview_text.append(f"{connection} ", style="yellow")
            overview_text.append(f"uptime: {uptime}", style="dim green")

            self.query_one("#overview_content", Static).update(overview_text)
        except Exception as e:
            LOG.error(f"Error refreshing overview: {e}")
            # Show basic info even if stats fail
            admin_version = aprsd_admin_extension.__version__
            callsign = CONF.callsign or "N/A"
            overview_text = Text()
            overview_text.append(f"{self.app_name} ", style="bold white")
            overview_text.append(f"v{admin_version} ", style="dim cyan")
            overview_text.append(f"{callsign}", style="bold cyan")
            self.query_one("#overview_content", Static).update(overview_text)
