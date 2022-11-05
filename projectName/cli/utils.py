from typer import Typer, echo

from projectName.cli import main_app

utils_app = Typer(name='utils', help='Различные полезные многоразовые команды')
main_app.add_typer(utils_app)

@utils_app.command(name='kek')
def kek() -> None:
    echo('Lol kek...')
