# STATUS: COMPLETE
from typing import Optional
from env.world import WorldState


def grade_task_a(answer: str, ground_truth: dict) -> float:
    """
    +0.5 if correct category found in answer (case-insensitive substring match)
    +0.5 if correct priority found in answer
    Returns sum.
    """
    answer_lower = answer.lower()
    score = 0.0
    
    if ground_truth["category"].lower() in answer_lower:
        score += 0.5
    
    if ground_truth["priority"].lower() in answer_lower:
        score += 0.5
    
    return score


def grade_task_b(answer: str, ground_truth: dict, world_state: WorldState) -> float:
    """
    +0.4 if correct decision ("approve"/"deny") found in answer
    +0.4 if key_reason substring found in answer
    +0.2 if answer does NOT mention wrong policy numbers
    Returns sum.
    """
    answer_lower = answer.lower()
    score = 0.0
    
    # Check decision
    if ground_truth["decision"].lower() in answer_lower:
        score += 0.4
    
    # Check key reason (look for the number)
    key_reason = ground_truth["key_reason"]
    if "7-day" in key_reason or "7 day" in key_reason:
        if "7" in answer_lower and ("day" in answer_lower or "refund" in answer_lower):
            score += 0.4
    elif "30-day" in key_reason or "30 day" in key_reason:
        if "30" in answer_lower and ("day" in answer_lower or "refund" in answer_lower):
            score += 0.4
    elif "14-day" in key_reason or "14 day" in key_reason:
        if "14" in answer_lower and ("day" in answer_lower or "refund" in answer_lower):
            score += 0.4
    
    # Check for wrong policy numbers
    correct_version = ground_truth["correct_policy_version"]
    wrong_numbers = []
    
    if correct_version == "v1":
        wrong_numbers = ["14", "30"]
    elif correct_version == "v2":
        wrong_numbers = ["7", "14"]
    elif correct_version == "v3":
        wrong_numbers = ["7", "30"]
    
    has_wrong_number = False
    for num in wrong_numbers:
        if num in answer_lower and ("day" in answer_lower or "refund" in answer_lower):
            has_wrong_number = True
            break
    
    if not has_wrong_number:
        score += 0.2
    
    return score


def grade_task_c(answer: str, ground_truth: dict, world_state: WorldState) -> float:
    """
    +0.4 if correct decision found
    +0.3 if correct policy version implied (check for correct window/price numbers)
    +0.3 if legacy_trap is NOT triggered (i.e., wrong policy numbers absent from answer)
    Returns sum.
    """
    answer_lower = answer.lower()
    score = 0.0
    
    # Check decision
    if ground_truth["decision"].lower() in answer_lower:
        score += 0.4
    
    # Check for correct policy version (look for correct numbers)
    correct_version = ground_truth["correct_policy_version"]
    if correct_version == "v1" and "7" in answer_lower:
        score += 0.3
    elif correct_version == "v2" and "30" in answer_lower:
        score += 0.3
    elif correct_version == "v3" and "14" in answer_lower:
        score += 0.3
    
    # Check if legacy trap is triggered
    legacy_trap = ground_truth.get("legacy_trap")
    if legacy_trap:
        # Check for wrong numbers
        if correct_version == "v1":
            wrong_numbers = ["14", "30", "39"]
        elif correct_version == "v2":
            wrong_numbers = ["7", "14", "39"]
        elif correct_version == "v3":
            wrong_numbers = ["7", "30"]
        else:
            wrong_numbers = []
        
        trap_triggered = False
        for num in wrong_numbers:
            if num in answer_lower:
                trap_triggered = True
                break
        
        if not trap_triggered:
            score += 0.3
    else:
        # No trap, give full points
        score += 0.3
    
    return score


def grade(answer: str, ticket: dict, world_state: WorldState) -> dict:
    """
    Routes to correct grader based on ticket["task_type"].
    Returns: {"score": float, "correct": bool, "policy_version_used": str, "policy_version_expected": str}
    correct = score >= 0.8
    """
    task_type = ticket["task_type"]
    ground_truth = ticket["ground_truth"]
    
    if task_type == "A":
        score = grade_task_a(answer, ground_truth)
    elif task_type == "B":
        score = grade_task_b(answer, ground_truth, world_state)
    elif task_type == "C":
        score = grade_task_c(answer, ground_truth, world_state)
    else:
        raise ValueError(f"Unknown task type: {task_type}")
    
    # Try to detect policy version used in answer
    answer_lower = answer.lower()
    policy_version_used = "unknown"
    if "7" in answer_lower and ("day" in answer_lower or "refund" in answer_lower):
        policy_version_used = "v1"
    elif "30" in answer_lower and ("day" in answer_lower or "refund" in answer_lower):
        policy_version_used = "v2"
    elif "14" in answer_lower and ("day" in answer_lower or "refund" in answer_lower):
        policy_version_used = "v3"
    
    return {
        "score": score,
        "correct": score >= 0.8,
        "policy_version_used": policy_version_used,
        "policy_version_expected": ticket["policy_version_expected"]
    }
