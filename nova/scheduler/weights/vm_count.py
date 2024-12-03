from nova.scheduler import weights

class VmCountWeigher(weights.BaseHostWeigher):
    def _weigh_object(self, host_state, weight_properties):
        return -host_state.num_instances
