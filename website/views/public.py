from urllib.parse import quote

from django.conf import settings
from django.views.generic import TemplateView


NAV_LINKS = [
    {"label": "Home", "href": "#home"},
    {"label": "Features", "href": "#features"},
    {"label": "How It Works", "href": "#how-it-works"},
    {"label": "About", "href": "#about"},
    {"label": "Contact", "href": "#contact"},
]

AUDIENCE_CARDS = [
    {
        "eyebrow": "Players",
        "title": "Stay focused on every training block",
        "description": (
            "Follow assigned sessions, log nutrition, and understand weekly progress "
            "from one clear football performance hub."
        ),
        "points": [
            "Follow assigned sessions",
            "Track nutrition and recovery habits",
            "View weekly progress in one place",
        ],
        "tone": "blue",
    },
    {
        "eyebrow": "Coaches",
        "title": "Lead structured development with less friction",
        "description": (
            "Build training plans, schedule sessions, and monitor every player without "
            "losing time across disconnected tools."
        ),
        "points": [
            "Create training plans quickly",
            "Assign sessions to the right players",
            "Monitor readiness and development",
        ],
        "tone": "green",
    },
    {
        "eyebrow": "Academies / Clubs",
        "title": "Coordinate people, plans, and performance",
        "description": (
            "Organize player development workflows and keep coach-player communication "
            "centralized inside one professional platform."
        ),
        "points": [
            "Organize player development at scale",
            "Manage training workflows centrally",
            "Align coaches and players across the club",
        ],
        "tone": "orange",
    },
]

FEATURE_CARDS = [
    {
        "icon": "TP",
        "title": "Personalized Training Plans",
        "description": "Create football-specific plans that fit player goals, stages, and weekly training cycles.",
    },
    {
        "icon": "SS",
        "title": "Session Scheduling",
        "description": "Keep every workout visible with a clear calendar flow for coaches and players.",
    },
    {
        "icon": "PA",
        "title": "Player Assignment",
        "description": "Assign the right sessions to the right players without juggling spreadsheets or chat threads.",
    },
    {
        "icon": "PD",
        "title": "Player Dashboard",
        "description": "Give athletes a clean weekly home for sessions, nutrition, and development status.",
    },
    {
        "icon": "NT",
        "title": "Nutrition Tracking",
        "description": "Support performance habits beyond the pitch with simple, visible meal tracking.",
    },
    {
        "icon": "WO",
        "title": "Weekly Performance Overview",
        "description": "Surface progress patterns and workload snapshots that are easy to scan and discuss.",
    },
    {
        "icon": "CM",
        "title": "Coach Management Tools",
        "description": "Approve coaches, manage access, and keep the coaching side of the platform organized.",
    },
]

HOW_IT_WORKS_STEPS = [
    {
        "number": "01",
        "title": "Coach creates a training plan",
        "description": "Build a structured plan with the sessions and weekly focus the player needs.",
    },
    {
        "number": "02",
        "title": "Sessions are scheduled and assigned",
        "description": "Place the right sessions on the calendar and connect them to the right athletes.",
    },
    {
        "number": "03",
        "title": "Players train and track nutrition",
        "description": "Athletes follow the plan, complete work, and keep daily habits visible.",
    },
    {
        "number": "04",
        "title": "Coaches monitor progress",
        "description": "Review completion, consistency, and development over time from one shared system.",
    },
]

PRODUCT_PREVIEWS = [
    {
        "title": "Player Home Dashboard",
        "label": "Player",
        "description": "A clear weekly home for today's session, nutrition, and performance momentum.",
        "tone": "blue",
        "metrics": ["Today Session", "Weekly Score", "Nutrition Check"],
    },
    {
        "title": "Coach Training Plans Screen",
        "label": "Coach",
        "description": "A practical overview of active plans, assigned players, and next sessions.",
        "tone": "green",
        "metrics": ["Active Plans", "Assigned Players", "Upcoming Sessions"],
    },
    {
        "title": "Create Training Plan Screen",
        "label": "Workflow",
        "description": "A guided builder for shaping session blocks, objectives, and schedule timing.",
        "tone": "orange",
        "metrics": ["Plan Builder", "Session Blocks", "Weekly Focus"],
    },
    {
        "title": "Admin Coach Requests Panel",
        "label": "Admin",
        "description": "A staff-ready approval area for reviewing coach access and certificates cleanly.",
        "tone": "blue",
        "metrics": ["Pending Reviews", "Certificates", "Approval Actions"],
    },
]

BENEFITS = [
    {
        "title": "Better training organization",
        "description": "Keep plans, sessions, and responsibilities clear across the full training cycle.",
    },
    {
        "title": "Stronger player engagement",
        "description": "Give players one reliable place to follow work, see progress, and stay accountable.",
    },
    {
        "title": "Clear performance tracking",
        "description": "Turn weekly activity into visible progress that coaches can actually act on.",
    },
    {
        "title": "Time-saving for coaches",
        "description": "Reduce scattered coordination and spend more time coaching instead of chasing updates.",
    },
    {
        "title": "Structured development workflow",
        "description": "Support a professional development process from session assignment to review and approval.",
    },
]


def _marketing_email():
    return (
        getattr(settings, "MARKETING_CONTACT_EMAIL", "")
        or getattr(settings, "ADMIN_SUPPORT_EMAIL", "")
        or getattr(settings, "EMAIL_HOST_USER", "")
        or "hello@xpertforma.com"
    ).strip()


def _mailto_link(subject):
    email = _marketing_email()
    return f"mailto:{email}?subject={quote(subject)}"


class LandingPageView(TemplateView):
    template_name = "website/public/landing.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "nav_links": NAV_LINKS,
                "audience_cards": AUDIENCE_CARDS,
                "feature_cards": FEATURE_CARDS,
                "how_it_works_steps": HOW_IT_WORKS_STEPS,
                "product_previews": PRODUCT_PREVIEWS,
                "benefits": BENEFITS,
                "contact_email": _marketing_email(),
                "get_started_href": "#final-cta",
                "request_demo_href": _mailto_link("XpertForma Demo Request"),
            }
        )
        return context
