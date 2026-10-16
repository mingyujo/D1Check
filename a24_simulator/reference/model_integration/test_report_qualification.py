"""Pure synthetic qualification tests; run only via registered guarded runner."""
import copy
import unittest
from build_report_qualified_data import qualify_report, WAIT_UNQUALIFIED, WAIT_WARNING


def fixture():
    rows = []
    cases = []
    expected = []
    for i in range(180):
        bad = i < 24
        row = {'identity': 'novel-%d' % i, 'kind':'PREDECLARED_NOVEL_GRID',
               'bank':'C252' if i < 12 else 'L64' if i < 24 else 'M128',
               'policy':'FIFO_WAIT_CG' if i < 36 else 'ATC', 'seed':7,
               'metrics':{'on_time':i,'planned':252}, 'P95_s':None if i % 2 else .23,
               'ap_prediction':[[0,31.0],[180,35.1]], 'raw_sha256':'a'*64}
        wait = {'status': WAIT_UNQUALIFIED if bad else 'RECORDED_WAIT_CONSTRAINTS_CHECKED',
                'native_group_domain_qualified':False if bad else True,
                'numeric_results_are_not_native_WAIT_validation':bad,
                'full_scheduler_reproduction':False,'installed_verified':False}
        case = {k:row[k] for k in ('identity','kind','bank','policy','seed')}
        if i < 36:
            case['WAIT'] = wait
        if bad:
            expected.append(copy.deepcopy(case))
        cases.append(case)
        rows.append(row)
    heldout = []
    for i in range(69):
        row={'identity':None if i < 4 else 'heldout-%d'%i,'kind':'WHOLE_COHORT_HELDOUT_VALIDATION',
             'bank':'M128','policy':'FIFO_WAIT_CG','seed':0,'response_error':None if i<24 else .2}
        heldout.append(row)
        cases.append({**copy.deepcopy(row),'WAIT':{'status':'RECORDED_WAIT_CONSTRAINTS_CHECKED'}})
    audit={'schema':'A24-SAVED-CONTRACT-SUPPLEMENT-v2',
           'status':'PASS_SAVED_CONTRACT_BINDINGS_WITH_UNQUALIFIED_WAIT_GENERALIZATIONS',
           'checks':10,'failed_checks':0,'registered_case_roster':249,'heldout_roster':69,'novel_roster':180,
           'all_249_cases_retained':True,'cases':cases,
           'source_wait_domain_qualifications':{'unqualified_case_ids':[c['identity'] for c in expected],
              'unqualified_count':24,'expected_unqualified_count':24}}
    contract={'schema':'A24-WAIT-DOMAIN-CORRECTION-CONTRACT-v1','expected_unqualified_count':24,
              'expected_unqualified_cases':expected}
    report={'scenarios':[{'rows':copy.deepcopy(rows)}], 'limitations':[],
            'audit':{'forecast_validation_and_harms':{'heldout_schedule_validation_rows':heldout}}}
    return report,audit,contract,rows


class QualificationTests(unittest.TestCase):
    def test_all24_annotated_and_all180_values_unchanged(self):
        report,audit,contract,source=fixture()
        before=copy.deepcopy(report['scenarios'][0]['rows'])
        out=qualify_report(report,audit,contract,source)
        rows=out['scenarios'][0]['rows']
        self.assertEqual(len(rows),180)
        self.assertEqual(sum(r['source_wait_domain_qualification']['status']==WAIT_UNQUALIFIED for r in rows),24)
        self.assertEqual([{k:v for k,v in r.items() if k!='source_wait_domain_qualification'} for r in rows],before)
        self.assertTrue(out['audit']['source_wait_domain_qualifications']['all_preexisting_forecast_fields_unchanged'])
        self.assertEqual(rows[0]['source_wait_domain_qualification']['message'],WAIT_WARNING)

    def test_native12_separate_and_unknown_heldout_preserved(self):
        report,audit,contract,source=fixture()
        out=qualify_report(report,audit,contract,source)
        self.assertEqual(sum(r['source_wait_domain_qualification']['native_group_domain_qualified'] is True for r in out['scenarios'][0]['rows']),12)
        held=out['audit']['forecast_validation_and_harms']['heldout_schedule_validation_rows']
        self.assertEqual(len(held),69)
        self.assertEqual(sum(r['source_wait_domain_qualification']['status']=='UNKNOWN_NO_SIMULATOR_START' for r in held),4)
        self.assertTrue(all(r['source_wait_domain_qualification']['status']!=WAIT_UNQUALIFIED for r in held))

    def test_missing_expected_case_is_rejected(self):
        args=list(fixture());args[2]['expected_unqualified_cases'].pop()
        with self.assertRaises(RuntimeError):qualify_report(*args)

    def test_duplicate_identity_is_rejected(self):
        args=list(fixture());args[0]['scenarios'][0]['rows'][1]['identity']='novel-0'
        with self.assertRaises(RuntimeError):qualify_report(*args)

    def test_wrong_bank_cannot_be_reclassified(self):
        args=list(fixture());args[0]['scenarios'][0]['rows'][0]['bank']='M128';args[1]['cases'][0]['bank']='M128'
        with self.assertRaises(RuntimeError):qualify_report(*args)

    def test_missing_source_row_hash_is_rejected(self):
        args=list(fixture());args[3].pop(0)
        with self.assertRaises(RuntimeError):qualify_report(*args)

    def test_unqualified_status_cannot_escape_registered24(self):
        args=list(fixture());args[1]['cases'][24]['WAIT']['status']=WAIT_UNQUALIFIED
        with self.assertRaises(RuntimeError):qualify_report(*args)

    def test_failed_predecessor_cannot_become_pass(self):
        args=list(fixture());args[1]['failed_checks']=1
        with self.assertRaises(RuntimeError):qualify_report(*args)