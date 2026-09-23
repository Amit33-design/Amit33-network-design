"""Python must reproduce the fixture the TypeScript suite also checks."""
import json

from backend.parity_fixtures import OUT, generate


def test_python_still_matches_the_shared_parity_fixture():
    """If this fails, either Python changed on purpose — regenerate with
    `python -m backend.parity_fixtures` and the TS suite will then demand the
    same change in exitRules.ts / pairTrading.ts — or Python drifted by
    accident, and the fixture just caught it."""
    with open(OUT) as f:
        committed = json.load(f)
    assert generate() == committed
