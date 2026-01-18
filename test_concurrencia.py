import asyncio, time
import httpx

URL = "http://127.0.0.1:8000/ask"  # <-- cambia si tu ruta es otra

QUESTIONS = [
    "qué productos están por agotarse",
    "qué productos están por caducarse",
    "existen novedades esta semana",
    "cómo puedo mejorar el servicio al cliente",
    "qué productos están por agotarse",
    "qué productos están por caducarse",
]

N_REQUESTS = 12  # prueba 6, 12, 24 para ver cola

async def worker(client, q):
    t0 = time.perf_counter()
    try:
        r = await client.post(URL, json={"question": q}, timeout=180)
        ms = (time.perf_counter() - t0) * 1000
        return q, r.status_code, ms
    except Exception as e:
        ms = (time.perf_counter() - t0) * 1000
        return q, "ERR", ms, str(e)

async def main():
    qs = [QUESTIONS[i % len(QUESTIONS)] for i in range(N_REQUESTS)]

    async with httpx.AsyncClient() as client:
        tasks = [worker(client, q) for q in qs]
        results = await asyncio.gather(*tasks)

        for item in results:
            if len(item) == 3:
                q, status, ms = item
                print(f"{status} | {ms:8.2f} ms | {q}")
            else:
                q, status, ms, err = item
                print(f"{status} | {ms:8.2f} ms | {q} | {err}")

if __name__ == "__main__":
    asyncio.run(main())
