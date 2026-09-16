from conftest import install, method_text

"""Spec 003 — the open-capacity context seed for grilling intake.

Content-presence and stamping tests over the Griller role asset (`roles/griller.md`).
Each test binds to one acceptance criterion of spec 003 and is named so that
`pytest -k <selector>` selects exactly it (see the spec's Evidence Plan table).

The asset prose wraps across many lines, so a multi-word needle can straddle a newline.
We normalize whitespace before matching — collapse every run of whitespace to a single
space — and assert single-spaced needles against it. Each needle captures the *substance*
of its criterion, so removing or garbling that intake element from `griller.md` fails the
test (tag-truth).
"""


# C-001 / R-001 — the canonical invitation, carried in griller.md verbatim so the framing
# cannot drift on recompile. The em dash is U+2014 and the apostrophes are U+0027, matching
# the asset byte for byte; kept as a single literal so this stays the strongest form of the
# assertion. (Written with — so this source file is pure ASCII yet identical in value.)
INVITATION = (
    "Before I draft, share any context you already hold, in whatever depth "
    "— one line or a long brief. Complete details aren't needed; "
    "I'll grill for whatever's missing."
)


def _asset_text() -> str:
    """The Griller asset with whitespace normalized to single spaces."""
    return " ".join(method_text("roles", "griller.md").split())


def test_invitation():
    """C-001: the asset contains the canonical invitation text verbatim."""
    assert INVITATION in _asset_text()


def test_reconcile():
    """C-002: all three reconcile sub-rules are present."""
    text = _asset_text()
    # settled decisions -> drafted content, and NOT re-grilled
    assert "become drafted spec content and are **not** re-grilled" in text
    # stated open questions -> [GAP] markers
    assert "Stated open questions become `[GAP G-###]` markers" in text
    # every claim checked against the repo (never transcribed uncritically)
    assert "Every claim is still checked against the repo" in text


def test_structured():
    """C-003: structured vs. unstructured seed, the list-back, and never-pre-structure."""
    text = _asset_text()
    # structured seed: its own sections give the settled/open split
    assert "its sections give the settled/open split" in text
    # unstructured seed: conservative inference, uncertain -> [GAP]
    assert (
        "anything you are not confident is settled becomes a `[GAP]` rather than being baked in"
        in text
    )
    # list back what was taken as already-settled
    assert "briefly **list back** what you took as already-settled" in text
    # never ask the requester to pre-structure the seed
    assert "Never ask the requester to pre-structure" in text


def test_contradiction():
    """C-004: both contradiction branches and the unsure -> [GAP] tie-breaker."""
    text = _asset_text()
    # genuine conflict -> surface as [GAP] and grill
    assert (
        "surface it as a `[GAP]` naming the contradiction and grill it like any other" in text
    )
    # plain repo factual error -> correct to the verified repo fact
    assert "correct it to the verified repo fact and note it" in text
    # tie-breaker keeping the two branches disjoint
    assert (
        "when you are unsure whether a seed claim is a settled repo fact, "
        "mark a `[GAP]` and grill rather than correcting silently" in text
    )


def test_done_seeding():
    """C-005: the done-seeding checkpoint precedes structured grilling."""
    text = _asset_text()
    assert (
        "Before structured grilling begins, ask the requester whether they are done seeding context"
        in text
    )
    assert "begin structured grilling only after they confirm they are finished" in text


def test_exempt():
    """C-006: the intake is exempt from the grilling discipline, which resumes at grilling."""
    text = _asset_text()
    # the intake/seed step is exempt from the one-line / option-table discipline
    assert (
        "pre-grilling phase, **exempt** from the one-line-of-inquiry / option-table discipline"
        in text
    )
    # that discipline resumes once structured grilling starts
    assert "discipline **resumes** once structured grilling starts" in text


def test_ephemeral():
    """C-007: the seed is ephemeral drafting input, not a persisted repo artifact."""
    text = _asset_text()
    assert "The seed is ephemeral." in text
    assert "persist no new file for it" in text


def test_ordering():
    """C-009: seed-first-then-improvements ordering and the not-already-settled rule."""
    text = _asset_text()
    # draft from the seed first
    assert "Draft from the seed first" in text
    # then consult the curated lessons at the improvements path
    assert "Then consult the curated lessons" in text
    assert "the `improvements` path" in text
    # raise recurring gap-classes only where the seed/repo have not already settled it
    assert "only where the seed and repo have not already settled it" in text


def test_stamped(tmp_path):
    """C-008 / R-008: the installed griller.md carries the invitation, and the
    grillwork-specify command body does NOT — the substance stayed in the role, not the
    command that launches it."""
    install(tmp_path)

    stamped_role = tmp_path / ".grillwork" / "engine" / "roles" / "griller.md"
    role_text = " ".join(stamped_role.read_text(encoding="utf-8").split())
    assert INVITATION in role_text

    specify_text = " ".join(method_text("commands", "grillwork-specify.md").split())
    assert INVITATION not in specify_text
