"""
AutoForm — agent-powered job application form filler.
Run with: streamlit run app.py
"""

import sys
import os
import streamlit as st
from playwright.sync_api import sync_playwright

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from run_live import load_profile
from agents.form_agent import run_form_agent

PROFILE_PATH      = "profile/user_profile.json"
MOCK_PROFILE_PATH = "profile/mock_profile.json"

# ── Page setup ────────────────────────────────────────────────────────────────
st.set_page_config(page_title="AutoForm", layout="wide")
st.title("AutoForm")
st.caption("Fill any job application form from your profile — automatically.")

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Your Profile")
    use_mock = st.toggle("Use mock profile (for testing)", value=False)
    profile = load_profile(MOCK_PROFILE_PATH if use_mock else PROFILE_PATH)
    if use_mock:
        st.caption("⚠️ Using fictional test profile — Alex Morgan")
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

col_btn, col_chk, col_link = st.columns([2, 3, 2])

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
with col_link:
    if "last_url" in st.session_state:
        st.link_button("Open in new tab ↗", st.session_state.last_url)

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
        st.session_state.last_url    = url
        st.rerun()

# ── Agent execution ───────────────────────────────────────────────────────────
if st.session_state.get("agent_run"):
    st.session_state.agent_run = False
    target_url  = st.session_state.get("agent_url", "")
    pause_login = st.session_state.get("agent_login", False)
    steps_log   = []

    def _on_step(n, desc):
        steps_log.append(f"Step {n}: {desc}")

    with st.spinner("Agent is working — watch the browser window…"):
        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch(
                    headless=False,
                    args=["--window-size=1280,800"]
                )
                ctx  = browser.new_context(viewport={"width": 1280, "height": 800})
                page = ctx.new_page()
                page.goto(target_url, wait_until="networkidle")
                n_steps = run_form_agent(
                    page, profile,
                    on_step=_on_step,
                    pause_for_login=pause_login
                )
                if not page.is_closed():
                    try:
                        page.wait_for_event("close", timeout=0)
                    except Exception:
                        pass
                browser.close()
            st.success(
                f"Agent finished in {n_steps} steps. "
                "Review what was filled before closing the browser."
            )
            with st.expander("Agent activity log"):
                for s in steps_log:
                    st.text(s)
        except Exception as e:
            st.error(f"Agent error: {e}")
