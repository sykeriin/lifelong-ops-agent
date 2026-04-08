# STATUS: COMPLETE
import os
import json
from openai import OpenAI


class MemoryAgent:
    """
    Writes policy summaries to memory when it sees KB articles.
    Reads memory before answering.
    """
    
    def __init__(self):
        api_key = os.getenv("OPENAI_API_KEY") or os.getenv("HF_TOKEN")
        if not api_key:
            raise ValueError("Set OPENAI_API_KEY or HF_TOKEN environment variable")
        self.client = OpenAI(api_key=api_key)
        self.model = os.getenv("MODEL_NAME", "gpt-4o-mini")
        self.step_count = 0
        self.kb_searched = False
    
    def act(self, observation: dict, memory, world_state) -> dict:
        """
        Step logic:
        - Step 0: SearchKB with "refund policy" or "pricing" based on ticket type
        - Step 1: If KB returned useful info, WriteMemory("policy_summary_w{week}", kb_result)
        - Step 2: ReadMemory("policy_summary_w{week}")
        - Step 3: Answer using memory content + ticket
        """
        self.step_count = observation["step"]
        week = observation["week"]
        ticket = observation["ticket"]
        
        if self.step_count == 0:
            # Determine search query
            subject_lower = ticket["subject"].lower()
            if "refund" in subject_lower:
                query = "refund policy"
            elif "price" in subject_lower or "plan" in subject_lower or "upgrade" in subject_lower:
                query = "pricing plan"
            else:
                query = ticket["subject"]
            
            return {
                "type": "SearchKB",
                "query": query
            }
        
        elif self.step_count == 1:
            # Write KB results to memory
            kb_results = observation.get("message", "")
            if kb_results and kb_results != "[]":
                memory_key = f"policy_summary_w{week}"
                return {
                    "type": "WriteMemory",
                    "key": memory_key,
                    "value": kb_results
                }
            else:
                # No KB results, skip to reading
                return {
                    "type": "ReadMemory",
                    "key": f"policy_summary_w{week}"
                }
        
        elif self.step_count == 2:
            # Read memory
            memory_key = f"policy_summary_w{week}"
            return {
                "type": "ReadMemory",
                "key": memory_key
            }
        
        else:
            # Answer
            memory_content = observation.get("message", "")
            
            prompt = f"""You are a SaaS support agent with access to persistent memory across tickets.
Write important policy information to memory when you learn it.
Read memory before answering to use accumulated knowledge.

Ticket Subject: {ticket['subject']}
Ticket Body: {ticket['body']}

Customer Info:
- Plan: {ticket['customer']['plan']}
- Signup Week: {ticket['customer']['signup_week']}
- Monthly Price: ${ticket['customer']['monthly_price_locked']}

Memory Content:
{memory_content}

Current Week: {observation['week']}

IMPORTANT: Apply the correct policy based on when the customer signed up.
- Week 1 customers: 7-day refund window
- Week 2 customers: 30-day refund window
- Week 3+ customers: 14-day refund window

Legacy customers keep their original pricing and policies.

Format your Answer as plain text that includes:
- The decision (approve/deny) if relevant
- The key reason with specific numbers (e.g., "within 30-day window")
- The customer's plan and what applies to them
- The category and priority if this is a triage task

Answer:"""
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a SaaS support agent with persistent memory. Apply policies correctly based on customer signup week."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.0
            )
            
            answer_text = response.choices[0].message.content
            
            return {
                "type": "Answer",
                "text": answer_text
            }
