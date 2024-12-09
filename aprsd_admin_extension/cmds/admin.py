import click
import datetime
import logging
import signal
import sys
import time
from oslo_config import cfg

import aprsd
from aprsd import cli_helper
from aprsd import threads as aprsd_threads
from aprsd import packets, client
from aprsd.threads import stats as stats_thread
from aprsd.threads import keep_alive

import aprsd_admin_extension
# Import the extension's configuration options
from aprsd_admin_extension import conf  # noqa
from aprsd_admin_extension import cmds, utils  # noqa

CONF = cfg.CONF
LOG = logging.getLogger("APRSD")


def signal_handler(sig, frame):
    print("signal_handler: called")
    # APRSD based threads are automatically added
    # to the APRSDThreadList when started.
    # This will tell them all to stop.
    aprsd_threads.APRSDThreadList().stop_all()
    if "subprocess" not in str(frame):
        LOG.info(
            "Ctrl+C, Sending all threads exit! Can take up to 10 seconds {}".format(
                datetime.datetime.now(),
            ),
        )
        time.sleep(1.5)
        packets.PacketTrack().save()
        packets.WatchList().save()
        packets.SeenList().save()


@cmds.aprsdadmin.command()
@cli_helper.add_options(cli_helper.common_options)
@click.pass_context
@cli_helper.process_standard_options
def admin(ctx):
    """APRSD Admin Extension"""

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    level, msg = utils._check_version()
    if level:
        LOG.warning(msg)
    else:
        LOG.info(msg)
    version = aprsd_admin_extension.__version__
    LOG.info(f"APRSD IRC Started version: {version}")
    LOG.info(f"APRSD version: {aprsd.__version__}")

    # If you need an aprs client, you can get it here

    # Initialize the client factory and create
    # The correct client object ready for use
    client.ClientFactory.setup()

    # Dump all the config options now.
    CONF.log_opt_values(LOG, logging.DEBUG)

    # Make sure we have 1 client transport enabled
    if not client.factory.is_client_enabled():
        LOG.error("No Clients are enabled in config.")
        sys.exit(-1)

    if not client.factory.is_client_configured():
        LOG.error("APRS client is not properly configured in config file.")
        sys.exit(-1)

    # Try and load saved MsgTrack list
    LOG.debug("Loading saved objects.")
    packets.PacketTrack().load()
    packets.WatchList().load()
    packets.SeenList().load()

    # This thread collects all the stats from all the
    # objects that generate stats and dumps them all to disk.
    stats_store_thread = stats_thread.APRSDStatsStoreThread()
    stats_store_thread.start()

    keepalive = keep_alive.KeepAliveThread()
    keepalive.start()

    LOG.info("Started the admin command.")

    # Now add your code here to start your extension.
    # You know that you have a client configured and connected
    # Create your threads, and start them here.

    # XXX YOUR threads started here.

    # Now wait for keepalive to be done.
    # CTRL-C will stop all the started threads automatically.
    stats_store_thread.join()
    keepalive.join()
