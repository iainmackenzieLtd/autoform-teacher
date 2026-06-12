"""
AutoForm — Streamlit UI for the form-filling pipeline.
Run with: streamlit run app.py
"""

import sys
import os
import json
import webbrowser
import streamlit as st
from playwright.sync_api import sync_playwright

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from run_live import fetch_fields, map_fields, load_profile
from agents.field_explainer import explain_field
from agents.form_agent import run_form_agent

PROFILE_PATH      = "profile/user_profile.json"
MOCK_PROFILE_PATH = "profile/mock_profile.json"


def classify_field(label):
    """Return 'block', 'sensitive', or 'safe' based on the field label."""
    l = (label or "").lower()
    for kw in ["national insurance", "ni number", "passport", "bank account", "sort code",
               "account number", "disability", "ethnic", "criminal", "dbs", "gender",
               "religion", "medical", "health condition"]:
        if kw in l:
            return "block"
    for kw in ["address", "postcode", "salary", "wage", "date of birth", "dob",
               "nationality", "right to work", "reference", "referee", "next of kin"]:
        if kw in l:
            return "sensitive"
    return "safe"


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


# ── Page setup ───────────────────────────────────────────────────────────────
st.set_page_config(page_title="AutoForm", layout="wide")
st.title("AutoForm")
st.caption("Fill any job application form from your profile — automatically.")

# ── Sidebar ──────────────────────────────────────────────────────────────────
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
st.subheader("Step 1 — Enter the form URL")
url = st.text_input("URL", label_visibility="collapsed",
                    placeholder="https://...")

col_read, col_agent, col_login, col_link = st.columns([2, 2, 3, 2])
with col_read:
    read_clicked = st.button("Read Form", type="primary", use_container_width=True,
                             help="Reads the HTML structure — fast and cheap. Best for simple open forms.")
with col_agent:
    agent_clicked = st.button("🤖 Launch Agent", use_container_width=True,
                              help="Claude fills the form visually. Works on any form type.")
with col_login:
    needs_login = st.checkbox(
        "Requires manual login",
        help=(
            "Tick for login-required portals. The browser opens and pauses — "
            "log in yourself, then click Resume in the Playwright Inspector."
        )
    )
with col_link:
    if "url" in st.session_state:
        st.link_button("Open in new tab ↗", st.session_state.url)

st.caption(
    "🤖 Agent mode sends browser screenshots to the Claude API. "
    "Use the mock profile when testing on unfamiliar sites."
)

if read_clicked and url:
    with st.spinner("Reading form..."):
        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch(headless=True)
                pg = browser.new_page()
                pg.goto(url, wait_until="networkidle")
                raw_fields = fetch_fields(pg)
                browser.close()
            mapped = map_fields(raw_fields, profile)
            st.session_state.mapped = mapped
            st.session_state.url = url
            st.session_state.pop("explanations", None)
            st.session_state.pop("gap_index", None)
            st.session_state.gap_answers = {}
            webbrowser.open_new_tab(url)
        except Exception as e:
            st.error(f"Could not read form: {e}")

if agent_clicked:
    if not url:
        st.error("Enter a URL above first.")
    else:
        st.session_state.agent_run  = True
        st.session_state.agent_url  = url
        st.session_state.agent_login = needs_login
        st.rerun()

# ── Agent execution ───────────────────────────────────────────────────────────
if st.session_state.get("agent_run"):
    st.session_state.agent_run = False
    target_url   = st.session_state.get("agent_url", url)
    pause_login  = st.session_state.get("agent_login", False)
    steps_log    = []

    def _on_step(n, desc):
        steps_log.append(f"Step {n}: {desc}")

    with st.spinner("AI Agent is working — watch the browser window…"):
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
                f"Agent finished in {n_steps} steps — "
                "review what was filled before closing the browser."
            )
            with st.expander("Agent activity log"):
                for s in steps_log:
                    st.text(s)
        except Exception as e:
            st.error(f"Agent error: {e}")


# ── Step 2: Review mapping (structured path only) ─────────────────────────────
if "mapped" in st.session_state:
    mapped   = st.session_state.mapped
    matched  = [f for f in mapped if f["status"] == "mapped"]
    gaps     = [f for f in mapped if f["status"] == "NEEDS USER INPUT"]
    overflow = [f for f in mapped if f["status"] == "OVERFLOW"]

    st.divider()
    st.subheader("Step 2 — Review mapping")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown(f"**✓ {len(matched)} fields matched from your profile**")
        if overflow:
            st.caption(
                f"{len(overflow)} extra form slots left blank — "
                "the form has more rows than your profile entries."
            )
        for f in matched:
            label = f["label"] or f["id"] or ""
            st.markdown(f"**{label}**")
            st.caption(str(f["value"])[:100])

    with col2:
        if not gaps:
            st.markdown("**✓ No gaps — everything matched**")
        else:
            st.markdown(f"**⚠️ {len(gaps)} fields need your input**")

            if "explanations" not in st.session_state:
                with st.spinner("Getting AI explanations..."):
                    from concurrent.futures import ThreadPoolExecutor
                    def _explain(f):
                        return f["id"], explain_field(f["label"] or f["id"] or "")
                    with ThreadPoolExecutor(max_workers=10) as pool:
                        st.session_state.explanations = dict(pool.map(_explain, gaps))

            if "gap_index" not in st.session_state:
                st.session_state.gap_index = 0
            if "gap_answers" not in st.session_state:
                st.session_state.gap_answers = {}

            idx     = st.session_state.gap_index
            answers = st.session_state.gap_answers

            if idx >= len(gaps):
                st.success(f"All {len(gaps)} gaps reviewed — scroll down to Step 3.")
                answered = sum(1 for a in answers.values() if a.strip())
                st.caption(f"{answered} answered · {len(gaps) - answered} skipped")
                if st.button("← Review again"):
                    st.session_state.gap_index = 0
                    st.rerun()
            else:
                f = gaps[idx]
                label       = f["label"] or f["id"] or ""
                explanation = st.session_state.get("explanations", {}).get(f["id"], "")

                st.progress(idx / len(gaps))
                st.caption(f"**{idx + 1} of {len(gaps)}** — {label}")

                if explanation:
                    st.info(f"💡 {explanation}")

                current_val = answers.get(f["id"], "")
                typed = st.text_area(
                    label, value=current_val, height=100,
                    label_visibility="collapsed",
                    placeholder="Type your answer here, or click Skip"
                )
                st.components.v1.html(
                    "<script>setTimeout(()=>{"
                    "const t=window.parent.document.querySelector('textarea');"
                    "if(t){t.focus();t.setSelectionRange(t.value.length,t.value.length);}"
                    "},120);</script>",
                    height=0
                )

                c_back, c_skip, c_next = st.columns([1, 1, 2])
                with c_back:
                    if idx > 0 and st.button("← Back"):
                        answers[f["id"]] = typed
                        st.session_state.gap_index -= 1
                        st.rerun()
                with c_skip:
                    if st.button("Skip →"):
                        answers[f["id"]] = ""
                        st.session_state.gap_index += 1
                        st.rerun()
                with c_next:
                    if st.button("Save & Next →", type="primary"):
                        answers[f["id"]] = typed
                        st.session_state.gap_index += 1
                        st.rerun()

    # Sync saved gap answers into mapped before Step 3
    answers = st.session_state.get("gap_answers", {})
    for f in mapped:
        if f["status"] == "NEEDS USER INPUT":
            saved = answers.get(f["id"], "")
            f["value"] = saved.strip() if saved and saved.strip() else None

    # ── Step 3: Approve and fill (structured path) ────────────────────────────
    st.divider()
    st.subheader("Step 3 — Approve fields before filling")
    st.caption(
        "Tick the fields you want AutoForm to type. "
        "🟢 Safe · 🟡 Sensitive (flagged) · 🔴 High-risk (unticked by default)"
    )

    LEVEL_ICON    = {"safe": "🟢", "sensitive": "🟡", "block": "🔴"}
    LEVEL_DEFAULT = {"safe": True,  "sensitive": True,  "block": False}

    fillable = [f for f in mapped if f.get("value")]
    no_value = [f for f in mapped if not f.get("value")]

    if not fillable:
        st.warning(
            "No fields have values — complete the gap inputs in Step 2 first, "
            "or use the AI Agent above."
        )
    else:
        st.caption(
            f"{len(fillable)} fields have values · "
            f"{len(no_value)} fields have no value and will be skipped"
        )
        st.markdown("")

        hcol1, hcol2, hcol3 = st.columns([1, 5, 6])
        hcol1.caption("Fill?")
        hcol2.caption("Field")
        hcol3.caption("Value that will be typed")
        st.markdown("---")

        for f in fillable:
            label   = f["label"] or f["id"] or ""
            level   = classify_field(label)
            icon    = LEVEL_ICON[level]
            default = LEVEL_DEFAULT[level]

            c1, c2, c3 = st.columns([1, 5, 6])
            with c1:
                st.checkbox("", key=f"approve_{f['id']}", value=default,
                            label_visibility="collapsed")
            with c2:
                st.markdown(f"{icon} **{label}**")
            with c3:
                st.caption(str(f["value"])[:120])

        st.markdown("---")

        approved_count = sum(
            1 for f in fillable
            if st.session_state.get(f"approve_{f['id']}", False)
        )
        st.caption(f"{approved_count} of {len(fillable)} fields approved")

        if st.button("Confirm and Fill", type="primary"):
            approved_fields = [
                f for f in fillable
                if st.session_state.get(f"approve_{f['id']}", False)
            ]
            with st.spinner(f"Filling {len(approved_fields)} fields…"):
                try:
                    with sync_playwright() as pw:
                        browser = pw.chromium.launch(
                            headless=False,
                            args=["--window-size=1400,900"]
                        )
                        pg = browser.new_page()
                        pg.goto(st.session_state.url, wait_until="networkidle")
                        filled, not_found = fill_live(pg, approved_fields)
                        browser.close()
                    blocked = len(fillable) - len(approved_fields)
                    st.success(
                        f"Done — {filled} filled · "
                        f"{blocked} skipped by you · "
                        f"{not_found} not found on page"
                    )
                except Exception as e:
                    st.error(f"Error: {e}")
