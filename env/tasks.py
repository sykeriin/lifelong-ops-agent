# STATUS: COMPLETE
import random
import uuid
from env.world import WorldState


# Task A templates
TASK_A_TEMPLATES = [
    {
        "subject": "Billing issue with {plan} plan",
        "body": "Hi, I'm {customer_name} and I noticed an unexpected charge on my {plan} plan. Can you help?",
        "category": "billing",
        "priority_base": "medium"
    },
    {
        "subject": "Question about {feature} feature",
        "body": "Hello, does my {plan} plan include {feature}? I can't find it in my dashboard.",
        "category": "feature",
        "priority_base": "low"
    },
    {
        "subject": "Cannot access my account",
        "body": "I'm {customer_name} and I can't log into my account. Please help urgently.",
        "category": "account",
        "priority_base": "low"
    },
    {
        "subject": "Want to upgrade to {target_plan}",
        "body": "Hi, I'm currently on {plan} and would like to upgrade to {target_plan}. What's the process?",
        "category": "upgrade",
        "priority_base": "low"
    },
    {
        "subject": "Refund request for {plan} plan",
        "body": "I'd like to request a refund for my {plan} subscription. I signed up {days} days ago.",
        "category": "refund",
        "priority_base": "high"
    },
    {
        "subject": "Billing cycle question",
        "body": "When will I be charged next for my {plan} plan? I'm {customer_name}.",
        "category": "billing",
        "priority_base": "medium"
    },
    {
        "subject": "Feature request: {feature}",
        "body": "Would love to see {feature} added to the {plan} plan!",
        "category": "feature",
        "priority_base": "low"
    },
    {
        "subject": "Account settings help needed",
        "body": "I'm trying to update my account settings but getting an error. I'm on the {plan} plan.",
        "category": "account",
        "priority_base": "low"
    }
]

CUSTOMER_NAMES = ["Alice", "Bob", "Charlie", "Diana", "Eve", "Frank", "Grace", "Henry"]
FEATURES = ["analytics", "api_access", "bulk_export", "sso", "dedicated_support"]


def generate_episode(task_type: str, world_state: WorldState, seed: int) -> dict:
    """Returns a single ticket dict with ground_truth populated."""
    rng = random.Random(seed)
    
    if task_type == "A":
        return _generate_task_a(world_state, rng)
    elif task_type == "B":
        return _generate_task_b(world_state, rng)
    elif task_type == "C":
        return _generate_task_c(world_state, rng)
    else:
        raise ValueError(f"Unknown task type: {task_type}")


def generate_batch(task_type: str, world_state: WorldState, n: int, seed: int) -> list[dict]:
    """Returns n tickets for a given task type and world state."""
    tickets = []
    for i in range(n):
        ticket = generate_episode(task_type, world_state, seed + i)
        tickets.append(ticket)
    return tickets


def _generate_task_a(world_state: WorldState, rng: random.Random) -> dict:
    """Generate Task A: Ticket Triage & Routing"""
    template = rng.choice(TASK_A_TEMPLATES)
    customer_name = rng.choice(CUSTOMER_NAMES)
    plan_name = rng.choice(list(world_state.plans.keys()))
    plan = world_state.plans[plan_name]
    
    # Determine signup week (can be any week <= current week)
    signup_week = rng.randint(1, world_state.week)
    
    # Get the price at signup
    if signup_week == 1:
        price_at_signup = {"Basic": 9.0, "Pro": 29.0, "Enterprise": 99.0}[plan_name]
    elif signup_week == 2:
        price_at_signup = {"Basic": 9.0, "Pro": 29.0, "Enterprise": 99.0}[plan_name]
    else:  # week 3+
        price_at_signup = {"Basic": 9.0, "Pro": 39.0, "Enterprise": 99.0}[plan_name]
    
    feature = rng.choice(FEATURES)
    target_plan = rng.choice([p for p in world_state.plans.keys() if p != plan_name])
    days = rng.randint(1, 45)
    
    subject = template["subject"].format(
        plan=plan_name,
        feature=feature,
        target_plan=target_plan,
        customer_name=customer_name,
        days=days
    )
    body = template["body"].format(
        plan=plan_name,
        feature=feature,
        target_plan=target_plan,
        customer_name=customer_name,
        days=days
    )
    
    # Determine priority
    category = template["category"]
    priority = template["priority_base"]
    
    if category == "refund":
        priority = "high"
    elif plan_name == "Enterprise":
        priority = "high"
    elif category == "billing":
        priority = "medium"
    
    # Get policy version for this customer
    policy_version = _get_policy_version_for_signup(signup_week, world_state)
    
    return {
        "id": str(uuid.uuid4()),
        "task_type": "A",
        "subject": subject,
        "body": body,
        "customer": {
            "id": str(uuid.uuid4()),
            "plan": plan_name,
            "signup_week": signup_week,
            "monthly_price_locked": price_at_signup
        },
        "ground_truth": {
            "category": category,
            "priority": priority
        },
        "policy_version_expected": policy_version
    }


def _generate_task_b(world_state: WorldState, rng: random.Random) -> dict:
    """Generate Task B: Policy Application"""
    customer_name = rng.choice(CUSTOMER_NAMES)
    plan_name = rng.choice(list(world_state.plans.keys()))
    
    # Determine signup week
    signup_week = rng.randint(1, world_state.week)
    
    # Get policy for this customer
    policy_version = _get_policy_version_for_signup(signup_week, world_state)
    refund_window = _get_refund_window_for_signup(signup_week, world_state)
    
    # Get price at signup
    if signup_week == 1:
        price_at_signup = {"Basic": 9.0, "Pro": 29.0, "Enterprise": 99.0}[plan_name]
    elif signup_week == 2:
        price_at_signup = {"Basic": 9.0, "Pro": 29.0, "Enterprise": 99.0}[plan_name]
    else:
        price_at_signup = {"Basic": 9.0, "Pro": 39.0, "Enterprise": 99.0}[plan_name]
    
    # Generate days since purchase
    days_since_purchase = rng.randint(1, 45)
    
    # Determine decision
    if days_since_purchase <= refund_window:
        decision = "approve"
        key_reason = f"within {refund_window}-day refund window"
    else:
        decision = "deny"
        key_reason = f"outside {refund_window}-day refund window"
    
    subject = f"Refund request for {plan_name} plan"
    body = f"Hi, I'm {customer_name}. I signed up for the {plan_name} plan {days_since_purchase} days ago and paid ${price_at_signup}/month. I'd like to request a refund."
    
    return {
        "id": str(uuid.uuid4()),
        "task_type": "B",
        "subject": subject,
        "body": body,
        "customer": {
            "id": str(uuid.uuid4()),
            "plan": plan_name,
            "signup_week": signup_week,
            "monthly_price_locked": price_at_signup
        },
        "ground_truth": {
            "decision": decision,
            "key_reason": key_reason,
            "correct_policy_version": policy_version
        },
        "policy_version_expected": policy_version
    }


def _generate_task_c(world_state: WorldState, rng: random.Random) -> dict:
    """Generate Task C: Legacy vs New Customer"""
    customer_name = rng.choice(CUSTOMER_NAMES)
    plan_name = rng.choice(list(world_state.plans.keys()))
    
    # 50% legacy, 50% new
    is_legacy = rng.random() < 0.5
    
    if is_legacy and world_state.week > 1:
        signup_week = rng.randint(1, world_state.week - 1)
    else:
        signup_week = world_state.week
        is_legacy = False
    
    # Get policy for this customer
    policy_version = _get_policy_version_for_signup(signup_week, world_state)
    refund_window = _get_refund_window_for_signup(signup_week, world_state)
    
    # Get price at signup
    if signup_week == 1:
        price_at_signup = {"Basic": 9.0, "Pro": 29.0, "Enterprise": 99.0}[plan_name]
    elif signup_week == 2:
        price_at_signup = {"Basic": 9.0, "Pro": 29.0, "Enterprise": 99.0}[plan_name]
    else:
        price_at_signup = {"Basic": 9.0, "Pro": 39.0, "Enterprise": 99.0}[plan_name]
    
    # Generate days since purchase
    days_since_purchase = rng.randint(1, 45)
    
    # Determine decision
    if days_since_purchase <= refund_window:
        decision = "approve"
        key_reason = f"within {refund_window}-day refund window"
    else:
        decision = "deny"
        key_reason = f"outside {refund_window}-day refund window"
    
    # Determine legacy trap
    legacy_trap = None
    if is_legacy:
        current_policy_version = world_state.current_policy.version
        current_refund_window = world_state.current_policy.refund_window_days
        if current_policy_version != policy_version:
            legacy_trap = f"Agent applies {current_policy_version} {current_refund_window}-day window to legacy customer who has {refund_window}-day window"
        
        if plan_name == "Pro" and world_state.week >= 3 and signup_week < 3:
            legacy_trap = f"Agent applies current $39 Pro price to customer locked at ${price_at_signup}"
    
    subject = f"Refund request for {plan_name} plan"
    body = f"Hi, I'm {customer_name}. I signed up for the {plan_name} plan in week {signup_week}, {days_since_purchase} days ago. I'm paying ${price_at_signup}/month. I'd like to request a refund."
    
    return {
        "id": str(uuid.uuid4()),
        "task_type": "C",
        "subject": subject,
        "body": body,
        "customer": {
            "id": str(uuid.uuid4()),
            "plan": plan_name,
            "signup_week": signup_week,
            "monthly_price_locked": price_at_signup
        },
        "ground_truth": {
            "decision": decision,
            "correct_policy_version": policy_version,
            "is_legacy": is_legacy,
            "legacy_trap": legacy_trap
        },
        "policy_version_expected": policy_version
    }


def _get_policy_version_for_signup(signup_week: int, world_state: WorldState) -> str:
    """Determine which policy version applies to a customer based on signup week."""
    if signup_week == 1:
        return "v1"
    elif signup_week == 2:
        return "v2"
    else:
        return "v3"


def _get_refund_window_for_signup(signup_week: int, world_state: WorldState) -> int:
    """Determine refund window for a customer based on signup week."""
    if signup_week == 1:
        return 7
    elif signup_week == 2:
        return 30
    else:
        return 14
