import typer

from projectName.cli.app import main_app
from projectName.cli.db import db
from projectName.cli.utils import utils_app

main_app_click = typer.main.get_command(main_app)
main_app_click.add_command(db)  # type: ignore

main_app = main_app_click  # type: ignore
