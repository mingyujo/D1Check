"""One evidence-led repair: do not intentionally idle with detector backlog."""
from tools import d1_list_candidate_service_list as parent

POLICY='LIST_SERVICE_EQUAL_WORK_BACKLOG_PC_V2'

class BacklogList(parent.ServiceList):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs);self.public_policy=POLICY
    def admitted(self,index,encoded,actions,queue):
        if actions[index]['wait']>0 and sum(q['task']=='detection' for q in queue)>1:
            return False
        return super().admitted(index,encoded,actions,queue)
