"""Realizing the engine's command files into the harness's own layout.

A realized command is not a copy of its source in `engine/commands/`. It is derived from it:
the `kind:` key is dropped, the remaining keys are spelled the way the harness spells them,
`{{ARGS}}` becomes the harness's argument placeholder, and a do-not-edit banner is prepended.
`INSTALL.md` specifies that derivation in prose, and the agent doing a fresh install performs
it — it is the one part of an install that needs to know what harness it is running in.

**The install writes down what it decided**, in `settings/realization.json`, and an update
re-applies it mechanically. That is what keeps the engine neutral: nothing here names a
harness, or branches on which one is configured. It reads a profile the adopter's own install
wrote and follows it, so supporting another harness costs a profile rather than a code path.

The profile records *rules*, not a file list, so a command that is new or renamed in the
version being installed is realized correctly too — which a manifest of paths could not do.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

PROFILE_FILENAME = "realization.json"

# The only frontmatter shape this can emit. A harness whose commands are TOML, JSON, or bare
# files is expressible as a profile only once someone writes the code for it — and until then
# the honest answer is to refuse and let the install prompt's agent do the realizing, rather
# than to write a file in the wrong format and report success.
FRONTMATTER_FORMAT = "yaml-frontmatter"

# Grillwork's routing key: it says which target a file belongs to, and means nothing to any
# harness, so it is consumed here and never written out.
_KIND_KEY = "kind"

# Substituted into every body. The only placeholder the engine's command sources use.
_ARGS_PLACEHOLDER = "{{ARGS}}"

BANNER_TEXT = (
    "Installed by Grillwork from engine/commands/ — do not edit.",
    "Re-running the install prompt rewrites this file wholesale.",
)

_FENCE = "---"
_KEY_RE = re.compile(r"^([A-Za-z0-9_-]+):\s*(.*)$")


class ProfileError(Exception):
    """Raised when no usable realization profile can be read."""


@dataclass(frozen=True)
class Profile:
    """How this repo's install realized the commands, so an update can do it again."""

    # Where each `kind:` lands, as a repo-relative directory.
    targets: dict[str, str]
    # The harness's argument placeholder, substituted for `{{ARGS}}`.
    argument_placeholder: str
    # Source key -> the key this harness spells it with. Anything unlisted passes through.
    keys: dict[str, str]
    # A one-line comment template containing `{text}`, for the do-not-edit banner.
    banner: str
    # The realized files' extension, including the dot.
    extension: str

    def target_dir(self, root: Path, kind: str) -> Path:
        try:
            return root / self.targets[kind]
        except KeyError:
            raise ProfileError(
                f"The realization profile has no target directory for kind {kind!r}; "
                f"it knows {sorted(self.targets)}."
            ) from None


def profile_path(root: Path) -> Path:
    return root / ".grillwork" / "settings" / PROFILE_FILENAME


def load_profile(root: Path) -> Profile:
    """Read the profile this repo's install wrote.

    Raises `ProfileError` when there is none, or when it describes something this cannot emit.
    Both are ordinary: an install predating the profile has no file, and a harness whose
    commands are not YAML-frontmatter markdown cannot be served by the current code. The
    caller's job is to fall back, not to guess.
    """
    path = profile_path(root)
    if not path.exists():
        raise ProfileError(
            f"No realization profile at {path}. This install predates it, or was made without "
            "one, so the command files have to be realized by the install prompt instead."
        )
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as e:
        raise ProfileError(f"{path} is not valid JSON: {e}") from e
    if not isinstance(data, dict):
        raise ProfileError(f"{path} must be a mapping.")

    fmt = data.get("format", FRONTMATTER_FORMAT)
    if fmt != FRONTMATTER_FORMAT:
        raise ProfileError(
            f"{path} asks for {fmt!r}, and only {FRONTMATTER_FORMAT!r} can be written "
            "mechanically. Realize the commands with the install prompt instead."
        )

    targets = data.get("targets")
    if not isinstance(targets, dict) or not targets:
        raise ProfileError(f"{path} has no `targets` mapping kinds to directories.")
    placeholder = data.get("argument_placeholder")
    if not isinstance(placeholder, str) or not placeholder:
        raise ProfileError(f"{path} has no `argument_placeholder`.")
    banner = data.get("banner")
    if not isinstance(banner, str) or "{text}" not in banner:
        raise ProfileError(f"{path} has no `banner` template containing `{{text}}`.")
    keys = data.get("keys")

    return Profile(
        targets={str(k): str(v) for k, v in targets.items()},
        argument_placeholder=placeholder,
        keys={str(k): str(v) for k, v in keys.items()} if isinstance(keys, dict) else {},
        banner=banner,
        extension=str(data.get("extension") or ".md"),
    )


def render(source_text: str, profile: Profile) -> tuple[str, str, str]:
    """Realize one command source. Returns its kind, its name, and the file to write.

    The frontmatter is rewritten line by line rather than parsed and re-serialized. Values here
    are prose containing colons, quotes and em dashes — a round trip through a serializer would
    requote them, and the install contract is that two agents realizing the same version
    produce the same bytes. Only the key is touched.
    """
    lines = source_text.splitlines()
    if not lines or lines[0].strip() != _FENCE:
        raise ValueError("A command source must open with a `---` frontmatter fence.")
    try:
        close = lines.index(_FENCE, 1)
    except ValueError:
        raise ValueError("A command source's frontmatter fence is never closed.") from None

    kind = name = ""
    out_keys: list[str] = []
    for line in lines[1:close]:
        match = _KEY_RE.match(line)
        if not match:
            # A continuation or a blank line: carried through untouched.
            out_keys.append(line)
            continue
        key, value = match.group(1), match.group(2)
        if key == _KIND_KEY:
            kind = value.strip()
            continue
        if key == "name":
            name = value.strip()
        out_keys.append(f"{profile.keys.get(key, key)}: {value}")

    if not kind:
        raise ValueError("A command source must carry a `kind:` key.")
    if not name:
        raise ValueError("A command source must carry a `name:` key.")

    body = "\n".join(lines[close + 1 :]).lstrip("\n")
    body = body.replace(_ARGS_PLACEHOLDER, profile.argument_placeholder)
    banner = "\n".join(profile.banner.format(text=t) for t in BANNER_TEXT)

    return kind, name, f"{_FENCE}\n" + "\n".join(out_keys) + f"\n{_FENCE}\n\n{banner}\n\n{body}\n"


def realize_all(commands_dir: Path, root: Path, profile: Profile) -> list[Path]:
    """Realize every command source into its target directory; return what was written."""
    written: list[Path] = []
    for src in sorted(commands_dir.glob("*.md")):
        kind, name, text = render(src.read_text(encoding="utf-8"), profile)
        target = profile.target_dir(root, kind)
        target.mkdir(parents=True, exist_ok=True)
        path = target / f"{name}{profile.extension}"
        path.write_text(text, encoding="utf-8")
        written.append(path)
    return written


def sweep_orphans(root: Path, profile: Profile, written: list[Path]) -> list[Path]:
    """Delete `grillwork-*` files in the target directories that this run did not write.

    The prefix is reserved, so anything else wearing it is a command the current version no
    longer has — retired or renamed. Nothing else removes these: realizing only overwrites the
    names it knows, so without this sweep a retired command survives every future update, still
    offering itself to any agent that reads its description.
    """
    kept = {p.resolve() for p in written}
    removed: list[Path] = []
    for relative in sorted(set(profile.targets.values())):
        directory = root / relative
        if not directory.is_dir():
            continue
        for path in sorted(directory.glob(f"grillwork-*{profile.extension}")):
            if path.resolve() not in kept:
                path.unlink()
                removed.append(path)
    return removed
