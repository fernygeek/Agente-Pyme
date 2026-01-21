from fastapi.testclient import TestClient
from agente_pyme import app

client = TestClient(app)

def test_preguntar_al_agente():
    # Ejemplos (repuestos automotrices)
    # payload = {"question": "¿Hay pastillas de freno para Chevrolet Aveo?"}
    # payload = {"question": "¿Qué filtros de aceite tengo en inventario?"}
    # payload = {"question": "¿Qué repuestos tengo para Toyota Hilux?"}
    payload = {"question": "¿Hay kits de embrague? ¿de qué marca y cuántos quedan?"}
    # payload = {"question": "Cuéntame un chiste"}
    # payload = {"question": "¿Hay filtros MANN para Chevrolet Spark?"}
    # payload = {"question": "¿Hay pastillas de freno Brembo para Chevrolet Aveo? ¿Cuántas y qué stock tienen?"}

    r = client.post("/ask", json=payload)

    assert r.status_code == 200, r.text
    data = r.json()
    print("Agent Answer:\n", data["answer"])

if __name__ == "__main__":
    test_preguntar_al_agente()