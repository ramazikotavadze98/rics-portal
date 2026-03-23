"""Extract and parse the embedded course data from Rise 360 index.html."""
import re, json
from pathlib import Path

COURSE_ROOT = Path(r"C:\Users\user\rics_FULL")

def extract_course_script(ctx_path):
    idx_html = (ctx_path / "scormcontent" / "index.html").read_text(encoding='utf-8', errors='ignore')
    scripts = re.findall(r'<script(?:[^>]*)>(.*?)</script>', idx_html, re.DOTALL)
    big_scripts = [s for s in scripts if len(s) > 5000]
    return big_scripts[0] if big_scripts else None

for ctx_name in ['403251']:
    ctx = COURSE_ROOT / ctx_name
    data = extract_course_script(ctx)
    if data:
        print(f"Script length: {len(data)}")
        print(data[:4000])
    else:
        print("No big script found")
