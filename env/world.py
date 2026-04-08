# STATUS: COMPLETE
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Plan:
    name: str
    monthly_price: float
    features: list[str]
    max_seats: int


@dataclass
class Policy:
    version: str
    refund_window_days: int
    upgrade_allowed: bool
    downgrade_allowed: bool
    priority_support: bool
    applies_to_new_customers_from_week: int


@dataclass
class WorldState:
    week: int
    plans: dict[str, Plan]
    current_policy: Policy
    legacy_policies: list[Policy]
    feature_flags: dict[str, bool]
    ticket_weights: dict[str, float]


def get_initial_state() -> WorldState:
    """Returns the initial world state at week 1."""
    return WorldState(
        week=1,
        plans={
            "Basic": Plan(
                name="Basic",
                monthly_price=9.0,
                features=["core_dashboard", "email_support"],
                max_seats=1
            ),
            "Pro": Plan(
                name="Pro",
                monthly_price=29.0,
                features=["core_dashboard", "email_support", "api_access", "analytics"],
                max_seats=5
            ),
            "Enterprise": Plan(
                name="Enterprise",
                monthly_price=99.0,
                features=["core_dashboard", "email_support", "api_access", "analytics", "sso", "dedicated_support"],
                max_seats=-1
            )
        },
        current_policy=Policy(
            version="v1",
            refund_window_days=7,
            upgrade_allowed=True,
            downgrade_allowed=True,
            priority_support=False,
            applies_to_new_customers_from_week=1
        ),
        legacy_policies=[],
        feature_flags={
            "analytics": True,
            "sso": True,
            "bulk_export": False
        },
        ticket_weights={"A": 0.4, "B": 0.4, "C": 0.2}
    )


def advance_week(state: WorldState) -> WorldState:
    """Pure function that advances world state by one week."""
    new_week = state.week + 1
    
    if new_week == 2:
        # Week 2 changes
        new_policy = Policy(
            version="v2",
            refund_window_days=30,
            upgrade_allowed=True,
            downgrade_allowed=True,
            priority_support=False,
            applies_to_new_customers_from_week=2
        )
        
        new_plans = {
            "Basic": Plan(
                name="Basic",
                monthly_price=9.0,
                features=["core_dashboard", "email_support"],
                max_seats=1
            ),
            "Pro": Plan(
                name="Pro",
                monthly_price=29.0,
                features=["core_dashboard", "email_support", "api_access", "analytics", "bulk_export"],
                max_seats=5
            ),
            "Enterprise": Plan(
                name="Enterprise",
                monthly_price=99.0,
                features=["core_dashboard", "email_support", "api_access", "analytics", "sso", "dedicated_support", "bulk_export"],
                max_seats=-1
            )
        }
        
        return WorldState(
            week=2,
            plans=new_plans,
            current_policy=new_policy,
            legacy_policies=[state.current_policy],
            feature_flags={
                "analytics": True,
                "sso": True,
                "bulk_export": True
            },
            ticket_weights={"A": 0.3, "B": 0.4, "C": 0.3}
        )
    
    elif new_week == 3:
        # Week 3 changes
        new_policy = Policy(
            version="v3",
            refund_window_days=14,
            upgrade_allowed=True,
            downgrade_allowed=True,
            priority_support=True,
            applies_to_new_customers_from_week=3
        )
        
        new_plans = {
            "Basic": Plan(
                name="Basic",
                monthly_price=9.0,
                features=["core_dashboard", "email_support"],
                max_seats=1
            ),
            "Pro": Plan(
                name="Pro",
                monthly_price=39.0,
                features=["core_dashboard", "email_support", "api_access", "bulk_export"],
                max_seats=5
            ),
            "Enterprise": Plan(
                name="Enterprise",
                monthly_price=99.0,
                features=["core_dashboard", "email_support", "api_access", "analytics", "sso", "dedicated_support", "bulk_export"],
                max_seats=-1
            )
        }
        
        return WorldState(
            week=3,
            plans=new_plans,
            current_policy=new_policy,
            legacy_policies=state.legacy_policies + [state.current_policy],
            feature_flags={
                "analytics": False,
                "sso": True,
                "bulk_export": True
            },
            ticket_weights={"A": 0.2, "B": 0.4, "C": 0.4}
        )
    
    else:
        # Beyond week 3, no changes
        return WorldState(
            week=new_week,
            plans=state.plans.copy(),
            current_policy=state.current_policy,
            legacy_policies=state.legacy_policies.copy(),
            feature_flags=state.feature_flags.copy(),
            ticket_weights=state.ticket_weights.copy()
        )
