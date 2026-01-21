from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from smolagents import ToolCallingAgent, LiteLLMModel
import time, json, logging, asyncio, uuid, warnings
from starlette.concurrency import run_in_threadpool

from tools import respuesta_final, consultar, productos_bajo_stock

# =========================
# LLM + AGENTE
# =========================
llm = LiteLLMModel(
    model_id="ollama_chat/qwen3:1.7b",
    api_base="http://localhost:11434",
    api_key="ollama",
    temperature=0.2,
    response_format={"type": "json_object"},
)

agent = ToolCallingAgent(
    tools=[respuesta_final, consultar, productos_bajo_stock],
    model=llm,
    max_steps=4,
)

# =========================
# INSTRUCCIONES (mejoradas)
# =========================
instrucciones = (
    "Eres un asistente de una PyME de repuestos automotrices en Ecuador.\n"
    "IDIOMA: Responde SIEMPRE en español latino (neutral).\n"
    "MONEDA: Todos los valores monetarios en USD ($). Nunca uses EUR.\n\n"

    "TU FUNCIÓN:\n"
    "- Ayudar con consultas de inventario, productos, proveedores y movimientos.\n"
    "- Dar sugerencias comerciales SOLO dentro del contexto del negocio.\n\n"

    "CUÁNDO USAR HERRAMIENTAS:\n"
    "- Para cualquier pregunta sobre datos del sistema (productos/proveedores/movimientos), SIEMPRE usa consultar.\n"
    "- Si piden LISTAR (ej: 'qué proveedores tengo', 'muéstrame todos los proveedores', 'qué productos hay'), usa modo='listar' y filtro=''.\n"
    "- Si piden BUSCAR (ej: 'hay kit de embrague', 'bujías NGK', 'filtro de aceite Aveo'), usa modo='buscar' y filtro con palabras clave.\n\n"

    "TABLAS PERMITIDAS PARA consultar:\n"
    "- producto, proveedor, movimiento_inventario o auto.\n"
    "- Recomendación: usa tabla='auto' si no estás segura.\n\n"

    "FUERA DE CONTEXTO:\n"
    "- Si preguntan algo ajeno al negocio (clima, política, chistes, etc.), responde EXACTAMENTE:\n"
    "  La pregunta está fuera del contexto del sistema\n\n"

    "FORMATO DE TOOL CALL:\n"
    "- Si vas a usar una herramienta, responde EXCLUSIVAMENTE con JSON:\n"
    "  {\"tool_name\":\"consultar\",\"tool_args\":{...}}\n"
    "  o {\"tool_name\":\"respuesta_final\",\"tool_args\":{...}}\n\n"

    "ENTREGA FINAL:\n"
    "- SIEMPRE termina llamando respuesta_final.\n"
    "- Cuando el usuario pregunte '¿hay X? ¿marca y cuántos?', incluye: nombre_prod, marca y stock_actual.\n"
)

# =========================
# LOGS
# =========================
LOG_FILE = "monitoreo.log"
logger = logging.getLogger("agent_logger")
logger.setLevel(logging.INFO)
logger.propagate = False

if not logger.handlers:
    fh = logging.FileHandler(LOG_FILE, encoding="utf-8")
    fh.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
    logger.addHandler(fh)

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
LLM_SEM = asyncio.Semaphore(3)

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

def to_answer_text(result) -> str:
    if isinstance(result, str):
        return result
    content = getattr(result, "content", None)
    if isinstance(content, str):
        return content
    if isinstance(result, dict):
        return json.dumps(result, ensure_ascii=False)
    return str(result)

warnings.filterwarnings("ignore", category=UserWarning)

# =========================
# FASTAPI
# =========================
app = FastAPI(title="Agente Pyme API (Repuestos Automotrices)")

class AskRequest(BaseModel):
    question: str = Field(..., min_length=1)

class AskResponse(BaseModel):
    question: str
    answer: str

@app.post("/ask", response_model=AskResponse)
async def ask(req: AskRequest):
    start = time.perf_counter()
    req_id = str(uuid.uuid4())[:8]

    try:
        prompt = instrucciones + "\nPregunta del usuario:\n" + req.question
        result = await call_llm_safely(agent.run, prompt, req_id=req_id)

        latency_ms = (time.perf_counter() - start) * 1000
        answer = to_answer_text(result)

        log_response(req_id=req_id, question=req.question, answer=answer, latency_ms=latency_ms)
        return AskResponse(question=req.question, answer=answer)

    except Exception as e:
        latency_ms = (time.perf_counter() - start) * 1000
        err_id = str(uuid.uuid4())[:8]
        log_response(req_id=err_id, question=req.question, answer=f"ERROR: {e}", latency_ms=latency_ms)
        raise HTTPException(status_code=500, detail=f"Error ejecutando el agente: {e}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("agente_pyme:app", reload=True)
