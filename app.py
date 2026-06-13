"""
AutoForm — agent-powered job application form filler.
Run with: streamlit run app.py
"""

import sys
import os
import glob
import json
import base64
import streamlit as st
from playwright.sync_api import sync_playwright

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from run_live import load_profile
from agents.form_agent import run_form_agent

PROFILE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "profile")
MAX_STEPS   = 20

# ── Governance: phase-controlled URL access ───────────────────────────────────
# TEST_MODE restricts the agent to approved synthetic test URLs only.
# Set to False only when external-site mode is implemented with explicit
# user confirmation, stronger warnings, and preserved submit blocking.
TEST_MODE = True
ALLOWED_DOMAINS = [
    "localhost",
    "127.0.0.1",
    "file:///",
    "iainmackenzieltd.github.io",
]

def _url_allowed(url: str) -> bool:
    return any(domain in url for domain in ALLOWED_DOMAINS)


def discover_profiles():
    """Return {display_name: file_path} for valid profile JSONs (must have 'personal' key)."""
    profiles = {}
    for path in sorted(glob.glob(os.path.join(PROFILE_DIR, "*.json"))):
        try:
            with open(path) as f:
                data = json.load(f)
            if "personal" not in data:
                continue
        except Exception:
            continue
        stem    = os.path.splitext(os.path.basename(path))[0]
        display = stem.replace("_", " ").title()
        profiles[display] = path
    return profiles


# ── Page setup ────────────────────────────────────────────────────────────────
st.set_page_config(page_title="AutoForm", layout="wide")

st.markdown("""
<style>
[data-testid="stCaptionContainer"] p { font-size: 1rem !important; line-height: 1.5; }
[data-testid="stMetricValue"]  { font-size: 2rem !important; }
[data-testid="stMetricLabel"]  { font-size: 1rem !important; }
[data-testid="stMetricDelta"] svg { display: none; }
[data-testid="stMetricDelta"]  { font-size: 0.95rem !important; }
[data-testid="stSidebar"] p,
[data-testid="stSidebar"] li { font-size: 0.95rem !important; }
</style>
""", unsafe_allow_html=True)

st.title("AutoForm")
st.caption(
    "Fills the repetitive fields of any teaching job application from your profile — "
    "personal details, employment history, qualifications, and referees. "
    "Supporting statements and open-ended questions are left for you to write."
)

if TEST_MODE:
    st.warning(
        "🔒 **Test mode** — synthetic forms only · no real applications · "
        "no automatic submission",
        icon=None
    )

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Your Profile")
    available = discover_profiles()
    if not available:
        st.error("No profiles found in the profile/ folder.")
        st.stop()
    selected_name = st.selectbox("Select profile", list(available.keys()))
    profile = load_profile(available[selected_name])
    p = profile["personal"]
    st.markdown(f"### {p['full_name']}")
    st.write(p["email"])
    st.write(p.get("phone_uk", ""))
    st.write(p.get("location_current", ""))

    st.divider()
    st.subheader("Work History")
    for job in profile["work_history"]:
        end = job["end"] or "Present"
        st.markdown(f"**{job['employer']}**")
        st.caption(f"{job['title']} · {job['start']}–{end}")

    st.divider()
    st.subheader("Education")
    for edu in profile["education"]:
        st.markdown(f"**{edu['qualification']} {edu['subject']}**")
        st.caption(edu["institution"])

# ── URL input ─────────────────────────────────────────────────────────────────
st.subheader("Enter the form URL")
url = st.text_input("URL", label_visibility="collapsed",
                    placeholder="https://...  or  file:///home/...")

agent_clicked = st.button("🤖 Launch Agent", type="primary")

st.caption(
    "⚠️ Agent mode sends browser screenshots to the Claude API. "
    "Use the mock profile when testing on unfamiliar sites."
)

if agent_clicked:
    if not url:
        st.error("Enter a URL first.")
    elif TEST_MODE and not _url_allowed(url):
        st.error(
            f"⛔ Test mode: only approved synthetic test URLs are allowed. "
            f"Approved domains: {', '.join(ALLOWED_DOMAINS)}"
        )
    else:
        st.session_state.agent_run = True
        st.session_state.agent_url = url
        st.session_state.pop("agent_result", None)
        st.rerun()

# ── Always-visible status area ────────────────────────────────────────────────
st.divider()

progress_bar    = st.progress(0, text="Ready — waiting to launch")
status_line     = st.empty()

col_step, col_info = st.columns([1, 2])
with col_step:
    step_slot = st.empty()
with col_info:
    info_slot = st.empty()

screenshot_slot = st.empty()   # live form view — updates each step
next_slot       = st.empty()
completion_slot = st.empty()

# ── Render panels based on current state ─────────────────────────────────────
result = st.session_state.get("agent_result")

if result:
    # ── Completed state ───────────────────────────────────────────────────────
    cost = (result["tok_in"] * 5 + result["tok_out"] * 25) / 1_000_000

    progress_bar.progress(1.0, text="Complete")

    with step_slot.container(border=True):
        st.metric("Step", "✓  Complete", delta=f"{result['n_steps']} steps used")

    with info_slot.container(border=True):
        st.caption("**Model**")
        st.caption("claude-opus-4-8")
        st.caption("**Tokens sent**  |  **Est. cost**")
        st.caption(f"{result['tok_in']:,}  |  ~${cost:.3f}")

    if result.get("final_screenshot"):
        with screenshot_slot.container():
            st.image(
                base64.b64decode(result["final_screenshot"]),
                caption="Final form state — scroll to review all fields",
                use_container_width=True,
            )

    with next_slot.container(border=True):
        st.subheader("✓ What to do next")
        st.write(
            "1. Check the field report below — any ⚠ fields need your input.\n"
            f"2. Open the form in your browser and complete those fields: {result.get('url','')}\n"
            "3. When you are satisfied, click **Submit Application**."
        )

    with completion_slot.container():
        st.divider()
        if result["completed"]:
            st.success(f"✓  Agent completed the form in {result['n_steps']} steps.")
            if result["done_reason"]:
                with st.container(border=True):
                    st.markdown("**The AI says:**")
                    st.write(result["done_reason"])
        else:
            st.warning(
                f"Agent reached the step limit ({result['n_steps']} steps) without "
                "signalling done. The form may be partially complete."
            )

        # Field report
        filled  = result.get("fields_filled", [])
        skipped = result.get("fields_skipped", [])
        if filled or skipped:
            with st.expander(f"Field report — {len(filled)} filled, {len(skipped)} skipped"):
                if filled:
                    st.markdown("**Filled**")
                    for f in filled:
                        st.markdown(f"- ✓ {f}")
                if skipped:
                    st.markdown("**Left blank / skipped**")
                    for s in skipped:
                        st.markdown(f"- ⚠ {s}")

        with st.expander("Agent activity log"):
            for s in result["steps_log"]:
                st.text(s)

else:
    # ── Idle state ────────────────────────────────────────────────────────────
    with step_slot.container(border=True):
        st.metric("Step", f"— / {MAX_STEPS}")

    with info_slot.container(border=True):
        st.caption("**Model**")
        st.caption("claude-opus-4-8")
        st.caption("**Tokens sent**  |  **Est. cost**")
        st.caption("—  |  —")

    with next_slot.container(border=True):
        st.markdown(
            "<div style='opacity:0.35'>"
            "<span style='font-size:1.25rem;font-weight:600'>What to do next</span>"
            " — available once the agent finishes<br><br>"
            "1. Check the field report — any ⚠ fields need your input.<br>"
            "2. Open the form URL in your browser and complete those fields.<br>"
            "3. When satisfied, click <strong>Submit Application</strong>."
            "</div>",
            unsafe_allow_html=True
        )

# ── Agent execution ───────────────────────────────────────────────────────────
if st.session_state.get("agent_run"):
    st.session_state.agent_run = False
    target_url = st.session_state.get("agent_url", "")
    steps_log  = []

    state = {"step": 0, "tok_in": 0, "tok_out": 0, "last_screenshot": None}

    def _redraw_panels(running=True):
        cost = (state["tok_in"] * 5 + state["tok_out"] * 25) / 1_000_000
        with step_slot.container(border=True):
            if not running:
                st.metric("Step", "✓  Complete", delta=f"{state['step']} steps used")
            else:
                st.metric("Step", f"{state['step']} / {MAX_STEPS}", delta="Running")
        with info_slot.container(border=True):
            st.caption("**Model**")
            st.caption("claude-opus-4-8")
            st.caption("**Tokens sent**  |  **Est. cost**")
            tok_str  = f"{state['tok_in']:,}" if state['tok_in'] else "—"
            cost_str = f"~${cost:.3f}"        if state['tok_in'] else "—"
            st.caption(f"{tok_str}  |  {cost_str}")

    def _on_step(n, desc):
        state["step"] = n
        steps_log.append(f"Step {n}: {desc}")
        is_done = desc.lower().startswith("done")
        progress_bar.progress(
            1.0 if is_done else min(n / MAX_STEPS, 1.0),
            text="Complete" if is_done else f"Step {n} of up to {MAX_STEPS}"
        )
        if is_done:
            status_line.caption("✓ Agent finished — review the screenshot, then open the form to submit.")
            _redraw_panels(running=False)
            with next_slot.container(border=True):
                st.subheader("✓ What to do next")
                st.write(
                    "1. Check the field report below — any ⚠ fields need your input.\n"
                    f"2. Open the form in your browser and complete those fields: {target_url}\n"
                    "3. When you are satisfied, click **Submit Application**."
                )
            done_reason_live = desc[5:].lstrip("—").strip()
            with completion_slot.container():
                st.divider()
                st.success(f"✓  Agent completed the form in {n} steps.")
                if done_reason_live:
                    with st.container(border=True):
                        st.markdown("**The AI says:**")
                        st.write(done_reason_live)
        elif "screenshot" not in desc.lower():
            status_line.caption(f"↳ {desc}")
            _redraw_panels(running=True)

    def _on_screenshot(b64_data):
        state["last_screenshot"] = b64_data
        screenshot_slot.image(
            base64.b64decode(b64_data),
            caption=f"Step {state['step']} — live form view",
            use_container_width=True,
        )

    def _on_tokens(tok_in, tok_out):
        state["tok_in"]  = tok_in
        state["tok_out"] = tok_out
        _redraw_panels(running=True)

    # Show starting state before first step fires
    progress_bar.progress(0, text="Starting…")
    with step_slot.container(border=True):
        st.metric("Step", "Starting…")
    with info_slot.container(border=True):
        st.caption("**Model**")
        st.caption("claude-opus-4-8")
        st.caption("**Tokens sent**  |  **Est. cost**")
        st.caption("—  |  —")

    _agent_done  = False
    _agent_error = None

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            ctx  = browser.new_context(viewport={"width": 1280, "height": 900})
            page = ctx.new_page()
            page.goto(target_url, wait_until="networkidle")
            n_steps, completed, done_reason, tok_in, tok_out, fields_filled, fields_skipped = run_form_agent(
                page, profile,
                on_step=_on_step,
                on_screenshot=_on_screenshot,
                on_tokens=_on_tokens,
                max_steps=MAX_STEPS,
            )
            browser.close()

        st.session_state.agent_result = {
            "n_steps":          n_steps,
            "completed":        completed,
            "done_reason":      done_reason,
            "tok_in":           tok_in,
            "tok_out":          tok_out,
            "steps_log":        steps_log,
            "fields_filled":    fields_filled,
            "fields_skipped":   fields_skipped,
            "final_screenshot": state["last_screenshot"],
            "url":              target_url,
        }
        _agent_done = True

    except Exception as e:
        _agent_error = str(e)

    # Both branches are outside the try block — no exception can interfere
    if _agent_error:
        status_line.empty()
        st.error(f"Agent error: {_agent_error}")

    if _agent_done:
        st.rerun()
