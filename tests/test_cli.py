"""The helper commands give a clean red error + exit 1 on missing file/config, rather than
dumping a raw traceback (the same treatment init/upgrade/check already have)."""

import json

from conftest import install, run
from grillwork import spec


def test_build_branch_prints_branch_name():
    # Pure string derivation (no file read), so all three commands that touch the branch agree.
    result = run(["build-branch", "specs/006-thing/spec.md"])
    assert result.exit_code == 0
    assert json.loads(result.stdout) == {"branch": "grillwork/build/006-thing"}


def test_markers_missing_file_is_clean(tmp_path):
    result = run(["markers", str(tmp_path / "nope.md")])
    assert result.exit_code == 1
    assert "Error:" in result.output
    assert "Traceback" not in result.output


def test_next_seq_without_install_is_clean(tmp_path):
    result = run(["next-seq", str(tmp_path)])
    assert result.exit_code == 1
    assert "Error:" in result.output
    assert "Traceback" not in result.output


def test_new_spec_without_install_is_clean(tmp_path):
    result = run(["new-spec", "--title", "x", str(tmp_path)])
    assert result.exit_code == 1
    assert "Error:" in result.output
    assert "Traceback" not in result.output


def test_config_dumps_bindings_as_json(tmp_path):
    install(tmp_path, gate="uv run pytest", integration_target="main")
    result = run(["config", str(tmp_path)])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["builder"] == "claude-code"
    assert data["gate"] == "uv run pytest"
    assert data["integration_target"] == "main"
    assert data["improvements"].endswith("improvements.md")


def test_record_finding_appends(tmp_path):
    install(tmp_path)
    path = spec.new_spec(tmp_path, "alpha")["path"]
    result = run(
        ["record-finding", path, "--gap", "size limit", "--why", "not grilled", "--phase", "build"]
    )
    assert result.exit_code == 0 and json.loads(result.output)["count"] == 1


def test_config_without_install_is_clean(tmp_path):
    result = run(["config", str(tmp_path)])
    assert result.exit_code == 1
    assert "Error:" in result.output
    assert "Traceback" not in result.output


def test_spec_status_reads_and_sets(tmp_path):
    install(tmp_path)
    path = spec.new_spec(tmp_path, "alpha")["path"]

    read = run(["spec-status", path])
    assert read.exit_code == 0 and json.loads(read.output)["status"] == "drafting"

    written = run(["spec-status", path, "--set", "accepted"])
    assert written.exit_code == 0 and json.loads(written.output)["status"] == "accepted"


def test_spec_status_unknown_value_is_clean(tmp_path):
    install(tmp_path)
    path = spec.new_spec(tmp_path, "alpha")["path"]
    result = run(["spec-status", path, "--set", "nonsense"])
    assert result.exit_code == 1
    assert "Error:" in result.output
    assert "Traceback" not in result.output
