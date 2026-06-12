"""
Form Agent — uses Claude computer use to fill any web form visually.

Claude receives screenshots of the browser and controls it like a human:
clicking fields, typing values, scrolling. Works on any form type,
including multi-section, login-required, and JavaScript-heavy pages.

Privacy note: screenshots sent to the Claude API may contain visible
personal data. Use the mock profile when testing on unknown sites.
"""

import base64
import anthropic
from dotenv import load_dotenv

load_dotenv()

_client = anthropic.Anthropic()

DISPLAY_WIDTH  = 1280
DISPLAY_HEIGHT = 800


def _screenshot(page):
    """Capture the current browser view as a base64 PNG."""
    data = base64.standard_b64encode(page.screenshot()).decode()
    return [{"type": "image", "source": {
        "type": "base64", "media_type": "image/png", "data": data
    }}]


def _execute(page, action_input):
    """Execute one computer-use action on the Playwright page."""
    action = action_input.get("action", "")

    if action == "screenshot":
        return _screenshot(page)

    elif action == "left_click":
        x, y = action_input["coordinate"]
        page.mouse.click(x, y)

    elif action == "double_click":
        x, y = action_input["coordinate"]
        page.mouse.dblclick(x, y)

    elif action == "right_click":
        x, y = action_input["coordinate"]
        page.mouse.click(x, y, button="right")

    elif action == "type":
        page.keyboard.type(action_input["text"])

    elif action == "key":
        page.keyboard.press(action_input["key"])

    elif action == "scroll":
        x, y = action_input["coordinate"]
        direction = action_input.get("direction", "down")
        amount = action_input.get("amount", 3)
        page.mouse.move(x, y)
        page.mouse.wheel(0, amount * 100 * (1 if direction == "down" else -1))

    elif action == "mouse_move":
        x, y = action_input["coordinate"]
        page.mouse.move(x, y)

    elif action == "left_click_drag":
        s = action_input["start_coordinate"]
        e = action_input["coordinate"]
        page.mouse.move(s[0], s[1])
        page.mouse.down()
        page.mouse.move(e[0], e[1])
        page.mouse.up()

    return _screenshot(page)


def _profile_summary(profile):
    """Format profile data as plain text for Claude's system prompt."""
    p = profile.get("personal", {})
    lines = [
        f"Full name:    {p.get('full_name', '')}",
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
        for r in job.get("responsibilities", [])[:2]:
            lines.append(f"    · {r}")
    lines += ["", "Education:"]
    for edu in profile.get("education", []):
        lines.append(
            f"  {edu.get('end','')}: {edu.get('qualification','')} "
            f"{edu.get('subject','')}, {edu.get('institution','')}"
        )
    lines += ["", "CPD / Training:"]
    for cpd in profile.get("cpd", []):
        lines.append(f"  {cpd.get('date','')}: {cpd.get('title','')} ({cpd.get('provider','')})")
    return "\n".join(lines)


def run_form_agent(page, profile, on_step=None, max_steps=40, pause_for_login=False):
    """
    Fill the form visible in `page` using Claude computer use.

    page            — open Playwright page, already at the form URL
    profile         — dict of applicant data (personal, work_history, education, cpd)
    on_step         — optional callback(step_num: int, description: str) for UI updates
    max_steps       — safety cap on API loop iterations
    pause_for_login — if True, opens Playwright Inspector and waits for user to log in
                      manually before the agent starts; user clicks Resume to continue

    Returns: number of steps taken.
    """
    if pause_for_login:
        page.pause()  # Opens Playwright Inspector — user logs in, then clicks Resume
    system = f"""You are a careful assistant filling a job application form on behalf of an applicant.

Applicant details:
{_profile_summary(profile)}

Instructions:
- Fill in form fields using the applicant's information above
- If you do not have data for a field, leave it blank — do not invent information
- Do NOT click Submit, Apply, Send, or any button that would send the form
- Do NOT navigate away from the form page
- Scroll down to check for fields below the visible area
- When you have filled everything you can, write "DONE" and stop"""

    messages = [{
        "role": "user",
        "content": "Please fill in this job application form. Start by taking a screenshot to see what is there."
    }]

    tools = [{
        "type": "computer_20241022",
        "name": "computer",
        "display_width_px":  DISPLAY_WIDTH,
        "display_height_px": DISPLAY_HEIGHT,
    }]

    steps_taken = 0
    for step in range(max_steps):
        response = _client.beta.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=4096,
            system=system,
            tools=tools,
            messages=messages,
            betas=["computer-use-2024-10-22"],
        )

        # Build tool results and a human-readable description for the UI
        tool_results = []
        descriptions = []
        for block in response.content:
            if block.type == "tool_use" and block.name == "computer":
                a = block.input.get("action", "")
                if a == "type":
                    descriptions.append(f"Typing: {block.input.get('text','')[:40]}")
                elif a in ("left_click", "click"):
                    descriptions.append(f"Clicking at {block.input.get('coordinate')}")
                elif a == "scroll":
                    descriptions.append("Scrolling")
                elif a == "screenshot":
                    descriptions.append("Taking screenshot")
                else:
                    descriptions.append(a)

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": _execute(page, block.input),
                })

        steps_taken = step + 1
        if on_step and descriptions:
            on_step(steps_taken, " · ".join(descriptions))

        # Check if Claude signalled it is finished
        text = " ".join(b.text for b in response.content if hasattr(b, "text"))
        if "DONE" in text.upper() or response.stop_reason == "end_turn":
            break

        if not tool_results:
            break

        messages.append({"role": "assistant", "content": response.content})
        messages.append({"role": "user",      "content": tool_results})

    return steps_taken
