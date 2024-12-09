from oslo_config import cfg


extension_group = cfg.OptGroup(
    name="aprsd_admin_extension",
    title="APRSD aprsdadmin extension settings",
)

extension_opts = [
    cfg.BoolOpt(
        "web_enabled",
        default=True,
        help="Enable the Admin Web Interface",
    ),
    cfg.StrOpt(
        "web_ip",
        default="0.0.0.0",
        help="The ip address to listen on",
    ),
    cfg.PortOpt(
        "web_port",
        default=8001,
        help="The port to listen on",
    ),
    cfg.StrOpt(
        "user",
        default="admin",
        help="The admin user for the admin web interface",
    ),
    cfg.StrOpt(
        "password",
        default="password",
        secret=True,
        help="Admin interface password",
    ),
]

ALL_OPTS = extension_opts


def register_opts(cfg):
    cfg.register_group(extension_group)
    cfg.register_opts(ALL_OPTS, group=extension_group)


def list_opts():
    return {
        extension_group.name: extension_opts,
    }
