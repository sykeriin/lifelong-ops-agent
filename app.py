# HuggingFace Space entry point
# This wraps the FastAPI server for Gradio/Spaces deployment

import gradio as gr
import requests
import json
import subprocess
import time
import threading
import os

# Start the FastAPI server in background
def start_server():
    subprocess.Popen(["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8080"])
    time.sleep(3)  # Wait for server to start

# Start server on import
server_thread = threading.Thread(target=start_server, daemon=True)
server_thread.start()

BASE_URL = "http://localhost:8080"

def reset_env(seed, week):
    """Reset the environment"""
    try:
        response = requests.post(f"{BASE_URL}/reset", json={"seed": int(seed), "week": int(week)})
        return json.dumps(response.json(), indent=2)
    except Exception as e:
        return f"Error: {str(e)}"

def search_kb(query):
    """Search knowledge base"""
    try:
        response = requests.post(f"{BASE_URL}/step", json={
            "action": {"type": "SearchKB", "query": query}
        })
        data = response.json()
        return json.dumps(data["observation"]["message"], indent=2)
    except Exception as e:
        return f"Error: {str(e)}"

def get_state():
    """Get current world state"""
    try:
        response = requests.get(f"{BASE_URL}/state")
        return json.dumps(response.json(), indent=2)
    except Exception as e:
        return f"Error: {str(e)}"

# Create Gradio interface
with gr.Blocks(title="Lifelong Ops Agent Benchmark") as demo:
    gr.Markdown("""
    # 🤖 Lifelong Ops Agent Benchmark
    
    An OpenEnv-compliant RL environment for testing agent adaptation to policy drift in SaaS operations.
    
    **Key Features:**
    - 3 weeks of policy evolution (refund windows, pricing, features)
    - Legacy customer handling (grandfathered terms)
    - Lifelong learning metrics (adaptation speed, forgetting)
    
    [GitHub](https://github.com/yourusername/lifelong-ops-agent) | [Paper](https://arxiv.org)
    """)
    
    with gr.Tab("Environment"):
        with gr.Row():
            seed_input = gr.Number(label="Seed", value=42)
            week_input = gr.Number(label="Week", value=1, minimum=1, maximum=3)
            reset_btn = gr.Button("Reset Environment")
        
        reset_output = gr.Textbox(label="Observation", lines=10)
        reset_btn.click(reset_env, inputs=[seed_input, week_input], outputs=reset_output)
    
    with gr.Tab("Knowledge Base"):
        kb_query = gr.Textbox(label="Search Query", placeholder="e.g., refund policy")
        kb_btn = gr.Button("Search KB")
        kb_output = gr.Textbox(label="Results", lines=10)
        kb_btn.click(search_kb, inputs=kb_query, outputs=kb_output)
    
    with gr.Tab("World State"):
        state_btn = gr.Button("Get Current State")
        state_output = gr.Textbox(label="State", lines=15)
        state_btn.click(get_state, outputs=state_output)
    
    with gr.Tab("About"):
        gr.Markdown("""
        ## How It Works
        
        This benchmark simulates a SaaS support environment where policies drift over time:
        
        - **Week 1**: 7-day refunds, Pro at $29/mo
        - **Week 2**: 30-day refunds for new customers, bulk export launches
        - **Week 3**: 14-day refunds, Pro at $39/mo for new customers
        
        Agents must:
        1. Learn new policies quickly (adaptation)
        2. Remember old policies for legacy customers (no forgetting)
        3. Apply the correct policy based on customer signup week
        
        ## Metrics
        
        - **Accuracy**: Per-episode correctness
        - **Adaptation Speed**: Episodes until 80% accuracy in new week
        - **Forgetting Score**: Performance drop on old tasks after learning new ones
        
        ## API Endpoints
        
        - `POST /reset` - Start new episode
        - `POST /step` - Execute action
        - `GET /state` - Inspect world state
        - `GET /health` - Health check
        """)

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860)
