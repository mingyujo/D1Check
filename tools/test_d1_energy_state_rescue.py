"""PC guards for the one-shot COLLECT-04 evidence recovery path."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from tools import d1_energy_state_rescue as rescue


class RescueGuardTest(TestCase):
    def test_existing_output_never_touches_device(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = root / "plan.json"
            plan.write_text(json.dumps({"experiment_id": "ENERGY-AP-STATE-COLLECT-04"}), encoding="utf-8")
            output = root / "rescue"
            output.mkdir()
            with patch.object(rescue.observed, "ObservedDevice") as device:
                with self.assertRaises(ValueError):
                    rescue.run(plan, "adb", output)
                device.assert_not_called()

    def test_no_launched_session_never_touches_device(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = root / "plan.json"
            plan.write_text(json.dumps({
                "experiment_id": "ENERGY-AP-STATE-COLLECT-04",
                "output_root": str(root / "run"),
                "entries": [{"session_id": "sample"}],
            }), encoding="utf-8")
            with patch.object(rescue.observed, "ObservedDevice") as device:
                with self.assertRaises(ValueError):
                    rescue.run(plan, "adb", root / "rescue")
                device.assert_not_called()
