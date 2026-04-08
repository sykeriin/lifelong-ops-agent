# STATUS: COMPLETE
from typing import Optional
from env.world import WorldState


KB_ARTICLES = [
    {
        "id": "plan_basic_v1",
        "title": "Basic Plan Details",
        "body": "The Basic plan costs $9/month and includes core_dashboard and email_support. Maximum 1 seat.",
        "valid_from_week": 1,
        "valid_until_week": None,
        "tags": ["pricing", "basic", "plan"]
    },
    {
        "id": "plan_pro_v1",
        "title": "Pro Plan Details (Week 1-2)",
        "body": "The Pro plan costs $29/month and includes core_dashboard, email_support, api_access, and analytics. Maximum 5 seats.",
        "valid_from_week": 1,
        "valid_until_week": 2,
        "tags": ["pricing", "pro", "plan"]
    },
    {
        "id": "plan_pro_v2",
        "title": "Pro Plan Details (Week 2)",
        "body": "The Pro plan costs $29/month for existing customers. New customers from Week 2 get bulk_export feature included. Maximum 5 seats.",
        "valid_from_week": 2,
        "valid_until_week": 2,
        "tags": ["pricing", "pro", "plan"]
    },
    {
        "id": "plan_pro_v3",
        "title": "Pro Plan Details (Week 3+)",
        "body": "The Pro plan costs $39/month for NEW customers starting Week 3. Legacy customers keep $29/month. Includes core_dashboard, email_support, api_access, and bulk_export. Analytics removed as of Week 3. Maximum 5 seats.",
        "valid_from_week": 3,
        "valid_until_week": None,
        "tags": ["pricing", "pro", "plan", "legacy"]
    },
    {
        "id": "plan_enterprise_v1",
        "title": "Enterprise Plan Details",
        "body": "The Enterprise plan costs $99/month and includes all features: core_dashboard, email_support, api_access, analytics, sso, dedicated_support, and bulk_export (from Week 2). Unlimited seats. Priority support with 2-hour SLA from Week 3.",
        "valid_from_week": 1,
        "valid_until_week": None,
        "tags": ["pricing", "enterprise", "plan"]
    },
    {
        "id": "refund_policy_v1",
        "title": "Refund Policy v1",
        "body": "Customers may request a refund within 7 days of purchase. This applies to all customers who signed up in Week 1.",
        "valid_from_week": 1,
        "valid_until_week": 1,
        "tags": ["refund", "policy", "v1"]
    },
    {
        "id": "refund_policy_v2",
        "title": "Refund Policy v2",
        "body": "As of Week 2, new customers may request a refund within 30 days of purchase. Customers who signed up before Week 2 retain their original 7-day refund window.",
        "valid_from_week": 2,
        "valid_until_week": 2,
        "tags": ["refund", "policy", "v2"]
    },
    {
        "id": "refund_policy_v3",
        "title": "Refund Policy v3",
        "body": "As of Week 3, the refund window for new customers is 14 days. Customers who signed up in Week 2 keep their 30-day window. Customers who signed up in Week 1 keep their 7-day window.",
        "valid_from_week": 3,
        "valid_until_week": None,
        "tags": ["refund", "policy", "v3"]
    },
    {
        "id": "bulk_export_announcement",
        "title": "Bulk Export Feature Launch",
        "body": "Bulk export is now available on Pro and Enterprise plans starting Week 2.",
        "valid_from_week": 2,
        "valid_until_week": None,
        "tags": ["feature", "bulk_export", "announcement"]
    },
    {
        "id": "analytics_deprecation",
        "title": "Analytics Feature Deprecation",
        "body": "Analytics has been removed from Basic and Pro plans as of Week 3. Enterprise customers retain access to analytics.",
        "valid_from_week": 3,
        "valid_until_week": None,
        "tags": ["feature", "analytics", "deprecation"]
    },
    {
        "id": "enterprise_priority_support",
        "title": "Enterprise Priority Support",
        "body": "Enterprise customers now receive priority support with 2-hour SLA starting Week 3.",
        "valid_from_week": 3,
        "valid_until_week": None,
        "tags": ["enterprise", "support", "priority"]
    },
    {
        "id": "legacy_customer_clause",
        "title": "Legacy Customer Policy",
        "body": "Customers who signed up before a policy change retain their original terms, including pricing and refund windows. This is our commitment to grandfathering existing customers.",
        "valid_from_week": 1,
        "valid_until_week": None,
        "tags": ["legacy", "policy", "grandfathering"]
    }
]


def search_kb(query: str, world_state: WorldState, top_k: int = 3) -> list[dict]:
    """
    Returns top_k articles relevant to query that are valid in the current week.
    Uses simple keyword overlap scoring.
    """
    query_lower = query.lower()
    query_words = set(query_lower.split())
    
    scored_articles = []
    
    for article in KB_ARTICLES:
        # Filter by validity
        if article["valid_from_week"] > world_state.week:
            continue
        if article["valid_until_week"] is not None and article["valid_until_week"] < world_state.week:
            continue
        
        # Score by keyword overlap
        article_text = (article["title"] + " " + article["body"] + " " + " ".join(article["tags"])).lower()
        article_words = set(article_text.split())
        
        overlap = len(query_words & article_words)
        
        # Boost score if query substring appears in title or body
        if query_lower in article["title"].lower():
            overlap += 5
        if query_lower in article["body"].lower():
            overlap += 3
        
        if overlap > 0:
            scored_articles.append((overlap, article))
    
    # Sort by score descending
    scored_articles.sort(key=lambda x: x[0], reverse=True)
    
    # Return top_k
    return [article for _, article in scored_articles[:top_k]]
