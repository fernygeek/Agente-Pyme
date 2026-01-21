from smolagents import tool
from sqlalchemy import text
from db import SessionRO
import json
import re

# =========================
# UTILIDADES
# =========================

def _safe_limit(limit) -> int:
    try:
        limit = int(limit)
    except Exception:
        limit = 10
    return max(1, min(limit, 50))


def _sanitize_like(texto: str) -> str:
    """Higiene anti-inyección para usar SOLO en LIKE."""
    if not texto:
        return ""
    t = texto.strip()

    # limpia tokens peligrosos
    t = re.sub(r"[;'\"]|--|/\*|\*/|=", " ", t)
    t = re.sub(r"\s+", " ", t).strip()

    # typo común
    t = t.replace("embriague", "embrague")
    return t


ALLOWED = {
    "producto": {
        "table": "dbo.Producto",
        "columns": [
            "id_producto","nombre_prod","descripcion","marca",
            "precio_venta","costo_compra","stock_actual","stock_minimo",
            "fecha_entrada","id_proveedor"
        ],
        "search_cols": ["nombre_prod", "descripcion", "marca"],
        "order_by": "nombre_prod",
    },
    "proveedor": {
        "table": "dbo.Proveedor",
        "columns": [
            "id_proveedor","nombre_empresa","telefono","email","direccion","nombre_vendedor"
        ],
        "search_cols": ["nombre_empresa", "nombre_vendedor"],
        "order_by": "nombre_empresa",
    },
    "movimiento_inventario": {
        "table": "dbo.MovimientoInventario",
        "columns": [
            "id_movimiento","fecha","tipo_movimiento","id_producto","cantidad","observacion"
        ],
        "search_cols": ["observacion", "tipo_movimiento"],
        "order_by": "fecha DESC",
    },
}


@tool
def respuesta_final(respuesta: str) -> str:
    """
    Devuelve la respuesta final del agente al usuario.

    Args:
        respuesta (str): Mensaje final que se mostrará al usuario.

    Returns:
        str: Respuesta final formateada para el usuario.
    """
    return f"RESPUESTA FINAL: {respuesta}"


def _run_query(tabla: str, filtro: str, limit: int, modo: str) -> list[dict]:
    cfg = ALLOWED[tabla]
    limit = _safe_limit(limit)
    modo = (modo or "buscar").strip().lower()

    cols = ", ".join(cfg["columns"])

    # LISTAR: ignora filtro
    if modo == "listar":
        sql = f"""
        SELECT TOP ({limit}) {cols}
        FROM {cfg['table']}
        ORDER BY {cfg['order_by']}
        """
        with SessionRO() as db:
            rows = db.execute(text(sql), {}).mappings().all()
            return [dict(r) for r in rows]

    # BUSCAR: aplica LIKE sobre varias columnas
    f = _sanitize_like(filtro)
    if not f:
        # si no hay filtro, devolvemos TOP igual (pero es "buscar" vacío)
        sql = f"""
        SELECT TOP ({limit}) {cols}
        FROM {cfg['table']}
        ORDER BY {cfg['order_by']}
        """
        with SessionRO() as db:
            rows = db.execute(text(sql), {}).mappings().all()
            return [dict(r) for r in rows]

    params = {}
    ors = []
    for i, col in enumerate(cfg["search_cols"]):
        k = f"q{i}"
        ors.append(f"{col} LIKE :{k}")
        params[k] = f"%{f}%"

    where = "WHERE " + " OR ".join(ors)

    sql = f"""
    SELECT TOP ({limit}) {cols}
    FROM {cfg['table']}
    {where}
    ORDER BY {cfg['order_by']}
    """

    with SessionRO() as db:
        rows = db.execute(text(sql), params).mappings().all()
        return [dict(r) for r in rows]


@tool
def consultar(tabla: str, filtro: str = "", limit: int = 10, modo: str = "buscar") -> str:
    """
    Consulta SOLO LECTURA a la base de datos (PyME repuestos automotrices).

    Args:
        tabla (str): Tabla lógica a consultar.
            Valores permitidos: "producto", "proveedor", "movimiento_inventario", "auto".
        filtro (str): Texto libre para buscar (solo se usa si modo="buscar").
        limit (int): Máximo de registros a retornar (1..50).
        modo (str): "buscar" para filtrar por texto (LIKE), o "listar" para listar sin filtro.

    Returns:
        str: JSON con lista de filas o, si tabla="auto", un objeto con resultados por tabla.
    """
    tabla = (tabla or "").strip().lower()
    modo = (modo or "buscar").strip().lower()

    if tabla == "auto":
        # En auto: si modo="listar", listamos de cada tabla (TOP limit)
        # En auto: si modo="buscar", buscamos en orden: producto, proveedor, movimientos
        order = ["producto", "proveedor", "movimiento_inventario"]
        out = {}

        for t in order:
            rows = _run_query(t, filtro, limit, modo)
            if rows:
                out[t] = rows

        if not out:
            return json.dumps({"mensaje": "No se encontraron coincidencias."}, ensure_ascii=False)

        return json.dumps(out, ensure_ascii=False, default=str)

    if tabla not in ALLOWED:
        return json.dumps(
            {"error": f"Tabla no permitida: {tabla}", "permitidas": list(ALLOWED.keys()) + ["auto"]},
            ensure_ascii=False
        )

    rows = _run_query(tabla, filtro, limit, modo)
    return json.dumps(rows, ensure_ascii=False, default=str)


@tool
def productos_bajo_stock(limit: int = 10) -> str:
    """
    Lista productos con bajo stock (stock_actual <= stock_minimo).

    Args:
        limit: Máximo de productos a retornar (1..50).

    Returns:
        JSON con lista de productos bajo stock.
    """
    try:
        limit = int(limit)
    except Exception:
        limit = 10
    limit = max(1, min(limit, 50))

    sql = f"""
    SELECT TOP ({limit})
        id_producto, nombre_prod, marca,
        stock_actual, stock_minimo, precio_venta
    FROM dbo.Producto
    WHERE stock_actual <= stock_minimo
    ORDER BY (stock_minimo - stock_actual) DESC, nombre_prod
    """

    with SessionRO() as db:
        rows = db.execute(text(sql)).mappings().all()
        return json.dumps([dict(r) for r in rows], ensure_ascii=False, default=str)