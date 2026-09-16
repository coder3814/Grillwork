"""The harness seam — engine content a binding can read without importing the engine.

An adopter's harness lives on the far side of the engine's boundary, and the boundary is the
repo: the payload is a doorbell and the files are the truth. But three things a harness needs
are facts about the *engine* rather than about the change — which files in a bundle are
artifacts rather than the textual account, what the acceptance package says, and what the
lifecycle's stages are. A harness that restates any of them is a fork that drifts, and the
first external install proved it: the worked example had re-derived two of the three and
imported the third, which worked only inside this repo and only from Python.

So the engine prints them. These tests hold that surface to the same contract as the rest of
the CLI — one JSON object on stdout, nothing else — and pin the two rules a binding must not
have to guess: the account files are not artifacts, and the model is the whole model.

Driven through the CLI in-process (the suite's idiom), so what is asserted is exactly what a
harness parses.
"""

from __future__ import annotations

import json
from pathlib import Path

from conftest import install, method_text, run

# The read surface, as `hooks-contract.md` states it. Named here so a command added to the CLI
# without being written into the contract — or removed from one and not the other — fails.
READ_SURFACE = ("statuses", "spec-status", "evidence-artifacts", "package")


def _json(result):
    assert result.exit_code == 0, result.output
    assert result.stderr == "", f"stdout must be the only channel: {result.stderr!r}"
    return json.loads(result.stdout)


def _spec_with_evidence(tmp_path, files: dict[str, str]):
    """A repo holding one spec whose evidence dir contains ``files``. Returns the spec path."""
    root = install(tmp_path / "repo")
    created = json.loads(run(["new-spec", "--title", "Export CSV", str(root)]).stdout)
    spec_path = Path(created["path"])
    evidence = spec_path.parent / "evidence"
    evidence.mkdir(parents=True, exist_ok=True)
    for name, content in files.items():
        (evidence / name).write_text(content, encoding="utf-8")
    return str(spec_path)


# --- the contract ---------------------------------------------------------------------------


def test_the_contract_states_the_read_surface():
    """A harness is told to run these and to restate nothing, which only holds if the contract
    is where they are written down. It is also what the version integer now covers: the
    versioning rule has to name the read surface, or a shape change here carries no signal."""
    contract = method_text("hooks-contract.md")

    for command in READ_SURFACE:
        assert f"`{command}" in contract, f"the contract does not state `{command}`"
    assert "read surface" in contract.lower()
    assert "Contract version: 5" in contract


def test_every_stated_command_is_really_there():
    """The contract is normative, so a command it names must exist and must answer. Names drift
    from implementations quietly; this is the check that makes that loud."""
    for command in READ_SURFACE:
        result = run([command, "--help"])
        assert result.exit_code == 0, f"`{command}` is stated in the contract but {result.output}"


# --- the lifecycle ------------------------------------------------------------------------


def test_statuses_prints_the_lifecycle_in_order(tmp_path):
    """A board needs one column per stage, and a notifier needs to know which stage is last.
    Order is part of the answer: these are a sequence, not a set."""
    listed = _json(run(["statuses"]))["statuses"]

    assert listed[0] == "drafting"
    assert listed[-1] == "closed"
    assert "verified" in listed and "accepted" in listed
    assert len(listed) == len(set(listed))


# --- the evidence bundle's artifacts ------------------------------------------------------


def test_evidence_artifacts_excludes_the_account_files(tmp_path):
    """The rule a publisher must not restate. `bundle.md`, `manifest.json` and `.gitignore` are
    the textual record of the change — publishing them would upload the engine's own bookkeeping
    and, for `manifest.json`, the very file the URLs are about to be written into."""
    spec = _spec_with_evidence(
        tmp_path,
        {
            "C-001-suite.log": "pass\n",
            "screenshot.png": "bytes\n",
            "bundle.md": "## Verdict\nDONE\n",
            "manifest.json": '{"artifacts": []}\n',
            ".gitignore": "*\n",
        },
    )

    listed = _json(run(["evidence-artifacts", spec]))

    assert listed["artifacts"] == ["C-001-suite.log", "screenshot.png"]
    assert listed["dir"].endswith("evidence")


def test_evidence_artifacts_agrees_with_what_the_manifest_hashes(tmp_path):
    """The listing and the manifest must name the same files: the manifest is where a publish
    success records a URL per artifact, so a publisher told about a file the manifest does not
    carry would report a URL the engine then drops."""
    spec = _spec_with_evidence(
        tmp_path,
        {"a.log": "a\n", "b.log": "b\n", "bundle.md": "x\n", ".gitignore": "*\n"},
    )

    listed = _json(run(["evidence-artifacts", spec]))["artifacts"]
    hashed = _json(run(["evidence-manifest", spec]))["artifacts"]

    assert listed == hashed


def test_an_empty_bundle_lists_nothing_rather_than_failing(tmp_path):
    """Nothing to publish is an ordinary state, not an error — a spec whose evidence is all
    account and no artifact still has to sync and still has to publish successfully."""
    spec = _spec_with_evidence(tmp_path, {"bundle.md": "## Verdict\nDONE\n"})

    assert _json(run(["evidence-artifacts", spec]))["artifacts"] == []


# --- the acceptance package ---------------------------------------------------------------


def test_package_prints_the_whole_model(tmp_path):
    """Every field of the neutral model reaches a binding. The point of printing it is that a
    renderer never re-parses the spec files; a field left out of the JSON is a field the
    renderer would have to go back to disk for."""
    spec = _spec_with_evidence(tmp_path, {"bundle.md": "## Verdict\nDONE\n"})

    model = _json(run(["package", spec]))

    assert set(model) == {
        "state", "status", "summary", "what_was_done", "evidence", "evidence_map_present",
        "verdict", "base_sha", "candidate_sha", "findings", "amendments", "bundle_present",
        "missing_sections",
    }


def test_package_carries_the_spec_status_and_its_evidence_rows(tmp_path):
    """The two things the worked example was re-deriving for itself: the status (which header
    row holds it, and how it is spelled, is the engine's) and the evidence map (whose artifact
    refs and on-disk presence drive every link a renderer forms)."""
    spec = _spec_with_evidence(
        tmp_path,
        {
            "C-001-suite.log": "pass\n",
            "bundle.md": (
                "## What was done\n\nMade the thing.\n\n"
                "## Revisions\n\nBase: aaaa1111\nCandidate: bbbb2222\n\n"
                "## Evidence map\n\n"
                "| Criterion | Shows | Artifact(s) |\n|---|---|---|\n"
                "| C-001 | the suite is green | evidence/C-001-suite.log |\n"
                "| C-002 | a thing that is gone | evidence/absent.log |\n\n"
                "## Verdict\n\nDONE\n"
            ),
        },
    )
    run(["spec-status", spec, "--set", "verified"])

    model = _json(run(["package", spec]))

    assert model["status"] == "verified"
    assert model["state"] == "C"
    assert (model["base_sha"], model["candidate_sha"]) == ("aaaa1111", "bbbb2222")
    assert [row["criterion"] for row in model["evidence"]] == ["C-001", "C-002"]
    # `present` is the flag a renderer turns into a missing-artifact note instead of a link.
    assert model["evidence"][0]["artifacts"][0] == {
        "ref": "evidence/C-001-suite.log", "present": True
    }
    assert model["evidence"][1]["artifacts"][0]["present"] is False


def test_package_reports_a_missing_bundle_as_content_not_an_error(tmp_path):
    """The model never raises on degenerate content (a renderer turns the flags into explicit
    notes), and the CLI must not turn it into a failure either — a spec that has not been built
    yet is the ordinary early case, and a board still has to show it."""
    root = install(tmp_path / "repo")
    created = json.loads(run(["new-spec", "--title", "Not built yet", str(root)]).stdout)

    model = _json(run(["package", created["path"]]))

    assert model["bundle_present"] is False
    assert model["state"] == "A"
    assert "Verdict" in model["missing_sections"]
