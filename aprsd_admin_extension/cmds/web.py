import datetime
import logging
import os
import signal
import time
from logging.handlers import QueueHandler

import aprsd
import click
import socketio
from aprsd import cli_helper, packets
from aprsd import main as aprsd_main
from aprsd import threads as aprsd_threads
from aprsd.log import log as aprsd_log
from aprsd.threads import service
from loguru import logger
from oslo_config import cfg

# Import the extension's configuration options
from aprsd_admin_extension import (  # noqa
    cmds,
    conf,  # noqa
    utils,
)
from aprsd_admin_extension.threads import log_monitor

os.environ["APRSD_ADMIN_COMMAND"] = "1"
# this import has to happen AFTER we set the
# above environment variable, so that the code
# inside the wsgi.py has the value
from aprsd_admin_extension import wsgi as admin_wsgi  # noqa


CONF = cfg.CONF
LOG = logging.getLogger("APRSD")
sio = None


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


@cmds.admin.command()
@cli_helper.add_options(cli_helper.common_options)
@click.pass_context
@cli_helper.process_standard_options
def web(ctx):
    """Start the aprsd admin interface."""
    global sio
    signal.signal(signal.SIGINT, aprsd_main.signal_handler)
    signal.signal(signal.SIGTERM, aprsd_main.signal_handler)

    level, msg = utils._check_version()
    if level:
        LOG.warning(msg)
    else:
        LOG.info(msg)
    LOG.info(f"APRSD Started version: {aprsd.__version__}")
    # Dump all the config options now.
    CONF.log_opt_values(LOG, logging.DEBUG)

    server_threads = service.ServiceThreads()
    if CONF.aprsd_admin_extension.web_enabled:
        LOG.warning("Registering LogMonitorThread")
        server_threads.register(log_monitor.LogMonitorThread())

    if CONF.aprsd_admin_extension.web_enabled:
        logger.add(
            QueueHandler(aprsd_log.logging_queue),
            format=CONF.logging.logformat,
            level=ctx.obj["loglevel"],
            colorize=False,
        )

    async_mode = "threading"
    sio = socketio.Server(logger=True, async_mode=async_mode)
    admin_wsgi.app.wsgi_app = socketio.WSGIApp(sio, admin_wsgi.app.wsgi_app)
    admin_wsgi.init_app(socket_io=sio, init_config=False)
    sio.register_namespace(admin_wsgi.LoggingNamespace("/logs"))
    CONF.log_opt_values(LOG, logging.DEBUG)
    admin_wsgi.app.run(
        threaded=True,
        debug=False,
        port=CONF.aprsd_admin_extension.web_port,
        host=CONF.aprsd_admin_extension.web_ip,
    )
