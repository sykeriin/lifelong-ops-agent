# STATUS: COMPLETE
import os

from baseline.llm_client import get_openai_client


class StatelessAgent:
    """Never reads or writes memory. Just searches KB and answers."""
    
    def __init__(self):
        self.client = get_openai_client()
        self.model = os.getenv("MODEL_NAME", "llama-3.1-70b-versatile")
        self.step_count = 0
    
    def act(self, observation: dict, memory, world_state) -> dict:
        """
        Step logic:
        - Step 0: SearchKB with ticket subject
        - Step 1: Answer based on KB result + ticket body
        """
        self.step_count = observation["step"]
        
        if self.step_count == 0:
            # Search KB
            return {
                "type": "SearchKB",
                "query": observation["ticket"]["subject"]
            }
        else:
            # Answer
            ticket = observation["ticket"]
            kb_results = observation.get("message", "")
            
            prompt = f"""You are a SaaS support agent. Answer the customer ticket accurately based on current policies. You have no memory of past tickets.

Ticket Subject: {ticket['subject']}
Ticket Body: {ticket['body']}

Customer Info:
- Plan: {ticket['customer']['plan']}
- Signup Week: {ticket['customer']['signup_week']}
- Monthly Price: ${ticket['customer']['monthly_price_locked']}

Knowledge Base Results:
{kb_results}

Current Week: {observation['week']}

Format your Answer as plain text that includes:
- The decision (approve/deny) if relevant
- The key reason with specific numbers (e.g., "within 30-day window")
- The customer's plan and what applies to them
- The category and priority if this is a triage task

Answer:"""
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a SaaS support agent. Answer the customer ticket accurately based on current policies. You have no memory of past tickets."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.0
            )
            
            answer_text = response.choices[0].message.content
            
            return {
                "type": "Answer",
                "text": answer_text
            }
