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
    model_id="ollama_chat/qwen3:1.7b", # el modelo en Ollma
    api_base="http://localhost:11434", # Ollama local
    api_key="ollama",                  # api_key dummy
    temperature=0.2,
    response_format={"type": "json_object"}, # fuerza JSON
)

agent = ToolCallingAgent(
    tools=[respuesta_final, consultar],
    model=llm,
    max_steps=4, #pasos en el razonamiento
)

#instrucciones del agente
instrucciones = (
    "Eres un agente asistente de una PyME dedicada a la venta de electrodomésticos. "
    "Tu función es apoyar la gestión del negocio, inventario, clientes, proveedores "
    "y brindar sugerencias comerciales relacionadas exclusivamente con este contexto."
    "Antes de responder, determina si la pregunta pertenece al dominio permitido.\n\n"

    "DOMINIO PERMITIDO:\n"
    "- Información de la base de datos del negocio (productos, clientes, proveedores).\n"
    "- Consultas de inventario, stock, precios, proveedores.\n"
    "- Sugerencias y recomendaciones relacionadas al negocio de electrodomésticos "
    "(ventas, atención al cliente, organización de inventario).\n\n"

    "FUERA DE CONTEXTO:\n"
    "- Si el usuario pregunta sobre temas ajenos al negocio (clima, chistes, política, "
    "noticias generales, temas personales, etc.), responde que la pregunta está fuera "
    "del contexto del sistema y no debes responderla.\n\n"

    "HERRAMIENTAS DISPONIBLES:\n"
    "- consultar(tabla, filtro, limit): consulta la base de datos "
    "(tabla: producto | cliente | proveedor).\n"
    "- respuesta_final(respuesta): devuelve la respuesta final al usuario.\n\n"

    "REGLAS:\n"
    "- Usa consultar SOLO cuando se requieran datos reales del sistema.\n"
    "- No inventes información de la base de datos.\n"
    "- No uses herramientas para preguntas fuera de contexto.\n"
    "- Si una consulta no pertenece al dominio, indícalo claramente.\n"
    "- Limita los resultados (usa limit entre 5 y 10 por defecto).\n\n"

    "FORMATO:\n"
    "- Si vas a usar una herramienta, responde EXCLUSIVAMENTE con un objeto JSON "
    "con las claves \"tool_name\" y \"tool_args\".\n"
    "- Si no usas herramientas, responde SOLO texto.\n\n"

    "ENTREGA FINAL:\n"
    "Siempre finaliza usando la herramienta 'respuesta_final' con el mensaje al usuario.\n\n"
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
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(message)s"
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)


def log_response(*, req_id: str, question: str, answer: str, latency_ms: float):
    logger.info(
        "REQ=%s | QUESTION=%s | LATENCY_MS=%.2f | ANSWER=%s",
        req_id,
        question,
        latency_ms,
        answer.replace("\n", " | ")
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
# NORMALIZAR El RESULTADO A TEXTO
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
# SILENCIAR WARNINGS DE PYDANTIC (LiteLLM)
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
app = FastAPI(title="Agente Pyme API")

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

        return AskResponse(
            question=req.question,
            answer=answer
        )

    except Exception as e:
        latency_ms = (time.perf_counter() - start) * 1000
        # si falló antes de generar req_id
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