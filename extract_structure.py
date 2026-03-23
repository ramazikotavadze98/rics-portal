"""Extract lesson structure from Storyline data.js files in each module."""
import re
import json
from pathlib import Path

COURSE_ROOT = Path(r"C:\Users\user\rics_FULL")

def parse_data_js(data_js_path):
    """Extract JSON from globalProvideData('data', '...') call."""
    txt = data_js_path.read_text(encoding='utf-8', errors='ignore')
    # Format: window.globalProvideData('data', '{...json...}');
    # with escaped single quotes - find JSON between first { and last }
    start = txt.find('{')
    end = txt.rfind('}')
    if start == -1 or end == -1:
        return None
    raw = txt[start:end+1]
    try:
        return json.loads(raw)
    except Exception as e:
        print(f"    JSON error: {e} | raw start: {repr(raw[:100])}")
        return None

for ctx_name in ['403251', '403255', '403267', '403280', '403301', '403312', '403331']:
    ctx = COURSE_ROOT / ctx_name
    assets = ctx / "scormcontent" / "assets"
    print(f"\n=== MODULE {ctx_name} ===")

    if not assets.exists():
        print("  No assets dir")
        continue

    asset_folders = sorted([f for f in assets.iterdir() if f.is_dir()])
    if not asset_folders:
        print("  No asset folders")
        continue

    for af in asset_folders:
        data_js = af / "html5" / "data" / "js" / "data.js"
        if not data_js.exists():
            continue
        data = parse_data_js(data_js)
        if not data:
            print(f"  [{af.name}] Could not parse data.js")
            continue

        print(f"  [{af.name}] Keys: {list(data.keys())[:15]}")
        # Look for navigation/slide structure
        if "navtree" in data:
            print(f"    navtree: {json.dumps(data['navtree'])[:500]}")
        if "interactions" in data:
            print(f"    interactions count: {len(data['interactions'])}")
        # Check for slide titles
        for key in ["slides", "story", "nav", "toc", "chapters"]:
            if key in data:
                print(f"    {key}: {str(data[key])[:300]}")
        break  # just first asset folder per module for now
