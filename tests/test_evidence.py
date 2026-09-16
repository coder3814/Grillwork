"""Acceptance suite for spec 010 (the engine boundary: hooks in, trackers out) — the
evidence-disposition half: C-007..C-013.

Authored blind from the spec, before implementation. Everything is driven through the CLI
(`grillwork.cli.app` under CliRunner, the suite's existing idiom) and asserted through
observable seams: file-system state under `evidence/`, `git check-ignore` verdicts, exit
codes, stderr warnings, and the manifest's content. The publish double is a Python script
invoked as a `[sys.executable, script, state-dir]` argv list (Windows/POSIX portable, no
shell) whose exit code, stdout, latency, and invocation count the test controls — harder
than a real hook in each dimension under test (a slow publisher for awaitedness, a
lying-stdout-but-exit-1 publisher for the exit-code-alone rule, a spawn-failing binding for
the re-attempt). It writes a completion marker before exiting, so awaited-ness is asserted
on the hook's own record. All local, no network.

The manifest's exact YAML schema is deliberately the implementation's (the spec pins the
content: one filename + content-hash entry per artifact, URLs + a success timestamp after
publish, an empty artifact list when there are no artifacts) — so `_entries` extracts
filename->hash pairs schema-agnostically rather than asserting key names. Timestamps are
matched as date-time-shaped text (YAML's own timestamp form).
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

from conftest import install, run

# A content hash: bare hex (md5/sha1/sha256/...) or algorithm-prefixed ("sha256:<hex>").
_HASH_RE = re.compile(r"^(?:[A-Za-z0-9_-]+:)?[0-9a-fA-F]{32,}$")
# A recorded success timestamp, as date-time-shaped text (the YAML timestamp form).
_TIMESTAMP_RE = re.compile(r"\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}")


# --- shared drivers (mirrors tests/test_hooks.py; kept local so each module stays
# self-contained while the 007/008 conftest relocates with the worked example) ------------


def _stderr(result):
    try:
        return result.stderr or ""
    except (ValueError, AttributeError):
        return ""


def _all_output(result):
    return (result.output or "") + _stderr(result)


def _init(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    return install(root)


def _config_path(root: Path) -> Path:
    return root / ".grillwork" / "settings" / "config.json"


def _configure(root: Path, *, hooks=None, evidence=None) -> None:
    path = _config_path(root)
    data = json.loads(path.read_text(encoding="utf-8")) or {}
    if hooks is not None:
        data["hooks"] = hooks
    if evidence is not None:
        data["evidence"] = evidence
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _new_spec(root: Path, title: str = "Alpha") -> dict:
    result = run(["new-spec", "--title", title, str(root)])
    assert result.exit_code == 0, _all_output(result)
    return json.loads(result.stdout)


def _set_status(spec_path, status: str):
    return run(["spec-status", str(spec_path), "--set", status])


def _read_status(spec_path) -> str:
    result = run(["spec-status", str(spec_path)])
    assert result.exit_code == 0, _all_output(result)
    return json.loads(result.stdout)["status"]


def _script(dirpath: Path, name: str, body: str) -> Path:
    path = dirpath / name
    path.write_text(body, encoding="utf-8")
    return path


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", *args],
        cwd=cwd, check=True, capture_output=True,
    )


def _ignored(repo: Path, path: Path) -> bool:
    """git's own verdict on a path — check-ignore exits 0 (ignored) or 1 (not)."""
    proc = subprocess.run(
        ["git", "-C", str(repo), "check-ignore", "-q", str(path)], capture_output=True
    )
    assert proc.returncode in (0, 1), proc.stderr
    return proc.returncode == 0


# The awaited publish double. State dir knobs (all test-written files):
#   mode.txt    "ok" (default) -> exit 0; anything else -> exit 1
#   stdout.txt  printed verbatim (the `<artifact-name> <url>` pairs, R-009)
#   sleep.txt   seconds to hold before completing (makes awaited-ness deterministic, C-007)
# It counts every invocation (count.txt — the single-re-attempt proof, C-009) and writes
# marker.txt before exiting (its own completion record).
_PUBLISHER = """\
import os, sys, time
state = sys.argv[1]
def read(name, default=""):
    p = os.path.join(state, name)
    if os.path.exists(p):
        with open(p, encoding="utf-8") as fh:
            return fh.read()
    return default
count = int(read("count.txt", "0").strip() or "0") + 1
with open(os.path.join(state, "count.txt"), "w", encoding="utf-8") as fh:
    fh.write(str(count))
delay = read("sleep.txt", "").strip()
if delay:
    time.sleep(float(delay))
sys.stdout.write(read("stdout.txt", ""))
sys.stdout.flush()
with open(os.path.join(state, "marker.txt"), "w", encoding="utf-8") as fh:
    fh.write("completed")
mode = read("mode.txt", "ok").strip() or "ok"
sys.exit(0 if mode == "ok" else 1)
"""

_URL_LINES = (
    "trace.txt https://example.invalid/blobs/trace\n"
    "report.txt https://example.invalid/blobs/report\n"
)


def _bind_publisher(root: Path, work: Path, *, commit: bool, push: bool,
                    mode: str = "ok", stdout: str = "", sleep: str = "") -> Path:
    """Bind the publish double as the one `publish-evidence` command; return its state dir."""
    state = work / "pubstate"
    state.mkdir(parents=True, exist_ok=True)
    (state / "mode.txt").write_text(mode, encoding="utf-8")
    if stdout:
        (state / "stdout.txt").write_text(stdout, encoding="utf-8")
    if sleep:
        (state / "sleep.txt").write_text(sleep, encoding="utf-8")
    script = _script(work, "publisher.py", _PUBLISHER)
    _configure(
        root,
        hooks={"publish-evidence": [[sys.executable, str(script), str(state)]]},
        evidence={"commit": commit, "push": push},
    )
    return state


def _publish_count(state: Path) -> int:
    path = state / "count.txt"
    return int(path.read_text(encoding="utf-8").strip()) if path.exists() else 0


def _make_evidence(spec_path, artifacts: dict[str, str] | None) -> Path:
    """The build's evidence bundle beside the spec: `bundle.md` (the account) plus artifact
    files. ``artifacts=None`` models an artifact-less bundle."""
    ev = Path(spec_path).parent / "evidence"
    ev.mkdir(parents=True, exist_ok=True)
    (ev / "bundle.md").write_text("# Evidence bundle\n\nThe build's account.\n", encoding="utf-8")
    for name, content in (artifacts or {}).items():
        (ev / name).write_text(content, encoding="utf-8")
    return ev


def _run_manifest(spec_path) -> Path:
    result = run(["evidence-manifest", str(spec_path)])
    assert result.exit_code == 0, (
        f"`grillwork evidence-manifest` failed or is not implemented: {_all_output(result)}"
    )
    manifest = Path(spec_path).parent / "evidence" / "manifest.json"
    assert manifest.exists(), "evidence-manifest wrote no evidence/manifest.json"
    return manifest


def _strings(node):
    if isinstance(node, str):
        yield node
    elif isinstance(node, dict):
        for key, value in node.items():
            if isinstance(key, str):
                yield key
            yield from _strings(value)
    elif isinstance(node, list):
        for item in node:
            yield from _strings(item)


def _entries(evidence_dir: Path, names) -> dict[str, str | None]:
    """filename -> content-hash for each of ``names`` recorded in the manifest, extracted
    schema-agnostically: a name found as a mapping key with a hash-shaped value, or found in
    a mapping alongside a hash-shaped string (nested or not), counts as its entry."""
    data = json.loads((evidence_dir / "manifest.json").read_text(encoding="utf-8"))
    found: dict[str, str | None] = {}

    def visit(node):
        if isinstance(node, dict):
            direct = {k for k in node if isinstance(k, str)}
            direct |= {v for v in node.values() if isinstance(v, str)}
            for name in names:
                if name not in direct or name in found:
                    continue
                value = node.get(name)
                if isinstance(value, str) and _HASH_RE.match(value):
                    found[name] = value
                else:
                    found[name] = next(
                        (s for s in _strings(node) if s != name and _HASH_RE.match(s)), None
                    )
            for value in node.values():
                visit(value)
        elif isinstance(node, list):
            for item in node:
                visit(item)

    visit(data)
    return found


def _has_empty_list(node) -> bool:
    if node == []:
        return True
    if isinstance(node, dict):
        return any(_has_empty_list(v) for v in node.values())
    if isinstance(node, list):
        return any(_has_empty_list(v) for v in node)
    return False


_ARTIFACTS = {"trace.txt": "trace bytes\n", "report.txt": "report bytes\n"}


# --- C-007 -------------------------------------------------------------------------------


def test_publish_awaited_and_recorded(tmp_path):
    """C-007 — with `push: true` and a publish hook that prints `<name> <url>` pairs and
    exits 0, `spec-status --set verified` returns only after the hook completes (it is the
    one AWAITED hook, R-005), and the manifest then carries the printed URLs and a success
    timestamp beside the hashes (R-009/R-010)."""
    root = _init(tmp_path / "repo")
    created = _new_spec(root)
    ev = _make_evidence(created["path"], _ARTIFACTS)
    # A slow publisher: a fire-and-forget dispatch would return before its marker exists.
    state = _bind_publisher(root, tmp_path, commit=True, push=True,
                            stdout=_URL_LINES, sleep="0.7")
    manifest = _run_manifest(created["path"])
    assert "example.invalid" not in manifest.read_text(encoding="utf-8")

    result = _set_status(created["path"], "verified")
    assert result.exit_code == 0, _all_output(result)
    assert (state / "marker.txt").exists(), (
        "the verified flip returned before the publish hook completed — "
        "publish-evidence must be awaited"
    )
    assert _read_status(created["path"]) == "verified"

    text = manifest.read_text(encoding="utf-8")
    assert "https://example.invalid/blobs/trace" in text, "manifest lacks the printed URLs"
    assert "https://example.invalid/blobs/report" in text
    assert _TIMESTAMP_RE.search(text), "manifest records no publish-success timestamp"
    assert ev.exists()  # nothing was pruned by a mere publish


# --- C-008 -------------------------------------------------------------------------------


def test_publish_failure_nonblocking(tmp_path):
    """C-008 — a failed publish never blocks `verified` (R-005/R-010): a hook that exits 1
    leaves the flip standing with a warning naming the hook and no success recorded (even
    though it PRINTED valid-looking pairs — success is the exit code alone); `push: true`
    with no publish command bound, or more than one, likewise stands, warns, and records no
    success."""
    root = _init(tmp_path / "repo")

    # (1) the hook runs and exits 1 — its stdout pairs must NOT be recorded.
    a = _new_spec(root, "Alpha")
    _make_evidence(a["path"], _ARTIFACTS)
    _bind_publisher(root, tmp_path, commit=True, push=True, mode="fail", stdout=_URL_LINES)
    manifest = _run_manifest(a["path"])
    result = _set_status(a["path"], "verified")
    assert result.exit_code == 0, _all_output(result)
    assert _read_status(a["path"]) == "verified"  # verified stands
    assert "publisher.py" in _stderr(result), (
        f"the warning must name the failed hook; stderr={_stderr(result)!r}"
    )
    assert "example.invalid" not in manifest.read_text(encoding="utf-8"), (
        "a nonzero-exiting publish must record no success — exit code governs, not stdout"
    )

    # (2) push: true with NO publish command bound.
    b = _new_spec(root, "Bravo")
    _make_evidence(b["path"], _ARTIFACTS)
    _configure(root, hooks={}, evidence={"commit": True, "push": True})
    manifest_b = _run_manifest(b["path"])
    result = _set_status(b["path"], "verified")
    assert result.exit_code == 0, _all_output(result)
    assert _read_status(b["path"]) == "verified"
    assert "publish" in _stderr(result).lower(), (
        f"push: true with nothing bound must warn; stderr={_stderr(result)!r}"
    )
    assert "example.invalid" not in manifest_b.read_text(encoding="utf-8")

    # (3) push: true with MORE THAN ONE bound (publish-evidence binds at most one, R-010).
    c = _new_spec(root, "Charlie")
    _make_evidence(c["path"], _ARTIFACTS)
    state = _bind_publisher(root, tmp_path, commit=True, push=True, stdout=_URL_LINES)
    script = tmp_path / "publisher.py"
    cmd = [sys.executable, str(script), str(state)]
    _configure(root, hooks={"publish-evidence": [cmd, cmd]},
               evidence={"commit": True, "push": True})
    manifest_c = _run_manifest(c["path"])
    result = _set_status(c["path"], "verified")
    assert result.exit_code == 0, _all_output(result)
    assert _read_status(c["path"]) == "verified"
    assert "publish" in _stderr(result).lower(), (
        f"more than one bound publish command must warn; stderr={_stderr(result)!r}"
    )
    assert "example.invalid" not in manifest_c.read_text(encoding="utf-8"), (
        "no success may be recorded while publish-evidence is misbound"
    )


# --- C-009 -------------------------------------------------------------------------------


def test_close_reattempts_publish_once(tmp_path):
    """C-009 — with push-only disposition (`commit: false, push: true`) and no recorded
    success, `grillwork prune-evidence` re-attempts the publish exactly once: on failure
    (including a spawn failure) it prunes nothing, warns, and exits nonzero — the refusal
    signal the close flow halts on, status staying `accepted`; on success it prunes
    (R-010/R-011)."""
    root = _init(tmp_path / "repo")
    created = _new_spec(root)
    ev = _make_evidence(created["path"], _ARTIFACTS)
    state = _bind_publisher(root, tmp_path, commit=False, push=True,
                            mode="fail", stdout=_URL_LINES)
    _run_manifest(created["path"])
    assert _set_status(created["path"], "approved").exit_code == 0

    # (1) the publish fails: exactly one re-attempt, nothing pruned, nonzero, a warning.
    result = run(["prune-evidence", created["path"]])
    assert result.exit_code != 0, (
        "a failed re-attempt must refuse the prune with a nonzero exit "
        f"(the close flow's halt signal); got {_all_output(result)!r}"
    )
    assert _publish_count(state) == 1, "prune must re-attempt the publish exactly once"
    assert (ev / "trace.txt").exists() and (ev / "report.txt").exists(), (
        "a refused prune must delete nothing"
    )
    assert "publish" in _all_output(result).lower(), "the refusal must warn about the publish"
    assert _read_status(created["path"]) == "approved"  # the refusal changes no status

    # (2) a SPAWN failure counts as a failed publish: same refusal.
    _configure(root, hooks={"publish-evidence": [["grillwork-no-such-publish-cmd-xyz"]]},
               evidence={"commit": False, "push": True})
    result = run(["prune-evidence", created["path"]])
    assert result.exit_code != 0
    assert (ev / "trace.txt").exists() and (ev / "report.txt").exists()

    # (3) re-running close repeats the re-attempt; on success it prunes.
    (state / "mode.txt").write_text("ok", encoding="utf-8")
    (state / "count.txt").write_text("0", encoding="utf-8")
    script = tmp_path / "publisher.py"
    _configure(root, hooks={"publish-evidence": [[sys.executable, str(script), str(state)]]},
               evidence={"commit": False, "push": True})
    result = run(["prune-evidence", created["path"]])
    assert result.exit_code == 0, _all_output(result)
    assert _publish_count(state) == 1, "the successful close re-attempts once, then prunes"
    assert not (ev / "trace.txt").exists() and not (ev / "report.txt").exists(), (
        "a successful re-attempt must unblock the prune"
    )
    assert (ev / "bundle.md").exists() and (ev / "manifest.json").exists(), (
        "the textual account is never pruned"
    )


# --- C-010 -------------------------------------------------------------------------------


def test_prune_matrix(tmp_path):
    """C-010 — the four-combination prune matrix (R-011): artifact bytes are pruned iff
    `commit: false` (gated on recorded publish success when `push: true`); `commit: true`
    evidence is never pruned; `bundle.md` and `manifest.json` always survive."""
    combos = (
        ("commit-true-push-true", True, True),
        ("commit-true-push-false", True, False),
        ("commit-false-push-true", False, True),   # with recorded success
        ("commit-false-push-false", False, False),  # ungated
    )
    for name, commit, push in combos:
        root = _init(tmp_path / name)
        created = _new_spec(root)
        ev = _make_evidence(created["path"], _ARTIFACTS)
        if push:
            state = _bind_publisher(root, tmp_path / f"{name}-pub", commit=commit, push=True,
                                    stdout=_URL_LINES)
        else:
            _configure(root, hooks={}, evidence={"commit": commit, "push": False})
        _run_manifest(created["path"])
        if push:
            # The verified flip fires the awaited publish and records its success.
            result = _set_status(created["path"], "verified")
            assert result.exit_code == 0, f"{name}: {_all_output(result)}"
            assert _publish_count(state) == 1, f"{name}: the publish never ran"
        assert _set_status(created["path"], "approved").exit_code == 0

        result = run(["prune-evidence", created["path"]])
        assert result.exit_code == 0, f"{name}: {_all_output(result)}"
        for artifact in _ARTIFACTS:
            if commit:
                assert (ev / artifact).exists(), (
                    f"{name}: commit: true evidence must never be pruned ({artifact})"
                )
            else:
                assert not (ev / artifact).exists(), (
                    f"{name}: artifact bytes must be pruned ({artifact})"
                )
        assert (ev / "bundle.md").exists(), f"{name}: bundle.md must survive every prune"
        assert (ev / "manifest.json").exists(), f"{name}: manifest.json must survive every prune"


# --- C-011 -------------------------------------------------------------------------------


def test_commit_false_gitignore(tmp_path):
    """C-011 — with `commit: false`, the engine's first write into `evidence/` creates a
    per-evidence-dir `.gitignore` ignoring artifact bytes while re-including `bundle.md`,
    `manifest.json`, and itself (git's own check-ignore verdicts prove it); flipping
    `commit` back to true removes it on the next engine write (R-008)."""
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init")
    _init(root)
    created = _new_spec(root)
    ev = _make_evidence(created["path"], _ARTIFACTS)
    _configure(root, hooks={}, evidence={"commit": False, "push": False})

    _run_manifest(created["path"])  # the engine's first write into evidence/
    gitignore = ev / ".gitignore"
    assert gitignore.exists(), "commit: false must write evidence/.gitignore"
    for artifact in _ARTIFACTS:
        assert _ignored(root, ev / artifact), f"artifact {artifact} must be git-ignored"
    for account in ("bundle.md", "manifest.json", ".gitignore"):
        assert not _ignored(root, ev / account), f"{account} must stay trackable (re-included)"

    _configure(root, hooks={}, evidence={"commit": True, "push": False})
    _run_manifest(created["path"])  # the next engine write, after the flip back
    assert not gitignore.exists(), "flipping commit back to true must remove the .gitignore"
    assert not _ignored(root, ev / "trace.txt"), "artifacts must be trackable again"


# --- C-012 -------------------------------------------------------------------------------


def test_manifest_hashes(tmp_path):
    """C-012 — `grillwork evidence-manifest <spec>` writes one filename + content-hash entry
    per artifact; changing an artifact and re-running changes exactly that hash; a bundle
    with zero artifacts yields a manifest with an empty artifact list, still written
    (R-009). Deterministic, no publish involved."""
    root = _init(tmp_path / "repo")
    created = _new_spec(root)
    ev = _make_evidence(created["path"], _ARTIFACTS)

    _run_manifest(created["path"])
    before = _entries(ev, set(_ARTIFACTS))
    assert set(before) == set(_ARTIFACTS), (
        f"one entry per artifact; got entries for {sorted(before)}"
    )
    for artifact, digest in before.items():
        assert digest, f"no content hash recorded for {artifact}"

    (ev / "trace.txt").write_text("changed bytes\n", encoding="utf-8")
    _run_manifest(created["path"])
    after = _entries(ev, set(_ARTIFACTS))
    assert after["trace.txt"] != before["trace.txt"], (
        "a changed artifact must change its recorded hash"
    )
    assert after["report.txt"] == before["report.txt"], (
        "an unchanged artifact's hash must not change"
    )

    # Zero artifacts: the manifest is still written, with an empty artifact list, and the
    # account files are not themselves artifact entries.
    empty = _new_spec(root, "Bravo")
    ev_empty = _make_evidence(empty["path"], None)
    manifest = _run_manifest(empty["path"])
    data = json.loads(manifest.read_text(encoding="utf-8"))
    assert _has_empty_list(data), (
        "an artifact-less bundle must yield a manifest carrying an empty artifact list"
    )
    account = _entries(ev_empty, {"bundle.md", "manifest.json"})
    assert not any(account.values()), (
        f"bundle.md/manifest.json are the account, not artifacts; got {account}"
    )


# --- C-013 -------------------------------------------------------------------------------


def test_refire_invalidates_success(tmp_path):
    """C-013 — after a re-verification bounce, firing `publish-evidence` again invalidates
    the prior success record: a stale success must never gate a prune of new bytes, so the
    prune refuses until the NEW publish succeeds (R-010)."""
    root = _init(tmp_path / "repo")
    created = _new_spec(root)
    ev = _make_evidence(created["path"], _ARTIFACTS)
    state = _bind_publisher(root, tmp_path, commit=False, push=True, stdout=_URL_LINES)
    manifest = _run_manifest(created["path"])

    # First verification: the publish succeeds and its success is recorded.
    result = _set_status(created["path"], "verified")
    assert result.exit_code == 0, _all_output(result)
    assert (state / "marker.txt").exists(), "the first publish never ran"
    assert "example.invalid" in manifest.read_text(encoding="utf-8"), (
        "the first publish's success (URLs) must be recorded before the bounce"
    )

    # The bounce, then a re-verification whose publish now FAILS.
    assert _set_status(created["path"], "building").exit_code == 0
    (state / "mode.txt").write_text("fail", encoding="utf-8")
    result = _set_status(created["path"], "verified")
    assert result.exit_code == 0, _all_output(result)  # a failed publish never blocks verified

    # The stale success must not gate the prune: it refuses until a new success exists.
    result = run(["prune-evidence", created["path"]])
    assert result.exit_code != 0, (
        "the re-fire must have invalidated the prior success — the prune may not ride a "
        "stale record"
    )
    assert (ev / "trace.txt").exists() and (ev / "report.txt").exists(), (
        "a refused prune deletes nothing"
    )

    # Once the new publish succeeds, the prune goes through.
    (state / "mode.txt").write_text("ok", encoding="utf-8")
    result = run(["prune-evidence", created["path"]])
    assert result.exit_code == 0, _all_output(result)
    assert not (ev / "trace.txt").exists() and not (ev / "report.txt").exists()
    assert (ev / "bundle.md").exists() and (ev / "manifest.json").exists()
