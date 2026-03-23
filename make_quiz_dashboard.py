from pathlib import Path
import base64
import html
import json
import re

_HERE = Path(__file__).parent
COURSE_ROOT = _HERE / "rics_FULL"
VIDEOS_ROOT = _HERE / "rics_videos"
OUT = _HERE / "LOCAL_STUDY_PORTAL.html"
STRUCTURE_JSON = _HERE / "lesson_structure.json"

PART_RE = re.compile(r"^(PART\s+(?:ONE|TWO|THREE|FOUR|FIVE|SIX|SEVEN|EIGHT|NINE|TEN|\d+)|MODULE SUMMARY)\b", re.IGNORECASE)
LESSON_COUNT_RE = re.compile(r"^Lesson\s+\d+\s+of\s+\d+$", re.IGNORECASE)
TITLE_RE = re.compile(r"<title>(.*?)</title>", re.IGNORECASE | re.DOTALL)
MANIFEST_TITLE_RE = re.compile(r"<organization[^>]*>.*?<title>(.*?)</title>", re.IGNORECASE | re.DOTALL)


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""


def read_story_title(story_path: Path) -> str:
    txt = read_text(story_path)
    match = TITLE_RE.search(txt)
    if not match:
        return story_path.parent.name
    title = re.sub(r"\s+", " ", match.group(1)).strip()
    return title or story_path.parent.name


def read_module_title(ctx: Path) -> str:
    manifest = read_text(ctx / "imsmanifest.xml")
    match = MANIFEST_TITLE_RE.search(manifest)
    if not match:
        return f"Module {ctx.name}"
    return re.sub(r"\s+", " ", match.group(1)).strip()


def classify_item(title: str) -> tuple[str, str]:
    lower = title.lower()
    if "knowledge check" in lower:
        return "quiz", "CHECK"
    if "glossary" in lower:
        return "glossary", "TERM"
    if "key learning points" in lower:
        return "summary", "KEY"
    if "summary" in lower or "end of module" in lower or "module summary" in lower:
        return "summary", "SUM"
    if "scenario" in lower:
        return "scenario", "CASE"
    if "introduction to the module" in lower or "course overview" in lower:
        return "video", "VID"
    return "lesson", "READ"


def clean_nav_lines(nav_text: str) -> list[str]:
    lines = [line.strip() for line in nav_text.splitlines()]
    lines = [line for line in lines if line]

    if "0% COMPLETE" in lines:
        lines = lines[lines.index("0% COMPLETE") + 1 :]
    if "Home" in lines:
        lines = lines[: lines.index("Home")]

    cleaned = []
    skip_exact = {
        "EXIT COURSE",
        "SKIP TO LESSON",
        "Top of page",
        "0% COMPLETE",
        "Home",
        "Lesson content",
        "+",
    }

    for line in lines:
        if line in skip_exact:
            continue
        if LESSON_COUNT_RE.match(line):
            continue
        if line.endswith("Completed"):
            continue
        if line == "Unstarted":
            continue
        cleaned.append(line)

    return cleaned


def parse_nav_structure(nav_text: str) -> list[dict]:
    lines = clean_nav_lines(nav_text)
    groups = []
    current_group = {"heading": None, "items": []}

    for line in lines:
        if PART_RE.match(line):
            if current_group["heading"] or current_group["items"]:
                groups.append(current_group)
            current_group = {"heading": line, "items": []}
            continue

        item_type, badge = classify_item(line)
        current_group["items"].append({
            "title": line,
            "item_type": item_type,
            "badge": badge,
        })

    if current_group["heading"] or current_group["items"]:
        groups.append(current_group)

    return [group for group in groups if group["heading"] or group["items"]]


def load_course_lessons(ctx: Path) -> list[dict]:
    """Load raw lesson list from whichever course data format the module uses.

    Supports three export formats:
    - locales/und.js  (modules 403280, 403301, 403312)
    - window.courseData in index.html  (module 403331)
    - embedded deserialize("<base64>") inside __fetchCourse (403255, 403267)
    """
    raw_lessons: list[dict] = []

    und = ctx / "scormcontent" / "locales" / "und.js"
    if und.exists():
        txt = read_text(und)
        m = re.search(r'__resolveJsonp\("course:und",\s*"([^"]+)"', txt)
        if m:
            try:
                data = json.loads(base64.b64decode(m.group(1)).decode("utf-8"))
                raw_lessons = data["course"]["lessons"]
            except Exception:
                pass

    if not raw_lessons:
        idx = ctx / "scormcontent" / "index.html"
        txt = read_text(idx)
        m = re.search(r'window\.courseData\s*=\s*"([^"]+)"', txt)
        if m:
            try:
                data = json.loads(base64.b64decode(m.group(1)).decode("utf-8"))
                raw_lessons = data.get("course", data).get("lessons", [])
            except Exception:
                pass

    if not raw_lessons:
        idx = ctx / "scormcontent" / "index.html"
        txt = read_text(idx)
        marker = 'return Promise.resolve(deserialize("'
        i = txt.find(marker)
        if i != -1:
            i += len(marker)
            j = txt.find('")', i)
            if j != -1:
                try:
                    data = json.loads(base64.b64decode(txt[i:j]).decode("utf-8"))
                    raw_lessons = data.get("course", data).get("lessons", [])
                except Exception:
                    pass

    return raw_lessons


def load_lesson_id_pairs(ctx: Path) -> list[tuple[str, str]]:
    """Return ordered (title, id) pairs for all non-part-header lessons in a Rise module."""
    raw_lessons = load_course_lessons(ctx)

    return [
        (l["title"].strip(), l["id"])
        for l in raw_lessons
        if not PART_RE.match(l["title"].strip())
    ]


def groups_from_lessons(ctx_name: str, lessons: list[dict]) -> list[dict]:
    """Build sidebar groups directly from ordered lesson list in course metadata."""
    groups = []
    current_group = {"heading": None, "items": []}

    for lesson in lessons:
        title = lesson.get("title", "").strip()
        lesson_id = lesson.get("id")
        if not title:
            continue

        is_heading = PART_RE.match(title) or title.lower() == "module summary"
        if is_heading:
            if current_group["heading"] or current_group["items"]:
                groups.append(current_group)
            current_group = {"heading": title, "items": []}
            continue

        item_type, badge = classify_item(title)
        item = {
            "title": title,
            "item_type": item_type,
            "badge": badge,
        }
        if lesson_id:
            item["path"] = _lesson_path(ctx_name, lesson_id)
        current_group["items"].append(item)

    if current_group["heading"] or current_group["items"]:
        groups.append(current_group)

    return [group for group in groups if group["heading"] or group["items"]]


# Modules whose index.html has a shouldLoad() guard that requires an iframe
# with IsLmsPresent on the parent — route through rics_FULL/launch.html.
_NEEDS_LAUNCHER: set[str] = {"403255", "403267"}


def _lesson_path(ctx_name: str, lesson_id: str) -> str:
    if ctx_name in _NEEDS_LAUNCHER:
        return f"rics_FULL/launch.html?m={ctx_name}&l={lesson_id}"
    return f"rics_FULL/{ctx_name}/scormcontent/index.html#/lessons/{lesson_id}"


def _norm(s: str) -> str:
    """Normalize whitespace and case for title comparison."""
    return re.sub(r"\s+", " ", s).strip().lower()


def assign_lesson_paths(ctx_name: str, groups: list[dict], lesson_pairs: list[tuple[str, str]]) -> None:
    """Set item['path'] on each nav item by matching titles sequentially to lesson IDs.

    Sequential matching handles duplicate titles (e.g. multiple 'Summary' or
    'Knowledge check' entries across different parts).
    Whitespace normalisation handles double-space inconsistencies in authored content.
    """
    pair_idx = 0
    for group in groups:
        for item in group["items"]:
            title = _norm(item["title"])
            for i in range(pair_idx, len(lesson_pairs)):
                if _norm(lesson_pairs[i][0]) == title:
                    lesson_id = lesson_pairs[i][1]
                    item["path"] = _lesson_path(ctx_name, lesson_id)
                    pair_idx = i + 1
                    break


def fallback_story_pages(ctx: Path) -> list[dict]:
    pages = []
    seen = set()
    candidates = list(ctx.rglob("story.html")) + list(ctx.rglob("*_story.html"))
    for story in sorted(candidates):
        rel_path = story.relative_to(COURSE_ROOT).as_posix()
        if rel_path in seen:
            continue
        seen.add(rel_path)
        title = read_story_title(story)
        item_type, badge = classify_item(title)
        pages.append({
            "title": title,
            "path": f"rics_FULL/{rel_path}",
            "item_type": item_type,
            "badge": badge,
        })
    return pages


def render_item(item: dict) -> str:
    badge_class = item["item_type"]
    title = html.escape(item["title"])
    badge = html.escape(item["badge"])
    if item.get("path"):
        key = html.escape(item["path"])
        return (
            f'<a class="lesson-row lesson-row--link" href="/{html.escape(item["path"])}" target="_blank" data-progress-key="{key}">'
            f'<span class="badge badge--{badge_class}">{badge}</span>'
            f'<span class="lesson-title">{title}</span>'
            '</a>'
        )
    return (
        f'<div class="lesson-row">'
        f'<span class="badge badge--{badge_class}">{badge}</span>'
        f'<span class="lesson-title">{title}</span>'
        '</div>'
    )


def render_groups(groups: list[dict]) -> str:
    sections = []
    for group in groups:
        heading = ""
        if group["heading"]:
            heading = f'<div class="part-heading">{html.escape(group["heading"])}</div>'
        items = "".join(render_item(item) for item in group["items"])
        sections.append(f'<div class="part-block">{heading}<div class="lesson-list">{items}</div></div>')
    return "".join(sections)


def video_base_name(name: str) -> str:
    if name.endswith(".merged.mp4"):
        return name[: -len(".merged.mp4")]
    if name.endswith(".fhls-fastly_skyfire-643.mp4"):
        return name[: -len(".fhls-fastly_skyfire-643.mp4")]
    if name.endswith(".fhls-fastly_skyfire-audio-high-English.mp4"):
        return name[: -len(".fhls-fastly_skyfire-audio-high-English.mp4")]
    return Path(name).stem


structure_data = {}
if STRUCTURE_JSON.exists():
    structure_data = json.loads(read_text(STRUCTURE_JSON) or "{}")

contexts = sorted((p for p in COURSE_ROOT.iterdir() if p.is_dir() and p.name.isdigit()), key=lambda p: p.name)
module_rows = []
total_items = 0
total_checks = 0
structured_modules = 0

for ctx in contexts:
    launch = ctx / "scormdriver" / "indexAPI.html"
    fallback = ctx / "scormcontent" / "index.html"
    launch_path = launch if launch.exists() else fallback
    module_data = structure_data.get(ctx.name, {})
    nav_text = module_data.get("navText", "")
    groups = parse_nav_structure(nav_text) if nav_text else []
    course_lessons = load_course_lessons(ctx)
    if groups:
        lesson_pairs = [(l["title"].strip(), l["id"]) for l in course_lessons if l.get("id")]
        assign_lesson_paths(ctx.name, groups, lesson_pairs)
    elif course_lessons:
        groups = groups_from_lessons(ctx.name, course_lessons)
    title = read_module_title(ctx)

    launch_rel = None
    if launch_path.exists():
        launch_rel = f"rics_FULL/{launch_path.relative_to(COURSE_ROOT).as_posix()}"

    item_count = sum(len(group["items"]) for group in groups)
    check_count = sum(1 for group in groups for item in group["items"] if item["item_type"] == "quiz")

    fallback_pages = []
    structure_note = ""
    structure_status = "exact" if groups else "module-only"
    if groups:
        structured_modules += 1
        total_items += item_count
        total_checks += check_count
    else:
        fallback_pages = fallback_story_pages(ctx)
        structure_note = ""

    module_rows.append({
        "context": ctx.name,
        "title": title,
        "launch_path": launch_rel,
        "groups": groups,
        "item_count": item_count,
        "check_count": check_count,
        "fallback_pages": fallback_pages,
        "structure_note": structure_note,
        "structure_status": structure_status,
    })

video_groups = {}
if VIDEOS_ROOT.exists():
    for file_path in sorted(VIDEOS_ROOT.glob("*.mp4"), key=lambda p: p.stat().st_size, reverse=True):
        name = file_path.name
        base = video_base_name(name)
        group = video_groups.setdefault(base, {
            "title": base,
            "merged": None,
            "video": None,
            "audio": None,
            "variants": [],
        })

        variant = {
            "name": name,
            "size": f"{(file_path.stat().st_size / (1024 ** 3)):.2f} GB",
            "path": f"rics_videos/{name}",
        }
        group["variants"].append(variant)

        if name.endswith(".merged.mp4"):
            group["merged"] = variant
        elif name.endswith(".fhls-fastly_skyfire-audio-high-English.mp4"):
            group["audio"] = variant
        elif name.endswith(".fhls-fastly_skyfire-643.mp4"):
            group["video"] = variant

video_items = sorted(video_groups.values(), key=lambda v: v["title"].lower())


def variant_label(name: str) -> str:
    if name.endswith(".merged.mp4"):
        return "Merged video (audio + video)"
    if name.endswith(".fhls-fastly_skyfire-643.mp4"):
        return "Video track only (no sound)"
    if name.endswith(".fhls-fastly_skyfire-audio-high-English.mp4"):
        return "Audio track only"
    return name

module_sections = []
for row in module_rows:
    status_label = "Exact sidebar" if row["structure_status"] == "exact" else "Open in player"
    stats = f'Items: {row["item_count"]} | Checks: {row["check_count"]}' if row["groups"] else f'Packaged Storyline pages: {len(row["fallback_pages"])}'
    body = render_groups(row["groups"]) if row["groups"] else ""
    body_html = f'<div class="sidebar-shell">{body}</div>' if row["groups"] else ""

    fallback_html = ""
    if row["fallback_pages"]:
        fallback_preview = "".join(render_item(item) for item in row["fallback_pages"][:8])
        more_count = len(row["fallback_pages"]) - min(len(row["fallback_pages"]), 8)
        more = f'<div class="muted">Plus {more_count} more packaged pages.</div>' if more_count > 0 else ""
        fallback_html = (
            '<div class="fallback-box">'
            '<div class="fallback-head">Packaged Storyline pages</div>'
            f'<div class="lesson-list">{fallback_preview}</div>'
            f'{more}'
            '</div>'
        )

    module_sections.append(
        f"""
        <section class="module-card">
          <div class="module-head">
            <div>
              <div class="module-id">Module {row['context']}</div>
              <h3>{html.escape(row['title'])}</h3>
              <div class="meta">{stats}</div>
              <span class="status-pill status-pill--{row['structure_status']}">{status_label}</span>
            </div>
          </div>
                    {body_html}
          {fallback_html}
        </section>
        """
    )

video_cards = "\n".join(
        f"""
        <div class="video-card" data-sync="{'1' if item['audio'] and item['video'] and not item['merged'] else '0'}">
            <div class="title">{html.escape(item['title'])}</div>
            <video class="video-player" controls preload="metadata" playsinline src="/{html.escape((item['merged'] or item['video'])['path'])}"></video>
            {
                f'<audio class="video-audio" preload="metadata" src="/{html.escape(item["audio"]["path"])}"></audio>'
                f'<button class="btn btn--video btn--audio js-sync-btn" type="button">Enable Sound</button>'
                f'<div class="muted">This file uses a separate audio track. Click Enable Sound once, then play.</div>'
                if item['audio'] and item['video'] and not item['merged'] else ''
            }
            <div class="meta">Available files (simple labels):</div>
            <div class="variant-links">{"".join(f'<a class="btn btn--variant" href="/{html.escape(v["path"])}" target="_blank">{html.escape(variant_label(v["name"]))} ({v["size"]})</a>' for v in item['variants'])}</div>
        </div>
        """
        for item in video_items
) or '<div class="video-card"><div class="title">No local videos found yet.</div></div>'

html_doc = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>RICS Self-Study Portal</title>
  <style>
    :root {{
            --bg: #f2efe9;
            --ink: #192a32;
            --muted: #5f6d72;
      --panel: #ffffff;
            --line: #d8ddd8;
            --nav: #f8f9f6;
            --part: #e7ece8;
            --accent: #0f6a66;
            --accent-2: #dd8a2f;
      --shadow: 0 14px 36px rgba(18, 32, 51, 0.08);
      --lesson: #dce8f7;
      --video: #d8ede8;
      --summary: #ece4d7;
      --quiz: #f3dcc5;
      --glossary: #e4ddf7;
      --scenario: #f6e4ea;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
            font-family: "Trebuchet MS", "Segoe UI", Tahoma, Arial, sans-serif;
      color: var(--ink);
      background:
                radial-gradient(1000px 420px at 100% -10%, #f4ddc2 0, transparent 60%),
                radial-gradient(920px 380px at -10% 0%, #d7efe8 0, transparent 55%),
        var(--bg);
    }}
    .wrap {{ max-width: 1400px; margin: 0 auto; padding: 24px 16px 44px; }}
    .hero {{
            background: linear-gradient(125deg, #0f6a66 0%, #21847a 52%, #dd8a2f 100%);
      color: #fff;
      border-radius: 18px;
      padding: 22px 20px;
            box-shadow: 0 16px 34px rgba(15, 106, 102, 0.22);
    }}
    h1 {{ margin: 0 0 8px; font-size: clamp(28px, 4vw, 42px); }}
    .sub {{ margin: 0; max-width: 880px; color: rgba(255, 255, 255, 0.92); }}
    .stats {{ margin-top: 10px; font-weight: 700; }}
    .tip {{
      margin-top: 12px;
      background: rgba(255, 255, 255, 0.12);
      border: 1px solid rgba(255, 255, 255, 0.18);
      border-radius: 12px;
      padding: 10px 12px;
      font-size: 14px;
    }}
    .progress-bar {{
      margin-top: 12px;
      display: grid;
      gap: 6px;
      max-width: 520px;
    }}
    .progress-track {{
      height: 10px;
      border-radius: 999px;
      background: rgba(255, 255, 255, 0.25);
      overflow: hidden;
    }}
    .progress-fill {{
      height: 100%;
      width: 0%;
      background: linear-gradient(90deg, #fff8df, #ffe2b7);
      transition: width 0.25s ease;
    }}
    .progress-text {{ font-size: 13px; color: rgba(255, 255, 255, 0.95); }}
        .hero-links {{
            margin-top: 12px;
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
        }}
        .hero-link {{
            display: inline-block;
            text-decoration: none;
            color: #fff;
            font-weight: 800;
            font-size: 13px;
            border: 1px solid rgba(255, 255, 255, 0.45);
            border-radius: 999px;
            padding: 7px 12px;
            background: rgba(255, 255, 255, 0.12);
        }}
        .hero-link:hover {{ background: rgba(255, 255, 255, 0.22); }}
    .module-grid {{
      margin-top: 18px;
      display: grid;
      gap: 14px;
      grid-template-columns: repeat(auto-fit, minmax(420px, 1fr));
    }}
    .module-card {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 18px;
      padding: 14px;
      box-shadow: var(--shadow);
    }}
        .module-head {{ margin-bottom: 12px; }}
    .module-id {{
      color: var(--accent);
      font-size: 12px;
      font-weight: 800;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      margin-bottom: 4px;
    }}
    .module-head h3 {{ margin: 0 0 5px; font-size: 21px; line-height: 1.2; }}
    .meta {{ color: var(--muted); font-size: 13px; }}
    .status-pill {{
            display: inline-block;
            margin-top: 8px;
      border-radius: 999px;
      padding: 5px 10px;
      font-size: 12px;
      font-weight: 800;
      letter-spacing: 0.04em;
      text-transform: uppercase;
      border: 1px solid transparent;
    }}
    .status-pill--exact {{ background: #dff1eb; color: #155d4f; border-color: #bfe2d7; }}
    .status-pill--module-only {{ background: #f3e7da; color: #7a4d17; border-color: #e9cfaf; }}
    .btn {{
      display: inline-block;
      text-decoration: none;
            background: linear-gradient(135deg, #0f6a66 0%, #2e7e7c 52%, #dd8a2f 100%);
      color: #fff;
      padding: 9px 14px;
      border-radius: 11px;
      font-weight: 800;
      font-size: 14px;
      white-space: nowrap;
    }}
    .btn--video {{ background: linear-gradient(135deg, #264b77, #0b5d7a); }}
    .sidebar-shell {{
      background: var(--nav);
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 12px;
    }}
    .part-block + .part-block {{ margin-top: 12px; }}
    .part-heading {{
      background: var(--part);
      border-radius: 10px;
      padding: 8px 10px;
      font-size: 12px;
      font-weight: 800;
      letter-spacing: 0.05em;
      text-transform: uppercase;
      color: #394657;
      margin-bottom: 8px;
    }}
    .lesson-list {{ display: grid; gap: 7px; }}
    .lesson-row {{
      display: flex;
      align-items: center;
      gap: 10px;
      min-width: 0;
      background: #fff;
      border: 1px solid var(--line);
      border-radius: 12px;
      padding: 8px 10px;
            transition: transform 0.15s ease, box-shadow 0.15s ease;
    }}
    .lesson-row--link {{ text-decoration: none; color: inherit; }}
        .lesson-row--link:hover {{ transform: translateY(-1px); box-shadow: 0 6px 16px rgba(17, 31, 38, 0.1); }}
    .lesson-row--done {{
      border-color: #9fcebf;
      background: linear-gradient(180deg, #f6fcf9 0%, #eef9f4 100%);
    }}
    .lesson-row--done .lesson-title {{
      color: #145041;
      font-weight: 700;
    }}
    .lesson-title {{ line-height: 1.35; }}
    .badge {{
      flex: 0 0 auto;
      min-width: 44px;
      text-align: center;
      border-radius: 999px;
      padding: 4px 8px;
      font-size: 11px;
      font-weight: 800;
      letter-spacing: 0.05em;
      text-transform: uppercase;
    }}
    .badge--lesson {{ background: var(--lesson); color: #1f4b7b; }}
    .badge--video {{ background: var(--video); color: #1f5c52; }}
    .badge--summary {{ background: var(--summary); color: #6e4f22; }}
    .badge--quiz {{ background: var(--quiz); color: #7d4212; }}
    .badge--glossary {{ background: var(--glossary); color: #53388e; }}
    .badge--scenario {{ background: var(--scenario); color: #8a3757; }}
    .module-note {{ color: var(--muted); line-height: 1.5; }}
    .fallback-box {{ margin-top: 12px; border-top: 1px dashed var(--line); padding-top: 12px; }}
    .fallback-head {{ font-weight: 800; margin-bottom: 8px; }}
    .videos {{ margin-top: 24px; }}
    .videos h2 {{ margin: 0 0 10px; }}
    .video-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 10px; }}
    .video-card {{ background: #fff; border: 1px solid var(--line); border-radius: 14px; padding: 12px; box-shadow: var(--shadow); }}
    .video-player {{ width: 100%; border-radius: 10px; background: #000; margin: 8px 0; max-height: 62vh; }}
    .video-audio {{ display: none; }}
    .btn--audio {{ margin-bottom: 8px; }}
    .variant-links {{ display: grid; gap: 6px; margin-top: 8px; }}
    .btn--variant {{ background: #f3f6fb; color: #18334d; border: 1px solid var(--line); }}
    .title {{ font-weight: 800; margin-bottom: 6px; word-break: break-word; }}
    .muted {{ color: var(--muted); font-size: 13px; }}
    @media (max-width: 740px) {{
      .module-grid {{ grid-template-columns: 1fr; }}
      .module-head {{ flex-direction: column; }}
      .module-actions {{ align-items: flex-start; }}
    }}
  </style>
</head>
<body>
  <div class="wrap">
    <section class="hero">
      <h1>RICS Self-Study Portal</h1>
      <div class="stats">Modules: {len(module_rows)} | Exact sidebars: {structured_modules} | Structured items: {total_items} | Knowledge checks: {total_checks} | Videos: {len(video_items)}</div>
      <div class="progress-bar" aria-live="polite">
        <div class="progress-track"><div class="progress-fill" id="progressFill"></div></div>
        <div class="progress-text" id="progressText">Progress: 0 / 0</div>
      </div>
      <div class="hero-links">
        <a class="hero-link" href="/rics_FULL/QUIZ_DASHBOARD.html" target="_blank">Open Quiz Dashboard</a>
        <a class="hero-link" href="#" id="resetProgressLink">Reset Progress</a>
      </div>
    </section>

    <div class="module-grid">
      {''.join(module_sections)}
    </div>

    <section class="videos">
            <h2>Videos</h2>
      <div class="video-grid">{video_cards}</div>
    </section>
  </div>
</body>
<script>
    (() => {{
        const PROGRESS_KEY = 'rics_portal_progress_v1';
        const lessonLinks = Array.from(document.querySelectorAll('.lesson-row--link[data-progress-key]'));
        const progressFill = document.getElementById('progressFill');
        const progressText = document.getElementById('progressText');
        const resetProgressLink = document.getElementById('resetProgressLink');

        const readProgress = () => {{
            try {{
                return JSON.parse(localStorage.getItem(PROGRESS_KEY) || '{{}}');
            }} catch (_e) {{
                return {{}};
            }}
        }};

        const writeProgress = (progress) => {{
            localStorage.setItem(PROGRESS_KEY, JSON.stringify(progress));
        }};

        const renderProgress = () => {{
            const progress = readProgress();
            let done = 0;
            lessonLinks.forEach((link) => {{
                const key = link.getAttribute('data-progress-key');
                const isDone = !!progress[key];
                link.classList.toggle('lesson-row--done', isDone);
                if (isDone) done += 1;
            }});

            const total = lessonLinks.length;
            const pct = total ? Math.round((done / total) * 100) : 0;
            if (progressFill) progressFill.style.width = `${{pct}}%`;
            if (progressText) progressText.textContent = `Progress: ${{done}} / ${{total}} (${{pct}}%)`;
        }};

        lessonLinks.forEach((link) => {{
            link.addEventListener('click', () => {{
                const key = link.getAttribute('data-progress-key');
                if (!key) return;
                const progress = readProgress();
                progress[key] = Date.now();
                writeProgress(progress);
                renderProgress();
            }});
        }});

        if (resetProgressLink) {{
            resetProgressLink.addEventListener('click', (event) => {{
                event.preventDefault();
                localStorage.removeItem(PROGRESS_KEY);
                renderProgress();
            }});
        }}

        renderProgress();

        const cards = document.querySelectorAll('.video-card[data-sync="1"]');
        cards.forEach((card) => {{
            const video = card.querySelector('.video-player');
            const audio = card.querySelector('.video-audio');
            const button = card.querySelector('.js-sync-btn');
            if (!video || !audio) return;

            const syncAudioTime = () => {{
                if (Math.abs(video.currentTime - audio.currentTime) > 0.35) {{
                    audio.currentTime = video.currentTime;
                }}
            }};

            video.addEventListener('play', () => {{
                audio.playbackRate = video.playbackRate;
                audio.muted = video.muted;
                audio.volume = video.volume;
                audio.currentTime = video.currentTime;
                audio.play().catch(() => {{}});
            }});

            video.addEventListener('pause', () => audio.pause());
            video.addEventListener('seeking', syncAudioTime);
            video.addEventListener('timeupdate', syncAudioTime);
            video.addEventListener('ratechange', () => {{
                audio.playbackRate = video.playbackRate;
            }});
            video.addEventListener('volumechange', () => {{
                audio.muted = video.muted;
                audio.volume = video.volume;
            }});
            video.addEventListener('ended', () => {{
                audio.pause();
                audio.currentTime = 0;
            }});

            if (button) {{
                button.addEventListener('click', async () => {{
                    audio.currentTime = video.currentTime;
                    audio.playbackRate = video.playbackRate;
                    audio.muted = video.muted;
                    audio.volume = video.volume;
                    if (video.paused) {{
                        await video.play().catch(() => {{}});
                    }}
                    await audio.play().catch(() => {{}});
                    button.textContent = 'Sound Enabled';
                }});
            }}
        }});
    }})();
</script>
</html>
"""

OUT.write_text(html_doc, encoding="utf-8")
print(f"Portal created: {OUT}")
print(f"Modules: {len(module_rows)} | Exact sidebars: {structured_modules} | Structured items: {total_items} | Knowledge checks: {total_checks} | Videos: {len(video_items)}")
