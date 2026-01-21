from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import os
from typing import Optional, Dict, List

ODBC_DRIVER = os.getenv("ODBC_DRIVER", "ODBC Driver 17 for SQL Server")
SERVER = os.getenv("DB_SERVER", "LAPTOP-DF414H36")
DB_NAME = os.getenv("DB_NAME", "PymeDb")

# ===========
# READ ONLY
# ===========
DB_RO_USER = os.getenv("DB_RO_USER", "pyme_readonly")
DB_RO_PASS = os.getenv("DB_RO_PASS", "Clave123")

DB_RO_URL = os.getenv(
    "DB_RO_URL",
    f"mssql+pyodbc://{DB_RO_USER}:{DB_RO_PASS}@{SERVER}/{DB_NAME}"
    f"?driver={ODBC_DRIVER.replace(' ', '+')}"
    "&TrustServerCertificate=yes"
)

# ===========
# READ WRITE (para endpoints de ventas/compras)
# ===========
DB_RW_USER = os.getenv("DB_RW_USER", "pyme_rw")
DB_RW_PASS = os.getenv("DB_RW_PASS", "Admin123")

DB_RW_URL = os.getenv(
    "DB_RW_URL",
    f"mssql+pyodbc://{DB_RW_USER}:{DB_RW_PASS}@{SERVER}/{DB_NAME}"
    f"?driver={ODBC_DRIVER.replace(' ', '+')}"
    "&TrustServerCertificate=yes"
)

engine_ro = create_engine(DB_RO_URL, pool_pre_ping=True, future=True)
engine_rw = create_engine(DB_RW_URL, pool_pre_ping=True, future=True)

SessionRO = sessionmaker(autocommit=False, autoflush=False, bind=engine_ro, future=True)
SessionRW = sessionmaker(autocommit=False, autoflush=False, bind=engine_rw, future=True)

def query_all_ro(sql: str, params: Optional[Dict] = None) -> List[Dict]:
    """Solo lectura (para el agente)."""
    with SessionRO() as db:
        rows = db.execute(text(sql), params or {}).mappings().all()
        return [dict(r) for r in rows]

def exec_rw(sql: str, params: Optional[Dict] = None) -> int:
    """
    Para endpoints RW (ventas/compras).
    Devuelve rowcount. OJO: aquí SÍ se modifica la BD.
    """
    with SessionRW() as db:
        res = db.execute(text(sql), params or {})
        db.commit()
        return res.rowcount
