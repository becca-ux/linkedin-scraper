"""Ideal candidate profiles for each role at Hook.

Profiles derived from 6 exemplar candidates provided by the hiring team:
- AE exemplars: Carson Venneri (interVal.ai), Sam Champion (Hook), Charlie (MoveAI)
- CSM exemplars: Lucy (Sonder), Katy-Jo Close (Multiverse), Adi (Tendable)
"""

# ---------------------------------------------------------------------------
# Exemplar CVs — used as calibration data for Claude scoring
# ---------------------------------------------------------------------------

_AE_EXEMPLARS = """
=== EXEMPLAR AE 1: Carson R. Venneri ===
Location: Toronto, ON
Current Role: Strategic Account Executive at interVal.ai (Jan 2025 - Present)

- Grew the company from $300K ARR to $1.85M+ ARR, alongside the leadership team (sole AE)
- Ran full-cycle deals across SMB, mid-market and enterprise segments from prospecting to close
- Sold six-figure deals to multiple new logos
- Built and managed a pipeline of ~$3M, with deal sizes ranging from $15K-$850K+
- Sourced, managed and closed two of the largest enterprise deals in company history
- Collaborates with leadership to build-out GTM playbook
- Oversees Sales Development Representatives

Previous: SMB & Mid-Market AE at interVal.ai (Mar 2023 - Jan 2025)
- Built and managed a pipeline of ~$1M, deal sizes $15K-$250K
- Closed the company's first U.S deal
- Set company record for deal velocity in a quarter

Previous: BDR at interVal.ai (Jul 2022 - Mar 2023)
- 1 of 2 founding BDRs brought on to drive pipeline
- Built a $1M+ pipeline in a whitespace market with an unproven brand/product

Education: BA Business Administration, University of Western Ontario
Skills: Prospecting, Consultative Selling, Negotiating, Pipeline Generation, Value Selling, SaaS

=== EXEMPLAR AE 2: Sam Champion ===
Location: London, England
Current Role: Senior Account Executive (Enterprise Segment) at Hook (Oct 2024 - Present)

- Closed >70% of all company revenue, from near-zero $ at joining to present day (~18 months post-Series A)
- Promoted to Senior AE after over-achieving the past 6 quarter's quota

Previous: Founding Account Executive at Hook (Jan 2023 - Oct 2024)
- Reporting direct to the CEO - working together to build out the GTM motion
- Interviewing new AE candidates & helping onboard/coach new starters

Previous: Account Executive at Codat (Aug 2022 - Dec 2022)
Previous: Senior AE at Lantum (Jan 2022 - Jul 2022) - Enterprise role, closed deals up to £240,000 TCV
Previous: AE at Lantum (Jul 2021 - Jan 2022) - Mid-market, full cycle
Previous: BDR at Lantum (Jan 2021 - Jul 2021)

Education: University of California, Berkeley

=== EXEMPLAR AE 3: Charlie ===
Location: London (assumed)
Current Role: Enterprise Account Executive at MoveAI (Jan 2024 - Present)

- First sales hire at Move, responsible for setting, delivering, and optimizing the GTM strategy
- Joined at $700k ARR, now led commercial team to $1.8m ARR (more than doubled)
- Holding and achieving a $1m target with multiple 6-figure deals closed
- Sourced and owned the company's 2nd, 3rd & 4th largest deals ($140K-$210K)
- Led renewal of largest clients (EA, Sony, etc.)
- 41% conversion rate from Opportunities to Closed Won
- Built the pricing strategy and GTM for the company's most successful product
- Of $1m target, 80% is new business

Previous: Account Executive at SilicoAI (Sep 2021 - Jan 2024)
- Part of team that closed Vodafone for £120K p.a. — Silico's first customer
- 77% discovery-to-demo success rate, 65% PoV close rate
- Ran PoVs with Siemens, ABB, Openreach, Rabobank, Shell, Meta, Bentley
- 5 of 8 mature opportunities were self-sourced from cold outbound

Education: BA Economics and Philosophy, University of Southampton
"""


_CSM_EXEMPLARS = """
=== EXEMPLAR CSM 1: Lucy ===
Location: London/UK
Current Role: Senior Customer Success Manager at Sonder (May 2023 - Present)

- Drove 105% NRR for FY25 including 100% retention
- Achieved 100% CSAT for the UK market
- Founding member of Sonder's UK expansion, owns UK customer strategy and retention number
- Spearheads UK customer strategy, working with VP Customer and Product
- Collaborated with sales to secure the largest deal to date

Previous: Senior CSM at Atomi (Oct 2022 - Apr 2023)
- Guided, coached and mentored 3 CSMs
- Owned complex negotiations with C-suite, 95% renewal rate across $2.5m book

Previous: CSM at Atomi (Oct 2021 - Oct 2022)
- 138 customers, $1.4m portfolio
- Exceeded yearly expansion goals by 229%

Previous: Partner Consultant at Xero (Apr 2020 - Aug 2021)
- Three promotions in under 2.5 years (BDR -> Account Manager -> Partner Consultant)
- Delivered presentations to 400+ partners, executed national training program for 800+ clients

Education: Bachelor of Business, University of Technology Sydney

=== EXEMPLAR CSM 2: Katy-Jo Close ===
Location: London
Current Role: Regional Director, Customer Success at Multiverse (May 2023 - Present)

- YoY revenue grew 129%, NHS seeing 1000% YoY growth
- Met all individual retention goals, 0 regrettable attrition
- Manages Major Account region with c. 34m revenue under management across 20 accounts
- Team of 6 Enterprise / Senior Enterprise CSMs
- Recruited 2 successful Enterprise CSMs

Previous: Enterprise CSM at Multiverse (Jul 2022 - May 2023)
- 125% YoY revenue growth, 216% growth in first landed Major Account
- Turned around high-churn risk accounts to close c. 800k in revenue
- CSM of the Quarter award in first full quarter

Previous: Customer Propositions Consultant at Landsec (Jan 2022 - May 2022)
Previous: Consultant at North Highland (Sep 2019 - Jan 2022) - Management consulting

Education: BSc 1st Class Economics, University of Exeter
Certifications: Prosci Change Management, CIRCL Accredited Coach

=== EXEMPLAR CSM 3: Adi ===
Location: London (assumed)
Current Role: Senior Customer Success Manager at Tendable (Aug 2025 - Present)

- Achieved 110% Net Revenue Retention on a 2.5m portfolio of NHS and Private healthcare providers

Previous: CSM at Tendable (Jun 2024 - Jul 2025)
- Managed over 20 accounts in healthcare, average NPS of 65 and NRR of 105%

Previous: Lead Consultant at Newton Europe (Jan 2023 - Jan 2024)
- Secured 7m in revenue by defining project acceptance criteria
- Led teams of 2-3, delivered 10m savings through operational improvements
- Delivered digital tools 4 weeks ahead of schedule, realising 700k savings
- Increased forecasted savings by 50% through improved methodology

Previous: Senior Consultant at Newton Europe (Aug 2021 - Dec 2022)
Previous: Consultant at Newton Europe (Nov 2019 - Sep 2021)

Education: Integrated Masters (First) Mechanical Engineering, Imperial College London
Skills: SQL, Python, Tableau, Power BI, Excel
"""


# ---------------------------------------------------------------------------
# Role profiles
# ---------------------------------------------------------------------------

ROLE_PROFILES = {
    "ae": {
        "title": "Account Executive",
        "description": (
            "Hook is a B2B SaaS company (Series A, ~45 people) based in London, "
            "looking for an Account Executive who can run full-cycle deals from "
            "prospecting to close. The ideal candidate has been an early/founding "
            "AE at a high-growth startup, built pipeline and GTM from scratch, "
            "and has a track record of closing six-figure enterprise deals while "
            "growing company ARR significantly."
        ),
        "must_haves": [
            "2+ years full-cycle B2B SaaS closing experience (prospecting through close)",
            "Experience at an early-stage or high-growth startup (Series A-C)",
            "Track record closing deals of $100K+ / £100K+",
            "Demonstrated ability to build pipeline and source own deals",
            "Consistent quota attainment or strong revenue growth metrics",
        ],
        "nice_to_haves": [
            "Founding AE or first sales hire — built GTM playbook from scratch",
            "BDR-to-AE career progression showing upward trajectory",
            "Experience growing company ARR significantly (e.g. 2x+ growth)",
            "Enterprise selling experience with complex, multi-stakeholder cycles",
            "Sold into multiple segments (SMB, mid-market, enterprise)",
            "Based in or willing to relocate to London",
        ],
        "red_flags": [
            "Only inbound/account management — no outbound prospecting experience",
            "Only large enterprise sales org experience (may struggle in startup pace)",
            "No evidence of quota attainment or revenue impact",
            "Very short tenures (<1 year) at multiple companies without progression",
            "Only agency, services, or non-SaaS experience",
        ],
    },
    "csm": {
        "title": "Customer Success Manager",
        "description": (
            "Hook is a B2B SaaS company (Series A, ~45 people) based in London, "
            "looking for a Customer Success Manager who can own enterprise "
            "relationships, drive net revenue retention, and reduce churn. The "
            "ideal candidate has managed a significant book of business with "
            "strong NRR metrics, has experience at high-growth startups, and "
            "brings either team leadership experience or a consulting background "
            "that gives them strong strategic and analytical skills."
        ),
        "must_haves": [
            "2+ years in Customer Success, Account Management, or Consulting at a B2B SaaS company",
            "Experience managing enterprise accounts with a book of business £1M+",
            "Track record of net revenue retention above 100%",
            "Strong stakeholder management — comfortable with C-suite and senior decision-makers",
            "Data-driven approach to customer health, renewal forecasting, and expansion",
        ],
        "nice_to_haves": [
            "Team leadership or mentoring experience (managing/coaching other CSMs)",
            "Management consulting background (McKinsey, BCG, Newton, North Highland, etc.)",
            "Rapid career progression — multiple promotions within a company",
            "Experience at a high-growth startup (Series A-C) or scaling a new market/region",
            "Cross-functional collaboration — working with Product, Sales, and leadership",
            "Based in or willing to relocate to London",
        ],
        "red_flags": [
            "Only support/reactive roles — no strategic account ownership",
            "No revenue or retention metrics to point to",
            "Only worked at very large, established companies (may struggle in startup pace)",
            "Very short tenures (<1 year) at multiple companies without progression",
            "No evidence of expansion revenue or commercial acumen",
        ],
    },
}


def get_profile(role_key: str) -> dict:
    """Get the ideal candidate profile for a role.

    Valid role_keys: ae, csm
    """
    profile = ROLE_PROFILES.get(role_key)
    if not profile:
        raise ValueError(
            f"Unknown role: {role_key}. "
            f"Valid roles: {list(ROLE_PROFILES.keys())}"
        )
    return profile


def get_example_cvs(role_key: str) -> str:
    """Get the exemplar CVs for a role, used as scoring calibration."""
    if role_key == "ae":
        return _AE_EXEMPLARS
    elif role_key == "csm":
        return _CSM_EXEMPLARS
    return ""


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
