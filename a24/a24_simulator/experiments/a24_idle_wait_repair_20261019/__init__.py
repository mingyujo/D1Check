"""Idle WAIT dominance guard, separate from the completed ATC-BC experiment."""
from pathlib import Path
import sys

VERSION = 'A24_IDLE_WAIT_DOMINANCE_V1'
NETWORK_VERSION = 'A24_ROLLING_ATC_BC50_V1'


def load_components():
    experiments = str(Path(__file__).resolve().parent.parent)
    if experiments not in sys.path:
        sys.path.insert(0, experiments)
    from a24_atc_bc_20261019 import load_components as load_base
    from .policy import Policy
    base = load_base()
    base.Policy = Policy
    base.version = VERSION
    return base
