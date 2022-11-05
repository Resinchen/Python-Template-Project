from pathlib import Path
from types import ModuleType
from typing import Callable, Optional, cast

import alembic.command
import click
from alembic.config import Config
from alembic.script import Script
from click import Command, Group
from sqlalchemy import MetaData
from sqlalchemy.engine import Engine



def get_versions_path(db: ModuleType) -> str:
    return str(Path(db.__file__).parent / 'versions')


def get_env_path(alembic_module: ModuleType) -> str:
    return str(Path(alembic_module.__file__).parent)


def prepare_config(
    engine: Engine,
    metadata: MetaData,
    version_locations: str,
    script_location: str,
    command_name: Optional[str] = None,
    file_template: str = '%%(year)d_%%(month).2d_%%(day).2d_%%(rev)s_%%(slug)s',
) -> Config:
    config = Config()
    config.attributes["engine"] = engine
    config.attributes["metadata"] = metadata
    if command_name:
        config.attributes["command_name"] = command_name
    config.set_main_option("version_locations", version_locations)
    config.set_main_option('script_location', script_location)
    config.set_main_option('file_template', file_template)

    return config


@click.group(help='Команды для управления миграциями')
@click.pass_obj
def manage(config: Config) -> None:
    config.set_section_option('post_write_hooks', 'hooks', 'isort, black')

    config.set_section_option('post_write_hooks', 'isort.type', 'console_scripts')
    config.set_section_option('post_write_hooks', 'isort.entrypoint', 'isort')

    config.set_section_option('post_write_hooks', 'black.type', 'console_scripts')
    config.set_section_option('post_write_hooks', 'black.entrypoint', 'black')
    config.set_section_option('post_write_hooks', 'black.options', '--skip-string-normalization')


SQL_FLAG_HELP = """Сгенерировать raw-sql перехода между версиями без его применения на базу (default: False).

Из-за нюансов наших миграций (например, всякой магии с рефлексией схемы) эта опция работает корректно не для всех
миграций.

По дефолту генерирует историю для всех миграций от initial до <REVISION_NAME>. Чтобы посмотреть sql-дифф между двумя
версиями базы, нужно указать две <REVISION_NAME>, например, для upgrade: 2e12d64a02a0:881bf3e31506
(для downgrade наоборот: 881bf3e31506:2e12d64a02a0).
"""


@manage.command(help='Обновить бд до указанной версии')
@click.argument("revision_name", required=True)
@click.option("--sql", is_flag=True, default=False, help=SQL_FLAG_HELP)
@click.pass_obj
def upgrade(config: Config, revision_name: str, sql: bool) -> None:
    """
    Надо указать revision_name, обязательне поле, можно использовать head - последняя ревизия.
    последнюю ревизию можно глянуть в (project_name) db manage history
    """
    click.echo(f'Upgrading database to {revision_name}')

    alembic.command.upgrade(config, revision_name, sql=sql)
    click.echo('Successfully upgraded')


@manage.command(help='Откатить бд до нужной версии')
@click.argument("revision_name", required=True)
@click.option("--sql", is_flag=True, default=False, help=SQL_FLAG_HELP)
@click.pass_obj
def downgrade(config: Config, revision_name: str, sql: bool) -> None:
    click.echo(f'Downgrading database to {revision_name}')

    alembic.command.downgrade(config, revision_name, sql=sql)
    click.echo('Successfully downgraded')


@manage.command(help='Создать миграцию')
@click.option("--message", "-m", help="Message string to use with the revision", required=True)
@click.pass_obj
def revision(config: Config, message: str) -> None:
    click.echo(f'Check revision with message {message}')
    script = cast(Script, alembic.command.revision(config, message=message, autogenerate=True))
    version_folder = Path(cast(str, config.get_main_option('version_locations')))
    with open(version_folder / 'last_version.txt', 'w') as f:
        f.write(script.revision)
    click.echo('New migration was successfully created')


@manage.command(help='Информация о текущей версии бд')
@click.pass_obj
def current(config: Config) -> None:
    alembic.command.current(config, verbose=True)


@manage.command()
@click.pass_obj
def history(config: Config) -> None:
    alembic.command.history(config, verbose=True)


@click.command(short_help='Создать все таблицы из моделей алхимии')
@click.pass_obj
def create_all(config: Config) -> None:
    click.echo('creating')
    config.attributes["metadata"].create_all()
    click.echo('complete!')


@click.command(short_help='Дропнуть базу')
@click.pass_obj
def drop_all(config: Config) -> None:
    click.confirm('it really need?', abort=True)
    click.echo('dropping')
    meta = config.attributes["metadata"]
    engine = config.attributes["engine"]
    for table in meta.tables:
        engine.execute(f'DROP TABLE IF EXISTS "{table}" CASCADE')
    engine.execute('DROP TABLE IF EXISTS alembic_version')
    engine.execute('DROP SCHEMA IF EXISTS huey')
    meta.drop_all()
    click.echo('complete!')


def create_cli(*commands: Command) -> Callable[[Group], Group]:
    def add_to_group(db: Group) -> Group:
        for command in commands:
            db.add_command(command)

        return db

    return add_to_group


@create_cli(manage, create_all, drop_all)
@click.group(short_help='Команды для создания и дропа таблиц в бд и управления миграциями')
@click.pass_context
def db(ctx: click.Context) -> None:
    """Команды для создания и дропа таблиц в бд."""
    import projectName.db as current_db
    import projectName.db.alembic
    from projectName.config.db import SomeDBSettings
    from projectName.db import metadata

    settings = SomeDBSettings()
    settings.setup_db()
    ctx.obj = prepare_config(
        settings.create_engine(),
        metadata,
        version_locations=get_versions_path(current_db),
        script_location=get_env_path(projectName.db.alembic),
    )
