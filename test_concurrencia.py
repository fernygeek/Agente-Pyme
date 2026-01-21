import asyncio, time
import httpx

URL = "http://127.0.0.1:8000/ask"  # <-- cambia si tu endpoint es otro

QUESTIONS = [
    # Inventario / stock mínimo
    "¿Qué repuestos están por agotarse (stock bajo o por debajo del mínimo)?",
    # "Muéstrame los productos con stock_actual <= stock_minimo.",
    # "¿Qué productos tienen menos de 5 unidades disponibles?",

    # Compatibilidad por modelo (usando tu campo 'marca' como modelo/vehículo)
    "¿Hay repuestos para Toyota Hilux? ¿Cuáles y cuántos quedan?",
    # "¿Hay kits de embrague para Toyota Hilux? ¿Marca y stock disponible?",
    # "¿Qué repuestos hay para Chevrolet Aveo y cuántos quedan?",

    # Proveedores
    "¿Qué proveedores tengo registrados y cómo puedo contactarlos?",
    # "¿Qué proveedor me vende filtros de aceite? (si existe en la base)",

    # Movimientos de inventario
    "¿Qué movimientos de inventario recientes hay? (entradas/salidas/otros)",
    # "¿Cuántas salidas por venta se registraron recientemente?",

    # Sugerencias de negocio (sin inventar datos)
    "Dame sugerencias para mejorar ventas de repuestos automotrices basadas en inventario y rotación.",
    # "¿Cómo puedo mejorar el servicio al cliente en una tienda de repuestos automotrices?",
]

N_REQUESTS = 12  # prueba 6, 12, 24 para ver cola

async def worker(client, q):
    t0 = time.perf_counter()
    try:
        r = await client.post(URL, json={"question": q}, timeout=180)
        ms = (time.perf_counter() - t0) * 1000
        return q, r.status_code, ms, r.text
    except Exception as e:
        ms = (time.perf_counter() - t0) * 1000
        return q, "ERR", ms, str(e)

async def main():
    qs = [QUESTIONS[i % len(QUESTIONS)] for i in range(N_REQUESTS)]

    async with httpx.AsyncClient() as client:
        tasks = [worker(client, q) for q in qs]
        results = await asyncio.gather(*tasks)

        for q, status, ms, extra in results:
            # Si falla, imprime error; si OK, imprime respuesta corta
            if status == "ERR":
                print(f"{status} | {ms:8.2f} ms | {q} | {extra}")
            else:
                # extra es r.text; recortamos para que no sea gigante
                snippet = extra.replace("\n", " ")
                if len(snippet) > 180:
                    snippet = snippet[:180] + "..."
                print(f"{status} | {ms:8.2f} ms | {q} | {snippet}")

if __name__ == "__main__":
    asyncio.run(main())