import unittest
from tools import d1_rolling_hybrid_shared_check as s

class Shared(unittest.TestCase):
    def test_recorded_eol_conversion_preserves_content(self):
        payload=b'a\nb\n';entry=dict(canonical_lf_sha256=s.digest(payload))
        s.validate_source(payload,entry);s.validate_source(b'a\r\nb\r\n',entry)
    def test_content_change_is_rejected(self):
        with self.assertRaises(ValueError):s.validate_source(b'a\nc\n',dict(canonical_lf_sha256=s.digest(b'a\nb\n')))
    def test_shared_check_has_no_runtime_imports_or_mutations(self):
        import ast,inspect
        tree=ast.parse(inspect.getsource(s))
        imports=[n.module for n in ast.walk(tree) if isinstance(n,ast.ImportFrom)]
        self.assertFalse(any(n and n.startswith('tools') for n in imports))
        calls=[n.func.attr for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute)]
        self.assertFalse(set(calls)&{'simulate','write_text','mkdir','unlink','fit'})

if __name__=='__main__':unittest.main()
