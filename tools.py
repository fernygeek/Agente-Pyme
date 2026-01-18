from smolagents import tool
from sqlalchemy import text
from db import SessionLocal  # tu SessionLocal
import json

# =========================
# HERRAMIENTAS PERSONALIZADAS
# =========================

# El docstring es importante porque lo usa el framework para generar el esquema JSON
@tool
def respuesta_final(respuesta: str) -> str:
    """Devuelve la respuesta final del agente al usuario.

    Args:
        respuesta (str): texto generado por el agente.

    Returns:
        str: Respuesta final formateada para el usuario
    """
    return f"RESPUESTA FINAL: {respuesta}"


ALLOWED = {
    "producto": {
        "table": "Producto",
        "name_col": "nombre_prod",
        "columns": ["id_producto", "nombre_prod", "marca", "precio_venta", "stock_actual", "stock_minimo", "fecha_entrada", "id_proveedor"],
        "order_by": "nombre_prod",
    },
    "cliente": {
        "table": "Cliente",
        "name_col": "nombre_cli",
        "columns": ["id_cliente", "nombre_cli", "telefono_cli", "direccion_cli", "email"],
        "order_by": "nombre_cli",
    },
    "proveedor": {
        "table": "Proveedor",
        "name_col": "nombre_empresa",
        "columns": ["id_proveedor", "nombre_empresa", "telefono", "email", "direccion", "nombre_vendedor"],
        "order_by": "nombre_empresa",
    },
}

@tool
def consultar(tabla: str, filtro: str = "", limit: int = 10) -> str:
    """Consulta registros de una tabla permitida (producto, cliente, proveedor).

    Args:
        tabla (str): producto | cliente | proveedor
        filtro (str): texto a buscar por nombre (opcional)
        limit (int): máximo de filas a retornar (default 10, máximo 50)

    Returns:
        str: resultados en JSON (lista de filas).
    """
    tabla = tabla.strip().lower()
    if tabla not in ALLOWED:
        return f"Tabla no permitida: {tabla}. Permitidas: {list(ALLOWED.keys())}"

    try:
        limit = int(limit)
    except Exception:
        limit = 10
    limit = max(1, min(limit, 50))

    cfg = ALLOWED[tabla]
    limit = max(1, min(int(limit), 50))

    cols = ", ".join(cfg["columns"])
    where = ""
    params = {"lim": limit}

    if filtro:
        f = filtro.strip()
        # si parece condición SQL, quédate solo con palabras (no condiciones)
        if "=" in f or "'" in f or " AND " in f.upper() or " OR " in f.upper():
            # intenta rescatar la última palabra útil
            f = f.replace("=", " ").replace("'", " ")
            f = " ".join([w for w in f.split() if w.isalpha() or len(w) >= 4])

        where = f"WHERE {cfg['name_col']} LIKE :q"
        params["q"] = f"%{f}%"

    # TOP necesita literal en algunos casos; aquí lo hacemos seguro con params en SQL Server:
    sql = f"""
    SELECT TOP ({limit}) {cols}
    FROM {cfg['table']}
    {where}
    ORDER BY {cfg['order_by']}
    """

    with SessionLocal() as db:
        rows = db.execute(text(sql), params).mappings().all()
        return json.dumps([dict(r) for r in rows], ensure_ascii=False, default=str)