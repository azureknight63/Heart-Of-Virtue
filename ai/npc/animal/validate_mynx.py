import json
import os
import sys

HERE = os.path.dirname(__file__)
JSON_PATH = os.path.join(HERE, "mynx.json")

required_keys = [
    "creature_name",
    "file_version",
    "species",
    "brief_lore",
    "physical_description",
    "behavior_profile",
    "communication_constraints",
    "response_format_guidelines",
    "guardrails_and_safety",
    "system_prompt_snippet",
]


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def main():
    try:
        data = load_json(JSON_PATH)
    except Exception as e:
        print(f"ERROR: failed to load {JSON_PATH}: {e}")
        sys.exit(2)

    errors = []

    for k in required_keys:
        if k not in data:
            errors.append(f"missing required key: {k}")

    # Check creature_name matches filename
    name = data.get("creature_name", "")
    fname = os.path.splitext(os.path.basename(JSON_PATH))[0]
    if name.lower() != fname.lower():
        errors.append(f"creature_name ('{name}') does not match filename ('{fname}')")

    # Simple guardrail checks
    comm = data.get("communication_constraints", {})
    verbal = comm.get("verbal", "").lower()
    if "cannot speak" not in verbal and "cannot speak human" not in verbal:
        errors.append("communication_constraints.verbal should indicate the creature cannot speak human words")

    if errors:
        print("VALIDATION: FAIL")
        for e in errors:
            print(" -", e)
        sys.exit(1)

    print("VALIDATION: PASS - mynx.json looks correct")


if __name__ == '__main__':
    main()

