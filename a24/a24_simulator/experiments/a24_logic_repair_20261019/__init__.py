"""Opt-in corrected components; importing this package starts no experiment."""
import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace

VERSION = 'A24_LOGIC_REPAIR_20261019_V1'
BASE_COMMIT = 'ac3a5af569e04bc6be01f1ef976b9dd4eb6558cf'


def load_components():
    """Load the CPU3 engine, corrected ORIGINAL physics and corrected policy.

    Frozen producers continue to import their original components. New callers
    explicitly use this entry point and register a new operation before running.
    Paths are resolved from this checkout, never from historical absolute pins.
    """
    experiments = Path(__file__).resolve().parent.parent
    public = str(experiments / 'public_transfer_20261018')
    if public not in sys.path:
        sys.path.insert(0, public)
    import common_transfer
    for folder in ('a24_parallel_20261018', 'a24_candidate_repair_20261018',
                   'a24_s26_method_20261019'):
        path = str(experiments / folder)
        if path not in sys.path:
            sys.path.insert(0, path)

    def module(name, filename):
        spec = importlib.util.spec_from_file_location(name, filename)
        result = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(result)
        return result

    port = experiments / 'a24_s26_method_20261019'
    original = module('_a24_logic_base_physics', port / 'physics.py')
    engine = module('_a24_logic_base_engine', port / 'engine.py')
    from .physics import make_physics_class
    from .policy import Policy
    return SimpleNamespace(Physics=make_physics_class(original.Physics),
                           Policy=Policy, engine=engine, B=common_transfer.B,
                           version=VERSION, base_commit=BASE_COMMIT)
