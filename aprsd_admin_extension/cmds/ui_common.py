"""Common UI utilities for admin and stats UI commands."""

import base64
import json
import logging
import urllib.request

from oslo_config import cfg
from textual.containers import Container
from textual.widgets import Button, Static

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
