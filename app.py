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


def fill_live(url, mapped_fields):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        page.goto(url, wait_until="networkidle")
        filled = 0
        skipped = 0
        for field in mapped_fields:
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
        page.wait_for_timeout(60000)
        browser.close()
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
    with st.spinner("Opening form and reading fields..."):
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                page.goto(url, wait_until="networkidle")
                raw_fields = fetch_fields(page)
                browser.close()
            mapped = map_fields(raw_fields, profile)
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
                st.session_state.explanations = {
                    f["id"]: explain_field(f["label"] or f["id"] or "")
                    for f in gaps
                }

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
    st.info("A browser window will open, fill the form, and stay open for 60 seconds so you can review it.")

    if st.button("Fill Form", type="primary"):
        with st.spinner("Filling form in browser..."):
            try:
                filled, skipped = fill_live(st.session_state.url, mapped)
                st.success(f"Done — {filled} fields filled, {skipped} skipped. Check the browser window.")
            except Exception as e:
                st.error(f"Error: {e}")
