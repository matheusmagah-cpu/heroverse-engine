#!/usr/bin/env python3
"""One dispatch guard for every expensive workflow (E116; generalises E106's preflight and E112's order).

Each workflow in WORKFLOWS runs this as its first step after the checkout, before any step or job that holds a
secret, with its inputs (`GUARD_INPUTS: ${{ toJSON(inputs) }}`) and the run's own read-only token:

  dispatch_guard.py run WORKFLOW.yml      every check below; exit 1 with the named refusal, else GUARD_OK
  dispatch_guard.py local WORKFLOW.yml    the checks that need no API (inputs, order, imports), e.g. before a dispatch
  dispatch_guard.py attempt WORKFLOW.yml  only the re-run attempt rule (4), for a job whose guard ran in another job

Checks, each a named refusal (classified in ops/refusal_registry.json):
  1. inputs: the workflow's own input rules, and the files they name exist   GUARD_INPUT_INVALID, GUARD_INPUT_MISSING
     (episode.yml also E112's order: a later part waits for the earlier one)   EARLIER_PART_NOT_RECORDED
  2. capacity: the newest asset release (ci/assets.sh) has room for the run's uploads (1000 a release, E85), the
     Cloudflare allocation is not used up today when the run makes images (CF_DAILY_IMAGES, E62), a publish record
     fits YouTube's title and description limits (E52), and a Pavo batch's expected free-model units fit what is
     left today of the one budget every Pavo generation shares (E128: main's quota ledger + today's shot-probe
     records on their claude/shot-probe-* branches; its count goes to the probe as the `pavo_used` output)
                                                              GUARD_ASSETS_FULL, GUARD_CF_ALLOCATION_USED,
                                                              GUARD_RECORD_OVER_LIMIT, PAVO_BUDGET_SHORT,
                                                              PAVO_FREE_QUOTA_SUSPECTED
  3. one run per subject (the same episode plan, pilot, characters or footage library): not this script but GitHub,
     by the job-level `concurrency: group: heroverse-subject-<subject>` every guarded workflow shares (E112, E63,
     E10; test_dispatch_guard checks each group renders subject_of)
  4. the latest run of this workflow on the same subject failed (whatever its other inputs: resume_run, attempts,
     adopt_run): refused unless main has a new commit touching a file that run depends on (the workflow, the
     scripts it calls and their local imports, the subject's files) since the failed run's head_sha, or the failed
     run is recorded as external in evidence/dispatch/retries.json. A "Re-run" attempt after a failed attempt is
     the same commit, so only that record lets it through (`attempt`: the first step of a job whose guard ran in
     another job)                                             GUARD_RERUN_WITHOUT_FIX
  5. every Python script the workflow calls imports in the job's environment: each module-level import (followed
     through the repo's own modules) is stdlib, a repo module or a package the workflow (or the shell script it runs)
     installs, and the script's top level imports under
     `python3 -I` with those packages stubbed (E73, E81, E89)  GUARD_IMPORT_UNRESOLVED
An API that cannot be read refuses (GUARD_API_UNAVAILABLE): the guard never passes what it could not check.
The API is read-only (actions, releases, commits, compare) with the run's GITHUB_TOKEN; nothing is written.
"""
import ast
import base64
import functools
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


# ---- per workflow: inputs (1), uploads to the asset release (2), files its run depends on (4) ----
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
    return {"uploads": 1,
            "deps": [i["plan"], f"migration/production/bible/shots/{ep}.json", f"migration/evidence/preflight/{ep}.json",
                     "migration/production/characters/"]}


def long_build(i):
    """The long's build (long-build.yml, the long design's slice 3) takes a long plan only and ships approved clips."""
    plan = _plan(i)
    need(plan.get("version") == "bible-long-plan-v1", "plan", i.get("plan"), "a long plan (bible-long-plan-v1)")
    need(re.fullmatch(r"(\d{6,20})?", i.get("resume_run") or ""), "resume_run", i.get("resume_run"), "a run id or empty")
    ep = plan["episode"]
    return {"uploads": 2,   # the composed long and its .srt track
            "deps": [i["plan"], f"migration/production/bible/shots/{ep}.json", f"migration/evidence/preflight/{ep}.json",
                     "migration/production/characters/"]}


def shot_probe(i):
    plan = _plan(i)
    shots = ids(i.get("shots"))
    need(shots and re.fullmatch(IDS, i.get("shots", "")), "shots", i.get("shots"), "comma list of shot ids")
    # E127: a long's `window_of` shot is a second view of an earlier clip: never generated, so never probed
    known = {s.get("id") for s in plan.get("shots", []) if s.get("window_of") is None}
    need(set(shots) <= known, "shots", i.get("shots"), f"ids of this plan's generated shots ({len(known)} shots)")
    need(re.fullmatch(r"[1-6]", i.get("attempts") or ""), "attempts", i.get("attempts"), "1-6")
    need(re.fullmatch(r"(\d{6,20})?", i.get("adopt_run") or ""), "adopt_run", i.get("adopt_run"), "a run id or empty")
    deps = [i["plan"], "migration/production/characters/", "migration/evidence/pavo/setups.json"]
    if plan.get("version") == "bible-long-plan-v1":
        # E127: only a long's probe depends on its committed preflight (check-probe's LONG_PROBE_PREFLIGHT); a Short's
        # does not, so a new Short report is no fix that lifts GUARD_RERUN_WITHOUT_FIX
        deps.append(f"migration/evidence/preflight/{plan['episode']}.json")
    sys.path.insert(0, str(ROOT / "migration" / "production" / "bible"))
    import long_preflight  # E128: the batch's free-model units (planned_units, as probe-queue)
    by_id = {s.get("id"): s for s in plan.get("shots", [])}
    # review of #475: the worst case (every generation make_shot may spend), so a batch never starts it cannot finish
    units = 0 if i.get("adopt_run") else long_preflight.planned_units([by_id[x] for x in shots], int(i["attempts"]),
                                                                      worst=True)
    return {"uploads": len(shots) * int(i["attempts"]), "deps": deps, "pavo_units": units,
            "short": plan.get("version") != "bible-long-plan-v1"}   # E137: the Shorts' share of the rolling quota


def cf_images(i):
    pilot = i.get("pilot", "")
    need(re.fullmatch(r"pilot-\d{3}|characters", pilot), "pilot", pilot, "pilot-NNN or characters (E96)")
    need(i.get("engine") in ("flux", "sdxl"), "engine", i.get("engine"), "flux or sdxl")
    need(re.fullmatch(rf"({SLUG}(,{SLUG})*)?", i.get("only") or ""), "only", i.get("only"), "comma list of image ids")
    rel = f"migration/production/{pilot}/images.json"
    need_file(rel)
    n = len(ids(i.get("only"))) or len(load(rel).get("images", []))
    return {"uploads": 2 * n, "images": n, "deps": [f"migration/production/{pilot}/"]}


def _pilot(i):
    pilot = i.get("pilot", "")
    need(re.fullmatch(r"pilot-\d{3}", pilot), "pilot", pilot, "pilot-NNN")
    need_file(f"migration/production/{pilot}/script.json")
    return pilot


def pilot_render(i):
    pilot = _pilot(i)
    return {"uploads": 12, "deps": [f"migration/production/{pilot}/", "migration/ci/"]}


def pilot_preview(i):
    pilot = _pilot(i)
    return {"uploads": 6, "deps": [f"migration/production/{pilot}/", "migration/ci/"]}


def footage(i):
    q = i.get("queries") or "migration/production/footage/queries.json"
    m = re.fullmatch(r"migration/production/(footage/queries|(pilot-\d{3})/beats(-\d)?)\.json", q)
    need(m, "queries", q, "footage/queries.json or pilot-NNN/beats(-N).json")
    need(re.fullmatch(r"\d{1,2}", i.get("per_theme") or "3"), "per_theme", i.get("per_theme"), "1-2 digits")
    need_file(q)
    themes = load(q).get("themes", [])
    return {"uploads": len(themes) * int(i.get("per_theme") or 3),
            "deps": [q, "migration/production/footage/"]}


def pavo_footage(i):
    lst = i.get("list", "")
    m = re.fullmatch(r"migration/production/(pilot-\d{3})/pavo(-\d+)?\.json", lst)
    need(m, "list", lst, "migration/production/pilot-NNN/pavo(-N).json")
    need_file(lst)
    entries = load(lst)
    return {"uploads": len(entries) if isinstance(entries, list) else 50,
            "deps": [lst, "migration/production/footage/"]}


def scene_stills(i):
    plan = _plan(i)
    shots = ids(i.get("shots"))
    need(shots and re.fullmatch(IDS, i.get("shots", "")), "shots", i.get("shots"), "comma list of shot ids")
    known = {s.get("id") for s in plan.get("shots", [])}
    need(set(shots) <= known, "shots", i.get("shots"), f"ids of this plan ({len(known)} shots)")
    need(re.fullmatch(r"[1-3]", i.get("candidates") or ""), "candidates", i.get("candidates"), "1-3")
    return {"uploads": 0, "deps": [i["plan"], "migration/production/bible/stills/"],   # a review branch, no asset
            "flux_images": len(shots) * int(i["candidates"])}   # E134: what this run asks of the allocation


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
    return {"uploads": 1, "deps": [rel, "migration/publish/"]}


def subject_of(workflow, inputs):
    """The subject a run works on, from its inputs alone (no file read): the episode's plan path, the pilot (or
    characters), or the footage library. The guarded jobs' concurrency group is heroverse-subject-<subject>, and the
    failure history (4) is keyed on workflow + subject. None: the workflow has no subject."""
    first = inputs.get(WORKFLOWS[workflow][0][0]) or ""
    if workflow in ("episode.yml", "shot-probe.yml", "scene-stills.yml", "long-build.yml"):
        return first
    if workflow == "publish-episode.yml":
        return f"migration/production/bible/plans/{first}.json"
    if workflow in ("cf-images.yml", "pilot-render-stills.yml", "pilot-preview.yml"):
        return first
    if workflow in ("footage.yml", "pavo-footage.yml"):
        m = re.match(r"migration/production/(pilot-\d{3})/", first or "migration/production/footage/")
        return m.group(1) if m else "footage-library"
    return None


# workflow file -> (input names in run-name order, the first one naming the subject; check). run-name is
# "<stem>: k=v k=v" (test_dispatch_guard), so a later dispatch finds the earlier runs of its subject.
WORKFLOWS = {
    "episode.yml": (("plan", "resume_run"), episode),   # regenerate is always refused (E114), and kept off run-name
    "shot-probe.yml": (("plan", "shots", "attempts", "adopt_run"), shot_probe),
    "long-build.yml": (("plan", "resume_run"), long_build),
    "cf-images.yml": (("pilot", "engine", "only"), cf_images),
    "pilot-render-stills.yml": (("pilot",), pilot_render),
    "pilot-preview.yml": (("pilot",), pilot_preview),
    "footage.yml": (("queries", "per_theme"), footage),
    "pavo-footage.yml": (("list",), pavo_footage),
    "publish-episode.yml": (("episode", "source_url", "publish_at"), publish_episode),
    "scene-stills.yml": (("plan", "shots", "candidates"), scene_stills),
}
# the job of each workflow that holds its subject's concurrency group (pavo-footage's work is a matrix of clip jobs:
# GitHub keeps one pending job per group and cancels the rest, so it keeps its workflow-level group only)
SUBJECT_JOBS = {"episode.yml": "build", "shot-probe.yml": "probe", "cf-images.yml": "images",
                "pilot-render-stills.yml": "render", "pilot-preview.yml": "preview", "footage.yml": "library",
                "publish-episode.yml": "publish", "scene-stills.yml": "stills", "long-build.yml": "prepare"}


def run_name(workflow, inputs):
    keys = WORKFLOWS[workflow][0]
    return f"{workflow[:-4]}: " + " ".join(f"{k}={inputs.get(k) or ''}" for k in keys)


def run_subject(workflow, title):
    """The subject of an earlier run, read from the first input of its run-name; None when it is not one of ours."""
    key = WORKFLOWS[workflow][0][0]
    m = re.match(re.escape(f"{workflow[:-4]}: {key}=") + r"(\S*)(?: |$)", title or "")
    return subject_of(workflow, {key: m.group(1)}) if m else None


# ---- (5) imports in the job's environment ----
@functools.lru_cache(maxsize=None)
def workflow_texts(workflow):
    """The workflow and the shell scripts it runs (render_pilot.sh installs the render's venvs)."""
    text = (WF_DIR / workflow).read_text()
    out = [text]
    for sh in sorted(set(re.findall(r"migration/ci/[\w-]+\.sh", text))):
        if (ROOT / sh).is_file():
            out.append((ROOT / sh).read_text())
    return tuple(out)


@functools.lru_cache(maxsize=None)
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
    return frozenset(names)


@functools.lru_cache(maxsize=None)
def scripts(workflow):
    found = []
    for text in workflow_texts(workflow):
        for rel in re.findall(r"migration/[\w/.-]+?\.py\b", text):
            if (ROOT / rel).is_file() and rel not in found:
                found.append(rel)
    return tuple(found)


@functools.lru_cache(maxsize=None)
def _module_index():
    """stem -> every repo module with that name (never collapsed: two client.py stay two)."""
    index = {}
    for p in sorted((ROOT / "migration").rglob("*.py")):
        rel = str(p.relative_to(ROOT))
        if "/." in rel or p.name.startswith("test_"):
            continue
        if p.name == "__init__.py":
            index.setdefault(p.parent.name, []).append(p)
        else:
            index.setdefault(p.stem, []).append(p)
    return index


def _path_value(node, env, path):
    """Evaluate the path expressions scripts give sys.path (Path(__file__).resolve().parents[1] / "x", HERE, REPO
    / "migration", str(...), os.path.dirname(...)); None when it is anything else."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Name):
        return path if node.id == "__file__" else env.get(node.id)
    if isinstance(node, ast.Call):
        f = node.func
        name = f.id if isinstance(f, ast.Name) else f.attr if isinstance(f, ast.Attribute) else ""
        if name in ("Path", "str", "abspath", "realpath") and len(node.args) == 1:
            v = _path_value(node.args[0], env, path)
            return Path(v) if v is not None else None
        if name == "dirname" and len(node.args) == 1:
            v = _path_value(node.args[0], env, path)
            return Path(v).parent if v is not None else None
        if name == "join" and node.args:
            parts = [_path_value(a, env, path) for a in node.args]
            return Path(*parts) if None not in parts else None
        if name in ("resolve", "absolute") and isinstance(f, ast.Attribute):
            v = _path_value(f.value, env, path)
            return Path(v).resolve() if v is not None else None
    if isinstance(node, ast.Attribute) and node.attr == "parent":
        v = _path_value(node.value, env, path)
        return Path(v).parent if v is not None else None
    if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Attribute) and node.value.attr == "parents":
        v = _path_value(node.value.value, env, path)
        k = node.slice.value if isinstance(node.slice, ast.Constant) else None
        return Path(v).parents[k] if v is not None and isinstance(k, int) else None
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
        a, b = _path_value(node.left, env, path), _path_value(node.right, env, path)
        return Path(a) / b if a is not None and b is not None else None
    return None


def _sys_path_dirs(tree, path):
    """The folders a module puts on sys.path (sys.path.insert / append), evaluated where they can be."""
    env = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            v = _path_value(node.value, env, path)
            if v is not None:
                env[node.targets[0].id] = v
    dirs = []
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in ("insert", "append")
                and isinstance(node.func.value, ast.Attribute) and node.func.value.attr == "path" and node.args):
            v = _path_value(node.args[-1], env, path)
            if v is not None:
                dirs.append(Path(v))
    return dirs


def _resolve(name, path, extra_dirs):
    """The repo module(s) `name` means when imported from `path`: its own folder and the folders it (or its entry
    script) puts on sys.path first; else every repo module of that name (an unresolved local name is followed in
    all its homes, never collapsed into one)."""
    for d in [path.parent] + extra_dirs:
        for cand in (d / f"{name}.py", d / name / "__init__.py"):
            if cand.is_file():
                return [cand.resolve()]
    return [p.resolve() for p in _module_index().get(name, [])]


def _imports(tree, lazy=False):
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
    walk(tree.body)
    if lazy:
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                names.add(node.module.split(".")[0])
    return names


def static_import_problems(workflow):
    """Every module-level import reached from the workflow's scripts, resolved from the importing file's folder and
    sys.path inserts. An entry script's lazy imports of the repo's own modules are followed too (E81: footage.py's
    vetting called cinematic lazily, and cinematic imports numpy at its top), but not its lazy third-party imports,
    which belong to a path another venv runs. Returns (problems, every repo file reached)."""
    have, seen, bad = installed(workflow), set(), []
    todo = [((ROOT / s).resolve(), True, []) for s in scripts(workflow)]
    while todo:
        path, entry, inherited = todo.pop()
        if path in seen:
            continue
        seen.add(path)
        tree = ast.parse(path.read_text())
        dirs = _sys_path_dirs(tree, path) + inherited
        top = _imports(tree)
        for name in sorted(_imports(tree, lazy=entry)):
            if name in sys.stdlib_module_names or name in have or name == "__future__":
                continue
            homes = _resolve(name, path, dirs)
            if homes:
                todo += [(h, False, dirs) for h in homes]
            elif name in top:
                bad.append(f"{_rel(path)} imports {name}: not stdlib, not in the repo, not installed by {workflow}")
    return bad, sorted(_rel(p) for p in seen)


def _rel(path):
    try:
        return str(Path(path).relative_to(ROOT))
    except ValueError:
        return str(path)


SMOKE = r"""
import importlib.abc, importlib.util, json, runpy, sys, types
from unittest import mock
STUBS = set(sys.argv[1].split(",")) - {""}
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
path0, mods0 = list(sys.path), set(sys.modules)
for script in sys.argv[2:]:
    sys.argv[1:] = []
    try:
        runpy.run_path(script, run_name="__dispatch_guard__")
    except BaseException as e:
        if not (isinstance(e, SystemExit) and e.code in (0, None)):
            print(json.dumps([script, type(e).__name__ + ": " + str(e)]))
    sys.path[:] = path0          # each script starts as `python3 -I script` would: nothing the one before added
    for name in set(sys.modules) - mods0:
        del sys.modules[name]
"""


def runtime_import_problems(workflow):
    """Each script's top level run as `python3 -I` runs it (E73), the workflow's packages stubbed; one process for
    all of a workflow's scripts, sys.path and sys.modules reset between them."""
    paths = [str(ROOT / rel) for rel in scripts(workflow)]
    if not paths:
        return []
    r = subprocess.run([sys.executable, "-I", "-B", "-c", SMOKE, ",".join(sorted(installed(workflow)))] + paths,
                       cwd=ROOT, capture_output=True, text=True, timeout=300, env={"PATH": os.environ.get("PATH", "")})
    bad = []
    for line in r.stdout.splitlines():
        try:
            script, err = json.loads(line)
        except ValueError:
            continue
        bad.append(f"{_rel(script)}: {err}")
    if r.returncode and not bad:
        bad.append(f"import smoke exited {r.returncode}: {(r.stderr.strip().splitlines() or [''])[-1]}")
    return bad


def import_problems(workflow, scan=None):
    static, _ = scan or static_import_problems(workflow)
    return static + runtime_import_problems(workflow)


def depends_on(workflow, facts):
    """Path prefixes a run of this workflow depends on: the workflow, its scripts and their local imports (from the
    one import scan of this check), the shell scripts it runs and the subject's files."""
    shells = re.findall(r"migration/ci/[\w-]+\.sh", workflow_texts(workflow)[0])
    return sorted(set([f".github/workflows/{workflow}"] + facts["files"] + shells + facts["deps"]))


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


STILLS_TITLE = re.compile(r"^scene-stills: plan=\S+ shots=(\S+) candidates=([1-3])$")


def stills_images_today(api, today, run_id=None):
    """E134: FLUX images scene-stills.yml runs asked for today (UTC), from the runs themselves (their titles: shots x
    candidates), whatever happened to their review branch afterwards. Counting the candidates' commits on the
    claude/stills-* branches missed every run whose branch was squash-merged and deleted (genesis-09 run 40615150859:
    30 images, #487), so run 40623485981 passed the guard with the allocation already used up. A run this guard
    refused made nothing; this run is not counted twice. Conservative: a run that stopped early counts in full."""
    runs = (api(f"actions/workflows/scene-stills.yml/runs?created=%3E%3D{today}&per_page=100") or {}).get(
        "workflow_runs", [])
    n = 0
    for r in runs:
        if str(r.get("id")) == str(run_id) or not str(r.get("created_at", "")).startswith(today):
            continue
        if r.get("conclusion") in FAILED and failed_in_guard(api, r["id"]):
            continue
        m = STILLS_TITLE.match(r.get("display_title") or "")
        if m:
            n += len(m.group(1).split(",")) * int(m.group(2))
    return n


def cf_images_today(api, today, run_id=None):
    """FLUX images used today (UTC), by REST: the records cf-images.yml commits to main (episode_preflight's own
    predicate, cf_allocation.flux_record, on its images/ records) plus what today's scene-stills.yml runs asked for
    (E134: from the runs, not from their review branches)."""
    sys.path.insert(0, str(ROOT / "migration" / "production" / "imagegen"))
    import cf_allocation
    shas = [c["sha"] for c in api(f"commits?sha=main&since={today}T00:00:00Z&per_page=100") or []
            if cf_allocation.MARK in (c["commit"]["message"] or "").split("\n", 1)[0]]
    used = 0
    for sha in dict.fromkeys(shas):
        c = api(f"commits/{sha}") or {}
        meta = c.get("commit", {})
        subject = (meta.get("message") or "").split("\n", 1)[0]
        if not (meta.get("committer") or {}).get("date", "").startswith(today):
            continue
        used += sum(1 for f in c.get("files", []) if f.get("status") == "added" and "/images/" in f["filename"]
                    and cf_allocation.flux_record(subject, f["filename"]))
    return used + stills_images_today(api, today, run_id)


BRANCH_PAGES = 10   # 1000 branches; more refuses PAVO_BUDGET_UNREADABLE (review of #475: never a partial count)


def pavo_actions_usage(api, today, now=None):
    """E128: shot-probe usage (quota.combine) from the records the record job pushed to claude/shot-probe-* branches,
    by REST: units of the records committed today (UTC), the failed tail of those of the last quota.COOL_DOWN too (a
    stop before midnight holds after it). The MCP guard reads the same records from the local refs. A record that
    cannot be read, or more branches than BRANCH_PAGES pages, refuses: the count is never partial."""
    sys.path.insert(0, str(ROOT / "migration" / "integrations" / "pavo"))
    import quota
    now = now or datetime.now(timezone.utc)
    records, shorts, page = [], [], 1
    while True:
        if page > BRANCH_PAGES:
            refuse("PAVO_BUDGET_UNREADABLE", f"more than {BRANCH_PAGES * 100} branches: delete merged probe branches "
                                             "or raise BRANCH_PAGES")
        batch = api(f"branches?per_page=100&page={page}") or []
        for b in batch:
            path = quota.probe_record_path(b.get("name", ""))
            if not path:
                continue
            c = api(f"commits/{b['commit']['sha']}") or {}
            date = ((c.get("commit") or {}).get("committer") or {}).get("date", "")
            try:
                at = datetime.fromisoformat(date.replace("Z", "+00:00"))
            except ValueError:
                refuse("PAVO_BUDGET_UNREADABLE", f"{b['name']}: no commit time")
            if not quota.wanted(at, today, now):
                continue
            f = api(f"contents/{path}?ref={b['commit']['sha']}")
            if not f:
                continue      # the probe job left no record (NO_PROBE_RECORD)
            try:
                record = json.loads(base64.b64decode(f["content"]))
            except (KeyError, ValueError, TypeError):
                refuse("PAVO_BUDGET_UNREADABLE", f"{b['name']}: its record cannot be read")
            records.append((at, record))
            m = quota.PROBE_BRANCH.fullmatch(b.get("name", ""))
            if m and m.group(1).endswith("-short"):
                shorts.append((at, record))
        if len(batch) < 100:
            break
        page += 1
    usage = quota.combine(records, today)
    usage["short_units"] = quota.combine(shorts, today)["units"]   # E137: the Shorts' share
    return usage


def pavo_budget(facts, api, today, now=None):
    """E128: refuse a Pavo batch that does not fit today's free-model budget (PAVO_BUDGET_SHORT) or runs into a
    suspected quota stop; returns the units used today (the probe seeds its run-local ledger with them)."""
    import quota
    when = now or datetime.now(timezone.utc)
    usage = pavo_actions_usage(api, today, when)
    guard = quota.QuotaGuard(quota.LEDGER, now=lambda: when, actions=lambda day: usage)
    try:
        fits = guard.check_batch(facts["pavo_units"])
    except quota.PavoError as exc:
        raise Refusal(str(exc)) from None
    if facts.get("short"):   # E137: the Shorts take at most SHORTS_DAILY_JOBS jobs a UTC day, the long the rest
        done = -(-int(usage.get("short_units") or 0) // quota.VIDEO_UNITS)
        planned = -(-int(facts["pavo_units"]) // quota.VIDEO_UNITS)
        if done + planned > quota.SHORTS_DAILY_JOBS:
            refuse("PAVO_SHORTS_SHARE", f"{done} Short jobs today and {planned} planned (worst case) pass the Shorts' "
                                        f"{quota.SHORTS_DAILY_JOBS} a day: split the batch or wait for the next UTC day "
                                        "(the long has priority, E137)")
    return fits["used"]


def capacity(workflow, facts, api, today):
    tag = newest_tag()
    n = asset_count(api, tag)
    if facts["uploads"] and n + facts["uploads"] > ASSET_LIMIT:
        refuse("GUARD_ASSETS_FULL", f"{tag} holds {n} of {ASSET_LIMIT} assets and this run uploads up to "
                                    f"{facts['uploads']}: add a new tag at the front of migration/ci/assets.sh TAGS (E85)")
    if facts.get("flux"):
        used, cap = cf_images_today(api, today, facts.get("run_id")), cf_daily_images()
        planned = facts.get("flux_images", 0)   # E134: this run's own images must fit too
        if used >= cap or used + planned > cap:
            refuse("GUARD_CF_ALLOCATION_USED", f"{used} FLUX images used today and {planned} asked of about {cap}: "
                                               f"fewer shots or candidates, or dispatch after 00:00 UTC (E62, E134)")
    if facts.get("pavo_units"):
        facts["pavo_used"] = pavo_budget(facts, api, today)


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


def attempt_check(api, run_id, attempt, sha):
    """GitHub's "Re-run" runs the same commit again: allowed after a cancelled or successful attempt, or one this
    guard refused; after a failed one only when retries.json records its external cause."""
    if attempt <= 1:
        return
    prev = api(f"actions/runs/{run_id}/attempts/{attempt - 1}") or {}
    if prev.get("conclusion") in FAILED and not failed_in_guard(api, run_id, attempt - 1) and not recorded_retry(run_id):
        refuse("GUARD_RERUN_WITHOUT_FIX", f"attempt {attempt} of run {run_id} re-runs commit {sha[:12]}, on which "
                                          f"attempt {attempt - 1} failed: merge a fix and dispatch again, or record "
                                          f"an external cause in {RETRIES.relative_to(ROOT)}")


def same_subject(workflow, facts, inputs, title):
    if facts["subject"] is None:
        return title == run_name(workflow, inputs)      # no subject: the same inputs
    return run_subject(workflow, title) == facts["subject"]


def rerun(workflow, facts, inputs, api, run_id, attempt, sha):
    """(4) keyed on workflow + subject, whatever the other inputs (resume_run, attempts, adopt_run): the latest run
    of this subject that this guard did not refuse failed -> a commit since its head_sha must touch what it depends
    on, or retries.json records its external cause."""
    attempt_check(api, run_id, attempt, sha)
    runs = (api(f"actions/workflows/{workflow}/runs?status=completed&per_page=100") or {}).get("workflow_runs", [])
    for r in runs:
        if str(r["id"]) == str(run_id) or not same_subject(workflow, facts, inputs, r.get("display_title")):
            continue
        if r.get("conclusion") not in FAILED:
            return                    # the last run of this subject did not fail
        if failed_in_guard(api, r["id"]):
            continue                  # refused by this guard before any work: not a failure of the subject
        if recorded_retry(r["id"]):
            return
        deps = depends_on(workflow, facts)
        cmp = api(f"compare/{r['head_sha']}...{sha}") or {}
        files = [f["filename"] for f in cmp.get("files", [])]
        if cmp.get("status") == "ahead" and (len(files) >= 300 or any(
                f == d or (d.endswith("/") and f.startswith(d)) or f.startswith(d + "/") for f in files for d in deps)):
            return
        refuse("GUARD_RERUN_WITHOUT_FIX", f"run {r['id']} on {facts['subject'] or 'these inputs'} failed at "
                                          f"{r['head_sha'][:12]} and main has no commit since touching what it "
                                          f"depends on ({len(deps)} paths: {', '.join(deps[:6])}...): merge the fix "
                                          f"first, or record an external cause in {RETRIES.relative_to(ROOT)}")


PLAN_STRICT = ("shot-probe.yml",)   # E135: workflows whose next step is the plan's strict check


def plan_strict_problems(plan_path, run=subprocess.run):
    """E135: the plan's own strict check, the one shot-probe.yml runs right after this guard (plan_check.py --strict for
    a Short, long_plan_check.py --strict for a long): its problems, [] when it passes. genesis-09 run 40626005505
    passed the guard and stopped in that step on 11 STILL_NOT_APPROVED, a whole run spent to learn what this predicts
    for nothing."""
    plan = load(plan_path)
    checker = "long_plan_check.py" if plan.get("version") == "bible-long-plan-v1" else "plan_check.py"
    done = run([sys.executable, "-I", "-B", str(ROOT / "migration" / "production" / "bible" / checker),
                str(ROOT / plan_path), "--strict"], capture_output=True, text=True, cwd=str(ROOT))
    if done.returncode == 0:
        return []
    try:
        problems = list(json.loads(done.stdout).get("problems") or [])
    except (ValueError, AttributeError):
        problems = []
    return problems or [f"{checker} exit {done.returncode}: {(done.stderr or done.stdout).strip()[-300:]}"]


def check_local(workflow, inputs):
    if workflow not in WORKFLOWS:
        refuse("GUARD_WORKFLOW_UNKNOWN", f"{workflow}: add it to dispatch_guard.WORKFLOWS")
    facts = WORKFLOWS[workflow][1](inputs)
    if workflow in PLAN_STRICT:
        problems = plan_strict_problems(inputs["plan"])
        if problems:
            refuse("GUARD_PLAN_NOT_STRICT", f"{len(problems)} problem(s), e.g. {problems[0][:200]} (the workflow's own "
                                            "plan check would stop the run: fix the plan first, E135)")
    facts["subject"] = subject_of(workflow, inputs)
    facts["flux"] = (workflow == "cf-images.yml" and inputs.get("engine") == "flux") or workflow == "scene-stills.yml"
    scan = static_import_problems(workflow)      # once: its problems here, its files for (4)
    bad = import_problems(workflow, scan)
    if bad:
        refuse("GUARD_IMPORT_UNRESOLVED", "; ".join(bad))
    facts["files"] = scan[1]
    return facts


def check(workflow, inputs, api, run_id, attempt, sha, today):
    facts = check_local(workflow, inputs)
    facts["run_id"] = run_id
    capacity(workflow, facts, api, today)
    rerun(workflow, facts, inputs, api, run_id, attempt, sha)
    return facts


def main(argv):
    if len(argv) != 3 or argv[1] not in ("run", "local", "attempt"):
        raise SystemExit(__doc__)
    env = os.environ
    inputs = json.loads(env.get("GUARD_INPUTS") or "{}")
    try:
        if argv[1] == "local":
            facts = check_local(argv[2], inputs)
        else:
            repo, token = env["GITHUB_REPOSITORY"], env.get("GH_TOKEN", "")
            api = lambda p: github(p, token, repo)  # noqa: E731
            attempt, sha = int(env.get("GITHUB_RUN_ATTEMPT") or 1), env["GITHUB_SHA"]
            if argv[1] == "attempt":
                attempt_check(api, env["GITHUB_RUN_ID"], attempt, sha)
                print(f"GUARD_OK {argv[2]} attempt {attempt}")
                return 0
            facts = check(argv[2], inputs, api, env["GITHUB_RUN_ID"], attempt, sha,
                          datetime.now(timezone.utc).strftime("%Y-%m-%d"))
    except Refusal as e:
        print(e)
        return 1
    if env.get("GITHUB_OUTPUT") and facts["subject"]:
        with open(env["GITHUB_OUTPUT"], "a") as out:
            out.write(f"subject={facts['subject']}\n")
    if env.get("GITHUB_OUTPUT") and "pavo_used" in facts:   # E128: shot-probe's run-local quota ledger is seeded with it
        with open(env["GITHUB_OUTPUT"], "a") as out:
            out.write(f"pavo_used={facts['pavo_used']}\n")
    print(f"GUARD_OK {argv[2]} subject={facts['subject']} uploads<={facts['uploads']}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
