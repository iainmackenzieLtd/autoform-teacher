"""
AutoForm — agent-powered job application form filler.
Run with: streamlit run app.py
"""

import sys
import os
import glob
import json
import streamlit as st
from playwright.sync_api import sync_playwright

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from run_live import load_profile
from agents.form_agent import run_form_agent

PROFILE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "profile")
MAX_STEPS   = 20


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
st.caption("Fill any job application form from your profile — automatically.")

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

col_btn, col_chk = st.columns([2, 4])
with col_btn:
    agent_clicked = st.button("🤖 Launch Agent (Opens additional window)", type="primary",
                              use_container_width=True)
with col_chk:
    needs_login = st.checkbox(
        "Requires manual login",
        help=(
            "Tick for login-required portals. The browser will open and pause — "
            "log in yourself, navigate to the form, then click Resume in the "
            "Playwright Inspector window to hand control to the agent."
        )
    )

st.caption(
    "⚠️ Agent mode sends browser screenshots to the Claude API. "
    "Use the mock profile when testing on unfamiliar sites."
)
st.info(
    "💡 When you click **Launch Agent**, a browser window will open alongside this one. "
    "You can watch the form being filled in real time — do not close it until the agent finishes.",
    icon=None
)

if agent_clicked:
    if not url:
        st.error("Enter a URL first.")
    else:
        st.session_state.agent_run    = True
        st.session_state.agent_url    = url
        st.session_state.agent_login  = needs_login
        st.session_state.pop("agent_result", None)  # Clear any previous result
        st.rerun()

# ── Always-visible status area ────────────────────────────────────────────────
st.divider()

progress_bar = st.progress(0, text="Ready — waiting to launch")
status_line  = st.empty()

col_step, col_info = st.columns([1, 2])
with col_step:
    step_slot = st.empty()
with col_info:
    info_slot = st.empty()

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

    with next_slot.container(border=True):
        st.subheader("✓ What to do next")
        st.write(
            "1. Switch to the form window and scroll through every field.\n"
            "2. Complete any fields that were left blank.\n"
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
            "1. Switch to the form window and scroll through every field.<br>"
            "2. Complete any fields that were left blank.<br>"
            "3. When satisfied, click <strong>Submit Application</strong>."
            "</div>",
            unsafe_allow_html=True
        )

# ── Agent execution ───────────────────────────────────────────────────────────
if st.session_state.get("agent_run"):
    st.session_state.agent_run = False
    target_url  = st.session_state.get("agent_url", "")
    pause_login = st.session_state.get("agent_login", False)
    steps_log   = []

    state = {"step": 0, "tok_in": 0, "tok_out": 0}

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
            status_line.caption(
                "✓ Agent finished — review the form in the browser window, "
                "submit it, then close the window when done."
            )
            _redraw_panels(running=False)
            # Light up completion UI immediately — same mechanism as step_slot updates
            with next_slot.container(border=True):
                st.subheader("✓ What to do next")
                st.write(
                    "1. Switch to the form window and scroll through every field.\n"
                    "2. Complete any fields that were left blank.\n"
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
            browser = pw.chromium.launch(
                headless=False,
                args=["--window-size=860,860", "--window-position=580,30"]
            )
            ctx  = browser.new_context(viewport={"width": 860, "height": 800})
            page = ctx.new_page()
            page.goto(target_url, wait_until="networkidle")
            n_steps, completed, done_reason, tok_in, tok_out = run_form_agent(
                page, profile,
                on_step=_on_step,
                on_tokens=_on_tokens,
                max_steps=MAX_STEPS,
                pause_for_login=pause_login
            )
            if not page.is_closed():
                try:
                    page.wait_for_event("close", timeout=0)
                except Exception:
                    pass
            browser.close()

        st.session_state.agent_result = {
            "n_steps":     n_steps,
            "completed":   completed,
            "done_reason": done_reason,
            "tok_in":      tok_in,
            "tok_out":     tok_out,
            "steps_log":   steps_log,
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
