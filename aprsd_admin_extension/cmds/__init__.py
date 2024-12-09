from aprsd.cli_helper import AliasedGroup
from aprsd.main import cli
import click


@cli.group(cls=AliasedGroup, aliases=["admin"], help="APRSD Admin Extension")
@click.pass_context
def admin(ctx):
    pass
