"""A24 rolling + public ATC + group-balanced BC, separately versioned."""
from pathlib import Path
import sys

VERSION = 'A24_ROLLING_ATC_BC50_V1'
WIDTH = 50


def load_components():
    experiments = Path(__file__).resolve().parent.parent
    if str(experiments) not in sys.path:
        sys.path.insert(0, str(experiments))
    from a24_logic_repair_20261019 import load_components as load_base
    base = load_base()
    from .policy import Policy
    base.Policy = Policy
    base.version = VERSION
    return base
