import os

# Tests run against SQLite in a temp file: no Postgres needed in CI, and a
# fresh schema per run keeps them order-independent.
os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///./test_finn.db")
os.environ.setdefault("DATA_MODE", "seed")
os.environ.setdefault("LLM_PROVIDER", "null")
os.environ.setdefault("SCHEDULER_ENABLED", "false")
