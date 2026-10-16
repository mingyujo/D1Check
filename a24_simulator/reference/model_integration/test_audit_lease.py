"""Pure saved CIM/argv fixtures for the new audit lease. SOURCE ONLY, NOT RUN."""
import copy
import unittest

import audit_lease as lease

ENTRY = r"C:\task space\A24-MODEL-INTEGRATION-20261016\audit_lease.py"
OP = r"C:\task space\outputs\NODE_VERIFY_LEASE_OPERATION_G002_01.json"
CMD = '"C:\\Python runtime\\python.exe" -B "' + ENTRY + '" --operation "' + OP + '"'


def fixture():
    return [dict(ProcessId=1, ParentProcessId=0, Name="powershell.exe", CreatedUtc="2026-10-16T00:00:00.0000000Z", CommandLine="powershell"),
            dict(ProcessId=10, ParentProcessId=1, Name="python.exe", CreatedUtc="2026-10-16T01:00:00.0000000Z", CommandLine=CMD),
            dict(ProcessId=20, ParentProcessId=10, Name="python.exe", CreatedUtc="2026-10-16T01:00:01.0000000Z", CommandLine=CMD),
            dict(ProcessId=30, ParentProcessId=20, Name="node.exe", CreatedUtc="2026-10-16T01:00:02.0000000Z", CommandLine="node verifier.cjs")]


class AuditLeaseFixtures(unittest.TestCase):
    def test_exact_wrapper_and_shim_ancestry_with_quoted_paths(self):
        self.assertEqual(lease.node_ancestry_fixture(fixture(), 30, ENTRY, OP), [20, 10])
        self.assertEqual(lease.windows_argv(CMD)[-3:], [ENTRY, "--operation", OP])

    def test_same_command_outside_actual_parent_chain_is_not_authorization(self):
        rows = fixture()
        rows.append(dict(ProcessId=40, ParentProcessId=1, Name="python.exe",
                         CreatedUtc="2026-10-16T01:00:00Z", CommandLine=CMD))
        with self.assertRaisesRegex(RuntimeError, "Another Python"):
            lease.node_ancestry_fixture(rows, 30, ENTRY, OP)

    def test_reused_parent_PID_or_reversed_creation_time_rejected(self):
        rows = fixture()
        rows[2]["CreatedUtc"] = "2026-10-16T01:01:00Z"
        with self.assertRaisesRegex(RuntimeError, "reused"):
            lease.node_ancestry_fixture(rows, 30, ENTRY, OP)

    def test_ancestor_operation_or_entry_mismatch_rejected(self):
        for key in ("operation", "entry"):
            rows = fixture()
            rows[2]["CommandLine"] = CMD.replace(OP, OP + ".other") if key == "operation" else CMD.replace(ENTRY, ENTRY + ".other")
            with self.assertRaises(RuntimeError):
                lease.node_ancestry_fixture(rows, 30, ENTRY, OP)

    def test_node_without_direct_lease_python_parent_rejected(self):
        rows = fixture()
        rows[3]["ParentProcessId"] = 1
        with self.assertRaisesRegex(RuntimeError, "direct Python"):
            lease.node_ancestry_fixture(rows, 30, ENTRY, OP)

    def test_duplicate_PID_and_creation_cycle_rejected(self):
        rows = fixture()
        rows.append(copy.deepcopy(rows[1]))
        with self.assertRaisesRegex(RuntimeError, "snapshot"):
            lease.node_ancestry_fixture(rows, 30, ENTRY, OP)
        rows = fixture()
        rows[1]["ParentProcessId"] = 20
        with self.assertRaises(RuntimeError):
            lease.node_ancestry_fixture(rows, 30, ENTRY, OP)

    def test_python_code_injection_and_extra_arguments_rejected(self):
        for command in (CMD.replace(" -B ", " -c "), CMD + " --extra", CMD.replace(" -B ", " -m ")):
            with self.assertRaises(RuntimeError):
                lease.python_invocation(command, ENTRY, OP)

    def test_legacy_creation_date_and_unknown_timezone(self):
        self.assertEqual(lease.created_ms({"CreationDate": "/Date(1000+0900)/"}), 1000)
        with self.assertRaises(RuntimeError):
            lease.created_ms({"CreatedUtc": "2026-10-16T01:00:00"})


if __name__ == "__main__":
    unittest.main()
