from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from smolagents import ToolCallingAgent, LiteLLMModel
import time
import json
import logging
import asyncio
from starlette.concurrency import run_in_threadpool
import uuid
import warnings

from tools import respuesta_final, consultar


# =========================
# LLM + AGENTE
# =========================
llm = LiteLLMModel(
    model_id="ollama_chat/qwen3:1.7b",  # el modelo en Ollama
    api_base="http://localhost:11434",  # Ollama local
    api_key="ollama",                   # api_key dummy
    temperature=0.2,
    response_format={"type": "json_object"},  # fuerza JSON cuando llama tools
)

agent = ToolCallingAgent(
    tools=[respuesta_final, consultar],
    model=llm,
    max_steps=4,  # pasos en el razonamiento
)

# =========================
# INSTRUCCIONES DEL AGENTE
# =========================
instrucciones = (
    "Eres un agente asistente de una PyME dedicada a la venta de repuestos automotrices en Ecuador. "
    "Tu función es apoyar la gestión del negocio (inventario, proveedores y movimientos de inventario) "
    "y brindar información y sugerencias comerciales SOLO dentro de este contexto.\n\n"

    "IDIOMA OBLIGATORIO:\n"
    "- Responde SIEMPRE en español latino (neutral).\n"
    "- Usa un lenguaje claro, profesional y comprensible para un negocio de repuestos automotrices.\n\n"

    "MONEDA Y UNIDADES (OBLIGATORIO):\n"
    "- La moneda oficial del sistema es DÓLARES ESTADOUNIDENSES (USD) y se representa con '$'.\n"
    "- Todos los precios, costos, totales y montos deben mostrarse exclusivamente en USD.\n"
    "- Si el usuario menciona otra moneda (EUR, etc.), NO conviertas automáticamente.\n"
    "- Solo realiza conversión si el usuario lo solicita explícitamente; si no indica el tipo de cambio, "
    "debes pedirlo o aclarar el supuesto antes de convertir.\n\n"

    "DOMINIO PERMITIDO:\n"
    "- Información obtenida ÚNICAMENTE de la base de datos del negocio "
    "(Producto, Proveedor, MovimientoInventario).\n"
    "- Consultas de inventario: stock actual, stock mínimo, precios, entradas/salidas y movimientos.\n"
    "- Sugerencias relacionadas con reposición, rotación de inventario, productos bajo mínimo "
    "y atención al cliente en una PyME de repuestos automotrices.\n\n"

    "FUERA DE CONTEXTO:\n"
    "- Si el usuario pregunta sobre temas ajenos al negocio (clima, chistes, política, "
    "noticias generales, temas personales, etc.), responde EXACTAMENTE:\n"
    "\"La pregunta está fuera del contexto del sistema\".\n\n"

    "HERRAMIENTAS DISPONIBLES:\n"
    "- consultar(tabla, filtro, limit): consulta información de la base de datos "
    "(tabla: producto | proveedor | movimiento_inventario).\n"
    "- respuesta_final(respuesta): devuelve la respuesta final al usuario.\n\n"

    "REGLAS DE CONSULTA (OBLIGATORIO):\n"
    "- Usa la herramienta consultar SOLO cuando necesites datos reales de la base de datos.\n"
    "- No inventes información que no esté en los resultados devueltos.\n"
    "- Limita los resultados entre 5 y 10 por defecto, salvo que el usuario pida otro valor.\n"
    "- No uses herramientas si la pregunta está fuera del dominio permitido.\n\n"

    "REGLAS DE RESPUESTA PARA PRODUCTOS (MUY IMPORTANTE):\n"
    "- Cuando consultes la tabla Producto, SIEMPRE responde listando los resultados con este formato:\n"
    "  • nombre_prod | marca | stock_actual (unidades)\n"
    "- Si el nombre del producto incluye un vehículo o modelo (ej. Toyota Hilux, Chevrolet Aveo), "
    "debes mencionarlo explícitamente en la respuesta.\n"
    "- No respondas de forma genérica (ej. 'sí hay productos'). Siempre muestra el nombre exacto del producto.\n"
    "- Si hay varios productos, enuméralos y luego da un breve resumen.\n"
    "- Si no hay resultados, indícalo claramente.\n\n"

    "FORMATO DE USO DE HERRAMIENTAS:\n"
    "- Si vas a usar una herramienta, responde EXCLUSIVAMENTE con un objeto JSON "
    "con las claves \"tool_name\" y \"tool_args\".\n"
    "- Si no usas herramientas, responde SOLO texto.\n\n"

    "ENTREGA FINAL:\n"
    "- Siempre finaliza usando la herramienta 'respuesta_final'.\n"
    "- La respuesta final debe estar en español latino, clara y orientada al negocio.\n\n"
)

# =========================
# LOGS
# =========================
LOG_FILE = "monitoreo.log"

logger = logging.getLogger("agent_logger")
logger.setLevel(logging.INFO)

# Evita duplicados
logger.propagate = False

if not logger.handlers:
    file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)


def log_response(*, req_id: str, question: str, answer: str, latency_ms: float):
    logger.info(
        "REQ=%s | QUESTION=%s | LATENCY_MS=%.2f | ANSWER=%s",
        req_id,
        question,
        latency_ms,
        (answer or "").replace("\n", " | ")
    )

# =========================
# CONCURRENCIA
# =========================
LLM_SEM = asyncio.Semaphore(3)  # máximo 3 llamadas LLM simultáneas

async def call_llm_safely(fn, *args, req_id: str, **kwargs):
    t_wait = time.perf_counter()
    logger.info("REQ=%s | LLM_QUEUE_ENTER", req_id)

    async with LLM_SEM:
        wait_ms = (time.perf_counter() - t_wait) * 1000
        logger.info("REQ=%s | LLM_START | WAIT_MS=%.2f", req_id, wait_ms)

        t_run = time.perf_counter()
        result = await run_in_threadpool(fn, *args, **kwargs)
        run_ms = (time.perf_counter() - t_run) * 1000

        logger.info("REQ=%s | LLM_END | RUN_MS=%.2f", req_id, run_ms)
        return result

# ================================
# NORMALIZAR RESULTADO A TEXTO
# ================================
def to_answer_text(result) -> str:
    if isinstance(result, str):
        return result

    content = getattr(result, "content", None)
    if isinstance(content, str):
        return content

    if isinstance(result, dict):
        return json.dumps(result, ensure_ascii=False)

    return str(result)

# =========================
# SILENCIAR WARNINGS (LiteLLM)
# =========================
warnings.filterwarnings(
    "ignore",
    message=r"Pydantic serializer warnings:.*",
    category=UserWarning,
)

warnings.filterwarnings(
    "ignore",
    message=r".*PydanticSerializationUnexpectedValue.*",
    category=UserWarning,
)

# =========================
# FASTAPI
# =========================
app = FastAPI(title="Agente Pyme API (Repuestos Automotrices)")

class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, description="Pregunta del usuario")

class AskResponse(BaseModel):
    question: str
    answer: str

# =========================
# ENDPOINT
# =========================
@app.post("/ask", response_model=AskResponse)
async def ask(req: AskRequest):
    start = time.perf_counter()
    req_id = str(uuid.uuid4())[:8]

    try:
        prompt = instrucciones + req.question
        result = await call_llm_safely(agent.run, prompt, req_id=req_id)

        latency_ms = (time.perf_counter() - start) * 1000
        answer = to_answer_text(result)

        log_response(
            req_id=req_id,
            question=req.question,
            answer=answer,
            latency_ms=latency_ms
        )

        return AskResponse(question=req.question, answer=answer)

    except Exception as e:
        latency_ms = (time.perf_counter() - start) * 1000
        err_id = str(uuid.uuid4())[:8]
        log_response(
            req_id=err_id,
            question=req.question,
            answer=f"ERROR: {e}",
            latency_ms=latency_ms,
        )
        raise HTTPException(status_code=500, detail=f"Error ejecutando el agente: {e}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("agente_pyme:app", reload=True)