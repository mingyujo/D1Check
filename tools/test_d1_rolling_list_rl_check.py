import ast,inspect,unittest
from tools import d1_rolling_list_rl_check as s
class Shared(unittest.TestCase):
    def test_only_line_ending_conversion_accepted(self):
        record=dict(canonical_lf_sha256=s.sha(b'a\nb\n'));s.validate_source(b'a\r\nb\r\n',record)
        with self.assertRaises(ValueError):s.validate_source(b'a\nc\n',record)
    def test_no_runtime_import_or_mutation(self):
        tree=ast.parse(inspect.getsource(s));modules=[n.module for n in ast.walk(tree) if isinstance(n,ast.ImportFrom)]
        self.assertFalse(any(n and n.startswith('tools') for n in modules))
        calls=[n.func.attr for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute)]
        self.assertFalse(set(calls)&{'simulate','fit','mkdir','write_text','unlink'})
if __name__=='__main__':unittest.main()
