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


def discover_profiles():
    """Return {display_name: file_path} for valid profile JSONs (must have 'personal' key)."""
    profiles = {}
    for path in sorted(glob.glob(os.path.join(PROFILE_DIR, "*.json"))):
        try:
            with open(path) as f:
                data = json.load(f)
            if "personal" not in data:
                continue  # skip files that aren't profiles (e.g. approval.json)
        except Exception:
            continue
        stem = os.path.splitext(os.path.basename(path))[0]
        display = stem.replace("_", " ").title()
        profiles[display] = path
    return profiles

# ── Page setup ────────────────────────────────────────────────────────────────
st.set_page_config(page_title="AutoForm", layout="wide")
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
    steps_log = []

    st.info("Agent is working — watch the browser window.")
    status_line = st.empty()
    status_line.caption("Starting…")

    def _on_step(n, desc):
        steps_log.append(f"Step {n}: {desc}")
        status_line.caption(f"Step {n} — {desc}")

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(
                headless=False,
                args=["--window-size=1280,800"]
            )
            ctx  = browser.new_context(viewport={"width": 1280, "height": 800})
            page = ctx.new_page()
            page.goto(target_url, wait_until="networkidle")
            n_steps, completed, done_reason = run_form_agent(
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
        status_line.empty()

        if completed:
            st.success(f"✓ Agent completed the form in {n_steps} steps.")
            st.info(
                done_reason or
                "The form has been filled according to your profile. "
                "Please review every field carefully in the browser, "
                "then click Submit when you are ready to apply."
            )
        else:
            st.warning(
                f"Agent reached the step limit ({n_steps} steps) without finishing. "
                "The form may be partially complete — please scroll through and check "
                "every field before deciding whether to submit."
            )

        with st.expander("Agent activity log"):
            for s in steps_log:
                st.text(s)
    except Exception as e:
        status_line.empty()
        st.error(f"Agent error: {e}")
