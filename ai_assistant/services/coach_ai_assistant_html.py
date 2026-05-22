import re
from html import escape

import bleach
from bleach.css_sanitizer import CSSSanitizer


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
    option_cards = "\n".join(render_plan_option_card(option) for option in options)
    html = f"""
<div style="font-family: system-ui, -apple-system, Segoe UI, sans-serif; color: #0f172a; line-height: 1.45; font-size: 15px; background-color: #ffffff; width: 100%; box-sizing: border-box; margin: 0; padding: 0;">
  <div style="background-color: #1e6eeb; border: 1px solid #1458c3; border-radius: 8px; padding: 14px; margin-bottom: 12px;">
    <h3 style="margin: 0 0 6px 0; font-size: 18px; color: #ffffff;">Training plan options</h3>
    <p style="margin: 0; color: #fbfdff;">Three coach-ready drafts for <strong>{escape(player_name)}</strong>. Choose one using the native action below.</p>
  </div>
  {option_cards}
</div>
"""
    return sanitize_assistant_html(html)


def render_plan_option_card(option):
    focus_chips = "".join(
        f'<span style="display: inline-block; background-color: #fbfdff; color: #1458c3; '
        f'border: 1px solid #dbe5f0; '
        f'border-radius: 8px; padding: 4px 8px; margin: 0 6px 6px 0; font-size: 12px; '
        f'font-weight: 600;">{escape(area)}</span>'
        for area in option["focus_areas"]
    )
    preview_items = "".join(
        render_preview_session_item(session)
        for session in option["preview_sessions"][:3]
    )
    return f"""
  <div style="background-color: #ffffff; border: 1px solid #dbe5f0; border-radius: 8px; padding: 14px; margin-bottom: 12px; box-shadow: 0 10px 24px #dbe5f0;">
    <div style="margin-bottom: 8px;">
      <h4 style="margin: 0 0 4px 0; font-size: 16px; color: #0f172a;">{escape(option["title"])}</h4>
      <p style="margin: 0; color: #64748b;">{escape(option["description"])}</p>
    </div>
    <div style="margin: 8px 0;">
      <span style="display: inline-block; background-color: #f59e0b; color: #ffffff; border-radius: 8px; padding: 4px 8px; margin: 0 6px 6px 0; font-size: 12px; font-weight: 700;">{escape(option["difficulty"])}</span>
      <span style="display: inline-block; background-color: #22c55e; color: #ffffff; border-radius: 8px; padding: 4px 8px; margin: 0 6px 6px 0; font-size: 12px; font-weight: 700;">{escape(str(option["sessions_count"]))} sessions</span>
      <span style="display: inline-block; background-color: #2f78ef; color: #ffffff; border-radius: 8px; padding: 4px 8px; margin: 0 6px 6px 0; font-size: 12px; font-weight: 700;">{escape(option["duration"])}</span>
      <span style="display: inline-block; background-color: #fbfdff; color: #0f172a; border: 1px solid #dbe5f0; border-radius: 8px; padding: 4px 8px; margin: 0 6px 6px 0; font-size: 12px; font-weight: 700;">Start date: {escape(option["start_date"])}</span>
      <span style="display: inline-block; background-color: #fbfdff; color: #0f172a; border: 1px solid #dbe5f0; border-radius: 8px; padding: 4px 8px; margin: 0 6px 6px 0; font-size: 12px; font-weight: 700;">End date: {escape(option["end_date"])}</span>
    </div>
    <div style="margin: 4px 0 8px 0;">{focus_chips}</div>
    <div style="background-color: #fbfdff; border-top: 1px solid #dbe5f0; padding-top: 10px;">
      <p style="margin: 0 0 6px 0; color: #0f172a; font-size: 13px; font-weight: 700;">Preview sessions</p>
      <ul style="margin: 0; padding-left: 18px;">{preview_items}</ul>
    </div>
  </div>
"""


def render_preview_session_item(session):
    return f"""
        <li style="margin-bottom: 6px;">
          <strong>{escape(session["day_label"])}:</strong> {escape(session["title"])}
          <br>
          <span style="color: #64748b;">Type: {escape(session["session_type"])} - Intensity: {escape(session["intensity"])}</span>
          <br>
          <span style="color: #64748b;">Start: {escape(session["start_time"])} - End: {escape(session["end_time"])} - Location: {escape(session["location"])}</span>
        </li>
"""


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
        f'<span style="display: inline-block; background-color: {_status_chip_background(status)}; '
        f'color: {_status_chip_text_color(status)}; border-radius: 8px; padding: 3px 8px; '
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
