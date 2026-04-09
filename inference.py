# STATUS: COMPLETE
import os
import sys
from typing import TextIO

from dotenv import load_dotenv

# Shell exports win over .env so you can override for one-off runs (e.g. local Ollama).
load_dotenv(override=False)

from openai import OpenAI

from baseline.llm_client import get_openai_client, llm_endpoint_is_local
from baseline.memory_agent import MemoryAgent
from env.grader import clamp_task_score
from eval.lifelong_eval import run_lifelong_eval


def _out(emit_submission_logs: bool) -> TextIO:
    return sys.stderr if emit_submission_logs else sys.stdout


def main() -> None:
    emit_submission_logs = os.getenv("SUBMISSION_LOGS", "1").lower() not in (
        "0",
        "false",
        "no",
    )
    if not emit_submission_logs:
        print(
            "WARNING: SUBMISSION_LOGS=0 disables [START]/[STEP]/[END] on stdout; "
            "organizer harnesses expect structured logs. Remove SUBMISSION_LOGS or set SUBMISSION_LOGS=1.",
            file=sys.stderr,
            flush=True,
        )
    out = _out(emit_submission_logs)

    try:
        llm_client: OpenAI = get_openai_client()
    except ValueError as e:
        print(f"ERROR: {e}", file=out, flush=True)
        sys.exit(1)

    model_name = os.getenv("MODEL_NAME", "llama-3.1-70b-versatile")
    benchmark = os.getenv("OPENENV_BENCHMARK", "lifelong-ops-agent")
    base = (
        os.getenv("API_BASE_URL")
        or os.getenv("OPENAI_BASE_URL")
        or "https://api.groq.com/openai/v1"
    )

    print(f"Using model: {model_name}", file=out, flush=True)
    print(f"API base URL: {base}" + (" (local)" if llm_endpoint_is_local() else ""), file=out, flush=True)
    print(f"Benchmark (env): {benchmark}", file=out, flush=True)
    print(f"Submission stdout logs: {emit_submission_logs}", file=out, flush=True)
    print("=" * 60, file=out, flush=True)

    agent = MemoryAgent(client=llm_client)

    print("Starting Lifelong Evaluation...", file=out, flush=True)
    print("=" * 60, file=out, flush=True)

    # Submission guidance: complete in ~20 minutes on 2 vCPU / 8GB with a *fast* hosted API.
    # Local Ollama is much slower per token; without N_PER_TASK set we use a smaller default.
    if "N_PER_TASK" in os.environ:
        n_per_task = int(os.environ["N_PER_TASK"])
    elif llm_endpoint_is_local():
        n_per_task = 5
        print(
            "N_PER_TASK not set: using 5 for local API (~60 LLM episodes; ~20 min if ~20s/call). "
            "Set N_PER_TASK=20 for full protocol (can take hours on Ollama).",
            file=out,
            flush=True,
        )
    else:
        n_per_task = 20

    success_score_threshold = float(os.getenv("SUCCESS_SCORE_THRESHOLD", "0.1"))
    print(f"N_PER_TASK={n_per_task}", file=out, flush=True)

    results = run_lifelong_eval(
        agent,
        n_per_task=n_per_task,
        seed=42,
        emit_submission_logs=emit_submission_logs,
        log_benchmark=benchmark,
        log_model=model_name,
        success_score_threshold=success_score_threshold,
    )

    print("\n", file=out, flush=True)
    print("=" * 60, file=out, flush=True)
    print("LIFELONG EVAL RESULTS", file=out, flush=True)
    print("=" * 60, file=out, flush=True)
    print(
        f"Week 1 Accuracy:     {clamp_task_score(results['acc_week_1']):.3f}",
        file=out,
        flush=True,
    )
    print(
        f"Week 2 Accuracy:     {clamp_task_score(results['acc_week_2']):.3f}",
        file=out,
        flush=True,
    )
    print(
        f"Week 3 Accuracy:     {clamp_task_score(results['acc_week_3']):.3f}",
        file=out,
        flush=True,
    )
    print(
        f"Forgetting Score:    {results['forgetting_score']:.3f}  (positive = degraded on old tasks)",
        file=out,
        flush=True,
    )
    print(
        f"Adaptation (W2):     {results['adaptation_episodes_w2']} episodes to reach 0.8 accuracy",
        file=out,
        flush=True,
    )
    print(
        f"Adaptation (W3):     {results['adaptation_episodes_w3']} episodes to reach 0.8 accuracy",
        file=out,
        flush=True,
    )
    print("=" * 60, file=out, flush=True)

    print("\nPer-Task Breakdown:", file=out, flush=True)
    print("-" * 60, file=out, flush=True)
    for phase, tasks in results["per_task_breakdown"].items():
        print(f"\n{phase}:", file=out, flush=True)
        for task_type, score in tasks.items():
            print(
                f"  Task {task_type}: {clamp_task_score(score):.3f}",
                file=out,
                flush=True,
            )

    print("\n" + "=" * 60, file=out, flush=True)
    print(f"Memory keys at end: {len(results['memory_snapshot_end'])}", file=out, flush=True)
    print("=" * 60, file=out, flush=True)


if __name__ == "__main__":
    main()
