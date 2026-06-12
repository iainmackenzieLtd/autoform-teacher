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
MAX_STEPS   = 35


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
/* Captions — used in model/token info box and warnings */
[data-testid="stCaptionContainer"] p { font-size: 1rem !important; line-height: 1.5; }

/* Metric value (big number) */
[data-testid="stMetricValue"]  { font-size: 2rem !important; }

/* Metric label (small label above value) */
[data-testid="stMetricLabel"]  { font-size: 1rem !important; }

/* Metric delta (Running / Done text below value) */
[data-testid="stMetricDelta"] svg { display: none; }
[data-testid="stMetricDelta"]  { font-size: 0.95rem !important; }

/* Sidebar text */
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
    agent_clicked = st.button("🤖 Launch Agent", type="primary",
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

if agent_clicked:
    if not url:
        st.error("Enter a URL first.")
    else:
        st.session_state.agent_run   = True
        st.session_state.agent_url   = url
        st.session_state.agent_login = needs_login
        st.rerun()

# ── Always-visible status area ────────────────────────────────────────────────
st.divider()

# Progress bar — always rendered, idle at 0%
progress_bar = st.progress(0, text="Ready — waiting to launch")
status_line  = st.empty()

# Two-column layout: step counter (large) | model + token info (small)
col_step, col_info = st.columns([1, 2])

with col_step:
    step_slot = st.empty()
    with step_slot.container(border=True):
        st.metric("Step", f"— / {MAX_STEPS}")

with col_info:
    info_slot = st.empty()
    with info_slot.container(border=True):
        st.caption("**Model**")
        st.caption("claude-opus-4-8")
        st.caption("**Tokens sent**  |  **Est. cost**")
        st.caption("—  |  —")

# "What to do next" box — always visible, dimmed while idle/running
next_slot = st.empty()
with next_slot.container(border=True):
    st.markdown(
        "<div style='opacity:0.35'>"
        "<strong>What to do next</strong> — available once the agent finishes<br><br>"
        "1. Scroll through the form and check every field.<br>"
        "2. Complete any fields left blank.<br>"
        "3. When satisfied, click <strong>Submit Application</strong>."
        "</div>",
        unsafe_allow_html=True
    )

# Completion message area — empty until agent finishes
completion_slot = st.empty()

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
            status_line.empty()
            _redraw_panels(running=False)
        elif "screenshot" not in desc.lower():
            status_line.caption(f"↳ {desc}")
            _redraw_panels(running=True)

    def _on_tokens(tok_in, tok_out):
        state["tok_in"]  = tok_in
        state["tok_out"] = tok_out
        _redraw_panels(running=state["step"] == 0 or not state.get("done", False))

    # Kick off — show Starting state before first step fires
    progress_bar.progress(0, text="Starting…")
    with step_slot.container(border=True):
        st.metric("Step", "Starting…")
    with info_slot.container(border=True):
        st.caption("**Model**")
        st.caption("claude-opus-4-8")
        st.caption("**Tokens sent**  |  **Est. cost**")
        st.caption("—  |  —")

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

        progress_bar.progress(1.0, text="Complete")
        status_line.empty()
        _redraw_panels(running=False)

        # ── Completion panels ─────────────────────────────────────────────────
        with completion_slot.container():
            st.divider()

            if completed:
                st.success(f"✓  Agent completed the form in {n_steps} steps.")
                if done_reason:
                    with st.container(border=True):
                        st.markdown("**The AI says:**")
                        st.write(done_reason)
            else:
                st.warning(
                    f"Agent reached the step limit ({n_steps} steps) without signalling done. "
                    "The form may be partially complete."
                )

            with next_slot.container(border=True):
                st.markdown("**What to do next**")
                st.write(
                    "1. Scroll through the form in the browser window and check every field.\n"
                    "2. Complete any fields that were left blank.\n"
                    "3. When you are satisfied, click **Submit Application**."
                )

            with st.expander("Agent activity log"):
                for s in steps_log:
                    st.text(s)

    except Exception as e:
        status_line.empty()
        st.error(f"Agent error: {e}")
