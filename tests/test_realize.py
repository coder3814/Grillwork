"""Realizing the engine's command files from the profile an install recorded.

The contract this protects is that two agents realizing the same version produce the same
bytes — so these assert on the output exactly, not on it being roughly right.
"""

from __future__ import annotations

import json

import pytest
from conftest import (
    CLAUDE_PROFILE,
    ENGINE,
    commit,
    git,
    install,
    run,
    source_archive,
    update,
)
from grillwork import realize

COMMAND_SOURCE = """---
name: grillwork-specify
kind: command
description: "Grill a request into a spec. Explicit invocation only."
---

Grill this into a spec:

{{ARGS}}
"""

SUBAGENT_SOURCE = """---
name: grillwork-dor-reviewer
kind: subagent
description: "Internal to a running /grillwork-specify, and inert without it."
tools: Read, Grep, Glob
---

Dispose the spec READY or NOT READY.
"""


def _profile(**overrides) -> realize.Profile:
    data = {**CLAUDE_PROFILE, **overrides}
    return realize.Profile(
        targets=data["targets"],
        argument_placeholder=data["argument_placeholder"],
        keys=data.get("keys", {}),
        banner=data["banner"],
        extension=data["extension"],
    )


# --------------------------------------------------------------------------------------
# The transform
# --------------------------------------------------------------------------------------


def test_render_produces_the_realized_file_exactly():
    kind, name, text = realize.render(COMMAND_SOURCE, _profile())
    assert (kind, name) == ("command", "grillwork-specify")
    assert text == (
        "---\n"
        "name: grillwork-specify\n"
        'description: "Grill a request into a spec. Explicit invocation only."\n'
        "---\n"
        "\n"
        "<!-- Installed by Grillwork from engine/commands/ — do not edit. -->\n"
        "<!-- Re-running the install prompt rewrites this file wholesale. -->\n"
        "\n"
        "Grill this into a spec:\n"
        "\n"
        "$ARGUMENTS\n"
    )


def test_render_drops_kind_and_keeps_tools():
    # `kind` is Grillwork's routing key and means nothing to a harness; `tools` is the
    # harness's own and has to survive.
    _, _, text = realize.render(SUBAGENT_SOURCE, _profile())
    assert "kind:" not in text
    assert "tools: Read, Grep, Glob\n" in text


def test_render_spells_keys_the_way_the_profile_says():
    # A harness that calls it `allowed-tools` gets `allowed-tools`, with no code here knowing
    # that any such harness exists.
    _, _, text = realize.render(SUBAGENT_SOURCE, _profile(keys={"tools": "allowed-tools"}))
    assert "allowed-tools: Read, Grep, Glob\n" in text
    assert "\ntools:" not in text


def test_render_leaves_description_bytes_untouched():
    # Descriptions are prose full of colons, quotes and em dashes. Rewriting the frontmatter
    # line by line rather than re-serializing is what keeps them byte-identical.
    source_text = COMMAND_SOURCE.replace(
        '"Grill a request into a spec. Explicit invocation only."',
        '"Grill: a request — never on your own \'judgment\'."',
    )
    _, _, text = realize.render(source_text, _profile())
    assert 'description: "Grill: a request — never on your own \'judgment\'."' in text


def test_render_substitutes_every_placeholder():
    _, _, text = realize.render(COMMAND_SOURCE.replace("{{ARGS}}", "{{ARGS}} and {{ARGS}}"), _profile())
    assert "{{ARGS}}" not in text
    assert "$ARGUMENTS and $ARGUMENTS" in text


@pytest.mark.parametrize(
    "bad, message",
    [
        ("no frontmatter at all\n", "frontmatter fence"),
        ("---\nname: x\n", "never closed"),
        ("---\nname: x\n---\n\nbody\n", "`kind:`"),
        ("---\nkind: command\n---\n\nbody\n", "`name:`"),
    ],
)
def test_render_refuses_a_malformed_source(bad, message):
    with pytest.raises(ValueError, match=message):
        realize.render(bad, _profile())


def test_every_shipped_command_realizes(tmp_path):
    # The real engine, not a fixture: each of the fourteen has to come out with a kind the
    # profile knows and a name to be filed under.
    profile = _profile()
    for src in (ENGINE / "commands").glob("*.md"):
        kind, name, text = realize.render(src.read_text(encoding="utf-8"), profile)
        assert kind in profile.targets, f"{src.name} has kind {kind!r}"
        assert name == src.stem
        assert "{{ARGS}}" not in text


# --------------------------------------------------------------------------------------
# The profile
# --------------------------------------------------------------------------------------


def test_missing_profile_is_an_ordinary_refusal(tmp_path):
    root = install(tmp_path)
    with pytest.raises(realize.ProfileError, match="predates it"):
        realize.load_profile(root)


def test_a_format_that_cannot_be_written_is_refused(tmp_path):
    # Honest refusal rather than writing the wrong format and reporting success.
    root = install(tmp_path)
    realize.profile_path(root).write_text(
        json.dumps({**CLAUDE_PROFILE, "format": "toml"}), encoding="utf-8"
    )
    with pytest.raises(realize.ProfileError, match="mechanically"):
        realize.load_profile(root)


@pytest.mark.parametrize("missing", ["targets", "argument_placeholder", "banner"])
def test_an_incomplete_profile_is_refused(tmp_path, missing):
    root = install(tmp_path)
    data = {k: v for k, v in CLAUDE_PROFILE.items() if k != missing}
    realize.profile_path(root).write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(realize.ProfileError):
        realize.load_profile(root)


# --------------------------------------------------------------------------------------
# End to end, through the update
# --------------------------------------------------------------------------------------


def test_update_writes_every_command_and_subagent(repo, tmp_path):
    payload = update(repo, source_archive(tmp_path))

    assert payload["realized"] is True
    commands = sorted(p.name for p in (repo / ".claude" / "commands").glob("*.md"))
    agents = sorted(p.name for p in (repo / ".claude" / "agents").glob("*.md"))
    # Classified from the frontmatter, not by searching the text: a command body may well
    # discuss `kind: subagent`, and grillwork-upgrade's does.
    sources = {
        src.stem: realize.render(src.read_text(encoding="utf-8"), _profile())[0]
        for src in (ENGINE / "commands").glob("*.md")
    }
    expected_commands = sorted(
        f"{name}.md" for name, kind in sources.items() if kind == "command"
    )
    expected_agents = sorted(
        f"{name}.md" for name, kind in sources.items() if kind == "subagent"
    )
    assert commands == expected_commands
    assert agents == expected_agents
    assert len(payload["written"]) == len(sources)


def test_update_overwrites_an_edited_command(repo, tmp_path):
    # The do-not-edit banner says this will happen; the point is that it actually does.
    target = repo / ".claude" / "commands"
    target.mkdir(parents=True)
    (target / "grillwork-specify.md").write_text("someone edited this\n", encoding="utf-8")
    commit(repo, "edited")

    update(repo, source_archive(tmp_path))
    assert "someone edited this" not in (target / "grillwork-specify.md").read_text(encoding="utf-8")


def test_update_sweeps_a_retired_command(repo, tmp_path):
    # Nothing else removes these: realizing only overwrites the names it knows, so without the
    # sweep a retired command survives every future update, still offering itself to an agent.
    target = repo / ".claude" / "commands"
    target.mkdir(parents=True)
    retired = target / "grillwork-verify.md"
    retired.write_text("a command that no longer exists\n", encoding="utf-8")
    commit(repo, "retired command")

    payload = update(repo, source_archive(tmp_path))

    assert not retired.exists()
    assert str(retired) in payload["removed"]


def test_update_leaves_the_persons_own_commands_alone(repo, tmp_path):
    # The prefix is reserved; everything else in that directory is theirs.
    target = repo / ".claude" / "commands"
    target.mkdir(parents=True)
    mine = target / "deploy.md"
    mine.write_text("my own command\n", encoding="utf-8")
    commit(repo, "my command")

    update(repo, source_archive(tmp_path))
    assert mine.read_text(encoding="utf-8") == "my own command\n"


def test_update_without_a_profile_still_updates_the_engine(tmp_path):
    # An install too old to have a profile is not a failure: the engine is replaced, and
    # `realized` comes back false so the agent that ran it knows to finish the job.
    root = install(tmp_path / "old")
    git(root, "init", "-q")
    commit(root)

    result = run(["update", "--archive", str(source_archive(tmp_path)), str(root)])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["realized"] is False
    assert payload["written"] == []
    assert "Commands not realized" in result.stderr
    # The sources are there for the agent to realize from, and the engine is current.
    assert (root / ".grillwork" / "engine" / "commands" / "grillwork-specify.md").is_file()
