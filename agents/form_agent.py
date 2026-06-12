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
    addr_parts = [
        p.get("address_line_1", ""),
        p.get("address_line_2", ""),
        p.get("town_city", ""),
        p.get("county", ""),
        p.get("postcode", ""),
    ]
    address_full = ", ".join(a for a in addr_parts if a)
    lines = [
        f"Title:        {p.get('title', '')}",
        f"Full name:    {name}",
        f"First name:   {name.split()[0] if name else ''}",
        f"Last name:    {name.split()[-1] if name else ''}",
        f"Date of birth:{p.get('date_of_birth', '')}",
        f"Email:        {p.get('email', '')}",
        f"Phone:        {p.get('phone_uk', '')}",
        f"Address:      {address_full or p.get('location_current', '')}",
        f"Postcode:     {p.get('postcode', '')}",
        f"Nationality:  {p.get('nationality', '')}",
        f"Right to work:{p.get('right_to_work', '')}",
        f"Visa required:{p.get('visa_required', '')}",
        f"NI number:    {p.get('ni_number', '')}",
        f"DBS status:   {p.get('dbs_status', '')}",
        f"DBS number:   {p.get('dbs_number', '')}",
        f"Teacher ref:  {p.get('teacher_reference_number', '')}",
        f"QTS:          {p.get('qts', '')}",
        f"Availability: {p.get('availability', '')}",
    ]
    prefs = profile.get("employment_preferences", {})
    if prefs:
        lines += [
            "",
            "Employment preferences:",
            f"  Type:         {prefs.get('employment_type', '')}",
            f"  Contract:     {prefs.get('contract_type', '')}",
            f"  Start:        {prefs.get('preferred_start', '')}",
        ]
    lines += ["", "Work history:"]
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
    refs = profile.get("referees", [])
    if refs:
        lines += ["", "Referees:"]
        for i, r in enumerate(refs, 1):
            lines.append(
                f"  Referee {i}: {r.get('name','')} — {r.get('title','')} "
                f"at {r.get('organisation','')}"
            )
            lines.append(f"    Email: {r.get('email','')}  Phone: {r.get('phone','')}")
    stmt = profile.get("supporting_statement", "")
    if stmt:
        lines += ["", f"Supporting statement: {stmt}"]
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


def run_form_agent(page, profile, on_step=None, max_steps=35, pause_for_login=False):
    """
    Fill the form visible in `page` using Claude vision.

    page            — open Playwright page at the form URL
    profile         — dict of applicant data
    on_step         — optional callback(step_num, description) for UI updates
    max_steps       — safety cap on screenshot→action loops
    pause_for_login — if True, opens Playwright Inspector; user logs in then clicks Resume

    Returns: (steps_taken, completed) where completed=True means agent signalled done.
    """
    if pause_for_login:
        page.pause()

    profile_text = _profile_summary(profile)

    system = f"""You are filling a job application form on behalf of an applicant.
You will receive screenshots of the browser and must return JSON actions to fill the form.
You have full memory of this conversation — you can see all previous screenshots and actions.

Applicant details:
{profile_text}

Work through the form top to bottom, scrolling down to find all fields.

Field matching rules — pay close attention to labels:
- "Title" → use the title field (Mr, Ms, Dr etc)
- "First name" / "Forename" → first name only
- "Last name" / "Surname" → last name only
- "Full name" → complete name
- "Date of birth" → date of birth (DD/MM/YYYY format)
- "Address" → street address
- "Postcode" → postcode only
- "Nationality" → nationality
- "Right to work" → right to work answer (Yes/No)
- "Visa" or "work permit" → visa required answer (Yes/No)
- "NI number" or "National Insurance" → NI number
- "DBS" → DBS status or DBS number as appropriate
- "Teacher Reference" or "TRN" → teacher reference number
- "QTS" → QTS status (Yes/No/In progress)
- "Institution" or "University" → school/university name
- "Qualification" → the degree/certificate name (e.g. PGCE, BEng)
- "Subject" → the subject studied (e.g. Mathematics, Mechanical Engineering)
- "Grade" or "Grade / Class" → the grade achieved (e.g. Pass, 2:1, Distinction)
- "Year Awarded" or "Year" → the year as a number (e.g. 2015)
- "Course Title" or "Training Title" → the CPD course name
- "Provider" or "Awarding Body" → the organisation that ran the course
- "Start Date" → when the job or course started
- "End Date" → when it ended (or "Present" if current)
- "Duties" or "Responsibilities" → description of the role
- "Date" as a standalone field near a signature → today's date in DD/MM/YYYY format
- "Referee" fields → use the referees from the profile
- "Supporting statement" → use the supporting statement from the profile

For dropdowns: click the dropdown and select the closest matching option.
For radio buttons: click the correct option.
For checkboxes in a declaration: tick all of them.

Do NOT re-fill fields you have already filled.
Do NOT invent data — leave a field blank if you have nothing for it.
Do NOT click Submit, Apply, or any button that sends the form.

When you have scrolled to the bottom and filled everything visible, return:
[{{"action": "done", "reason": "Form filled. Please review all fields carefully, then click Submit when you are ready to apply."}}]

Return ONLY a JSON array — no explanation, no markdown, just the array.

Available actions:
  {{"action": "click", "x": <int>, "y": <int>, "label": "<what you are clicking>"}}
  {{"action": "type", "text": "<text to type>"}}
  {{"action": "scroll_down"}}
  {{"action": "key", "key": "<Tab|Enter|Escape>"}}
  {{"action": "done", "reason": "<message for the user>"}}"""

    messages = []  # Full conversation history so Claude remembers previous steps
    steps_taken = 0
    completed = False
    done_reason = ""

    for step in range(max_steps):
        if on_step:
            on_step(step + 1, "Taking screenshot and thinking…")

        screenshot_data = _screenshot(page)

        messages.append({
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
                        f"Step {step + 1} of {max_steps}. This is the current state of the browser. "
                        "Check what you have already done above, then return JSON actions "
                        "for the next thing to fill. When you have filled everything visible "
                        "and scrolled to the bottom, return [{\"action\": \"done\", \"reason\": \"...\"}]."
                    )
                }
            ]
        })

        response = _client.messages.create(
            model="claude-opus-4-8",
            max_tokens=2048,
            system=system,
            messages=messages
        )

        # Add assistant reply to history so Claude remembers it next step
        messages.append({"role": "assistant", "content": response.content})

        raw = response.content[0].text.strip()

        # Extract JSON array from response
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
            completed = True
            # Capture the reason from the done action for the UI
            for act in actions:
                if act.get("action") == "done":
                    done_reason = act.get("reason", "")
            break

        page.wait_for_timeout(600)

    return steps_taken, completed, done_reason
