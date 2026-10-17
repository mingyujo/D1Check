"""Equal checkpoint contents, independent optimizer storage/RNG for each arm."""
import copy
from nn_train import Learner

def independently_restored(snapshot,seed):
    learner=Learner(seed)
    learner.restore(copy.deepcopy(snapshot))
    return learner
