import libsql
import pytest

from rokkini import db


@pytest.fixture
def conn(tmp_path):
    db_file = tmp_path / "test.db"
    connection = libsql.connect(database=str(db_file))
    connection.execute("PRAGMA foreign_keys = ON")
    db.apply_schema(connection)
    yield connection
    connection.close()


@pytest.fixture
def admin_id(conn):
    return db.insert_utente(
        conn,
        username="admin",
        nome_visualizzato="Admin",
        password_hash="x",
        ruolo="super_admin",
    )
