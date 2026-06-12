"""
Form Agent — visual form filling using Claude vision + Playwright.

Instead of the deprecated computer_20241022 beta tool, this agent:
  1. Takes a Playwright screenshot
  2. Sends it to Claude as a regular image (vision API, claude-opus-4-8)
  3. Claude returns a JSON list of actions: click (x,y), type text, scroll
  4. Playwright executes each action
  5. Repeat until Claude returns {action: done}

Privacy note: screenshots are sent to the Claude API and may contain
visible personal data. Use the mock profile when testing on unknown forms.
"""

import json
import re
import base64
import anthropic
from dotenv import load_dotenv

load_dotenv()

_client = anthropic.Anthropic()

DISPLAY_WIDTH  = 1280
DISPLAY_HEIGHT = 800


def _screenshot(page):
    """Return current browser view as a base64 PNG string."""
    return base64.standard_b64encode(page.screenshot()).decode()


def _profile_summary(profile):
    """Format profile data as plain text for Claude's prompt."""
    p = profile.get("personal", {})
    name = p.get("full_name", "")
    lines = [
        f"Full name:    {name}",
        f"First name:   {name.split()[0] if name else ''}",
        f"Last name:    {name.split()[-1] if name else ''}",
        f"Email:        {p.get('email', '')}",
        f"Phone:        {p.get('phone_uk', '')}",
        f"Location:     {p.get('location_current', '')}",
        f"Availability: {p.get('availability', '')}",
        "",
        "Work history:",
    ]
    for job in profile.get("work_history", []):
        end = job.get("end") or "Present"
        lines.append(f"  {job['start']}–{end}: {job['title']} at {job['employer']}")
        duties = "; ".join(job.get("responsibilities", [])[:3])
        if duties:
            lines.append(f"    Duties: {duties}")
    lines += ["", "Education:"]
    for edu in profile.get("education", []):
        lines.append(
            f"  {edu.get('end','')}: {edu.get('qualification','')} "
            f"{edu.get('subject','')}, {edu.get('institution','')}, "
            f"Grade: {edu.get('grade','')}"
        )
    lines += ["", "CPD / Training:"]
    for cpd in profile.get("cpd", []):
        lines.append(
            f"  {cpd.get('date','')}: {cpd.get('title','')} "
            f"({cpd.get('provider','')})"
        )
    return "\n".join(lines)


def _execute_actions(page, actions):
    """
    Execute a list of actions on the Playwright page.
    Returns (list of description strings, done: bool).
    """
    descriptions = []
    for act in actions:
        kind = act.get("action", "")

        if kind == "click":
            x, y = int(act["x"]), int(act["y"])
            page.mouse.click(x, y)
            descriptions.append(f"Click ({x},{y}) — {act.get('label','')}")
            page.wait_for_timeout(400)

        elif kind == "type":
            text = act.get("text", "")
            page.keyboard.type(str(text), delay=25)
            descriptions.append(f"Type: {str(text)[:60]}")

        elif kind == "scroll_down":
            page.mouse.wheel(0, 400)
            descriptions.append("Scroll down")
            page.wait_for_timeout(300)

        elif kind == "key":
            key = act.get("key", "Tab")
            page.keyboard.press(key)
            descriptions.append(f"Key: {key}")

        elif kind == "done":
            descriptions.append(f"Done — {act.get('reason','form filled')}")
            return descriptions, True

    return descriptions, False


def run_form_agent(page, profile, on_step=None, max_steps=25, pause_for_login=False):
    """
    Fill the form visible in `page` using Claude vision.

    page            — open Playwright page at the form URL
    profile         — dict of applicant data
    on_step         — optional callback(step_num, description) for UI updates
    max_steps       — safety cap on screenshot→action loops
    pause_for_login — if True, opens Playwright Inspector; user logs in then clicks Resume

    Returns: number of steps taken.
    """
    if pause_for_login:
        page.pause()

    profile_text = _profile_summary(profile)

    system = f"""You are filling a job application form on behalf of an applicant.
You will receive a screenshot of the browser and must return JSON actions to fill the form.

Applicant details:
{profile_text}

Rules:
- Fill all visible form fields using the applicant's data
- If you see section navigation buttons (e.g. "Personal Details", "Employment"), click them to open each section
- Click a field first, then type into it
- Leave blank any field you have no data for — do not invent information
- Do NOT click Submit, Apply, Send, or any button that would send the form
- Scroll down to check for more fields below the visible area
- When all sections are complete, return a done action

Return ONLY a JSON array — no explanation, no markdown, just the array.

Available actions:
  {{"action": "click", "x": <int>, "y": <int>, "label": "<what you are clicking>"}}
  {{"action": "type", "text": "<text to type>"}}
  {{"action": "scroll_down"}}
  {{"action": "key", "key": "<Tab|Enter|Escape>"}}
  {{"action": "done", "reason": "<summary of what was filled>"}}

Example response:
[
  {{"action": "click", "x": 180, "y": 420, "label": "Personal Details section button"}},
  {{"action": "click", "x": 620, "y": 310, "label": "First Name field"}},
  {{"action": "type", "text": "Alex"}},
  {{"action": "click", "x": 900, "y": 310, "label": "Last Name field"}},
  {{"action": "type", "text": "Morgan"}},
  {{"action": "scroll_down"}}
]"""

    steps_taken = 0

    for step in range(max_steps):
        screenshot_data = _screenshot(page)

        response = _client.messages.create(
            model="claude-opus-4-8",
            max_tokens=2048,
            system=system,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": screenshot_data
                        }
                    },
                    {
                        "type": "text",
                        "text": (
                            f"Step {step + 1}. Look at this screenshot of the form. "
                            "Return a JSON array of actions to fill any visible empty fields. "
                            "If all visible sections are complete, return [{\"action\": \"done\"}]."
                        )
                    }
                ]
            }]
        )

        raw = response.content[0].text.strip()

        # Extract JSON array from response (Claude may add explanation despite instructions)
        match = re.search(r'\[.*\]', raw, re.DOTALL)
        if not match:
            if on_step:
                on_step(step + 1, f"No JSON returned: {raw[:80]}")
            break

        try:
            actions = json.loads(match.group())
        except json.JSONDecodeError as e:
            if on_step:
                on_step(step + 1, f"JSON parse error: {e}")
            break

        descriptions, done = _execute_actions(page, actions)
        steps_taken = step + 1

        if on_step:
            for desc in descriptions:
                on_step(steps_taken, desc)

        if done:
            break

        page.wait_for_timeout(600)

    return steps_taken
