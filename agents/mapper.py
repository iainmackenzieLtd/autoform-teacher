"""
Maps form fields (from form_reader) to user profile data.
Outputs a matched list: each field with its value, or flagged as NEEDS USER INPUT.

Usage: python3 agents/mapper.py tests/sample_form.html profile/user_profile.json
"""

import json
import sys
from agents.form_reader import read_form


def load_profile(filepath):
    with open(filepath, "r") as f:
        return json.load(f)


def join_bullets(items):
    return "; ".join(items) if items else None


def map_fields(form_path, profile_path):
    fields = read_form(form_path)
    profile = load_profile(profile_path)

    personal = profile.get("personal", {})
    work = profile.get("work_history", [])
    education = profile.get("education", [])
    cpd = profile.get("cpd", [])

    results = []

    for field in fields:
        fid = field["id"]
        label = field["label"] or fid
        value = None

        # --- Personal ---
        if fid == "full_name":
            value = personal.get("full_name")

        # --- Work history: job_N_* (1-indexed) ---
        elif fid.startswith("job_"):
            parts = fid.split("_")
            index = int(parts[1]) - 1
            key = "_".join(parts[2:])
            if index < len(work):
                job = work[index]
                if key == "school":
                    value = job.get("employer")
                elif key == "title":
                    value = job.get("title")
                elif key == "from":
                    value = job.get("start")
                elif key == "to":
                    value = job.get("end") or "Present"
                elif key == "duties":
                    value = join_bullets(job.get("responsibilities", []))

        # --- Qualifications: qual_N_* (1-indexed) ---
        elif fid.startswith("qual_"):
            parts = fid.split("_")
            index = int(parts[1]) - 1
            key = "_".join(parts[2:])
            if index < len(education):
                qual = education[index]
                if key == "year":
                    value = qual.get("end")
                elif key == "institution":
                    value = qual.get("institution")
                elif key == "name":
                    q = qual.get("qualification", "")
                    s = qual.get("subject", "")
                    value = f"{q} {s}".strip() if q or s else None

        # --- Training / CPD: train_N_* (1-indexed) ---
        elif fid.startswith("train_"):
            parts = fid.split("_")
            index = int(parts[1]) - 1
            key = "_".join(parts[2:])
            if index < len(cpd):
                entry = cpd[index]
                if key == "year":
                    value = entry.get("date")
                elif key == "provider":
                    value = entry.get("provider")
                elif key == "course":
                    value = entry.get("title")

        results.append({
            "id": fid,
            "label": label,
            "type": field["type"],
            "required": field["required"],
            "value": value,
            "status": "mapped" if value else "NEEDS USER INPUT"
        })

    return results


def print_results(results):
    col = 35
    for r in results:
        status = r["value"] if r["value"] else "*** NEEDS USER INPUT ***"
        label = r["label"][:col].ljust(col)
        print(f"{label} → {status}")


if __name__ == "__main__":
    form_path = sys.argv[1] if len(sys.argv) > 1 else "tests/sample_form.html"
    profile_path = sys.argv[2] if len(sys.argv) > 2 else "profile/user_profile.json"
    results = map_fields(form_path, profile_path)
    print_results(results)
