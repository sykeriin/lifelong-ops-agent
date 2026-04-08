# STATUS: COMPLETE
import os
import sys
from baseline.memory_agent import MemoryAgent
from eval.lifelong_eval import run_lifelong_eval


def main():
    # Check for API key
    api_key = os.getenv("OPENAI_API_KEY") or os.getenv("HF_TOKEN")
    if not api_key:
        print("ERROR: OPENAI_API_KEY or HF_TOKEN environment variable not set")
        sys.exit(1)
    
    model_name = os.getenv("MODEL_NAME", "gpt-4o-mini")
    print(f"Using model: {model_name}")
    print("=" * 60)
    
    # Create agent
    agent = MemoryAgent()
    
    # Run evaluation
    print("Starting Lifelong Evaluation...")
    print("=" * 60)
    
    results = run_lifelong_eval(agent, n_per_task=20, seed=42)
    
    # Print results
    print("\n")
    print("=" * 60)
    print("LIFELONG EVAL RESULTS")
    print("=" * 60)
    print(f"Week 1 Accuracy:     {results['acc_week_1']:.3f}")
    print(f"Week 2 Accuracy:     {results['acc_week_2']:.3f}")
    print(f"Week 3 Accuracy:     {results['acc_week_3']:.3f}")
    print(f"Forgetting Score:    {results['forgetting_score']:.3f}  (positive = degraded on old tasks)")
    print(f"Adaptation (W2):     {results['adaptation_episodes_w2']} episodes to reach 0.8 accuracy")
    print(f"Adaptation (W3):     {results['adaptation_episodes_w3']} episodes to reach 0.8 accuracy")
    print("=" * 60)
    
    # Print per-task breakdown
    print("\nPer-Task Breakdown:")
    print("-" * 60)
    for phase, tasks in results["per_task_breakdown"].items():
        print(f"\n{phase}:")
        for task_type, score in tasks.items():
            print(f"  Task {task_type}: {score:.3f}")
    
    print("\n" + "=" * 60)
    print(f"Memory keys at end: {len(results['memory_snapshot_end'])}")
    print("=" * 60)


if __name__ == "__main__":
    main()
