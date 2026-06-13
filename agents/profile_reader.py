"""
Profile Reader — extracts structured applicant data from a CV (PDF).
Sends the document to Claude and returns a dict matching the profile schema.
"""

import json
import base64
import os
import subprocess
import tempfile
import anthropic
from dotenv import load_dotenv

load_dotenv()
_client = anthropic.Anthropic()

# The target schema — defines what we try to extract
_EMPTY_PROFILE = {
    "personal": {
        "full_name": "", "title": "", "date_of_birth": "",
        "email": "", "phone_uk": "",
        "address_line_1": "", "address_line_2": "",
        "town_city": "", "county": "", "postcode": "",
        "nationality": "", "right_to_work": "", "visa_required": "",
        "ni_number": "", "dbs_status": "", "dbs_number": "",
        "teacher_reference_number": "", "qts": "", "availability": "",
        "location_current": ""
    },
    "work_history": [],
    "education": [],
    "cpd": [],
    "referees": [],
    "employment_preferences": {
        "employment_type": "", "contract_type": "", "preferred_start": ""
    }
}

_PROMPT = f"""Extract all information from this CV and return it as a JSON object.

Target schema:
{json.dumps(_EMPTY_PROFILE, indent=2)}

Rules:
- Extract only what is actually in the CV — do not invent, guess, or fill in gaps
- work_history: list each job as {{"employer":"","title":"","start":"","end":null,"responsibilities":[]}}
  - end is null if it is the current role, otherwise a string
  - responsibilities: up to 5 bullet points describing duties
- education: list as {{"qualification":"","subject":"","institution":"","grade":"","end":""}}
  - end is the year awarded as a string e.g. "2015"
- cpd: list courses/training as {{"title":"","provider":"","date":""}}
- referees: include only if listed in the CV — {{"name":"","title":"","organisation":"","email":"","phone":""}}
- Leave any field as "" or [] if not found — never invent data
- Return ONLY the JSON object — no explanation, no markdown fences"""


def docx_to_pdf(docx_bytes: bytes) -> bytes:
    """Convert a .docx file to PDF using LibreOffice (headless). No pip install needed."""
    with tempfile.TemporaryDirectory() as tmp:
        docx_path = os.path.join(tmp, "cv.docx")
        with open(docx_path, "wb") as f:
            f.write(docx_bytes)
        subprocess.run(
            ["libreoffice", "--headless", "--convert-to", "pdf", "--outdir", tmp, docx_path],
            check=True, capture_output=True
        )
        pdf_path = os.path.join(tmp, "cv.pdf")
        with open(pdf_path, "rb") as f:
            return f.read()


def read_cv(file_bytes: bytes) -> dict:
    """
    Extract profile data from a CV PDF.
    Returns a profile dict — fields not found in the CV are empty strings/lists.
    """
    b64 = base64.standard_b64encode(file_bytes).decode()

    response = _client.messages.create(
        model="claude-opus-4-8",
        max_tokens=4096,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "document",
                    "source": {
                        "type": "base64",
                        "media_type": "application/pdf",
                        "data": b64
                    }
                },
                {"type": "text", "text": _PROMPT}
            ]
        }]
    )

    raw = response.content[0].text.strip()
    start = raw.find('{')
    if start == -1:
        return {}
    try:
        data, _ = json.JSONDecoder().raw_decode(raw, start)
        return data
    except json.JSONDecodeError:
        return {}


def empty_profile() -> dict:
    """Return a blank profile dict matching the schema."""
    import copy
    return copy.deepcopy(_EMPTY_PROFILE)


def empty_job() -> dict:
    return {"employer": "", "title": "", "start": "", "end": "", "responsibilities": []}


def empty_education() -> dict:
    return {"qualification": "", "subject": "", "institution": "", "grade": "", "end": ""}


def empty_cpd() -> dict:
    return {"title": "", "provider": "", "date": ""}


def empty_referee() -> dict:
    return {"name": "", "title": "", "organisation": "", "email": "", "phone": ""}
