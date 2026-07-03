from sqlalchemy import text


def test_file_sqlite_enables_wal_and_busy_timeout(tmp_path):
    from app.db import make_engine
    eng = make_engine(f"sqlite+pysqlite:///{tmp_path}/t.db")
    with eng.connect() as c:
        assert c.execute(text("PRAGMA journal_mode")).scalar() == "wal"
        assert c.execute(text("PRAGMA busy_timeout")).scalar() == 5000


def test_memory_sqlite_still_works():
    from app.db import make_engine
    eng = make_engine("sqlite+pysqlite:///:memory:")
    with eng.connect() as c:
        assert c.execute(text("select 1")).scalar() == 1
