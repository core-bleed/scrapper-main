import pytest

from sdr_cli.db import get_connection, init_db


@pytest.fixture
def db_conn():
    conn = get_connection(":memory:")
    init_db(conn)
    yield conn
    conn.close()
