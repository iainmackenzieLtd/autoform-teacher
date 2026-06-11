"""
Reads an HTML form file and outputs a structured list of fields.
Uses only Python standard library — no packages required.

Usage: python3 agents/form_reader.py tests/sample_form.html
"""

import json
import sys
from html.parser import HTMLParser


class FormFieldExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.fields = []
        self.labels = {}
        self.in_label = False
        self.label_text = ""
        self.current_label_for = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "label":
            self.in_label = True
            self.label_text = ""
            self.current_label_for = attrs.get("for")
        elif tag in ("input", "textarea", "select"):
            field_id = attrs.get("id") or attrs.get("name", "")
            field_type = attrs.get("type", tag)
            required = "required" in attrs
            self.fields.append({
                "id": field_id,
                "type": field_type,
                "label": self.labels.get(field_id),
                "required": required
            })

    def handle_endtag(self, tag):
        if tag == "label":
            self.in_label = False
            if self.current_label_for:
                self.labels[self.current_label_for] = self.label_text.strip()

    def handle_data(self, data):
        if self.in_label:
            self.label_text += data


def read_form(filepath):
    with open(filepath, "r") as f:
        html = f.read()
    parser = FormFieldExtractor()
    parser.feed(html)
    return [f for f in parser.fields if f["type"] != "submit"]


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "tests/sample_form.html"
    fields = read_form(path)
    print(json.dumps(fields, indent=2))
