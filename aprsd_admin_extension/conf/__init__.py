from oslo_config import cfg

from aprsd_admin_extension.conf import main


CONF = cfg.CONF
main.register_opts(CONF)
