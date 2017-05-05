# -*- coding: utf-8 -*-
"""Implements computational spot placement strategies
"""

from __future__ import division
import networkx as nx

from icarus.util import iround
from icarus.registry import register_computation_placement

__all__ = [
        'uniform_computation_placement',
        'central_computation_placement'
          ]

@register_computation_placement('CENTRALITY')
def central_computation_placement(topology, computation_budget, n_services, **kwargs):
    """Places computation budget proportionally to the betweenness centrality of the
    node.
    
    Parameters
    ----------
    topology : Topology
        The topology object
    computation_budget : int
        The cumulative computation budget in terms of the number of VMs
    """
    betw = nx.betweenness_centrality(topology)
    root = [v for v in topology.graph['icr_candidates']
            if topology.node[v]['depth'] == 0][0]
    total_betw = sum(betw.values()) 
    icr_candidates = topology.graph['icr_candidates']
    total = 0
    for v in icr_candidates:
        topology.node[v]['stack'][1]['computation_size'] = iround(computation_budget*betw[v]/total_betw)
        total += topology.node[v]['stack'][1]['computation_size']

    topology.node[root]['stack'][1]['computation_size'] += int(computation_budget - total)
     

@register_computation_placement('UNIFORM')
def uniform_computation_placement(topology, computation_budget, **kwargs):
    """Places computation budget uniformly across cache nodes.
    
    Parameters
    ----------
    topology : Topology
        The topology object
    computation_budget : int
        The cumulative computation budget in terms of the number of VMs
    """

    icr_candidates = topology.graph['icr_candidates']
    cache_size = iround(computation_budget/len(icr_candidates))
    for v in icr_candidates:
        topology.node[v]['stack'][1]['computation_size'] = cache_size
