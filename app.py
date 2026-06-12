"""
AutoForm — simple Streamlit UI for the form-filling pipeline.
Run with: streamlit run app.py
"""

import sys
import os
import json
import streamlit as st
from playwright.sync_api import sync_playwright

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from run_live import fetch_fields, map_fields, load_profile
from agents.field_explainer import explain_field

PROFILE_PATH = "profile/user_profile.json"


def fill_live(page, mapped_fields):
    filled = 0
    skipped = 0
    for field in mapped_fields:
        if page.is_closed():
            break
        fid = field["id"]
        value = field["value"]
        if not value:
            skipped += 1
            continue
        locator = page.locator(f"#{fid}")
        if locator.count() == 0:
            skipped += 1
            continue
        locator.fill(str(value))
        filled += 1
    if not page.is_closed():
        try:
            page.wait_for_event("close", timeout=0)
        except Exception:
            pass
    return filled, skipped


# ── Page setup ──────────────────────────────────────────────
st.set_page_config(page_title="AutoForm", layout="wide")
st.title("AutoForm")
st.caption("Fill any job application form from your profile — automatically.")

profile = load_profile()

# ── Sidebar: profile summary ─────────────────────────────────
with st.sidebar:
    st.header("Your Profile")
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

# ── Step 1: URL input ─────────────────────────────────────────
st.subheader("Step 1 — Enter the form URL")
url = st.text_input(
    "URL",
    value="https://www.firstclasssupply.co.uk/create-cv-secondary/",
    label_visibility="collapsed"
)

if st.button("Read Form", type="primary"):
    # Close any previously opened form browser
    if "form_browser" in st.session_state:
        try:
            st.session_state.form_browser.close()
            st.session_state.form_pw.stop()
        except Exception:
            pass
        for k in ("form_pw", "form_browser", "form_page"):
            st.session_state.pop(k, None)

    with st.spinner("Opening form..."):
        try:
            pw = sync_playwright().start()
            browser = pw.chromium.launch(headless=False)
            page = browser.new_page()
            page.goto(url, wait_until="networkidle")
            raw_fields = fetch_fields(page)
            mapped = map_fields(raw_fields, profile)
            st.session_state.form_pw = pw
            st.session_state.form_browser = browser
            st.session_state.form_page = page
            st.session_state.mapped = mapped
            st.session_state.url = url
            st.session_state.pop("explanations", None)
        except Exception as e:
            st.error(f"Could not read form: {e}")

# ── Step 2: Review mapping ────────────────────────────────────
if "mapped" in st.session_state:
    mapped = st.session_state.mapped
    matched = [f for f in mapped if f["status"] == "mapped"]
    gaps = [f for f in mapped if f["status"] == "NEEDS USER INPUT"]

    st.divider()
    st.subheader(f"Step 2 — Review mapping")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown(f"**✓ {len(matched)} fields matched from your profile**")
        for f in matched:
            label = f["label"] or f["id"] or ""
            st.markdown(f"**{label}**")
            st.caption(str(f["value"])[:100])

    with col2:
        st.markdown(f"**⚠️ {len(gaps)} fields need your input**")

        if gaps and "explanations" not in st.session_state:
            with st.spinner("Getting AI explanations for each field..."):
                from concurrent.futures import ThreadPoolExecutor
                def _explain(f):
                    return f["id"], explain_field(f["label"] or f["id"] or "")
                with ThreadPoolExecutor(max_workers=10) as pool:
                    st.session_state.explanations = dict(pool.map(_explain, gaps))

        for f in gaps:
            label = f["label"] or f["id"] or ""
            explanation = st.session_state.get("explanations", {}).get(f["id"], "")
            if explanation:
                st.caption(f"💡 {explanation}")
            key = f"gap_{f['id']}"
            val = st.text_area(label, key=key, height=68)
            f["value"] = val if val.strip() else None

    # ── Step 3: Fill ──────────────────────────────────────────
    st.divider()
    st.subheader("Step 3 — Fill the form")
    st.info("The form is open in the browser window — review it, then click Fill Form. Close the browser window when you are done.")

    if st.button("Fill Form", type="primary"):
        page = st.session_state.get("form_page")
        if page is None or page.is_closed():
            st.error("The form browser was closed. Click 'Read Form' to reopen it.")
        else:
            with st.spinner("Filling form... close the browser window when done."):
                try:
                    filled, skipped = fill_live(page, mapped)
                    st.success(f"Done — {filled} fields filled, {skipped} skipped.")
                except Exception as e:
                    st.error(f"Error: {e}")
                finally:
                    try:
                        st.session_state.form_browser.close()
                        st.session_state.form_pw.stop()
                    except Exception:
                        pass
                    for k in ("form_pw", "form_browser", "form_page"):
                        st.session_state.pop(k, None)
