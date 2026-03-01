import re
import logging
from typing import Optional, Dict, Any, Tuple

logger = logging.getLogger(__name__)

class LocalNLU:
    """
    Local Natural Language Understanding (NLU) module.
    
    Industrial-grade voice assistants use a "Hybrid Intelligence" architecture:
    1. Edge/Local NLU: Handles high-frequency, low-latency, safety-critical commands (e.g., "Open Door", "Turn on lights").
       - Latency: < 10ms
       - Reliability: Deterministic (Rule-based / Grammar-based)
    2. Cloud LLM: Handles complex, creative, or long-tail queries.
       - Latency: 1s - 5s
       - Capability: General reasoning
       
    This module implements the Local NLU layer using robust pattern matching (Slot Filling).
    Future upgrades can replace regex with a lightweight BERT/DistilBERT model without changing the interface.
    """
    
    def __init__(self):
        # Define intents with regex patterns for robust matching
        # Captures variations like "帮我开门", "把门打开", "Open the door"
        self.intents = [
            {
                "name": "open_door",
                "patterns": [
                    r"(?:打开|开).{0,2}(?:门|锁)",  # 开门, 打开门, 把门打开
                    r"open.*door",
                    r"let.*me.*in"
                ],
                "confidence_threshold": 0.0  # Regex match is considered 1.0 confidence conceptually, but we rely on Speaker Verification Score externally
            },
            {
                "name": "turn_on_light",
                "patterns": [
                    r"(?:打开|开).{0,2}(?:灯|光)",
                    r"turn.*on.*light"
                ],
                "slots": {"location": "客厅"} # Default slot
            },
            {
                "name": "alert_police",
                "patterns": [
                    r"(?:报警|救命|紧急)",
                    r"call.*police",
                    r"help"
                ]
            }
        ]
        logger.info("Local NLU module initialized with rule-based engine.")

    def parse(self, text: str) -> Tuple[Optional[str], Dict[str, Any]]:
        """
        Parse text to identify intent.
        Returns: (intent_name, slots)
        """
        text = text.lower().strip()
        
        for intent in self.intents:
            for pattern in intent["patterns"]:
                if re.search(pattern, text):
                    logger.info(f"Local NLU matched intent: {intent['name']} (Pattern: {pattern})")
                    return intent["name"], intent.get("slots", {})
        
        return None, {}
