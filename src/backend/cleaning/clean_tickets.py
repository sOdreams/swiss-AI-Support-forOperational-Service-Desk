import json
import re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
RAW_DATA_PATH = BASE_DIR / "data" / "raw" / "jira_first_20000_requested_fields_synthetic.json"
OUTPUT_DIR = BASE_DIR / "data" / "processed"

ROUTING_OUTPUT = OUTPUT_DIR / "routing_dataset.json"
RAG_SOFT_OUTPUT = OUTPUT_DIR / "rag_dataset_soft.json"
RAG_BALANCED_OUTPUT = OUTPUT_DIR / "rag_dataset_balanced.json"
RAG_STRICT_OUTPUT = OUTPUT_DIR / "rag_dataset_strict.json"

EXACT_MATCH_ONLY = [
    "problem fixed",
    "issue fixed",
    "done",
    "resolved"
]

# Pure robotic routing noise - dropped in both Balanced and Strict
TRIAGE_ROUTING_PATTERNS = [
    "initial triage assigned to",
    "we validated the issue against",
    "impact assessment confirmed"
]

# Vague resolution statements - dropped ONLY in Strict
VAGUE_RESOLUTION_PATTERNS = [
    "resolution recorded:",
    "follow-up review completed"
]

def evaluate_rag_usefulness(comments_list: list, filter_level: str) -> bool:
    """
    Evaluates ticket usefulness based on three filter levels:
    - 'soft': Only removes exact short phrases.
    - 'balanced': Removes short phrases + robotic triage templates.
    - 'strict': Removes short phrases + triage templates + vague resolution templates.
    """
    if not comments_list:
        return False
        
    useful_comments_count = 0
    email_pattern = re.compile(r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+:\s*')
    
    for comment in comments_list:
        cleaned = email_pattern.sub('', comment).strip().lower()
        
        if len(cleaned) < 15:
            continue
            
        is_generic = False
        cleaned_no_punctuation = cleaned.replace(".", "").strip()
        
        # 1. Base level: Strict exact match for short phrases (applies to all)
        if cleaned_no_punctuation in EXACT_MATCH_ONLY:
            is_generic = True
        else:
            # 2. Balanced level: Add triage routing patterns
            if filter_level in ['balanced', 'strict']:
                for pattern in TRIAGE_ROUTING_PATTERNS:
                    if cleaned.startswith(pattern):
                        is_generic = True
                        break
            
            # 3. Strict level: Add vague resolution patterns
            if filter_level == 'strict' and not is_generic:
                for pattern in VAGUE_RESOLUTION_PATTERNS:
                    if cleaned.startswith(pattern):
                        is_generic = True
                        break
                        
        if not is_generic:
            useful_comments_count += 1
            
    return useful_comments_count > 0

def is_useful_for_routing(ticket: dict) -> bool:
    required_fields = ["Work type", "Affected Business or IT Services", "Service Team(s)", "Assignee"]
    for field in required_fields:
        val = ticket.get(field)
        if not val or (isinstance(val, list) and len(val) == 0):
            return False
    return True

def process_datasets():
    if not RAW_DATA_PATH.exists():
        print(f"Error: File not found at {RAW_DATA_PATH}")
        return

    with open(RAW_DATA_PATH, 'r', encoding='utf-8') as f:
        raw_data = json.load(f)
        
    tickets = raw_data.get('records', raw_data) if isinstance(raw_data, dict) else raw_data

    routing_dataset = []
    rag_soft_dataset = []
    rag_balanced_dataset = []
    rag_strict_dataset = []

    for ticket in tickets:
        if is_useful_for_routing(ticket):
            routing_dataset.append(ticket)
            
        comments = ticket.get("All Comments", [])
        
        # Helper to safely clean ticket before appending
        def clean_ticket_for_rag(t):
            clean_t = t.copy()
            for key in ["Priority", "Urgency", "Impact"]:
                clean_t.pop(key, None)
            return clean_t

        if evaluate_rag_usefulness(comments, 'soft'):
            rag_soft_dataset.append(clean_ticket_for_rag(ticket))
            
        if evaluate_rag_usefulness(comments, 'balanced'):
            rag_balanced_dataset.append(clean_ticket_for_rag(ticket))
            
        if evaluate_rag_usefulness(comments, 'strict'):
            rag_strict_dataset.append(clean_ticket_for_rag(ticket))

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    with open(ROUTING_OUTPUT, 'w', encoding='utf-8') as f:
        json.dump(routing_dataset, f, indent=2)
        
    with open(RAG_SOFT_OUTPUT, 'w', encoding='utf-8') as f:
        json.dump(rag_soft_dataset, f, indent=2)
        
    with open(RAG_BALANCED_OUTPUT, 'w', encoding='utf-8') as f:
        json.dump(rag_balanced_dataset, f, indent=2)
        
    with open(RAG_STRICT_OUTPUT, 'w', encoding='utf-8') as f:
        json.dump(rag_strict_dataset, f, indent=2)

    print("=== PHASE 1: DATASET GENERATION (3-TIER RAG) ===")
    print(f"Total Original Tickets:             {len(tickets)}")
    print(f"Routing Dataset (ML):               {len(routing_dataset)}")
    print(f"RAG Dataset (Soft Filter):          {len(rag_soft_dataset)}")
    print(f"RAG Dataset (Balanced Filter):      {len(rag_balanced_dataset)}")
    print(f"RAG Dataset (Strict Filter):        {len(rag_strict_dataset)}")
    print("================================================")

if __name__ == "__main__":
    process_datasets()