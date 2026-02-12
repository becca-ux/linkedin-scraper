"""Ideal candidate profiles for each role at Hook."""

ROLE_PROFILES = {
    "account_manager": {
        "title": "Account Manager",
        "description": (
            "Hook is a B2B SaaS company (Series A, ~45 people) looking for "
            "Account Managers who can own post-sale relationships, drive "
            "expansion revenue, and reduce churn."
        ),
        "must_haves": [
            "2-5 years in Account Management or Customer Success at a B2B SaaS company",
            "Experience managing a book of business ($500K-$2M ARR)",
            "Track record of net revenue retention above 100%",
            "Strong communication and relationship-building skills",
        ],
        "nice_to_haves": [
            "Experience at a Series A-C startup",
            "Familiarity with product-led growth motions",
            "Experience with Salesforce, Gainsight, or similar tools",
            "Background in a relevant vertical (fintech, martech, etc.)",
        ],
        "red_flags": [
            "Only agency or services experience (no SaaS)",
            "Very short tenures (<1 year) at multiple companies",
            "No quota-carrying experience",
        ],
    },
    "solutions_consultant": {
        "title": "Solutions Consultant",
        "description": (
            "Hook needs Solutions Consultants / Sales Engineers who can "
            "partner with AEs on technical sales cycles, run product demos, "
            "and handle technical objections."
        ),
        "must_haves": [
            "3-6 years as Solutions Consultant, Sales Engineer, or Pre-Sales",
            "Experience in B2B SaaS technical sales",
            "Ability to demo software and handle technical deep-dives",
            "Strong blend of technical and communication skills",
        ],
        "nice_to_haves": [
            "Engineering or CS background",
            "Experience at a growth-stage startup",
            "API and integration experience",
            "Familiarity with the data/analytics space",
        ],
        "red_flags": [
            "Purely engineering with no customer-facing experience",
            "Only worked at very large enterprises (may struggle in startup pace)",
        ],
    },
    "enterprise_ae": {
        "title": "Enterprise Account Executive",
        "description": (
            "Hook is hiring Enterprise AEs to close six-figure deals with "
            "large accounts. This is a strategic, consultative sales role."
        ),
        "must_haves": [
            "4-8 years of B2B SaaS sales experience",
            "At least 2 years selling to enterprise (deal sizes $100K+)",
            "Consistent quota attainment (>80%)",
            "Experience with complex, multi-stakeholder sales cycles",
        ],
        "nice_to_haves": [
            "Experience selling a new category or early-stage product",
            "Track record at high-growth startups",
            "MEDDIC, Challenger, or similar methodology experience",
            "Existing network in target verticals",
        ],
        "red_flags": [
            "Only SMB/transactional sales experience",
            "No clear evidence of quota attainment",
            "Job-hopping without progression",
        ],
    },
}


def get_profile(role_key: str) -> dict:
    """Get the ideal candidate profile for a role.

    Valid role_keys: account_manager, solutions_consultant, enterprise_ae
    """
    profile = ROLE_PROFILES.get(role_key)
    if not profile:
        raise ValueError(
            f"Unknown role: {role_key}. "
            f"Valid roles: {list(ROLE_PROFILES.keys())}"
        )
    return profile


def format_profile_for_prompt(role_key: str) -> str:
    """Format a role profile into text for the Claude scoring prompt."""
    profile = get_profile(role_key)
    lines = [
        f"Role: {profile['title']}",
        f"Context: {profile['description']}",
        "",
        "Must-Haves:",
    ]
    for item in profile["must_haves"]:
        lines.append(f"  - {item}")
    lines.append("")
    lines.append("Nice-to-Haves:")
    for item in profile["nice_to_haves"]:
        lines.append(f"  - {item}")
    lines.append("")
    lines.append("Red Flags:")
    for item in profile["red_flags"]:
        lines.append(f"  - {item}")
    return "\n".join(lines)
