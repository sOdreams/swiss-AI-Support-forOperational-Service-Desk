"""Fetch the pinned public training snapshot; do not commit downloaded data."""
import argparse
import hashlib
from pathlib import Path
import urllib.request

URL = "https://raw.githubusercontent.com/Swiss-ai-Weeks/SwissLife-2026/00fea7dbe887454436297d5aa19865dea5553434/jira_first_20000_requested_fields_synthetic.json"
SHA256 = "6f3ad42cbe5095d6541c47095258c233554c1da46fbc47c529735667876f8844"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    with urllib.request.urlopen(URL, timeout=120) as response:
        data = response.read()
    if hashlib.sha256(data).hexdigest() != SHA256:
        raise ValueError("Training snapshot checksum mismatch")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(data)
    print(f"Verified training snapshot saved to {args.output}")


if __name__ == "__main__":
    main()
