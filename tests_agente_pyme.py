from fastapi.testclient import TestClient
from agente_pyme import app

client = TestClient(app)

def test_preguntar_al_llm():
    # payload = {"question": "Hola podrías decirme si hay microondas"}
    # payload = {"question": "Hola podrías decirme si hay televisores en el inventario?"}
    # payload = {"question": "Hola podrías decirme si hay refrigeradores en el inventario?"}
    # payload = {"question": "Hola podrías decirme si hay refrigeradores en el inventario y que marca son?"}
    payload = {"question": "Hola podrías decirme si hay refrigeradores LG en el inventario"}
    r = client.post("/ask", json=payload)

    assert r.status_code == 200, r.text
    print("LLM Answer:\n", r.json()["answer"])

if __name__ == "__main__":
    test_preguntar_al_llm()