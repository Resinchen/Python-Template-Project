import enum
import socket
from typing import Any

from pydantic import BaseModel, BaseSettings, Field, validator
from sqlalchemy.engine import Engine
from sqlalchemy.engine.url import URL, make_url
from sqlalchemy.exc import ArgumentError
from sqlalchemy.pool import AssertionPool, NullPool, QueuePool, SingletonThreadPool, StaticPool
from projectName.db import log_overflow
from projectName.db.serializers import JsonSerializer

class SAUrl(URL):
    @classmethod
    def __get_validators__(cls):  # type: ignore
        yield cls.validate

    @classmethod
    def validate(cls, v: str) -> URL:
        try:
            return make_url(v)
        except ArgumentError as e:
            raise ValueError from e


class PoolClass(enum.Enum):
    QUEUE_POOL = QueuePool
    SINGLETON_THREADPOOL = SingletonThreadPool
    STATIC_POOL = StaticPool
    NULL_POOL = NullPool
    ASSERTION_POOL = AssertionPool


class BaseDBModel(BaseModel):
    url: SAUrl = Field(
        SAUrl.validate('postgresql://postgres:postgres@localhost/postgres'),
        description='https://docs.sqlalchemy.org/en/13/core/engines.html#engine-creation-api',
    )
    pool_recycle: int = Field(
        500, description='https://docs.sqlalchemy.org/en/13/core/engines.html#engine-creation-api'
    )
    pool_size: int = Field(10, description='https://docs.sqlalchemy.org/en/13/core/engines.html#engine-creation-api')
    echo: bool = Field(False, description='https://docs.sqlalchemy.org/en/13/core/engines.html#engine-creation-api')
    pool_overflow: int = Field(
        10, description='https://docs.sqlalchemy.org/en/13/core/engines.html#engine-creation-api'
    )
    pool_lifo: bool = Field(True, description='https://docs.sqlalchemy.org/en/13/core/engines.html#engine-creation-api')
    application_name: str = socket.gethostname()
    connection_timeout: int = 30
    pool_timeout: int = 5
    poolclass: PoolClass = PoolClass.QUEUE_POOL
    pool_pre_ping: bool = True
    connect_args: dict[str, Any] = {}
    query_cache_size: int = 1000

    @validator('poolclass', pre=True, always=True)
    def poolclass_validator(cls, v: str | PoolClass) -> PoolClass:
        if isinstance(v, PoolClass):
            return v
        value: PoolClass = getattr(PoolClass, v)
        if value is None:
            raise ValueError('Incorrect poolclass for DB engine')
        return value

    @staticmethod
    def _clear_unusable_args_from_kwargs(fail_args: set[str], kwargs: dict[str, Any]) -> dict[str, Any]:
        for arg in fail_args:
            if kwargs.get(arg):
                kwargs.pop(arg)

        return kwargs

    def create_engine(self, **kwargs: Any) -> Engine:
        from sqlalchemy import engine_from_config

        self.connect_args.setdefault('connect_timeout', self.connection_timeout)
        self.connect_args.setdefault('application_name', self.application_name)

        config = {
            'url': self.url,
            'echo': self.echo,
            'pool_recycle': self.pool_recycle,
            'pool_timeout': self.pool_timeout,
            'pool_pre_ping': self.pool_pre_ping,
            'pool_size': self.pool_size,
            'poolclass': self.poolclass.value,
            'connect_args': self.connect_args,
            'query_cache_size': self.query_cache_size,
            'pool_use_lifo': self.pool_lifo,
            'max_overflow': self.pool_overflow,
            'json_serializer': JsonSerializer,
            'executemany_mode': 'values',
            **kwargs,
        }
        if self.poolclass == PoolClass.SINGLETON_THREADPOOL:
            fail_args = {'pool_timeout', 'pool_use_lifo', 'max_overflow'}
            config = self._clear_unusable_args_from_kwargs(fail_args, config)
        if self.poolclass in {PoolClass.NULL_POOL, PoolClass.ASSERTION_POOL, PoolClass.STATIC_POOL}:
            fail_args = {'pool_timeout', 'pool_size', 'pool_use_lifo', 'max_overflow'}
            config = self._clear_unusable_args_from_kwargs(fail_args, config)

        return engine_from_config(config, prefix='')

    def setup_db(self) -> None:
        pass


class SomeDBSettings(BaseDBModel, BaseSettings):
    class Config:
        env_prefix = 'CPTG_DB_'

    def setup_db(self) -> None:
        from projectName.db import metadata

        engine = self.create_engine()
        if self.poolclass == PoolClass.QUEUE_POOL:
            log_overflow(engine)

        metadata.bind = self.create_engine()