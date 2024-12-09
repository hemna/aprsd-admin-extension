import click

from aprsd.cli_helper import AliasedGroup
from aprsd.main import cli


@cli.group(cls=AliasedGroup, aliases=['aprsdadmin'], help="APRSD Admin Extension")
@click.pass_context
def aprsdadmin(ctx):
    pass
