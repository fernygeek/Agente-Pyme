from sqlalchemy import text
from db import SessionLocal  # tu SessionLocal

def test_db_connection():
    with SessionLocal() as db:
        x = db.execute(text("SELECT 1")).scalar_one()
        assert x == 1
    print("OK: Conexión a BD (SELECT 1)")

def test_query_producto():
    with SessionLocal() as db:
        rows = db.execute(text("SELECT TOP (1) id_producto, nombre_prod FROM Producto")).mappings().all()
        assert isinstance(rows, list)
        print("OK: Consulta Producto. Ejemplo:", rows[0] if rows else "Tabla vacía")

if __name__ == "__main__":
    test_db_connection()
    test_query_producto()
