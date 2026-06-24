from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_MARKERS = (
    "DELETE OR REPLACE",
    "_Describe the product",
    "_The single most important",
    "_First slice",
)


def test_base_spec_is_active_and_concrete() -> None:
    spec = (ROOT / "specs" / "base.md").read_text(encoding="utf-8")

    assert "PRIORITY 1 (active)" in spec
    assert all(marker not in spec for marker in TEMPLATE_MARKERS)
    assert "Acceptance Signals" in spec
