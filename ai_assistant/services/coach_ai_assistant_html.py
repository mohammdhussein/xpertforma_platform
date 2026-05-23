import re
from html import escape

import bleach
from bleach.css_sanitizer import CSSSanitizer
from django.utils.dateparse import parse_date


ALLOWED_TAGS = ["div", "p", "h3", "h4", "span", "strong", "b", "ul", "li", "br"]
ALLOWED_ATTRIBUTES = {"*": ["style"]}
ALLOWED_CSS_PROPERTIES = [
    "background",
    "background-color",
    "border",
    "border-bottom",
    "border-left",
    "border-radius",
    "border-top",
    "box-shadow",
    "box-sizing",
    "color",
    "display",
    "font-family",
    "font-size",
    "font-weight",
    "gap",
    "line-height",
    "margin",
    "margin-bottom",
    "margin-left",
    "margin-right",
    "margin-top",
    "max-width",
    "padding",
    "padding-bottom",
    "padding-left",
    "padding-right",
    "padding-top",
    "text-align",
    "width",
    "word-break",
]


def render_answer_html(answer):
    status = _status_from_answer(answer)
    accent_color = _status_accent_color(status)
    html = (
        '<div style="font-family: system-ui, -apple-system, Segoe UI, sans-serif; color: #0f172a; '
        'line-height: 1.45; font-size: 15px; background-color: #ffffff; width: 100%; '
        'box-sizing: border-box; margin: 0; padding: 0;">'
        '<div style="background-color: #ffffff; border: 1px solid #dbe5f0; '
        f'border-left: 4px solid {accent_color}; border-radius: 8px; padding: 14px;">'
        f'<p style="margin: 0; color: #0f172a;">{_render_answer_text(answer or "", status)}</p>'
        "</div></div>"
    )
    return sanitize_assistant_html(html)


def render_plan_options_html(*, player_name, options):
    option_cards = "\n".join(
        render_plan_option_card(option, index=index)
        for index, option in enumerate(options, start=1)
    )
    option_count = len(options)
    count_label = _count_label(option_count)
    draft_label = "draft" if option_count == 1 else "drafts"
    html = f"""
<div style="width: 100%; background-color: #f8fafc; box-sizing: border-box; padding: 16px;">
  <div style="width: 100%; max-width: 720px; margin: 0 auto; font-family: system-ui, -apple-system, Segoe UI, sans-serif; color: #0f172a; line-height: 1.45; font-size: 15px;">
    <div style="background-color: #ffffff; border: 1px solid #dbe5f0; border-left: 4px solid #1e6eeb; border-radius: 22px; padding: 18px; margin-bottom: 16px; box-shadow: 0 4px 14px rgba(15,23,42,0.06);">
      <h3 style="margin: 0 0 6px 0; font-size: 22px; line-height: 1.2; color: #0f172a; font-weight: 800;">Training plan options</h3>
      <p style="margin: 0; color: #64748b; font-size: 14px;">{count_label} clean {draft_label} for <strong>{escape(player_name)}</strong>. Review the sessions, then choose one from the native app actions.</p>
    </div>
    {option_cards}
  </div>
</div>
"""
    return sanitize_assistant_html(html)


def render_plan_option_card(option, *, index=1):
    difficulty_background, difficulty_color = _difficulty_chip_colors(option["difficulty"])
    focus_chips = "".join(
        f'<span style="display: inline-block; background-color: #e8f1ff; color: #1458c3; '
        f'border-radius: 999px; padding: 6px 10px; margin: 0 6px 6px 0; font-size: 12px; '
        f'font-weight: 700;">{escape(area)}</span>'
        for area in option["focus_areas"]
    )
    preview_sessions = option["preview_sessions"][:3]
    preview_items = "".join(
        render_preview_session_item(session, is_last=session_index == len(preview_sessions))
        for session_index, session in enumerate(preview_sessions, start=1)
    )
    return f"""
    <div style="background-color: #ffffff; border: 1px solid #dbe5f0; border-radius: 22px; padding: 16px; margin-bottom: 14px; box-shadow: 0 4px 14px rgba(15,23,42,0.06);">
      <div style="margin-bottom: 12px;">
        <div style="margin-bottom: 8px;">
          <span style="display: inline-block; background-color: #1e6eeb; color: #ffffff; border-radius: 999px; padding: 5px 11px; margin: 0 6px 6px 0; font-size: 12px; font-weight: 800;">Option {index}</span>
          <span style="display: inline-block; background-color: {difficulty_background}; color: {difficulty_color}; border-radius: 999px; padding: 5px 11px; margin: 0 6px 6px 0; font-size: 12px; font-weight: 800;">{escape(option["difficulty"])}</span>
        </div>
        <h4 style="margin: 0 0 6px 0; font-size: 18px; line-height: 1.25; color: #0f172a; font-weight: 800; word-break: break-word;">{escape(option["title"])}</h4>
        <p style="margin: 0; color: #64748b; font-size: 14px; word-break: break-word;">{escape(option["description"])}</p>
      </div>
      <div style="background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 16px; padding: 12px; margin-bottom: 12px; color: #475569; font-size: 13px;">
        {_plan_summary(option)}
      </div>
      <div style="margin-bottom: 14px;">
        {focus_chips}
      </div>
      <div style="border-top: 1px solid #e2e8f0; padding-top: 12px;">
        <p style="margin: 0 0 10px 0; font-size: 13px; font-weight: 800; color: #0f172a;">Preview sessions</p>
        {preview_items}
      </div>
    </div>
"""


def render_preview_session_item(session, *, is_last=False):
    row_style = (
        "padding: 0 0 10px 0; margin-bottom: 10px; border-bottom: 1px solid #e2e8f0;"
        if not is_last
        else ""
    )
    return f"""
        <div style="{row_style}">
          <p style="margin: 0 0 3px 0; color: #0f172a; font-size: 14px; font-weight: 800; word-break: break-word;">{escape(session["day_label"])} &middot; {escape(session["title"])}</p>
          <p style="margin: 0; color: #64748b; font-size: 13px;">{escape(session["start_time"])}&ndash;{escape(session["end_time"])} &middot; {_display_label(session["session_type"])} &middot; {_display_label(session["intensity"])} &middot; {escape(session["location"])}</p>
        </div>
"""


def _plan_summary(option):
    sessions_count = option["sessions_count"]
    session_label = "session" if sessions_count == 1 else "sessions"
    date_range = _format_plan_date_range(option["start_date"], option["end_date"])
    return f'<strong style="color: #0f172a;">{escape(str(sessions_count))} {session_label}</strong> &middot; {date_range}'


def _format_plan_date_range(start_date, end_date):
    start = parse_date(str(start_date or ""))
    end = parse_date(str(end_date or ""))
    if start is None or end is None:
        return f"{escape(str(start_date or ''))}&ndash;{escape(str(end_date or ''))}"

    start_month = start.strftime("%b")
    end_month = end.strftime("%b")
    if start.year == end.year and start.month == end.month:
        return f"{start_month} {start.day}&ndash;{end.day}, {start.year}"
    if start.year == end.year:
        return f"{start_month} {start.day}&ndash;{end_month} {end.day}, {start.year}"
    return f"{start_month} {start.day}, {start.year}&ndash;{end_month} {end.day}, {end.year}"


def _difficulty_chip_colors(value):
    normalized = str(value or "").lower()
    if any(token in normalized for token in ("advanced", "high", "hard", "intense")):
        return "#fee2e2", "#b91c1c"
    return "#fff7ed", "#b45309"


def _display_label(value):
    return escape(str(value or "").replace("_", " ").title())


def _count_label(count):
    labels = {
        1: "One",
        2: "Two",
        3: "Three",
        4: "Four",
        5: "Five",
    }
    return labels.get(count, str(count))


def sanitize_assistant_html(html):
    css_sanitizer = CSSSanitizer(allowed_css_properties=ALLOWED_CSS_PROPERTIES)
    return bleach.clean(
        html,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        css_sanitizer=css_sanitizer,
        strip=True,
    )


def _render_answer_text(answer, status):
    if not status:
        return escape(answer)

    pattern = _status_pattern(status)
    match = pattern.search(answer)
    if not match:
        return escape(answer)

    prefix = answer[:match.start()].rstrip()
    suffix = answer[match.end():]
    if prefix.endswith("("):
        prefix = prefix[:-1].rstrip()
    suffix = re.sub(r"^\)", "", suffix).lstrip()

    chip = (
        f'<span style="display: inline-block;'
        f'color: {_status_chip_text_color(status)}; border-radius: 8px; padding: 3px 8px;'
        f'margin: 0 2px; font-size: 12px; font-weight: 700;">{escape(status)}</span>'
    )
    return f"{escape(prefix)} {chip}{escape(suffix)}".strip()


def _status_from_answer(answer):
    text = str(answer or "")
    for status in ("MISSED", "COMPLETED", "IN_PROGRESS", "NOT_STARTED"):
        if _status_pattern(status).search(text):
            return status
    return ""


def _status_pattern(status):
    if status == "IN_PROGRESS":
        return re.compile(r"\bIN[_\s-]?PROGRESS\b", flags=re.IGNORECASE)
    if status == "NOT_STARTED":
        return re.compile(r"\bNOT[_\s-]?STARTED\b", flags=re.IGNORECASE)
    return re.compile(rf"\b{status}\b", flags=re.IGNORECASE)


def _status_accent_color(status):
    if status == "COMPLETED":
        return "#22c55e"
    if status == "MISSED":
        return "#ef4444"
    if status == "NOT_STARTED":
        return "#64748b"
    return "#1e6eeb"


def _status_chip_background(status):
    if status == "COMPLETED":
        return "#dcfce7"
    if status == "MISSED":
        return "#fee2e2"
    if status == "NOT_STARTED":
        return "#f1f5f9"
    return "#dbeafe"


def _status_chip_text_color(status):
    if status == "COMPLETED":
        return "#166534"
    if status == "MISSED":
        return "#991b1b"
    if status == "NOT_STARTED":
        return "#475569"
    return "#1458c3"
