from sqlalchemy import text
from db import SessionRO  # sesión READ-ONLY

def test_db_connection():
    with SessionRO() as db:
        x = db.execute(text("SELECT 1")).scalar_one()
        assert x == 1
    print("OK: Conexión RO a BD (SELECT 1)")

def test_query_producto():
    with SessionRO() as db:
        rows = db.execute(
            text("SELECT TOP (1) id_producto, nombre_prod, marca FROM dbo.Producto ORDER BY id_producto")
        ).mappings().all()
        assert isinstance(rows, list)
        print("OK: Consulta Producto. Ejemplo:", dict(rows[0]) if rows else "Tabla vacía")

def test_query_proveedor():
    with SessionRO() as db:
        rows = db.execute(
            text("SELECT TOP (1) id_proveedor, nombre_empresa FROM dbo.Proveedor ORDER BY id_proveedor")
        ).mappings().all()
        assert isinstance(rows, list)
        print("OK: Consulta Proveedor. Ejemplo:", dict(rows[0]) if rows else "Tabla vacía")

def test_query_movimiento_inventario():
    with SessionRO() as db:
        rows = db.execute(
            text(
                "SELECT TOP (1) id_movimiento, fecha, tipo_movimiento, id_producto, cantidad "
                "FROM dbo.MovimientoInventario ORDER BY fecha DESC"
            )
        ).mappings().all()
        assert isinstance(rows, list)
        print("OK: Consulta MovimientoInventario. Ejemplo:", dict(rows[0]) if rows else "Tabla vacía")

if __name__ == "__main__":
    test_db_connection()
    test_query_producto()
    test_query_proveedor()
    test_query_movimiento_inventario()
