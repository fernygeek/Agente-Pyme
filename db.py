from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

ODBC_DRIVER = "ODBC Driver 17 for SQL Server"

DATABASE_URL = (
    "mssql+pyodbc://@LAPTOP-DF414H36/PymeDb"
    f"?driver={ODBC_DRIVER.replace(' ', '+')}"
    "&trusted_connection=yes"
    "&TrustServerCertificate=yes"
)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def query_all(sql: str, params: dict | None = None) -> list[dict]:
    with SessionLocal() as db:
        rows = db.execute(text(sql), params or {}).mappings().all()
        return [dict(r) for r in rows]
