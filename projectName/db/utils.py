import logging
from contextlib import contextmanager
from typing import Any, Iterator

import sqlalchemy as sa
import sqlalchemy.orm as so
from sqlalchemy.engine import Engine

from projectName.db.base import Session

logger = logging.getLogger(__name__)


@contextmanager
def create_session(**kwargs: Any) -> Iterator[so.Session]:
    """Provide a transactional scope around a series of operations."""
    new_session = Session(**kwargs)
    try:
        yield new_session
        new_session.commit()
    except Exception:
        new_session.rollback()
        raise
    finally:
        new_session.close()


def log_overflow(e: Engine) -> None:
    overflow = e.pool.overflow()  # type: ignore

    @sa.event.listens_for(e, 'checkin')
    @sa.event.listens_for(e, 'checkout')
    def pool_evt(dbapi_connection: Any, connection_record: Any, connection_proxy: Any = None) -> None:
        nonlocal overflow
        new_overflow = e.pool.overflow()  # type: ignore
        if new_overflow != overflow:
            size = e.pool.size()  # type: ignore
            checkedin = e.pool.checkedin()  # type: ignore
            checkedout = e.pool.checkedout()  # type: ignore

            if new_overflow > overflow:
                direction = 'incremented'
            else:
                direction = 'decremented'

            e.pool.logger.info(  # type: ignore
                'Pool overflow %s to %s \nsize = %s \ncheckedin = %s \ncheckedout = %s',
                direction,
                new_overflow,
                size,
                checkedin,
                checkedout,
                extra={'size': size, 'checkedin': checkedin, 'checkedout': checkedout, 'overflow': new_overflow},
            )
            overflow = new_overflow
