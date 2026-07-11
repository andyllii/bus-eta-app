"""Fetch the live TD Special Traffic News XML and dump element names + a sample.

Run from transportation-api/:  .venv/bin/python scripts/fetch_td_sample.py
"""
import sys
import os
import io
import httpx
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import settings

URL = settings.td_base_url.format(lang="en")


def main():
    r = httpx.get(URL, timeout=settings.request_timeout)
    r.raise_for_status()
    content = r.content

    print("=== RAW (first 4000 bytes) ===")
    print(content[:4000].decode("utf-8", "replace"))

    root = ET.fromstring(content)
    print("=== ROOT:", root.tag, "===")
    print("message count:", len(root.findall("message")))

    first = root.find("message")
    if first is not None:
        print("=== First <message> child element tags ===")
        for child in first:
            print("  %r: %r" % (child.tag, child.text))

    sample = root.findall("message")[:2]
    if sample:
        new_root = ET.Element(root.tag)
        for m in sample:
            new_root.append(m)
        ET.indent(new_root)
        out = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "td_trafficnews_sample.xml",
        )
        data = ET.tostring(new_root, encoding="utf-8", xml_declaration=True)
        with open(out, "wb") as f:
            f.write(data)
        print("Saved sample to %s" % out)


if __name__ == "__main__":
    main()
