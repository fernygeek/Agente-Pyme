# tools.py
from smolagents import tool
from sqlalchemy import text
from db import SessionRO  # sesión READ-ONLY
import json
import re

# =========================
# HERRAMIENTAS PERSONALIZADAS
# =========================

@tool
def respuesta_final(respuesta: str) -> str:
    """Devuelve la respuesta final del agente al usuario.

    Args:
        respuesta (str): Mensaje final que se mostrará al usuario.

    Returns:
        str: Respuesta final formateada para el usuario.
    """
    return f"RESPUESTA FINAL: {respuesta}"


# -------------------------
# Utilidades internas
# -------------------------

def _safe_limit(limit: int) -> int:
    """Normaliza el límite a un rango seguro 1..50."""
    try:
        limit = int(limit)
    except Exception:
        limit = 10
    return max(1, min(limit, 50))


def _sanitize_filtro(filtro: str) -> str:
    """Evita que el filtro parezca condición SQL o contenga tokens peligrosos."""
    if not filtro:
        return ""
    f = filtro.strip()

    # Bloquea tokens típicos de inyección / condiciones
    bad_tokens = [";", "--", "/*", "*/", " xp_", " sp_", " and ", " or ", "=", "'"]
    f_low = f.lower()
    if any(t in f_low for t in bad_tokens):
        f = f.replace("=", " ").replace("'", " ").replace(";", " ")
        f = f.replace("--", " ").replace("/*", " ").replace("*/", " ")
        # conserva palabras "útiles"
        f = " ".join([w for w in f.split() if w.isalpha() or len(w) >= 3])

    # recorta espacios múltiples
    f = re.sub(r"\s+", " ", f).strip()
    return f


# Mini diccionario EN -> ES (para evitar el caso "brake kit" vs "kit de embrague")
SYNONYMS = {
    "brake": "freno",
    "brakes": "frenos",
    "clutch": "embrague",
    "kit": "kit",
    "filter": "filtro",
    "oil": "aceite",
    "air": "aire",
    "fuel": "combustible",
    "shock": "amortiguador",
    "battery": "batería",
    "pads": "pastillas",
    "disc": "disco",
    "spark": "spark",  # lo dejamos igual por modelos (Chevrolet Spark)
    "tucson": "tucson",
    "hilux": "hilux",
    "sentra": "sentra",
    "aveo": "aveo",
    "dmax": "dmax",
    "rio": "rio",
}

def _normalize_filter(f: str) -> str:
    """Normaliza el filtro: limpia y reemplaza algunos términos EN->ES."""
    f = _sanitize_filtro(f)
    if not f:
        return ""

    # separa por espacios y puntuación simple
    words = re.split(r"[\s/\\\-\_\.\,\;\:\(\)\[\]\{\}\"]+", f)
    out = []
    for w in words:
        if not w:
            continue
        key = w.lower()
        out.append(SYNONYMS.get(key, w))
    return " ".join(out).strip()


# -------------------------
# Config de tablas permitidas
# -------------------------
ALLOWED = {
    "producto": {
        "table": "Producto",
        "name_col": "nombre_prod",
        "columns": [
            "id_producto", "nombre_prod", "descripcion", "marca",
            "precio_venta", "costo_compra",
            "stock_actual", "stock_minimo",
            "fecha_entrada", "id_proveedor"
        ],
        "order_by": "nombre_prod",
    },
    "proveedor": {
        "table": "Proveedor",
        "name_col": "nombre_empresa",
        "columns": [
            "id_proveedor", "nombre_empresa",
            "telefono", "email", "direccion", "nombre_vendedor"
        ],
        "order_by": "nombre_empresa",
    },
    "movimiento_inventario": {
        "table": "MovimientoInventario",
        "name_col": "observacion",
        "columns": [
            "id_movimiento", "fecha", "tipo_movimiento",
            "id_producto", "cantidad", "observacion"
        ],
        "order_by": "fecha DESC",
    },
}


@tool
def consultar(tabla: str, filtro: str = "", limit: int = 10) -> str:
    """Consulta información de la base de datos de la PyME de repuestos automotrices.

    Args:
        tabla (str): Tabla lógica a consultar. Permitidas:
            - "producto"
            - "proveedor"
            - "movimiento_inventario"
        filtro (str): Texto para filtrar (opcional).
        limit (int): Máximo de registros a retornar (1 a 50).

    Returns:
        str: Resultado de la consulta en formato JSON (lista de registros).
    """
    tabla = (tabla or "").strip().lower()
    if tabla not in ALLOWED:
        return json.dumps(
            {"error": f"Tabla no permitida: {tabla}", "permitidas": list(ALLOWED.keys())},
            ensure_ascii=False
        )

    limit = _safe_limit(limit)
    cfg = ALLOWED[tabla]

    cols = ", ".join(cfg["columns"])
    where = ""
    params = {}

    f = _normalize_filter(filtro) if filtro else ""

    if f:
        if tabla == "producto":
            # Buscar por nombre, descripción y marca
            where = """
            WHERE (nombre_prod LIKE :q OR descripcion LIKE :q OR marca LIKE :q)
            """
            params["q"] = f"%{f}%"

        elif tabla == "movimiento_inventario":
            # Si el filtro coincide con un tipo, filtramos por tipo_movimiento
            tipos = {"ENTRADA_COMPRA", "SALIDA_VENTA", "OTROS", "ENTRADA_AJUSTE"}
            if f.upper() in tipos:
                where = "WHERE tipo_movimiento = :t"
                params["t"] = f.upper()
            else:
                where = f"WHERE {cfg['name_col']} LIKE :q"
                params["q"] = f"%{f}%"

        else:
            where = f"WHERE {cfg['name_col']} LIKE :q"
            params["q"] = f"%{f}%"

    sql = f"""
    SELECT TOP ({limit}) {cols}
    FROM dbo.{cfg['table']}
    {where}
    ORDER BY {cfg['order_by']}
    """

    with SessionRO() as db:
        rows = db.execute(text(sql), params).mappings().all()
        return json.dumps([dict(r) for r in rows], ensure_ascii=False, default=str)