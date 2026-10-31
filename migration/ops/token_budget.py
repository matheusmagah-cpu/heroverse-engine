#!/usr/bin/env python3
"""Claude Code token budget for this project: half of the weekly cap, planned by real cost, enforced by a hook.

Sums assistant `usage` from ~/.claude/projects/*heroverse*/**/*.jsonl (subagents included) inside the current
weekly window, merges with the persisted ledger (max per session), and stops the session over budget.
Commands: status | plan [--write] | costs [--write] | check [--action T] | record [--action T --actual N].
Offline, deterministic. There is no warn-only path: over the budget (or the activity's allocation) is exit 2.
See migration/SYSTEM.md "Token budget"."""
import json
import os
import re
import select
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
FIELDS = ("input_tokens", "cache_creation_input_tokens", "output_tokens", "cache_read_input_tokens")
DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
ACTIVITIES = ("long", "shorts", "clocks", "reviews_prs", "reserve")
# action type -> activity whose allocation it spends (tool_*/main_turn/pr_cycle are measured, never allocated)
ACTIVITY_OF = {"agent_long": "long", "agent_short": "shorts", "clock_daily": "clocks", "agent_mining": "clocks",
               "agent_review": "reviews_prs", "agent_plan_pr": "reviews_prs", "agent_other": "reviews_prs"}
BRIEFS = [("agent_review", r"^(code review|review pr)"), ("clock_daily", r"daily loop|daily analysis|\bclock\b"),
          ("agent_mining", r"\bmining\b|\bmine\b"), ("agent_short", r"\bshorts?\b"), ("agent_long", r"\blong\b"),
          ("agent_plan_pr", r"\bplan\b")]


def load_json(env, name, default=None):
    p = Path(os.environ.get(env) or HERE / name)
    try:
        return json.loads(p.read_text())
    except (OSError, ValueError):
        if default is None:
            raise
        return default


def load_config():
    return load_json("TOKEN_BUDGET_CONFIG", "token_budget.json")


def now_utc():
    v = os.environ.get("TOKEN_BUDGET_NOW")
    return datetime.fromisoformat(v.replace("Z", "+00:00")) if v else datetime.now(timezone.utc)


def window_start(now, cfg):
    """The most recent weekly reset at or before `now`."""
    hh, mm = map(int, cfg["reset"]["time_utc"].split(":"))
    day = DAYS.index(cfg["reset"]["weekday"].lower())
    start = now.astimezone(timezone.utc).replace(hour=hh, minute=mm, second=0, microsecond=0)
    start -= timedelta(days=(start.weekday() - day) % 7)
    if start > now:
        start -= timedelta(days=7)
    return start


def weighted(c, cfg):
    return (c.get("input_tokens", 0) + c.get("cache_creation_input_tokens", 0) + c.get("output_tokens", 0)
            + cfg["cache_read_weight"] * c.get("cache_read_input_tokens", 0))


def classify(prompt):
    """Brief type of an agent run, from its first prompt."""
    p = (prompt or "").strip().lower()
    for name, rx in BRIEFS:
        if re.search(rx, p):
            return name
    return "agent_other"


def prompt_text(o):
    c = (o.get("message") or {}).get("content")
    return c if isinstance(c, str) else " ".join(b.get("text", "") for b in c or [] if isinstance(b, dict))


def read_transcript(f, start, end):
    """(first user prompt, {message id: (ts, counts, [tool_use ids by name])}, {tool_use id: result info})."""
    prompt, msgs, results = None, {}, {}
    with open(f, errors="ignore") as fh:
        for line in fh:
            try:
                o = json.loads(line)
                m = o.get("message")
                if o.get("type") == "user" and isinstance(m, dict):
                    if prompt is None:
                        prompt = prompt_text(o)
                    for b in m["content"] if isinstance(m.get("content"), list) else []:
                        if isinstance(b, dict) and b.get("type") == "tool_result":
                            body = b.get("content")
                            results[b.get("tool_use_id")] = (len(json.dumps(body)), True and
                                                             any(isinstance(x, dict) and x.get("type") == "image" for x in body or []))
                    continue
                if o.get("type") != "assistant" or m.get("model") == "<synthetic>" or "usage" not in m:
                    continue
                ts = datetime.fromisoformat(o["timestamp"].replace("Z", "+00:00"))
                if not (start <= ts < end):
                    continue
                u = m["usage"]
                v = {k: int(u.get(k) or 0) for k in FIELDS}
                tools = [(b.get("name", ""), b.get("id")) for b in m.get("content") or [] if isinstance(b, dict) and b.get("type") == "tool_use"]
                mid = m.get("id") or o.get("uuid")
                if mid not in msgs or sum(v.values()) > sum(msgs[mid][1].values()):
                    msgs[mid] = (ts, v, tools)
            except (ValueError, KeyError, TypeError, AttributeError):
                continue
    return prompt, msgs, results


def transcripts(projects_dir, start):
    projects_dir = Path(projects_dir)
    for f in sorted(projects_dir.glob("*heroverse*/**/*.jsonl")):
        try:
            if datetime.fromtimestamp(f.stat().st_mtime, timezone.utc) >= start:
                yield f, "/".join(f.relative_to(projects_dir).parts[1:]).removesuffix(".jsonl")
        except OSError:
            continue


def scan(projects_dir, start, end):
    """{session key: raw counts + activity} for assistant messages in [start, end). One message counts once."""
    out = {}
    for f, key in transcripts(projects_dir, start):
        try:
            prompt, msgs, _ = read_transcript(f, start, end)
        except OSError:
            continue
        s = out.setdefault(key, dict.fromkeys(FIELDS, 0))
        s["activity"] = ACTIVITY_OF[classify(prompt)] if "subagents/" in key else "reserve"
        for _, v, _ in msgs.values():
            for k in FIELDS:
                s[k] += v[k]
    return {k: v for k, v in out.items() if any(v[f] for f in FIELDS)}


def merge_max(a, b):
    """Merge two {session: counts} maps by max per field, so a restart that lost transcripts never lowers counts."""
    out = {k: dict(v) for k, v in a.items()}
    for key, v in b.items():
        cur = out.setdefault(key, dict.fromkeys(FIELDS, 0))
        for f in FIELDS:
            cur[f] = max(cur.get(f, 0), v.get(f, 0))
        cur["activity"] = v.get("activity") or cur.get("activity") or "reserve"
    return out


def ledger_path(start):
    d = Path(os.environ.get("TOKEN_BUDGET_LEDGER_DIR") or ROOT / "migration/evidence/tokens")
    return d / f"{start:%Y-%m-%d}.json"


def read_ledger(start):
    try:
        return json.loads(ledger_path(start).read_text())
    except (OSError, ValueError):
        return {}


def compute(cfg=None, now=None, use_cache=True):
    cfg = cfg or load_config()
    now = now or now_utc()
    start = window_start(now, cfg)
    cache = Path(os.environ.get("TOKEN_BUDGET_CACHE") or Path(tempfile.gettempdir()) / "heroverse-token-budget.json")
    if use_cache:
        try:
            c = json.loads(cache.read_text())
            if c["start"] == start.isoformat() and time.time() - c["at"] < cfg.get("cache_seconds", 60):
                return c["state"]
        except (OSError, ValueError, KeyError):
            pass
    projects = os.environ.get("TOKEN_BUDGET_PROJECTS_DIR") or Path.home() / ".claude/projects"
    led = read_ledger(start)
    sessions = merge_max(led.get("sessions", {}), scan(projects, start, now + timedelta(seconds=1)))
    by_activity = dict.fromkeys(ACTIVITIES, 0)
    for v in sessions.values():
        by_activity[v.get("activity", "reserve")] += weighted(v, cfg)
    used = sum(by_activity.values())
    budget = cfg["weekly_cap_tokens"] * cfg["project_share"]
    elapsed = max((now - start).total_seconds(), 1)
    state = {"window_start": start.isoformat(), "window_end": (start + timedelta(days=7)).isoformat(),
             "used": round(used), "budget": round(budget), "weekly_cap_tokens": cfg["weekly_cap_tokens"],
             "pct": round(100 * used / budget, 2), "projected_end_of_week": round(used * 7 * 86400 / elapsed),
             "by_activity": {k: round(v) for k, v in by_activity.items()}, "actions": led.get("actions", []),
             "sessions": sessions}
    if use_cache:
        try:
            cache.write_text(json.dumps({"start": start.isoformat(), "at": time.time(), "state": state}))
        except OSError:
            pass
    return state


def p90(xs):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, -(-9 * len(xs) // 10) - 1)] if xs else 0


def cost_samples(cfg, projects_dir, start, end):
    """{action: [weighted tokens]}: main turn; each agent run by brief type; tool call by kind (the issuing turn's
    cost split over its tool calls); PR cycle (all agent runs that name the same PR)."""
    out, prs = {}, {}
    add = lambda a, x: out.setdefault(a, []).append(x)
    for f, key in transcripts(projects_dir, start):
        try:
            prompt, msgs, results = read_transcript(f, start, end)
        except OSError:
            continue
        if not msgs:
            continue
        sub = "subagents/" in key
        total = 0
        for _, v, tools in msgs.values():
            w = weighted(v, cfg)
            total += w
            if not sub:
                add("main_turn", w)
            for name, tid in tools:
                size, image = results.get(tid, (0, False))
                kind = ("Bash" if name == "Bash" else "mcp" if name.startswith("mcp__") else "agent" if name in ("Agent", "Task")
                        else "read_image" if name == "Read" and image else "read_large" if name == "Read" and size > 20000
                        else "read" if name == "Read" else "other")
                add("tool_" + kind.lower(), w / len(tools))
        if sub:
            add(classify(prompt), total)
            for n in set(re.findall(r"\bPR #?(\d{3,})", prompt or "")[:1]):
                prs[n] = prs.get(n, 0) + total
    out["pr_cycle"] = list(prs.values())
    return out


def build_costs(cfg, now, projects_dir):
    """Costs of the previous full weekly window (the last week that is complete)."""
    end = window_start(now, cfg)
    start = end - timedelta(days=7)
    acts = {}
    for a, xs in sorted(cost_samples(cfg, projects_dir, start, end).items()):
        if xs:
            acts[a] = {"n": len(xs), "mean": round(sum(xs) / len(xs)), "p90": round(p90(xs)), "activity": ACTIVITY_OF.get(a)}
    return {"_doc": "Weighted tokens per action (input + cache_creation + output + cache_read_weight * cache_read), from the "
                    "local transcripts of the window below; recomputed weekly with `token_budget.py costs --write`. "
                    "Agent run = whole subagent transcript, by brief type (first prompt). Tool call = cost of the issuing "
                    "turn / its tool calls. pr_cycle = all agent runs naming one PR. Main-session clock runs cannot be "
                    "told apart locally. Transcripts before 2026-10-27T13:22Z no longer exist.",
            "cache_read_weight": cfg["cache_read_weight"], "window_start": start.isoformat(), "window_end": end.isoformat(),
            "actions": acts}


def estimate(action, state, costs):
    """p90 of this week's recorded actuals (3 or more), else the table's p90, else 0 (unmeasured)."""
    got = [a["actual"] for a in state["actions"] if a["action"] == action]
    if len(got) >= 3:
        return p90(got)
    return costs.get("actions", {}).get(action, {}).get("p90", 0)


def build_plan(cfg, costs, plan):
    budget = cfg["weekly_cap_tokens"] * cfg["project_share"]
    c, a = plan["cadence"], costs["actions"]
    mean = lambda k: a.get(k, {}).get("mean", 0)
    want = {"long": c["long_per_week"] * mean("agent_long"), "shorts": c["shorts_per_week"] * mean("agent_short"),
            "clocks": c["clock_runs_per_week"] * mean("clock_daily") + c["mining_runs_per_week"] * mean("agent_mining"),
            "reviews_prs": c["pr_cycles_per_week"] * mean("pr_cycle")}
    room = budget * (1 - plan["reserve_share"])
    k = min(1.0, room / sum(want.values())) if sum(want.values()) else 1.0   # cadence unaffordable: scale down, say so
    alloc = {x: round(v * k) for x, v in want.items()}
    alloc["reserve"] = round(budget - sum(alloc.values()))
    return dict(plan, budget=round(budget), allocations=alloc, scaled_to_budget=round(k, 3))


def plan_text(s, plan):
    rows = [f"{'activity':12}{'allocation':>14}{'spent':>14}{'left':>14}"]
    for x in ACTIVITIES:
        al, sp = plan["allocations"][x], s["by_activity"][x]
        rows.append(f"{x:12}{al:>14,}{sp:>14,}{al - sp:>14,}")
    rows.append(f"{'total':12}{plan['budget']:>14,}{s['used']:>14,}{plan['budget'] - s['used']:>14,}")
    if plan.get("scaled_to_budget", 1) < 1:
        rows.append(f"cadence scaled to {plan['scaled_to_budget']} of its measured cost to fit the budget")
    return "\n".join(rows)


def status_text(s):
    return (f"week {s['window_start'][:16]}Z..{s['window_end'][:16]}Z\n"
            f"used {s['used']:,} of budget {s['budget']:,} ({s['pct']}%); budget is half of the estimated "
            f"weekly cap {s['weekly_cap_tokens']:,}\n"
            f"projected end of week {s['projected_end_of_week']:,}"
            + ("  (over budget)" if s["projected_end_of_week"] > s["budget"] else ""))


def hook_input():
    if sys.stdin is None or sys.stdin.isatty():
        return {}
    try:
        if not select.select([sys.stdin], [], [], 0.5)[0]:
            return {}
        return json.loads(sys.stdin.read() or "{}")
    except (ValueError, OSError):
        return {}


def escape_allowed(data):
    """Over budget, the session may still report: `token_budget.py status` and `git status`, nothing else."""
    cmd = (data.get("tool_input") or {}).get("command", "") if data.get("tool_name") == "Bash" else ""
    cmd = cmd.strip()
    if not cmd or any(ch in cmd for ch in ";&|`$<>\n"):
        return False
    if cmd == "git status" or cmd.startswith("git status "):
        return True
    return cmd.startswith(("python3 -I -B migration/ops/token_budget.py status", "python3 migration/ops/token_budget.py status",
                           "python3 -I -B migration/ops/token_budget.py plan", "python3 migration/ops/token_budget.py plan"))


def hook_action(data):
    """The action a tool call spends: an agent run by the brief it carries, else the tool kind."""
    tool, inp = data.get("tool_name", ""), data.get("tool_input") or {}
    if tool in ("Agent", "Task"):
        return classify(inp.get("prompt"))
    kind = "mcp" if tool.startswith("mcp__") else tool.lower() if tool in ("Bash", "Read") else None
    return "tool_" + kind if kind else None


def refusal(s, action, est, why):
    return (f"TOKEN_BUDGET_EXCEEDED: {why} (action {action or '-'}, estimate p90 {est:,}; project used {s['used']:,} of "
            f"{s['budget']:,} weighted tokens, {s['pct']}%, half of the weekly cap; reset {s['window_end'][:16]}Z). "
            f"Stop; only `python3 -I -B migration/ops/token_budget.py status` and `git status` are allowed. "
            f"Report to the owner; do not work around it.")


def check(action=None, data=None):
    cfg = load_config()
    s = compute(cfg)
    data = data if data is not None else hook_input()
    action = action or hook_action(data)
    costs = load_json("TOKEN_BUDGET_COSTS", "token_costs.json", {"actions": {}})
    est = estimate(action, s, costs) if action else 0
    why = None
    if s["used"] + est >= s["budget"]:
        why = "the project budget would be crossed" if est else "the project budget is spent"
    elif action in ACTIVITY_OF:
        act = ACTIVITY_OF[action]
        alloc = load_json("TOKEN_BUDGET_PLAN", "token_plan.json", {"allocations": {}})["allocations"].get(act)
        if alloc is not None and s["by_activity"][act] + est >= alloc:
            why = f"the {act} allocation ({alloc:,}, spent {s['by_activity'][act]:,}) would be crossed"
    if why and not (escape_allowed(data) or "token_budget.py status" in str(data.get("prompt", ""))):
        print(refusal(s, action, est, why), file=sys.stderr)
        return 2
    return 0


def record(action=None, actual=None):
    s = compute(use_cache=False)
    costs = load_json("TOKEN_BUDGET_COSTS", "token_costs.json", {"actions": {}})
    acts = list(s["actions"])
    if action and actual is not None:
        acts.append({"action": action, "estimate": estimate(action, s, costs), "actual": int(actual),
                     "at": now_utc().isoformat(timespec="seconds")})
    p = ledger_path(datetime.fromisoformat(s["window_start"]))
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"window_start": s["window_start"], "window_end": s["window_end"], "used": s["used"],
                             "budget": s["budget"], "weekly_cap_tokens": s["weekly_cap_tokens"],
                             "by_activity": s["by_activity"], "actions": acts, "sessions": s["sessions"]},
                            indent=1, sort_keys=True) + "\n")
    print(f"recorded {p}: {s['used']:,}/{s['budget']:,}")
    return 0


def main(argv):
    cmd = argv[1] if len(argv) > 1 else "status"
    arg = lambda n: argv[argv.index(n) + 1] if n in argv and argv.index(n) + 1 < len(argv) else None
    try:
        cfg = load_config()
        projects = os.environ.get("TOKEN_BUDGET_PROJECTS_DIR") or Path.home() / ".claude/projects"
        if cmd == "status":
            print(status_text(compute(use_cache=False)))
        elif cmd == "check":
            return check(arg("--action"))
        elif cmd == "record":
            return record(arg("--action"), arg("--actual"))
        elif cmd == "costs":
            costs = build_costs(cfg, now_utc(), projects)
            if "--write" in argv:
                (HERE / "token_costs.json").write_text(json.dumps(costs, indent=1) + "\n")
            print(json.dumps(costs["actions"], indent=1))
        elif cmd == "plan":
            plan = load_json("TOKEN_BUDGET_PLAN", "token_plan.json")
            if "--write" in argv:
                plan = build_plan(cfg, load_json("TOKEN_BUDGET_COSTS", "token_costs.json"), plan)
                (HERE / "token_plan.json").write_text(json.dumps(plan, indent=1) + "\n")
            print(plan_text(compute(use_cache=False), plan))
        else:
            print("usage: token_budget.py status|plan|costs|check|record", file=sys.stderr)
            return 64
        return 0
    except Exception as e:   # a broken meter is said aloud (exit 1 = non-blocking) and never looks like a green budget
        print(f"TOKEN_BUDGET_ERROR: {type(e).__name__}: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
