import unittest
from compact_dataset import project,invariant


class CompactInputTests(unittest.TestCase):
    def test_numeric_and_cohort_identity_preserved(self):
        data={'sessions':[{'cohort_id':'a','provenance':{'native_session_id':'x','projection_content_sha256':'f'*64,
              'raw_receipts':[{'large_repeated':'body'}]},'observations':[{'t_ns':1799999999999999999,
              't_s':35.1,'ap_c':30.8,'lo_s':35.,'hi_s':35.2,'provenance':{'path':'raw'}}]}]}
        result=project(data,'a'*64)
        self.assertEqual(invariant(data),invariant(result))
        self.assertEqual(result['sessions'][0]['provenance']['native_session_id'],'x')
        self.assertEqual(result['sessions'][0]['observations'][0]['t_ns'],1799999999999999999)

    def test_exact_reference_pointer_escaping(self):
        result=project({'a/b':{'metadata_occurrences':[1,2,3]}},'f'*64)
        self.assertEqual(result['a/b']['metadata_occurrences_saved_reference']['json_pointer'],
                         '/a~1b/metadata_occurrences')


if __name__=='__main__':
    unittest.main()
