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
from agents.profile_reader import (
    read_cv, docx_to_pdf, empty_profile, empty_job, empty_education, empty_cpd, empty_referee
)

PROFILE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "profile")
MAX_STEPS   = 50

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
[data-testid="stForm"] {
    border: 2px solid rgba(255, 100, 80, 0.55) !important;
    border-radius: 0.5rem !important;
    background: rgba(255, 100, 80, 0.04) !important;
    padding: 1rem 1rem 0.5rem 1rem !important;
}
/* ── Clear button — red, via adjacent-sibling of marker div ────────────── */
[data-testid="stMarkdownContainer"]:has(#profile-clear-marker)
  + [data-testid="stHorizontalBlock"] button {
    background-color: #c0392b !important;
    color: white !important;
    border: none !important;
    font-weight: 600 !important;
    font-size: 0.95rem !important;
}
</style>
""", unsafe_allow_html=True)

st.title("AutoForm")

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Your Profile")
    if st.button("✏️ Edit Profile", use_container_width=True):
        st.session_state.page = "profile"
        st.rerun()
    _prof_sidebar_path = os.path.join(PROFILE_DIR, "user_profile.json")
    if os.path.exists(_prof_sidebar_path):
        profile = load_profile(_prof_sidebar_path)
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
    else:
        profile = None
        st.info("No profile saved yet — click Edit Profile to get started.")

def _match_opt(raw: str, options: list) -> str:
    """Map a raw extracted value to the nearest dropdown option, or '' if none fits."""
    raw = (raw or "").strip()
    if not raw:
        return ""
    if raw in options:
        return raw
    raw_lower = raw.lower()
    for opt in options:
        if opt.lower() == raw_lower:
            return opt
    # e.g. "Yes (awarded 2010)" → "Yes"
    for opt in options:
        if opt and raw_lower.startswith(opt.lower()):
            return opt
    return ""


# ── Page routing ──────────────────────────────────────────────────────────────
_page = st.session_state.get("page", "form")

if _page == "profile":
    _prof_path = os.path.join(PROFILE_DIR, "user_profile.json")
    if st.button("💾 Save Profile & Return to Form", type="primary"):
        os.makedirs(PROFILE_DIR, exist_ok=True)
        with open(_prof_path, "w") as _f:
            json.dump(st.session_state.profile_draft, _f, indent=2)
        st.session_state.page = "form"
        st.rerun()

    # ── Initialise draft in session state ─────────────────────────────────────
    if "profile_draft" not in st.session_state:
        base = empty_profile()
        if os.path.exists(_prof_path):
            with open(_prof_path) as _f:
                loaded = json.load(_f)
            # Merge loaded data into base schema so all keys always exist
            for k, v in loaded.items():
                if k in base:
                    base[k] = v
        st.session_state.profile_draft = base

    _d = st.session_state.profile_draft

    if st.session_state.pop("profile_just_saved", False):
        st.success("✅ Profile saved — switch to the Fill a Form tab to use it.")

    st.markdown('<div id="profile-clear-marker"></div>', unsafe_allow_html=True)
    col_hdr, col_clear = st.columns([5, 1])
    with col_hdr:
        st.subheader("My Profile")
    with col_clear:
        if st.button("🗑 Clear", help="Remove all saved data and start fresh",
                     use_container_width=True):
            st.session_state.profile_draft = empty_profile()
            st.session_state.cv_uploader_key = st.session_state.get("cv_uploader_key", 0) + 1
            if os.path.exists(_prof_path):
                os.remove(_prof_path)
            st.rerun()

    st.markdown(
        "Build your profile once — AutoForm uses it to fill every application. "
        "Upload your CV to extract details automatically, then check, edit, and add anything missing."
    )

    # ── CV Upload ──────────────────────────────────────────────────────────────
    with st.container(border=True):
        st.markdown("**Extract from CV**")
        st.info(
            "Your CV — including name, address, NI number, employment history, and any DBS or "
            "referee details — will be sent to Anthropic's Claude API for extraction. "
            "Anthropic states that commercial API data is not used for model training by default, "
            "and that API/screenshot data is generally deleted within 30 days by default, subject "
            "to Anthropic's terms, exceptions, and service-specific arrangements. "
            "AutoForm does not store your CV file. Only the extracted text fields on this page "
            "are saved locally on your device."
        )
        _cv_acknowledged = st.checkbox(
            "I understand this CV/profile will be sent to Anthropic's API. "
            "I confirm this is a **mock CV** during test mode."
        )
        _cv_file = st.file_uploader("Upload your CV (PDF or Word .docx)", type=["pdf", "docx"],
                                     label_visibility="collapsed",
                                     key=f"cv_upload_{st.session_state.get('cv_uploader_key', 0)}")
        if st.button("📄 Extract from CV", disabled=(_cv_file is None or not _cv_acknowledged)):
            with st.spinner("Reading your CV…"):
                _cv_bytes = _cv_file.read()
                if _cv_file.name.lower().endswith(".docx"):
                    _cv_bytes = docx_to_pdf(_cv_bytes)
                _extracted = read_cv(_cv_bytes)
            if _extracted:
                # Merge: extracted data fills empty fields; existing data is kept
                _p = _extracted.get("personal", {})
                for k, v in _p.items():
                    if v and not _d["personal"].get(k):
                        _d["personal"][k] = v
                if _extracted.get("work_history"):
                    _d["work_history"] = _extracted["work_history"]
                if _extracted.get("education"):
                    _d["education"] = _extracted["education"]
                if _extracted.get("cpd"):
                    _d["cpd"] = _extracted["cpd"]
                if _extracted.get("referees"):
                    _d["referees"] = _extracted["referees"]
                st.session_state.profile_draft = _d
                st.success("CV read — check the fields below and fill in any gaps.")
                st.rerun()
            else:
                st.error("Could not extract data from the CV. Try a different file.")

    # ── Personal Details ───────────────────────────────────────────────────────
    with st.expander("Personal Details", expanded=True):
        _p = _d["personal"]
        col1, col2 = st.columns(2)
        with col1:
            _TITLES = ["", "Mr", "Mrs", "Ms", "Miss", "Dr", "Prof"]
            _p["title"] = st.selectbox("Title", _TITLES,
                                       index=_TITLES.index(_match_opt(_p.get("title",""), _TITLES)))
            _p["full_name"] = st.text_input("Full name", _p.get("full_name",""))
            _p["email"]     = st.text_input("Email", _p.get("email",""))
            _p["phone_uk"]  = st.text_input("Phone", _p.get("phone_uk",""))
            _p["date_of_birth"] = st.text_input("Date of birth (DD/MM/YYYY)", _p.get("date_of_birth",""))
            _p["ni_number"] = st.text_input("NI number", _p.get("ni_number",""))
        with col2:
            _p["address_line_1"] = st.text_input("Address line 1", _p.get("address_line_1",""))
            _p["address_line_2"] = st.text_input("Address line 2", _p.get("address_line_2",""))
            _p["town_city"]  = st.text_input("Town / city", _p.get("town_city",""))
            _p["county"]     = st.text_input("County", _p.get("county",""))
            _p["postcode"]   = st.text_input("Postcode", _p.get("postcode",""))
            _p["nationality"]= st.text_input("Nationality", _p.get("nationality",""))
        _RTW_OPTS = ["", "Yes", "No"]
        _p["right_to_work"] = st.selectbox("Right to work in the UK", _RTW_OPTS,
                                            index=_RTW_OPTS.index(_match_opt(_p.get("right_to_work",""), _RTW_OPTS)))
        _p["dbs_status"]             = st.text_input("DBS status", _p.get("dbs_status",""))
        _p["teacher_reference_number"]= st.text_input("Teacher Reference Number (TRN)", _p.get("teacher_reference_number",""))
        _QTS_OPTS = ["", "Yes", "No", "In progress"]
        _p["qts"] = st.selectbox("QTS", _QTS_OPTS,
                                  index=_QTS_OPTS.index(_match_opt(_p.get("qts",""), _QTS_OPTS)))
        _p["availability"]           = st.text_input("Availability / notice period", _p.get("availability",""))
        _d["personal"] = _p

    # ── Work History ───────────────────────────────────────────────────────────
    with st.expander("Work History"):
        for _i, _job in enumerate(_d["work_history"]):
            with st.container(border=True):
                _c1, _c2 = st.columns([4, 1])
                with _c1:
                    st.markdown(f"**Job {_i + 1}**")
                with _c2:
                    if st.button("Remove", key=f"rm_job_{_i}"):
                        _d["work_history"].pop(_i)
                        st.rerun()
                _job["employer"] = st.text_input("Employer", _job.get("employer",""), key=f"emp_{_i}")
                _job["title"]    = st.text_input("Job title", _job.get("title",""), key=f"jtitle_{_i}")
                _c3, _c4 = st.columns(2)
                with _c3:
                    _job["start"] = st.text_input("Start", _job.get("start",""), key=f"jstart_{_i}")
                with _c4:
                    _job["end"]   = st.text_input("End (leave blank if current)", _job.get("end","") or "", key=f"jend_{_i}") or None
                _duties = "\n".join(_job.get("responsibilities", []))
                _new_duties = st.text_area("Main duties (one per line)", _duties, key=f"jduty_{_i}", height=80)
                _job["responsibilities"] = [r.strip() for r in _new_duties.splitlines() if r.strip()]
        if st.button("＋ Add job"):
            _d["work_history"].append(empty_job())
            st.rerun()

    # ── Education ─────────────────────────────────────────────────────────────
    with st.expander("Education & Qualifications"):
        for _i, _edu in enumerate(_d["education"]):
            with st.container(border=True):
                _c1, _c2 = st.columns([4, 1])
                with _c1:
                    st.markdown(f"**Qualification {_i + 1}**")
                with _c2:
                    if st.button("Remove", key=f"rm_edu_{_i}"):
                        _d["education"].pop(_i)
                        st.rerun()
                _c3, _c4 = st.columns(2)
                with _c3:
                    _edu["qualification"] = st.text_input("Qualification", _edu.get("qualification",""), key=f"eq_{_i}")
                    _edu["institution"]   = st.text_input("Institution", _edu.get("institution",""), key=f"ei_{_i}")
                with _c4:
                    _edu["subject"] = st.text_input("Subject", _edu.get("subject",""), key=f"es_{_i}")
                    _edu["grade"]   = st.text_input("Grade / class", _edu.get("grade",""), key=f"eg_{_i}")
                _edu["end"] = st.text_input("Year awarded", _edu.get("end",""), key=f"ey_{_i}")
        if st.button("＋ Add qualification"):
            _d["education"].append(empty_education())
            st.rerun()

    # ── CPD ───────────────────────────────────────────────────────────────────
    with st.expander("CPD / Training"):
        for _i, _cpd in enumerate(_d["cpd"]):
            with st.container(border=True):
                _c1, _c2 = st.columns([4, 1])
                with _c1:
                    st.markdown(f"**Course {_i + 1}**")
                with _c2:
                    if st.button("Remove", key=f"rm_cpd_{_i}"):
                        _d["cpd"].pop(_i)
                        st.rerun()
                _cpd["title"]    = st.text_input("Course / training title", _cpd.get("title",""), key=f"ct_{_i}")
                _cpd["provider"] = st.text_input("Provider", _cpd.get("provider",""), key=f"cp_{_i}")
                _cpd["date"]     = st.text_input("Date", _cpd.get("date",""), key=f"cd_{_i}")
        if st.button("＋ Add course"):
            _d["cpd"].append(empty_cpd())
            st.rerun()

    # ── Referees ──────────────────────────────────────────────────────────────
    with st.expander("Referees"):
        for _i, _ref in enumerate(_d["referees"]):
            with st.container(border=True):
                _c1, _c2 = st.columns([4, 1])
                with _c1:
                    st.markdown(f"**Referee {_i + 1}**")
                with _c2:
                    if st.button("Remove", key=f"rm_ref_{_i}"):
                        _d["referees"].pop(_i)
                        st.rerun()
                _c3, _c4 = st.columns(2)
                with _c3:
                    _ref["name"]         = st.text_input("Name", _ref.get("name",""), key=f"rn_{_i}")
                    _ref["organisation"] = st.text_input("Organisation", _ref.get("organisation",""), key=f"ro_{_i}")
                with _c4:
                    _ref["title"] = st.text_input("Job title", _ref.get("title",""), key=f"rt_{_i}")
                    _ref["email"] = st.text_input("Email", _ref.get("email",""), key=f"re_{_i}")
                _ref["phone"] = st.text_input("Phone", _ref.get("phone",""), key=f"rp_{_i}")
        if st.button("＋ Add referee"):
            _d["referees"].append(empty_referee())
            st.rerun()

    # ── Employment Preferences ────────────────────────────────────────────────
    with st.expander("Employment Preferences"):
        _prefs = _d.get("employment_preferences", {})
        _EMP_OPTS = ["", "Full-time", "Part-time", "Supply", "Any"]
        _prefs["employment_type"] = st.selectbox("Employment type", _EMP_OPTS,
                                                  index=_EMP_OPTS.index(_match_opt(_prefs.get("employment_type",""), _EMP_OPTS)))
        _CON_OPTS = ["", "Permanent", "Fixed-term", "Supply", "Any"]
        _prefs["contract_type"] = st.selectbox("Contract type", _CON_OPTS,
                                                index=_CON_OPTS.index(_match_opt(_prefs.get("contract_type",""), _CON_OPTS)))
        _prefs["preferred_start"]  = st.text_input("Preferred start", _prefs.get("preferred_start",""))
        _d["employment_preferences"] = _prefs

    # ── Save ──────────────────────────────────────────────────────────────────
    st.divider()
    if st.button("💾  Save Profile", type="primary"):
        os.makedirs(PROFILE_DIR, exist_ok=True)
        with open(_prof_path, "w") as _f:
            json.dump(_d, _f, indent=2)
        st.session_state.profile_just_saved = True
        st.rerun()

else:
    st.markdown("""
<div style='border-left:4px solid rgba(255,100,80,0.7);
            background:rgba(255,100,80,0.06);
            padding:1.1rem 1.4rem 1rem 1.4rem;
            border-radius:0 0.5rem 0.5rem 0;
            margin-bottom:0.75rem'>
  <p style='font-size:1.2rem;font-weight:600;margin:0 0 0.6rem 0;line-height:1.4'>
    Save time on every teaching job application.
  </p>
  <p style='font-size:1rem;margin:0 0 1rem 0;line-height:1.6;opacity:0.9'>
    AutoForm fills in the repetitive fields — personal details, employment history,
    qualifications, and referees — directly from your profile.
    Supporting statements and open-ended questions are left for you to write.
  </p>
  <p style='font-size:0.95rem;margin:0;line-height:1.8;opacity:0.85'>
    <strong>How to use:</strong><br>
    &nbsp;&nbsp;① &nbsp;Click <strong>Edit Profile</strong> in the sidebar — upload your CV or fill in your details<br>
    &nbsp;&nbsp;② &nbsp;Paste the URL of the application form into the box below<br>
    &nbsp;&nbsp;③ &nbsp;Click <strong>Launch Agent</strong> — the form fills automatically<br>
    &nbsp;&nbsp;④ &nbsp;A browser window opens with the completed form — review every field<br>
    &nbsp;&nbsp;⑤ &nbsp;Write any supporting statements, then click <strong>Submit Application</strong>
  </p>
</div>
""", unsafe_allow_html=True)
    if TEST_MODE:
        st.warning(
            "🔒 **Test mode** — synthetic forms only · no real applications · "
            "no automatic submission",
            icon=None
        )
    # ── URL input ─────────────────────────────────────────────────────────────
    st.subheader("Enter the form URL")
    _last_url = st.session_state.get("agent_url", "")
    with st.form("agent_form"):
        url = st.text_input("URL", value=_last_url, label_visibility="collapsed",
                            placeholder="https://...  or  file:///home/...")
        agent_clicked = st.form_submit_button("🤖 Launch Agent", type="primary")

    st.caption(
        "⚠️ Agent mode sends browser screenshots to the Claude API. "
        "Use the mock profile when testing on unfamiliar sites."
    )
    _active_name = (profile or {}).get("personal", {}).get("full_name", "")
    if _active_name:
        st.caption(f"👤 Active profile: **{_active_name}**")
    else:
        st.warning("⚠️ No profile saved — go to Edit Profile before launching.")

    if agent_clicked:
        if not url:
            st.error("Enter a URL first.")
        elif not profile:
            st.error("⚠️ No profile saved — go to Edit Profile first.")
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

    # ── Always-visible status area ─────────────────────────────────────────────
    st.divider()

    progress_bar    = st.progress(0, text="Ready — waiting to launch")
    status_line     = st.empty()

    col_step, col_info = st.columns([1, 2])
    with col_step:
        step_slot = st.empty()
    with col_info:
        info_slot = st.empty()

    screenshot_slot = st.empty()
    next_slot       = st.empty()
    completion_slot = st.empty()

    # ── Render panels based on current state ───────────────────────────────────
    result = st.session_state.get("agent_result")

    if result:
        cost = (result["tok_in"] * 5 + result["tok_out"] * 25) / 1_000_000
        progress_bar.progress(1.0, text="Complete")

        with step_slot.container(border=True):
            st.metric("Progress", "✓  Complete")
        with info_slot.container(border=True):
            st.caption("**Model**")
            st.caption("claude-sonnet-4-6")
            st.caption("**Tokens sent**  |  **Est. cost**")
            st.caption(f"{result['tok_in']:,}  |  ~${cost:.3f}")

        if result.get("final_screenshot"):
            with screenshot_slot.container():
                st.image(
                    base64.b64decode(result["final_screenshot"]),
                    caption="Final form state — scroll to review all fields",
                    use_container_width=True,
                )

        filled  = result.get("fields_filled", [])
        skipped = result.get("fields_skipped", [])

        with next_slot.container(border=True):
            st.subheader("✓ What to do next")
            st.markdown(
                "<p style='font-size:1.25rem;margin:0.25rem 0 0.75rem 0'>"
                "Please complete any gaps, supporting statements, and open-ended questions — "
                "then click <strong>Submit Application</strong>."
                "</p>",
                unsafe_allow_html=True
            )
            if skipped:
                st.markdown("**Fields needing your input:**")
                for s in skipped:
                    st.markdown(f"- ⚠ {s}")
            else:
                st.markdown(
                    "<p style='opacity:0.65;font-size:0.9rem;margin:0'>"
                    "⚠ Check the form carefully — any open-ended sections will need your own writing."
                    "</p>",
                    unsafe_allow_html=True
                )

        with completion_slot.container():
            st.divider()
            if result.get("filled_html"):
                st.download_button(
                    "📥 Download filled form",
                    data=result["filled_html"].encode("utf-8") if isinstance(result["filled_html"], str) else result["filled_html"],
                    file_name="filled_form.html",
                    mime="text/html",
                    help="Open this file in your browser — all fields will be pre-filled. Complete the writing sections, then click Submit.",
                    use_container_width=True,
                    type="primary",
                )
            if not result["completed"]:
                st.warning(
                    f"Agent reached the step limit ({result['n_steps']} steps) without "
                    "signalling done. The form may be partially complete."
                )
            if filled:
                with st.expander(f"✓ {len(filled)} fields filled by the agent"):
                    for f in filled:
                        st.markdown(f"- ✓ {f}")
            with st.expander("Agent activity log"):
                for s in result["steps_log"]:
                    st.text(s)

    else:
        with step_slot.container(border=True):
            st.metric("Progress", "—")
        with info_slot.container(border=True):
            st.caption("**Model**")
            st.caption("claude-sonnet-4-6")
            st.caption("**Tokens sent**  |  **Est. cost**")
            st.caption("—  |  —")
        with next_slot.container(border=True):
            st.markdown(
                "<div style='opacity:0.4'>"
                "<p style='font-size:1.5rem;font-weight:600;margin:0 0 0.4rem 0'>What to do next</p>"
                "<p style='font-size:1.25rem;margin:0 0 0.3rem 0'>"
                "Please complete any gaps, supporting statements, and open-ended questions — "
                "then click <strong>Submit Application</strong>."
                "</p>"
                "<p style='font-size:0.9rem;margin:0'>Available once the agent finishes.</p>"
                "</div>",
                unsafe_allow_html=True
            )

# ── Agent execution (outside tabs — runs regardless of active tab) ─────────────
if st.session_state.get("agent_run"):
    st.session_state.agent_run = False
    target_url = st.session_state.get("agent_url", "")
    steps_log  = []

    state = {"step": 0, "tok_in": 0, "tok_out": 0, "last_screenshot": None}

    def _redraw_panels(running=True):
        cost = (state["tok_in"] * 5 + state["tok_out"] * 25) / 1_000_000
        with step_slot.container(border=True):
            if not running:
                st.metric("Progress", "✓  Complete")
            else:
                pct = int(state['step'] / MAX_STEPS * 100)
                st.metric("Progress", f"{pct}%", delta="Running")
        with info_slot.container(border=True):
            st.caption("**Model**")
            st.caption("claude-sonnet-4-6")
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
                st.markdown(
                    "<p style='font-size:1.25rem;margin:0.25rem 0 0.75rem 0'>"
                    "Please complete any gaps, supporting statements, and open-ended questions — "
                    "then click <strong>Submit Application</strong>."
                    "</p>"
                    "<p style='font-size:0.9rem;opacity:0.6;margin:0'>"
                    "Field report will appear here once you close the review window."
                    "</p>",
                    unsafe_allow_html=True
                )
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
        st.metric("Progress", "Starting…")
    with info_slot.container(border=True):
        st.caption("**Model**")
        st.caption("claude-sonnet-4-6")
        st.caption("**Tokens sent**  |  **Est. cost**")
        st.caption("—  |  —")

    _agent_done  = False
    _agent_error = None
    _filled_html = None

    try:
        with sync_playwright() as pw:
            # ── Phase 1: headless fill ─────────────────────────────────────
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

            # ── Harvest all filled field values before closing ─────────────
            field_values = page.evaluate("""() => {
                const out = {};
                document.querySelectorAll('input, textarea, select').forEach(el => {
                    if (!el.id && !el.name) return;
                    const key = el.id || el.name;
                    if (el.type === 'radio' || el.type === 'checkbox') {
                        if (el.checked) out[key] = el.value;
                    } else {
                        if (el.value && el.value.trim()) out[key] = el.value;
                    }
                });
                return out;
            }""")
            # ── Capture filled HTML for download ──────────────────────────
            _raw_html = page.content()
            _fill_script = (
                "<script>(function(){const vals="
                + json.dumps(field_values)
                + """;function fill(){Object.entries(vals).forEach(([k,v])=>{
let el=document.getElementById(k)||document.querySelector('[name="'+k+'"]');
if(!el)return;
if(el.tagName==='SELECT'){el.value=v;el.dispatchEvent(new Event('change',{bubbles:true}));}
else if(el.type==='radio'){const r=document.querySelector('input[name="'+el.name+'"][value="'+v+'"]');
if(r){r.checked=true;r.dispatchEvent(new Event('change',{bubbles:true}));}}
else if(el.type==='checkbox'){el.checked=true;el.dispatchEvent(new Event('change',{bubbles:true}));}
else{el.value=v;el.dispatchEvent(new Event('input',{bubbles:true}));
el.dispatchEvent(new Event('change',{bubbles:true}));}});}
document.readyState==='loading'?document.addEventListener('DOMContentLoaded',fill):fill();
})();</script>"""
            )
            _filled_html = (
                _raw_html.replace("</body>", _fill_script + "</body>")
                if "</body>" in _raw_html
                else _raw_html + _fill_script
            )
            browser.close()

            # ── Phase 2: visible review window ────────────────────────────
            if completed:
                # Update 'What to do next' NOW — fields_skipped is available and
                # the visible browser is about to open, so the user can see the
                # list while they're filling in the form.
                with next_slot.container(border=True):
                    st.subheader("✓ What to do next")
                    st.markdown(
                        "<p style='font-size:1.25rem;margin:0.25rem 0 0.75rem 0'>"
                        "Please complete any gaps, supporting statements, and open-ended questions — "
                        "then click <strong>Submit Application</strong>."
                        "</p>",
                        unsafe_allow_html=True
                    )
                    if fields_skipped:
                        st.markdown("**Fields needing your input:**")
                        for s in fields_skipped:
                            st.markdown(f"- ⚠ {s}")
                    else:
                        st.markdown(
                            "<p style='opacity:0.65;font-size:0.9rem;margin:0'>"
                            "⚠ Check the form carefully — any open-ended sections will need your own writing."
                            "</p>",
                            unsafe_allow_html=True
                        )

                _in_docker = os.path.exists("/.dockerenv")
                if _in_docker:
                    status_line.caption(
                        "✓ Agent finished — running on server, no browser window available. "
                        "Review the completed fields in the report above."
                    )
                else:
                    status_line.caption(
                        "✓ Agent finished — a browser window will open with the completed form. "
                        "Review every field, then click Submit. Close the window when done."
                    )
                    vis_browser = pw.chromium.launch(
                        headless=False,
                        args=["--window-size=1100,900", "--window-position=200,30"]
                    )
                    vis_ctx  = vis_browser.new_context(viewport={"width": 1100, "height": 900})
                    vis_page = vis_ctx.new_page()
                    vis_page.goto(target_url, wait_until="networkidle")

                    # Restore all harvested values
                    vis_page.evaluate("""(values) => {
                        Object.entries(values).forEach(([key, val]) => {
                            let el = document.getElementById(key)
                                   || document.querySelector(`[name="${key}"]`);
                            if (!el) return;
                            if (el.tagName === 'SELECT') {
                                el.value = val;
                                el.dispatchEvent(new Event('change', {bubbles: true}));
                            } else if (el.type === 'radio') {
                                const r = document.querySelector(
                                    `input[name="${el.name}"][value="${val}"]`);
                                if (r) { r.checked = true;
                                         r.dispatchEvent(new Event('change', {bubbles: true})); }
                            } else if (el.type === 'checkbox') {
                                el.checked = true;
                                el.dispatchEvent(new Event('change', {bubbles: true}));
                            } else {
                                el.value = val;
                                el.dispatchEvent(new Event('input',  {bubbles: true}));
                                el.dispatchEvent(new Event('change', {bubbles: true}));
                                el.dispatchEvent(new Event('blur',   {bubbles: true}));
                            }
                        });
                    }""", field_values)

                    # Wait for user to review and close the window
                    status_line.caption(
                        "⏳ Browser window open — complete your writing sections, submit, then close the window."
                    )
                    try:
                        vis_page.wait_for_event("close", timeout=0)
                    except Exception:
                        pass
                    vis_browser.close()
                    status_line.caption("✓ Review window closed.")

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
            "filled_html":      _filled_html,
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
