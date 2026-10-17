import unittest
from test_observer import CensusTests
from observer_v2 import CoalescingObserver

class CoalescingTests(CensusTests):
    def bank(self):
        b=super().bank();b['diagnostic']['head_request_id']='a';return b

    def instance(self):
        x=CoalescingObserver.__new__(CoalescingObserver)
        x.mode='COALESCED_COST';x.opportunities=[];x.coalescing_events=[];return x

    def test_coalescing_uses_only_existing_legal_WAIT(self):
        x=self.instance();self.assertEqual(x.choose(self.bank(),0),72)
        self.assertEqual(len(x.opportunities),0);self.assertEqual(len(x.coalescing_events),1)

    def test_unsafe_WAIT_stays_blocked(self):
        x=self.instance();b=self.bank();b['mask'][72]=False
        self.assertEqual(x.choose(b,0),0);self.assertEqual(len(x.opportunities),1)

    def test_no_WAIT_with_ready_request_competition(self):
        x=self.instance();b=self.bank();b['actions'][3]={'kind':'DISPATCH','request_id':'b','route':'CPU'}
        b['physical_mask'][3]=True;b['mask'][3]=True
        self.assertEqual(x.choose(b,0),0);self.assertEqual(len(x.coalescing_events),0)

    def test_no_WAIT_when_one_resource_busy(self):
        x=self.instance();b=self.bank();b['physical_mask'][1]=False;b['mask'][1]=False
        self.assertEqual(x.choose(b,0),0)

if __name__=='__main__':unittest.main()
