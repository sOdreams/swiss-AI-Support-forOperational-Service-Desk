def calculate_priority(urgency: str, impact: str) -> str:
    """
    Calcula la Prioridad de forma determinista basándose en la matriz oficial del hackathon.
    Normaliza las entradas de texto para evitar fallos si el LLM devuelve formatos ligeramente distintos.
    """
    urgency_norm = str(urgency).lower().strip()
    impact_norm = str(impact).lower().strip()
    
    # 1. Normalización de Urgency (Filas)
    urgency_key = "Lowest"  # Default fallback
    if "critical" in urgency_norm: 
        urgency_key = "Critical"
    elif "highest" in urgency_norm: # Caso extremo si el LLM se confunde con Priority
        urgency_key = "Critical" 
    elif "high" in urgency_norm: 
        urgency_key = "High"
    elif "medium" in urgency_norm: 
        urgency_key = "Medium"
    elif "lowest" in urgency_norm: 
        urgency_key = "Lowest"
    elif "low" in urgency_norm: 
        urgency_key = "Low"
    
    # 2. Normalización de Impact (Columnas)
    impact_key = "No direct impact" # Default fallback
    if "major" in impact_norm or "widespread" in impact_norm: 
        impact_key = "Major"
    elif "significant" in impact_norm or "large" in impact_norm: 
        impact_key = "Significant"
    elif "moderate" in impact_norm or "limited" in impact_norm: 
        impact_key = "Moderate"
    elif "minor" in impact_norm or "localized" in impact_norm: 
        impact_key = "Minor"
    elif "no " in impact_norm or "information" in impact_norm: 
        impact_key = "No direct impact"

    # 3. Matriz Oficial de Prioridad del Hackathon
    matrix = {
        "Critical": {
            "Major": "Highest", 
            "Significant": "Highest", 
            "Moderate": "High", 
            "Minor": "Medium", 
            "No direct impact": "Medium"
        },
        "High": {
            "Major": "Highest", 
            "Significant": "High", 
            "Moderate": "High", 
            "Minor": "Medium", 
            "No direct impact": "Low"
        },
        "Medium": {
            "Major": "High", 
            "Significant": "High", 
            "Moderate": "Medium", 
            "Minor": "Low", 
            "No direct impact": "Low"
        },
        "Low": {
            "Major": "Medium", 
            "Significant": "Medium", 
            "Moderate": "Low", 
            "Minor": "Low", 
            "No direct impact": "Lowest"
        },
        "Lowest": {
            "Major": "Medium", 
            "Significant": "Low", 
            "Moderate": "Low", 
            "Minor": "Lowest", 
            "No direct impact": "Lowest"
        }
    }
    
    return matrix[urgency_key][impact_key]

if __name__ == "__main__":
    # Pruebas de validación rápida en consola
    print("=== TEST PRIORITY MATRIX ===")
    print(f"Critical / Major -> {calculate_priority('Critical', 'Major / Widespread')}")
    print(f"Medium / Minor -> {calculate_priority('Medium', 'minor / localized')}")
    print(f"Lowest / No direct impact -> {calculate_priority('Lowest', 'No direct impact / Information')}")
    print("============================")