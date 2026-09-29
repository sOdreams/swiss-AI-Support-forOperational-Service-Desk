import json
import requests

# Ruta al archivo JSON que acabas de proporcionar
INPUT_FILE = "/home/momin/Documents/aisupportagent/SwissLife-2026/jira_hackathon_blind_eval_challenge_20260923083915-1141.json"
OUTPUT_FILE = "respuestas_finales_hackathon.json"
API_URL = "http://127.0.0.1:8000/triage/batch"

def evaluate_tickets():
    # 1. Leer el archivo JSON original del reto
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Los 20 tickets están dentro de la llave "records"
    records = data.get("records", [])
    print(f"Se encontraron {len(records)} tickets para evaluar.")

    # 2. Transformar los datos al esquema BatchTicketRequest del backend
    batch_payload = {"tickets": []}
    
    for idx, ticket in enumerate(records):
        batch_payload["tickets"].append({
            "ticket_id": f"eval-{idx+1}",
            "ticket": ticket
        })

    # 3. Enviar la petición de procesamiento masivo al backend
    print("Enviando tickets al orquestador RAG + LLM. Esto tomará un par de minutos...")
    response = requests.post(API_URL, json=batch_payload)

    if response.status_code == 200:
        # 4. Guardar los resultados estructurados
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(response.json(), f, indent=2)
        print(f"Éxito: Los resultados se han guardado en {OUTPUT_FILE}")
    else:
        print(f"Error en la API: {response.status_code}")
        print(response.text)

if __name__ == "__main__":
    evaluate_tickets()