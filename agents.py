import dspy
import re
from typing import List, Dict, Optional, Union

# ============= SIGNATURES =============

class NegotiateSignature(dspy.Signature):
    """
    You are a supply chain agent negotiating a deal.
    
    INSTRUCTIONS:
    1. Review your private context and the history.
    2. Think strategically about your margins and goals.
    3. You MUST output your response with clear headers for parsing.
    
    FORMAT REQUIREMENTS:
    - Start with specific tags: [DECISION], [PRICE], [QUANTITY].
    - Then write your natural message in [MESSAGE].
    - Valid decisions: ACCEPT, REJECT, COUNTER.
    """
    private_context = dspy.InputField(desc="Your role, personality, goal, and private constraints")
    history = dspy.InputField(desc="The conversation history so far")
    response = dspy.OutputField(desc="Structured output containing [DECISION], [PRICE], [QUANTITY], and [MESSAGE]")

# ============= AGENT CLASSES =============

class BaseAgent(dspy.Module):
    def __init__(self, name: str, private_data: Dict):
        super().__init__()
        self.name = name
        self.private_data = private_data
        # History stores strings strictly: "Role: Message"
        self.history: List[str] = []
        self.generate_response = dspy.ChainOfThought(NegotiateSignature)

    def _format_history(self) -> str:
        """Safely format history, ignoring any non-string junk that might have slipped in."""
        clean_history = []
        for item in self.history:
            if isinstance(item, str):
                clean_history.append(item)
            elif isinstance(item, dict):
                # Fallback if a dict got in (e.g. from debug logs)
                role = item.get('role', 'Unknown')
                content = item.get('content', '')
                clean_history.append(f"[{role.upper()}]: {content}")
            else:
                clean_history.append(str(item))
                
        return "\n".join(clean_history) if clean_history else "No history yet."

    def add_message(self, role: str, content: str):
        """Strictly append formatted strings."""
        if not isinstance(content, str):
            content = str(content)
        self.history.append(f"[{role.upper()}]: {content}")

    def reset(self):
        self.history = []

class Retailer(BaseAgent):
    def __init__(self, name: str, goal: str, personality: str):
        private_data = {
            "role": "Retailer",
            "goal": goal,
            "personality": personality
        }
        super().__init__(name, private_data)

class Wholesaler(BaseAgent):
    def __init__(self, id: str, procurement_cost: int, operating_cost: int, 
                 inventory: int, target_margin: float, lead_time: int, goal: str, personality: str):
        
        break_even = procurement_cost + operating_cost
        
        # Determine operational capacity (80% of total inventory)
        operational_capacity = int(inventory * 0.8)

        private_data = {
            "id": id,
            "procurement_cost": procurement_cost,
            "operating_cost": operating_cost,
            "break_even": break_even,
            "inventory": inventory,
            "operational_capacity": operational_capacity, # NEW: Added for Scenario 2 Complex
            "target_margin": target_margin,
            "lead_time": lead_time,
            "goal": goal,
            "personality": personality
        }
        super().__init__(name=f"Wholesaler_{id}", private_data=private_data)
        self.id = id
        self.inventory_remaining = inventory

    def forward(self, incoming_message: str, sender_role: str = "Retailer") -> str:
        # 1. Add User Message (Allow dynamic sender for S5 Collusion)
        self.add_message(sender_role, incoming_message)
        
        context_str = (
            f"You are Wholesaler {self.id}.\n"
            f"Goal: {self.private_data['goal']}\n"
            f"Personality: {self.private_data['personality']}\n"
            f"Private Info (DO NOT REVEAL EXACT NUMBERS):\n"
            f"- Break-even: ${self.private_data['break_even']}/unit\n"
            f"- Total Inventory: {self.inventory_remaining} units\n"
            f"- Safe Warehouse Capacity: {self.private_data['operational_capacity']} units (Target < 80% utilization)\n" # EXPLICIT INSTRUCTION
            f"- Target Margin: {self.private_data['target_margin']:.0%}\n"
            f"- Lead Time: {self.private_data['lead_time']} days (Strict minimum)\n"
            f"IMPORTANT: Your response MUST strictly follow the format:\n"
            f"[DECISION]: <ACCEPT/REJECT/COUNTER>\n"
            f"[PRICE]: <Number or None>\n"
            f"[QUANTITY]: <Number or None>\n"
            f"[MESSAGE]: <Your natural negotiation text>"
        )

        # 2. Generate Response
        prediction = self.generate_response(
            private_context=context_str,
            history=self._format_history()
        )
        
        full_reply = prediction.response
        
        # 3. Parse & Add Assistant Message
        msg_match = re.search(r'\[MESSAGE\]:\s*(.*)', full_reply, re.DOTALL)
        clean_reply = msg_match.group(1).strip() if msg_match else full_reply
        
        self.add_message("You", clean_reply)
        
        return full_reply

    def parse_response(self, text: str) -> Dict:
        """Robust parser for structured output tags."""
        # 1. Decision
        decision = "inquire"
        dec_match = re.search(r'\[DECISION\]:\s*(\w+)', text, re.IGNORECASE)
        if dec_match:
            d_str = dec_match.group(1).lower()
            if "accept" in d_str: decision = "accept"
            elif "reject" in d_str: decision = "reject"
            elif "counter" in d_str: decision = "counter_offer"
        
        # 2. Price
        price = None
        price_match = re.search(r'\[PRICE\]:\s.*?\$?(\d+(?:\.\d{2})?)', text)
        if price_match:
            try:
                price = float(price_match.group(1))
            except ValueError:
                price = None

        # 3. Quantity
        quantity = None
        qty_match = re.search(r'\[QUANTITY\]:\s.*?(\d+)', text)
        if qty_match:
            try:
                quantity = int(qty_match.group(1))
            except ValueError:
                quantity = None
                
        # 4. Message
        msg_match = re.search(r'\[MESSAGE\]:\s*(.*)', text, re.DOTALL)
        clean_message = msg_match.group(1).strip() if msg_match else text

        return {
            "decision": decision,
            "price": price,
            "quantity": quantity,
            "clean_message": clean_message
        }
