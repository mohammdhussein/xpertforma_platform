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
    html = (
        '<div style="font-family: system-ui, -apple-system, Segoe UI, sans-serif; color: #0f172a; '
        'line-height: 1.45; font-size: 15px; background-color: #ffffff; border: 1px solid #dbe5f0; '
        'border-left: 4px solid #1e6eeb; border-radius: 8px; padding: 14px; box-shadow: 0 10px 24px #dbe5f0;">'
        f'<p style="margin: 0; color: #0f172a;">{escape(answer or "")}</p>'
        "</div>"
    )
    return sanitize_assistant_html(html)


def render_plan_options_html(*, player_name, options):
    option_cards = "\n".join(render_plan_option_card(option) for option in options)
    html = f"""
<div style="font-family: system-ui, -apple-system, Segoe UI, sans-serif; color: #0f172a; line-height: 1.45; font-size: 15px; background-color: #f8fafc;">
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
