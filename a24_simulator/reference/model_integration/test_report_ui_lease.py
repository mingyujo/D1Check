"""Pure new UI-lease boundaries only; no processes/files/browser or model tests."""
import copy
import unittest
import report_ui_lease as ui


def spec(name, sha="a" * 64):
    return {"path": "C:/fixture/" + name, "sha256": sha, "bytes": 1}


def contract():
    wrapper = spec("report_ui_lease.py")
    manifest = {"schema": ui.MANIFEST_SCHEMA, "allow_execution": True, "automatic_retry": False,
        "worker_lock_path": ui.ORIGINAL_LOCK, "expected_lease_operation_path": "C:/fixture/op.json",
        "lease_wrapper_entry_pin": wrapper, "output_dir": "C:/fixture/fresh",
        "rendered_html_filename": "A24_saved_V3.html", "expected_sessions": 115,
        "protected_pins": [spec("original" + str(n)) for n in range(351)]}
    manifest.update({k:0 for k in ui.ZERO_FIELDS})
    for key, name in (("data_pin", "data.json"), ("template_pin", "report.template.html"),
                      ("node_executable_pin", "node.exe"), ("chrome_executable_pin", "chrome.exe"),
                      ("playwright_entry_pin", "playwright.js"), ("renderer_pin", "render_report.cjs"),
                      ("qa_pin", "qa_report.cjs"), ("node_guard_pin", "report_ui_guard.cjs")):
        manifest[key] = spec(name)
    operation = {"mode":"REPORT_UI", "automatic_retry":False, "worker_lock_path":ui.ORIGINAL_LOCK,
        "output_dir":manifest["output_dir"], "protected_pins":copy.deepcopy(manifest["protected_pins"]),
        "ui_manifest_pin":spec("manifest.json")}
    operation.update({k:0 for k in ui.ZERO_FIELDS})
    operation["source_pins"] = [wrapper, manifest["renderer_pin"], manifest["qa_pin"], manifest["node_guard_pin"],
        spec("runtime_guard.py",ui.FROZEN_GUARD_SHA),spec("audit_lease.py",ui.FROZEN_AUDIT_LEASE_SHA)]
    operation["input_pins"] = [operation["ui_manifest_pin"], *[manifest[k] for k in
        ("data_pin","template_pin","node_executable_pin","chrome_executable_pin","playwright_entry_pin")]]
    return operation, manifest


class ReportUILeaseBoundaryFixtures(unittest.TestCase):
    def validate(self, op, manifest):
        return ui.validate_manifest(op,manifest,"C:/fixture/op.json","C:/fixture/report_ui_lease.py")

    def test_valid_separate_saved_only_contract(self):
        self.assertTrue(self.validate(*contract()))

    def test_output_namespace_and_path_traversal_rejected(self):
        for field, value in (("output_dir","C:/other"),("rendered_html_filename","../original.html"),
                             ("rendered_html_filename","C:/original.html")):
            op,m=contract();m[field]=value
            with self.assertRaises(RuntimeError):self.validate(op,m)

    def test_actual_entry_future_operation_and_original_lock_required(self):
        for field in ("expected_lease_operation_path","worker_lock_path"):
            op,m=contract();m[field]="C:/other/file"
            with self.assertRaises(RuntimeError):self.validate(op,m)
        op,m=contract();m["lease_wrapper_entry_pin"]=spec("wrong.py")
        with self.assertRaises(RuntimeError):self.validate(op,m)

    def test_zero_boundary_boolean_or_fit_rejected(self):
        for value in (False,1,None):
            op,m=contract();m["new_fit"]=value
            with self.assertRaises(RuntimeError):self.validate(op,m)

    def test_original351_and_exact_helper_pins_required(self):
        op,m=contract();m["protected_pins"][0]["sha256"]="b"*64
        with self.assertRaises(RuntimeError):self.validate(op,m)
        op,m=contract();op["source_pins"][-1]["sha256"]="b"*64
        with self.assertRaises(RuntimeError):self.validate(op,m)

    def test_runtime_manifest_input_and_stage_source_omission_rejected(self):
        for kind in ("input_pins","source_pins"):
            op,m=contract();op[kind]=op[kind][1:]
            with self.assertRaises(RuntimeError):self.validate(op,m)

    def test_child_command_is_explicit_heap_stage_manifest_no_shell(self):
        _,m=contract()
        for stage, key in (("render","renderer_pin"),("qa","qa_pin")):
            self.assertEqual(ui.stage_command(stage,m,"C:/fixture/manifest.json"),
                [m["node_executable_pin"]["path"],"--max-old-space-size=4096",m[key]["path"],"--manifest","C:/fixture/manifest.json"])
        with self.assertRaises(RuntimeError):ui.stage_command("fit",m,"C:/fixture/manifest.json")

    def test_parent_accepts_only_completed_bound_zero_software_UI_result(self):
        sha="a"*64
        r={"status":ui.STAGE_STATUS["qa"],"manifest_sha256":sha,"measured_J":None,
           "physical_goal_pass":False,"failed_checks":0,"checks":100,"HTTP_attempts":[],"JS_errors":[],
           "observed_sessions_with_all_source_curve_coordinates_checked":115,"scenario_policy_states_checked":6,
           "states":[{"theme":theme,"width":width,"status":"PASS"} for theme in ("light","dark") for width in (360,736,1280)]}
        r.update({k:0 for k in ui.ZERO_FIELDS})
        self.assertTrue(ui.accepted_stage("qa",0,r,sha))
        for key,value in (("status","PASS"),("failed_checks",1),("HTTP_attempts",["https://example.invalid"]),
                          ("JS_errors",["error"]),("measured_J",0),("physical_goal_pass",True),("manifest_sha256","b"*64),
                          ("observed_sessions_with_all_source_curve_coordinates_checked",114),("states",[]),
                          ("checks",0),("failed_checks",False)):
            bad=dict(r);bad[key]=value
            self.assertFalse(ui.accepted_stage("qa",0,bad,sha))
        self.assertFalse(ui.accepted_stage("qa",1,r,sha))


if __name__ == "__main__":
    unittest.main()
