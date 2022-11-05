from logging.config import fileConfig
from typing import Any

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

import projectName.db

config = context.config
target_metadata = config.attributes.get('metadata', None)


def include_symbol(tablename: str, schema: str) -> bool:
    if '_default' in tablename:
        return False

    return True


def _mock_executor(query_to_fetchone: dict[str, Any]) -> None:
    """Добавляет указанным запросам возвращаемое значение и учится работать с sync_enum_values.

    При оффлайн-прогоне миграций op.get_bind() возвращает урезанный объект коннекта:
        sqlalchemy.engine.strategies.MockEngineStrategy.MockConnection

    1. Выполнение запросов этой штукой возвращает None. Но в наших миграциях всё не так просто - иногда мы хотим делать
    SELECT и что-то получать на выход! Для этого надо уметь фетчить результат, иначе:
        AttributeError: 'NoneType' object has no attribute 'fetchone'

    2. А ещё внутри alembic_autogenerate_enums.sync_enum_values объект этого класса используется как менеджер
    контекста, к чему его жизнь не готовила, и мы исправляем это досадное недоразумение.

    Именно для этих целей мы и мокаем замоканный коннект.
    """
    from sqlalchemy.engine.strategies import MockEngineStrategy

    class ResultOfSelect:
        def __init__(self, fetchone: Any) -> None:
            self._fetchone = fetchone

        def fetchone(self) -> Any:
            return self._fetchone

    class MockedMockConnection(MockEngineStrategy.MockConnection):  # type: ignore
        def __init__(self, dialect, execute):  # type: ignore
            self._dialect = dialect
            self._origin_execute = execute

        def execute(self, query, *multiparams, **params):  # type: ignore
            self._origin_execute(query, *multiparams, **params)

            if query in query_to_fetchone:
                return ResultOfSelect(query_to_fetchone[query])

            return None

        def __enter__(self) -> 'MockedMockConnection':
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):  # type: ignore
            pass

    MockEngineStrategy.MockConnection = MockedMockConnection

def run_migrations_offline() -> None:
    connectable = config.attributes['engine']

    with connectable.connect() as connection:
        schema = connection.execute('SELECT current_schema();').scalar()
        config.attributes['schema'] = schema

        is_grafanareader_exists = schema != 'chatbot_dp'
        _mock_executor({"SELECT 1 FROM pg_roles WHERE rolname='grafanareader'": is_grafanareader_exists})

        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_symbol=include_symbol,
            literal_binds=True,
        )

        with context.begin_transaction():
            context.run_migrations()


def run_migrations_online() -> None:
    connectable = config.attributes['engine']

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_symbol=include_symbol,
        )

        with context.begin_transaction():
            config.attributes['schema'] = connection.execute('SELECT current_schema();').scalar()
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
