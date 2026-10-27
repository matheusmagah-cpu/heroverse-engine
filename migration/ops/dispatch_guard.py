#!/usr/bin/env python3
"""One dispatch guard for every expensive workflow (E116; generalises E106's preflight and E112's order).

Each workflow in WORKFLOWS runs this as its first step after the checkout, before any step or job that holds a
secret, with its inputs (`GUARD_INPUTS: ${{ toJSON(inputs) }}`) and the run's own read-only token:

  dispatch_guard.py run WORKFLOW.yml      every check below; exit 1 with the named refusal, else GUARD_OK
  dispatch_guard.py local WORKFLOW.yml    the checks that need no API (inputs, order, imports), e.g. before a dispatch

Checks, each a named refusal (classified in ops/refusal_registry.json):
  1. inputs: the workflow's own input rules, and the files they name exist   GUARD_INPUT_INVALID, GUARD_INPUT_MISSING
     (episode.yml also E112's order: a later part waits for the earlier one)   EARLIER_PART_NOT_RECORDED
  2. capacity: the newest asset release (ci/assets.sh) has room for the run's uploads (1000 a release, E85), the
     Cloudflare allocation is not used up today when the run makes images (CF_DAILY_IMAGES, E62), a publish record
     fits YouTube's title and description limits (E52)        GUARD_ASSETS_FULL, GUARD_CF_ALLOCATION_USED,
                                                              GUARD_RECORD_OVER_LIMIT
  3. one run in flight per subject (the same episode, pilot, characters or footage library), across every guarded
     workflow (E112, E63, E10)                                GUARD_SUBJECT_IN_FLIGHT
  4. the same inputs failed last time: refused unless main has a new commit touching a file that run depends on
     (the workflow, the scripts it calls and their local imports, the subject's files) since the failed run's
     head_sha, or the failed run is recorded as external in evidence/dispatch/retries.json (a re-run attempt of a
     failed run is the same commit, so only that record lets it through)   GUARD_RERUN_WITHOUT_FIX
  5. every Python script the workflow calls imports in the job's environment: each module-level import (followed
     through the repo's own modules) is stdlib, a repo module or a package the workflow (or the shell script it runs)
     installs, and the script's top level imports under
     `python3 -I` with those packages stubbed (E73, E81, E89)  GUARD_IMPORT_UNRESOLVED
An API that cannot be read refuses (GUARD_API_UNAVAILABLE): the guard never passes what it could not check.
The API is read-only (actions, releases, commits, compare) with the run's GITHUB_TOKEN; nothing is written.
"""
import ast
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
WF_DIR = ROOT / ".github" / "workflows"
RETRIES = ROOT / "migration" / "evidence" / "dispatch" / "retries.json"
GUARD_STEP = "Dispatch guard"
ASSET_LIMIT = 1000                     # GitHub: assets per release (E85)
TITLE_MAX, DESCRIPTION_MAX = 100, 5000  # YouTube: title characters, description bytes (E52)
FAILED = ("failure", "timed_out", "startup_failure")
SLUG = r"[a-z0-9]+(?:-[a-z0-9]+)*"
IDS = rf"^{SLUG}(?:,{SLUG})*$"
# distribution name -> import name, where they differ
IMPORT_NAME = {"pillow": "PIL", "opencv-python-headless": "cv2", "opencv-python": "cv2", "python3-pil": "PIL",
               "google-auth": "google", "faster-whisper": "faster_whisper", "ai-edge-litert": "ai_edge_litert"}


class Refusal(Exception):
    pass


def refuse(code, detail):
    raise Refusal(f"{code} {detail}")


def need(cond, name, value, rule):
    if not cond:
        refuse("GUARD_INPUT_INVALID", f"{name}={value!r}: {rule}")


def need_file(rel):
    if not (ROOT / rel).is_file():
        refuse("GUARD_INPUT_MISSING", f"{rel} is not on main")


def load(rel):
    try:
        return json.loads((ROOT / rel).read_text())
    except ValueError:
        refuse("GUARD_INPUT_INVALID", f"{rel} is not JSON")


def ids(text):
    return [x for x in (text or "").split(",") if x]


# ---- per workflow: inputs (1), subject (3), uploads to the asset release (2), files its run depends on (4) ----
def _plan(i):
    p = i.get("plan", "")
    m = re.fullmatch(rf"migration/production/bible/plans/({SLUG})\.json", p)
    need(m, "plan", p, "migration/production/bible/plans/<episode>.json")
    need_file(p)
    plan = load(p)
    need(plan.get("episode") == m.group(1), "plan", p, "its episode field names the file")
    return plan


def episode(i):
    plan = _plan(i)
    need(re.fullmatch(r"(\d{6,20})?", i.get("resume_run") or ""), "resume_run", i.get("resume_run"), "a run id or empty")
    sys.path.insert(0, str(ROOT / "migration" / "production" / "bible"))
    import episode_order  # E112: the one order rule, reused
    bad = episode_order.earlier_part_open(plan)
    if bad:
        raise Refusal(bad)
    ep = plan["episode"]
    return {"subject": ("episode", ep), "uploads": 1,
            "deps": [i["plan"], f"migration/production/bible/shots/{ep}.json", f"migration/evidence/preflight/{ep}",
                     "migration/production/characters/"]}


def shot_probe(i):
    plan = _plan(i)
    shots = ids(i.get("shots"))
    need(shots and re.fullmatch(IDS, i.get("shots", "")), "shots", i.get("shots"), "comma list of shot ids")
    known = {s.get("id") for s in plan.get("shots", [])}
    need(set(shots) <= known, "shots", i.get("shots"), f"ids of this plan ({len(known)} shots)")
    need(re.fullmatch(r"[1-6]", i.get("attempts") or ""), "attempts", i.get("attempts"), "1-6")
    need(re.fullmatch(r"(\d{6,20})?", i.get("adopt_run") or ""), "adopt_run", i.get("adopt_run"), "a run id or empty")
    ep = plan["episode"]
    return {"subject": ("episode", ep), "uploads": len(shots) * int(i["attempts"]),
            "deps": [i["plan"], "migration/production/characters/", "migration/evidence/pavo/setups.json"]}


def cf_images(i):
    pilot = i.get("pilot", "")
    need(re.fullmatch(r"pilot-\d{3}|characters", pilot), "pilot", pilot, "pilot-NNN or characters (E96)")
    need(i.get("engine") in ("flux", "sdxl"), "engine", i.get("engine"), "flux or sdxl")
    need(re.fullmatch(rf"({SLUG}(,{SLUG})*)?", i.get("only") or ""), "only", i.get("only"), "comma list of image ids")
    rel = f"migration/production/{pilot}/images.json"
    need_file(rel)
    n = len(ids(i.get("only"))) or len(load(rel).get("images", []))
    subject = ("characters", "characters") if pilot == "characters" else ("pilot", pilot)
    return {"subject": subject, "uploads": 2 * n, "images": n, "deps": [f"migration/production/{pilot}/"]}


def _pilot(i):
    pilot = i.get("pilot", "")
    need(re.fullmatch(r"pilot-\d{3}", pilot), "pilot", pilot, "pilot-NNN")
    need_file(f"migration/production/{pilot}/script.json")
    return pilot


def pilot_render(i):
    pilot = _pilot(i)
    return {"subject": ("pilot", pilot), "uploads": 12, "deps": [f"migration/production/{pilot}/", "migration/ci/"]}


def pilot_preview(i):
    pilot = _pilot(i)
    return {"subject": ("pilot", pilot), "uploads": 6, "deps": [f"migration/production/{pilot}/", "migration/ci/"]}


def footage(i):
    q = i.get("queries") or "migration/production/footage/queries.json"
    m = re.fullmatch(r"migration/production/(footage/queries|(pilot-\d{3})/beats(-\d)?)\.json", q)
    need(m, "queries", q, "footage/queries.json or pilot-NNN/beats(-N).json")
    need(re.fullmatch(r"\d{1,2}", i.get("per_theme") or "3"), "per_theme", i.get("per_theme"), "1-2 digits")
    need_file(q)
    themes = load(q).get("themes", [])
    subject = ("pilot", m.group(2)) if m.group(2) else ("footage", "library")
    return {"subject": subject, "uploads": len(themes) * int(i.get("per_theme") or 3),
            "deps": [q, "migration/production/footage/"]}


def pavo_footage(i):
    lst = i.get("list", "")
    m = re.fullmatch(r"migration/production/(pilot-\d{3})/pavo(-\d+)?\.json", lst)
    need(m, "list", lst, "migration/production/pilot-NNN/pavo(-N).json")
    need_file(lst)
    entries = load(lst)
    return {"subject": ("pilot", m.group(1)), "uploads": len(entries) if isinstance(entries, list) else 50,
            "deps": [lst, "migration/production/footage/"]}


def agnes_clip(i):
    need((i.get("prompt") or "").strip(), "prompt", i.get("prompt"), "not empty")
    need(re.fullmatch(r"\d{1,2}", i.get("seconds") or "") and 4 <= int(i["seconds"]) <= 12, "seconds",
         i.get("seconds"), "4-12")
    need(i.get("aspect") in ("9:16", "16:9"), "aspect", i.get("aspect"), "9:16 or 16:9")
    need(re.fullmatch(rf"({SLUG}(,{SLUG})*)?", i.get("characters") or ""), "characters", i.get("characters"),
         "comma list of character ids")
    need(re.fullmatch(r"([A-Za-z0-9._-]+\.(png|jpg|jpeg))?", i.get("first_frame") or ""), "first_frame",
         i.get("first_frame"), "a release asset name of a still")
    return {"subject": None, "uploads": 0, "deps": ["migration/production/characters/"]}


def publish_episode(i):
    ep = i.get("episode", "")
    need(re.fullmatch(SLUG, ep), "episode", ep, "an episode id")
    rel = f"migration/production/bible/episodes/{ep}.json"
    need_file(rel)
    need(re.fullmatch(r"(https://\S+)?", i.get("source_url") or ""), "source_url", i.get("source_url"), "https or empty")
    need(re.fullmatch(r"(\d{4}-\d\d-\d\dT\d\d:\d\d(:\d\d)?Z)?", i.get("publish_at") or ""), "publish_at",
         i.get("publish_at"), "RFC3339 UTC (Z) or empty")
    rec = load(rel)
    if len(rec.get("title", "")) > TITLE_MAX or len(rec.get("description", "").encode()) > DESCRIPTION_MAX:
        refuse("GUARD_RECORD_OVER_LIMIT", f"{rel}: title <= {TITLE_MAX} characters, description <= "
                                          f"{DESCRIPTION_MAX} bytes (E52)")
    return {"subject": ("episode", ep), "uploads": 1, "deps": [rel, "migration/publish/"]}


# workflow file -> (input names in run-name order, check). run-name is "<stem>: k=v k=v" (test_dispatch_guard).
WORKFLOWS = {
    "episode.yml": (("plan", "resume_run"), episode),   # regenerate is always refused (E114), and kept off run-name
    "shot-probe.yml": (("plan", "shots", "attempts", "adopt_run"), shot_probe),
    "cf-images.yml": (("pilot", "engine", "only"), cf_images),
    "pilot-render-stills.yml": (("pilot",), pilot_render),
    "pilot-preview.yml": (("pilot",), pilot_preview),
    "footage.yml": (("queries", "per_theme"), footage),
    "pavo-footage.yml": (("list",), pavo_footage),
    "agnes-clip.yml": (("seconds", "aspect", "characters", "first_frame", "prompt"), agnes_clip),
    "publish-episode.yml": (("episode", "source_url", "publish_at"), publish_episode),
}
MAKES_IMAGES = {"cf-images.yml"}


def run_name(workflow, inputs):
    keys = WORKFLOWS[workflow][0]
    return f"{workflow[:-4]}: " + " ".join(f"{k}={inputs.get(k) or ''}" for k in keys)


def parse_run_name(workflow, title):
    keys = WORKFLOWS[workflow][0]
    m = re.fullmatch(re.escape(f"{workflow[:-4]}: ") + " ".join(f"{k}=(.*?)" for k in keys), title or "")
    return dict(zip(keys, m.groups())) if m else None


# ---- (5) imports in the job's environment ----
def workflow_texts(workflow):
    """The workflow and the shell scripts it runs (render_pilot.sh installs the render's venvs)."""
    text = (WF_DIR / workflow).read_text()
    out = [text]
    for sh in sorted(set(re.findall(r"migration/ci/[\w-]+\.sh", text))):
        if (ROOT / sh).is_file():
            out.append((ROOT / sh).read_text())
    return out


def installed(workflow):
    """Import names of the packages the workflow (or a script it runs) installs: pinned pip, apt python3-*."""
    names = set()
    for text in workflow_texts(workflow):
        for line in text.splitlines():
            if "install" not in line and not re.match(r"\s*setup \w+ venv ", line):
                continue
            for dist in re.findall(r"['\"]?([A-Za-z][A-Za-z0-9_.-]*)==[0-9][\w.]*", line):
                names.add(IMPORT_NAME.get(dist.lower(), dist.lower().replace("-", "_")))
            for dist in re.findall(r"\b(python3-[a-z0-9]+)\b", line):
                names.add(IMPORT_NAME.get(dist, dist[len("python3-"):]))
    return names


def scripts(workflow):
    found = []
    for text in workflow_texts(workflow):
        for rel in re.findall(r"migration/[\w/.-]+?\.py\b", text):
            if (ROOT / rel).is_file() and rel not in found:
                found.append(rel)
    return found


def _module_index():
    index = {}
    for p in sorted((ROOT / "migration").rglob("*.py")):
        if "/." not in str(p.relative_to(ROOT)) and not p.name.startswith("test_"):
            index.setdefault(p.stem, p)
    for p in sorted((ROOT / "migration").rglob("__init__.py")):
        index.setdefault(p.parent.name, p)
    return index


def _imports(path, lazy=False):
    """Names imported at module level (also inside a top-level if/with), except under try/except ImportError.
    A lazy import inside a function is left out (lazy=True takes it too): it runs only on the path that calls it,
    often under another venv."""
    names = set()

    def walk(body):
        for node in body:
            if isinstance(node, ast.Import):
                names.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                names.add(node.module.split(".")[0])
            elif isinstance(node, ast.If):
                walk(node.body)
                walk(node.orelse)
            elif isinstance(node, ast.With):
                walk(node.body)
            elif isinstance(node, ast.Try):
                if not any(h.type is None or "ImportError" in ast.dump(h.type) or "ModuleNotFoundError" in ast.dump(h.type)
                           for h in node.handlers):
                    walk(node.body)
                walk(node.finalbody)
    tree = ast.parse(path.read_text())
    walk(tree.body)
    if lazy:
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                names.add(node.module.split(".")[0])
    return names


def static_import_problems(workflow):
    """Every module-level import reached from the workflow's scripts. An entry script's lazy imports of the repo's
    own modules are followed too (E81: footage.py's vetting called cinematic lazily, and cinematic imports numpy at
    its top), but not its lazy third-party imports, which belong to a path another venv runs."""
    have, index, seen, bad = installed(workflow), _module_index(), set(), []
    todo = [(ROOT / s, True) for s in scripts(workflow)]
    while todo:
        path, entry = todo.pop()
        if path in seen:
            continue
        seen.add(path)
        top = _imports(path)
        for name in sorted(_imports(path, lazy=entry)):
            if name in sys.stdlib_module_names or name in have or name == "__future__":
                continue
            if name in index:
                todo.append((index[name], False))
                continue
            if name in top:
                bad.append(f"{path.relative_to(ROOT)} imports {name}: not stdlib, not in the repo, not installed by "
                           f"{workflow}")
    return bad, sorted(str(p.relative_to(ROOT)) for p in seen)


SMOKE = r"""
import importlib.abc, importlib.util, runpy, sys, types
from unittest import mock
STUBS = set(sys.argv[2].split(",")) - {""}
class Stub(importlib.abc.MetaPathFinder, importlib.abc.Loader):
    def find_spec(self, name, path, target=None):
        if name.split(".")[0] in STUBS:
            return importlib.util.spec_from_loader(name, self, is_package=True)
    def create_module(self, spec):
        m = types.ModuleType(spec.name)
        m.__path__ = []
        m.__getattr__ = lambda attr: mock.MagicMock(name=attr)
        return m
    def exec_module(self, module):
        pass
sys.meta_path.insert(0, Stub())
sys.argv = [sys.argv[1]]
runpy.run_path(sys.argv[0], run_name="__dispatch_guard__")
"""


def runtime_import_problems(workflow):
    """Each script's top level run under `python3 -I` (as the workflow runs it, E73), installed packages stubbed."""
    stubs = ",".join(sorted(installed(workflow)))
    bad = []
    for rel in scripts(workflow):
        r = subprocess.run([sys.executable, "-I", "-B", "-c", SMOKE, str(ROOT / rel), stubs], cwd=ROOT,
                           capture_output=True, text=True, timeout=120, env={"PATH": os.environ.get("PATH", "")})
        if r.returncode:
            last = (r.stderr.strip().splitlines() or ["exit %d" % r.returncode])[-1]
            bad.append(f"{rel}: {last}")
    return bad


def import_problems(workflow):
    static, _ = static_import_problems(workflow)
    return static + runtime_import_problems(workflow)


def depends_on(workflow, facts):
    """Path prefixes a run of this workflow depends on: the workflow, its scripts and their local imports, the shell
    scripts it runs and the subject's files."""
    _, local = static_import_problems(workflow)
    shells = [sh for t in workflow_texts(workflow)[:1] for sh in re.findall(r"migration/ci/[\w-]+\.sh", t)]
    return sorted(set([f".github/workflows/{workflow}"] + local + shells + facts["deps"]))


# ---- the API (read-only) ----
def github(path, token, repo):
    url = f"https://api.github.com/repos/{repo}/{path}"
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json",
                                               "X-GitHub-Api-Version": "2022-11-28",
                                               **({"Authorization": f"Bearer {token}"} if token else {})})
    last = None
    for _ in range(3):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            last = f"HTTP {e.code}"
            if e.code < 500 and e.code != 429:
                break
        except (urllib.error.URLError, TimeoutError) as e:
            last = str(e)
    refuse("GUARD_API_UNAVAILABLE", f"{path.split('?')[0]}: {last} (dispatch again when the API answers)")


def newest_tag():
    m = re.search(r"^TAGS=\(([^)]*)\)", (ROOT / "migration" / "ci" / "assets.sh").read_text(), re.M)
    return m.group(1).split()[0]


def asset_count(api, tag):
    rel = api(f"releases/tags/{tag}")
    if rel is None:
        return 0                     # assets.sh creates it on the first upload
    n, page = 0, 1
    while True:
        batch = api(f"releases/{rel['id']}/assets?per_page=100&page={page}") or []
        n += len(batch)
        if len(batch) < 100:
            return n
        page += 1


def cf_daily_images():
    text = (ROOT / "migration" / "production" / "bible" / "episode_preflight.py").read_text()
    return int(re.search(r"^CF_DAILY_IMAGES = (\d+)", text, re.M).group(1))


def cf_images_today(api, today):
    """FLUX images recorded on main today (UTC), counted as episode_preflight.cf_images_today counts them, by REST."""
    used = 0
    for c in api(f"commits?sha=main&since={today}T00:00:00Z&per_page=100") or []:
        if "images from Cloudflare Workers AI" in c["commit"]["message"]:
            files = (api(f"commits/{c['sha']}") or {}).get("files", [])
            used += sum(1 for f in files if f.get("status") == "added" and "/images/" in f["filename"]
                        and f["filename"].endswith(".json"))
    return used


def capacity(workflow, facts, api, today):
    tag = newest_tag()
    n = asset_count(api, tag)
    if facts["uploads"] and n + facts["uploads"] > ASSET_LIMIT:
        refuse("GUARD_ASSETS_FULL", f"{tag} holds {n} of {ASSET_LIMIT} assets and this run uploads up to "
                                    f"{facts['uploads']}: add a new tag at the front of migration/ci/assets.sh TAGS (E85)")
    if workflow in MAKES_IMAGES:
        used, cap = cf_images_today(api, today), cf_daily_images()
        if used >= cap:
            refuse("GUARD_CF_ALLOCATION_USED", f"{used} FLUX images recorded today of about {cap}: dispatch after "
                                               f"00:00 UTC (E62)")


def in_flight(workflow, facts, api, run_id):
    if not facts["subject"]:
        return
    for status in ("in_progress", "queued", "waiting", "pending"):
        for r in (api(f"actions/runs?status={status}&per_page=100") or {}).get("workflow_runs", []):
            other = Path(r.get("path", "")).name
            if str(r["id"]) == str(run_id) or other not in WORKFLOWS:
                continue
            got = parse_run_name(other, r.get("display_title"))
            if got is None:
                continue
            try:
                theirs = WORKFLOWS[other][1](got)["subject"]
            except Refusal:
                continue
            if theirs == facts["subject"]:
                refuse("GUARD_SUBJECT_IN_FLIGHT", f"{facts['subject'][0]} {facts['subject'][1]} is in flight in "
                                                  f"{other} run {r['id']} ({status}): one run per subject (E112)")


def failed_in_guard(api, run_id, attempt=None):
    path = f"actions/runs/{run_id}/attempts/{attempt}/jobs" if attempt else f"actions/runs/{run_id}/jobs?filter=latest"
    for job in (api(path) or {}).get("jobs", []):
        for step in job.get("steps", []):
            if step.get("conclusion") == "failure":
                return step.get("name", "").startswith(GUARD_STEP)
    return False


def recorded_retry(run_id):
    if not RETRIES.is_file():
        return False
    return any(str(r.get("run")) == str(run_id) and r.get("reason") for r in json.loads(RETRIES.read_text())["retries"])


def rerun(workflow, facts, inputs, api, run_id, attempt, sha):
    if attempt > 1 and not failed_in_guard(api, run_id, attempt - 1) and not recorded_retry(run_id):
        refuse("GUARD_RERUN_WITHOUT_FIX", f"attempt {attempt} of run {run_id} re-runs commit {sha[:12]}, which already "
                                          f"failed: merge a fix and dispatch again, or record an external cause in "
                                          f"{RETRIES.relative_to(ROOT)}")
    title = run_name(workflow, inputs)
    runs = (api(f"actions/workflows/{workflow}/runs?status=completed&per_page=100") or {}).get("workflow_runs", [])
    for r in runs:
        if str(r["id"]) == str(run_id) or r.get("display_title") != title:
            continue
        if r.get("conclusion") not in FAILED:
            return                    # the last run of these inputs did not fail
        if failed_in_guard(api, r["id"]):
            continue                  # refused by this guard before any work: not a failure of the inputs
        if recorded_retry(r["id"]):
            return
        deps = depends_on(workflow, facts)
        cmp = api(f"compare/{r['head_sha']}...{sha}") or {}
        files = [f["filename"] for f in cmp.get("files", [])]
        if cmp.get("status") == "ahead" and (len(files) >= 300 or any(
                f == d or (d.endswith("/") and f.startswith(d)) or f.startswith(d + "/") for f in files for d in deps)):
            return
        refuse("GUARD_RERUN_WITHOUT_FIX", f"run {r['id']} of these inputs failed at {r['head_sha'][:12]} and main "
                                          f"has no commit since touching what it depends on ({len(deps)} paths: "
                                          f"{', '.join(deps[:6])}...): merge the fix first, or record an external "
                                          f"cause in {RETRIES.relative_to(ROOT)}")
    return


def check_local(workflow, inputs):
    if workflow not in WORKFLOWS:
        refuse("GUARD_WORKFLOW_UNKNOWN", f"{workflow}: add it to dispatch_guard.WORKFLOWS")
    facts = WORKFLOWS[workflow][1](inputs)
    bad = import_problems(workflow)
    if bad:
        refuse("GUARD_IMPORT_UNRESOLVED", "; ".join(bad))
    return facts


def check(workflow, inputs, api, run_id, attempt, sha, today):
    facts = check_local(workflow, inputs)
    capacity(workflow, facts, api, today)
    in_flight(workflow, facts, api, run_id)
    rerun(workflow, facts, inputs, api, run_id, attempt, sha)
    return facts


def main(argv):
    if len(argv) != 3 or argv[1] not in ("run", "local"):
        raise SystemExit(__doc__)
    env = os.environ
    inputs = json.loads(env.get("GUARD_INPUTS") or "{}")
    try:
        if argv[1] == "local":
            facts = check_local(argv[2], inputs)
        else:
            repo, token = env["GITHUB_REPOSITORY"], env.get("GH_TOKEN", "")
            facts = check(argv[2], inputs, lambda p: github(p, token, repo), env["GITHUB_RUN_ID"],
                          int(env.get("GITHUB_RUN_ATTEMPT") or 1), env["GITHUB_SHA"],
                          datetime.now(timezone.utc).strftime("%Y-%m-%d"))
    except Refusal as e:
        print(e)
        return 1
    print(f"GUARD_OK {argv[2]} subject={facts['subject']} uploads<={facts['uploads']}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
