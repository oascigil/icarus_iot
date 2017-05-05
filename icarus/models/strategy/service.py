# -*- coding: utf-8 -*-
"""Implementations of all service-based strategies"""
from __future__ import division
from __future__ import print_function

import networkx as nx

from icarus.registry import register_strategy
from icarus.util import inheritdoc, path_links
from .base import Strategy

__all__ = [
       'LeastCongestedStrategy',
       'MinDataTransferStrategy',
       'OptimalStrategy',
       'NaiveStrategy'
           ]

           
@register_strategy('LEAST_CONGESTED')
class LeastCongestedStrategy(Strategy):
    """A distributed approach for service-centric routing
    """
    def __init__(self, view, controller, debug=False, **kwargs):
        super(LeastCongestedStrategy, self).__init__(view,controller)
        self.receivers = view.topology().receivers()
        self.compSpots = self.view.service_nodes()
        self.num_nodes = len(self.compSpots.keys())
        self.num_services = self.view.num_services()
        self.debug = debug
        self.flow_copies = {}
        self.REQUEST = 0
        self.RESPONSE = 1
        self.EXECUTED = 2

    @inheritdoc(Strategy)
    def process_event(self, time, receiver, content, log, node, flow_id, data_destination, exec_destination, source_list, status):
        """
        data_destination : node where the data is to be fetched from
        exec_destination : node where the data is to be executed
        flow_id : Id of the flow that the request/response is part of
        node : the current node at which the request/response arrived
        status: either request=0, response=1, executed=2
        """
        service = content

        if status == self.REQUEST:
            if node == receiver:
                #source_list = self.view.content_source(service)
                if self.debug:
                    print ("Initial REQUEST:")
                    print ("Source list: " + repr(source_list))
                    print ("Event\n time: " + repr(time) + " receiver  " + repr(receiver) + " service " + repr(service) + " node " + repr(node) + " flow_id " + repr(flow_id) + " destination " + repr(data_destination) + " exec_destination " + repr(exec_destination) + " status " + repr(status)) 
                    print ("\n")
                self.flow_copies[flow_id] = len(source_list)
                self.controller.start_session(time, receiver, service, log, flow_id)
            elif node == data_destination:
                status = self.RESPONSE
                self.controller.add_event(time, receiver, service, node, flow_id, data_destination, exec_destination, source_list, status)
                return
            
            #source_list = self.view.content_source(service)
            next_nodes_set = set()
            dest_set = set()
            filtered = 0
            if self.debug:
                print ("Request is on its way to data_destination: " + repr(data_destination))
                print ("Event time: " + repr(time) + " receiver  " + repr(receiver) + " service " + repr(service) + " node " + repr(node) + " flow_id " + repr(flow_id) + " destination " + repr(data_destination) + " exec_destination " + repr(exec_destination) + " status " + repr(status)) 
                print ("\n")
            for source in source_list:
                path = self.view.shortest_path(node, source)
                next_node = path[1]
                if node != receiver and next_node < node: # you always go down in the tree
                    #print ("FILTERED: Next node: " + repr(next_node) + " node: " + repr(node))
                    filtered += 1
                else:
                    next_nodes_set.add(next_node)
                    dest_set.add(source)
            if len(next_nodes_set) == 1 and filtered == 0:
                next_node = next(iter(next_nodes_set)) # get the first element of next_nodes_set
                if self.view.has_computationalSpot(next_node):
                    cs = self.compSpots[next_node]
                    fin_time, vm_indx = cs.getFinishTime(service, time)
                    if exec_destination == -1:
                        exec_destination = [[next_node, fin_time]]
                    else:
                        exec_destination.append([next_node, fin_time])
            if len(dest_set) == 1 and data_destination == -1:
                data_destination = next(iter(dest_set))
            for next_node in next_nodes_set:
                linkDelay = self.view.link_delay(node, next_node)
                self.controller.add_event(time+linkDelay, receiver, service, next_node, flow_id, data_destination, exec_destination, source_list, status)

        elif status == self.RESPONSE:
            if node == data_destination:
                if self.debug:
                    print ("Request reached data_destination: " + repr(data_destination))
                    print ("Event time: " + repr(time) + " receiver  " + repr(receiver) + " service " + repr(service) + " node " + repr(node) + " flow_id " + repr(flow_id) + " destination " + repr(data_destination) + " exec_destination " + repr(exec_destination) + " status " + repr(status)) 
                    print ("\n")
                min_fin = float('inf')
                destination = -1
                exec_destination.reverse()
                for n, f in exec_destination:
                    if f < min_fin:
                        min_fin = f
                        destination = n
                if destination != node:
                    path = self.view.shortest_path(node, destination)
                    next_node = path[1]
                    linkDelay = self.view.link_delay(node, next_node)
                    status = self.RESPONSE
                    self.controller.forward_content_hop(node, next_node, flow_id) 
                    self.controller.add_event(time+linkDelay, receiver, service, next_node, flow_id, data_destination, destination, source_list, status)
                else:
                    cs.schedule_service(service, vm_indx, time)
                    status = self.EXECUTED
                    self.controller.add_event(fin_time, receiver, service, node, flow_id, data_destination, destination, source_list, status)
            elif node == exec_destination:
                cs = self.compSpots[node]
                fin_time, vm_indx = cs.getFinishTime(service, time)
                if self.debug:
                    print ("Response reached EXEC_destination: " + repr(exec_destination))
                    print ("Scheduling the execution at vm: " + repr(vm_indx))
                    print ("Event time: " + repr(time) + " receiver  " + repr(receiver) + " service " + repr(service) + " node " + repr(node) + " flow_id " + repr(flow_id) + " destination " + repr(data_destination) + " exec_destination " + repr(exec_destination) + " status " + repr(status)) 
                    print ("\n")
                cs.schedule_service(service, vm_indx, time)
                status = self.EXECUTED
                self.controller.add_event(fin_time, receiver, service, node, flow_id, data_destination, exec_destination, source_list, status)
            else:
                path = self.view.shortest_path(node, exec_destination)
                next_node = path[1]
                linkDelay = self.view.link_delay(node, next_node)
                if self.debug:
                    print ("Response is on its way to Exec_destination: " + repr(exec_destination))
                    print ("Event time: " + repr(time) + " receiver  " + repr(receiver) + " service " + repr(service) + " node " + repr(node) + " flow_id " + repr(flow_id) + " destination " + repr(data_destination) + " exec_destination " + repr(exec_destination) + " status " + repr(status)) 
                    print ("\n")
                self.controller.add_event(time+linkDelay, receiver, service, next_node, flow_id, data_destination, exec_destination, source_list, status)
        elif status == self.EXECUTED:
            if node == receiver:
                if self.debug:
                    print ("Executed response is back to RECEIVER " + repr(receiver))
                    print ("Event time: " + repr(time) + " receiver  " + repr(receiver) + " service " + repr(service) + " node " + repr(node) + " flow_id " + repr(flow_id) + " destination " + repr(data_destination) + " exec_destination " + repr(exec_destination) + " status " + repr(status)) 
                    print ("\n")
                self.flow_copies[flow_id] -= 1
                if self.flow_copies[flow_id] == 0:
                    self.controller.end_session(True, time, flow_id)
                    del self.flow_copies[flow_id]
                return
            else:
                if self.debug:
                    print ("Executed response is back to RECEIVER " + repr(receiver))
                    print ("Event time: " + repr(time) + " receiver  " + repr(receiver) + " service " + repr(service) + " node " + repr(node) + " flow_id " + repr(flow_id) + " destination " + repr(data_destination) + " exec_destination " + repr(exec_destination) + " status " + repr(status)) 
                    print ("\n")
                path = self.view.shortest_path(node, receiver)
                next_node = path[1]
                linkDelay = self.view.link_delay(node, next_node)
                self.controller.add_event(time+linkDelay, receiver, service, next_node, flow_id, data_destination, exec_destination, source_list, status)
        else:
            print ("Error: this should not happen!")


@register_strategy('MIN_DATA_TRANSFER')
class MinDataTransferStrategy(Strategy):
    """A distributed approach for service-centric routing
    """
    def __init__(self, view, controller, debug=False, **kwargs):
        super(MinDataTransferStrategy, self).__init__(view,controller)
        self.receivers = view.topology().receivers()
        self.compSpots = self.view.service_nodes()
        self.num_nodes = len(self.compSpots.keys())
        self.num_services = self.view.num_services()
        self.debug = debug
        self.flow_copies = {}
        self.REQUEST = 0
        self.RESPONSE = 1
        self.EXECUTED = 2

    @inheritdoc(Strategy)
    def process_event(self, time, receiver, content, log, node, flow_id, data_destination, exec_destination, source_list, status):
        """
        data_destination : node where the data is to be fetched from
        exec_destination : node where the data is to be executed
        flow_id : Id of the flow that the request/response is part of
        node : the current node at which the request/response arrived
        status: either request=0, response=1, executed=2
        """
        service = content

        if status == self.REQUEST:
            if node == receiver:
                #source_list = self.view.content_source(service)
                if self.debug:
                    print ("Initial REQUEST:")
                    print ("Source list: " + repr(source_list))
                    print ("Event\n time: " + repr(time) + " receiver  " + repr(receiver) + " service " + repr(service) + " node " + repr(node) + " flow_id " + repr(flow_id) + " destination " + repr(data_destination) + " exec_destination " + repr(exec_destination) + " status " + repr(status)) 
                    print ("\n")
                self.flow_copies[flow_id] = len(source_list)
                self.controller.start_session(time, receiver, service, log, flow_id)
            elif node == data_destination:
                status = self.RESPONSE
                self.controller.add_event(time, receiver, service, node, flow_id, data_destination, exec_destination, source_list, status)
                return
            
            #source_list = self.view.content_source(service)
            next_nodes_set = set()
            dest_set = set()
            filtered = 0
            if self.debug:
                print ("Request is on its way to data_destination: " + repr(data_destination))
                print ("Event time: " + repr(time) + " receiver  " + repr(receiver) + " service " + repr(service) + " node " + repr(node) + " flow_id " + repr(flow_id) + " destination " + repr(data_destination) + " exec_destination " + repr(exec_destination) + " status " + repr(status)) 
                print ("\n")
            for source in source_list:
                path = self.view.shortest_path(node, source)
                next_node = path[1]
                if node != receiver and next_node < node: # you always go down in the tree
                    filtered += 1
                else:
                    next_nodes_set.add(next_node)
                    dest_set.add(source)
            if len(next_nodes_set) == 1 and filtered == 0:
                next_node = next(iter(next_nodes_set)) # get the first element of next_nodes_set
                if self.view.has_computationalSpot(next_node):
                    cs = self.compSpots[next_node]
                    fin_time, vm_indx = cs.getFinishTime(service, time)
                    exec_destination = next_node
            if len(dest_set) == 1 and data_destination == -1:
                data_destination = next(iter(dest_set))
            for next_node in next_nodes_set:
                linkDelay = self.view.link_delay(node, next_node)
                self.controller.add_event(time+linkDelay, receiver, service, next_node, flow_id, data_destination, exec_destination, source_list, status)

        elif status == self.RESPONSE:
            if node == data_destination:
                if self.debug:
                    print ("Request reached data_destination: " + repr(data_destination))
                    print ("Event time: " + repr(time) + " receiver  " + repr(receiver) + " service " + repr(service) + " node " + repr(node) + " flow_id " + repr(flow_id) + " destination " + repr(data_destination) + " exec_destination " + repr(exec_destination) + " status " + repr(status)) 
                    print ("\n")
                path = self.view.shortest_path(node, exec_destination)
                next_node = path[1]
                linkDelay = self.view.link_delay(node, next_node)
                status = self.RESPONSE
                self.controller.forward_content_hop(node, next_node, flow_id) 
                self.controller.add_event(time+linkDelay, receiver, service, next_node, flow_id, data_destination, exec_destination, source_list, status)
            elif node == exec_destination:
                cs = self.compSpots[node]
                fin_time, vm_indx = cs.getFinishTime(service, time)
                if self.debug:
                    print ("Response reached EXEC_destination: " + repr(exec_destination))
                    print ("Scheduling the execution at vm: " + repr(vm_indx))
                    print ("Event time: " + repr(time) + " receiver  " + repr(receiver) + " service " + repr(service) + " node " + repr(node) + " flow_id " + repr(flow_id) + " destination " + repr(data_destination) + " exec_destination " + repr(exec_destination) + " status " + repr(status)) 
                    print ("\n")
                cs.schedule_service(service, vm_indx, time)
                status = self.EXECUTED
                self.controller.add_event(fin_time, receiver, service, node, flow_id, data_destination, exec_destination, source_list, status)
            else:
                path = self.view.shortest_path(node, exec_destination)
                next_node = path[1]
                linkDelay = self.view.link_delay(node, next_node)
                if self.debug:
                    print ("Response is on its way to Exec_destination: " + repr(exec_destination))
                    print ("Event time: " + repr(time) + " receiver  " + repr(receiver) + " service " + repr(service) + " node " + repr(node) + " flow_id " + repr(flow_id) + " destination " + repr(data_destination) + " exec_destination " + repr(exec_destination) + " status " + repr(status)) 
                    print ("\n")
                self.controller.add_event(time+linkDelay, receiver, service, next_node, flow_id, data_destination, exec_destination, source_list, status)
        elif status == self.EXECUTED:
            if node == receiver:
                if self.debug:
                    print ("Executed response is back to RECEIVER " + repr(receiver))
                    print ("Event time: " + repr(time) + " receiver  " + repr(receiver) + " service " + repr(service) + " node " + repr(node) + " flow_id " + repr(flow_id) + " destination " + repr(data_destination) + " exec_destination " + repr(exec_destination) + " status " + repr(status)) 
                    print ("\n")
                self.flow_copies[flow_id] -= 1
                if self.flow_copies[flow_id] == 0:
                    self.controller.end_session(True, time, flow_id)
                    del self.flow_copies[flow_id]
                return
            else:
                if self.debug:
                    print ("Executed response is back to RECEIVER " + repr(receiver))
                    print ("Event time: " + repr(time) + " receiver  " + repr(receiver) + " service " + repr(service) + " node " + repr(node) + " flow_id " + repr(flow_id) + " destination " + repr(data_destination) + " exec_destination " + repr(exec_destination) + " status " + repr(status)) 
                    print ("\n")
                path = self.view.shortest_path(node, receiver)
                next_node = path[1]
                linkDelay = self.view.link_delay(node, next_node)
                self.controller.add_event(time+linkDelay, receiver, service, next_node, flow_id, data_destination, exec_destination, source_list, status)
        else:
            print ("Error: this should not happen!")

@register_strategy('OPTIMAL')
class OptimalStrategy(Strategy):
    """A distributed approach for service-centric routing
    """
    def __init__(self, view, controller, debug=False, **kwargs):
        super(OptimalStrategy, self).__init__(view,controller)
        self.receivers = view.topology().receivers()
        self.compSpots = self.view.service_nodes()
        self.num_nodes = len(self.compSpots.keys())
        self.num_services = self.view.num_services()
        self.debug = debug
        self.REQUEST = 0
        self.RESPONSE = 1
        self.EXECUTED = 2

    @inheritdoc(Strategy)
    def process_event(self, time, receiver, content, log, node, flow_id, data_destination, exec_destination, source_list, status):
        """
        data_destination : node where the data is to be fetched from
        exec_destination : node where the data is to be executed
        flow_id : Id of the flow that the request/response is part of
        node : the current node at which the request/response arrived
        status: either request=0, response=1, executed=2
        """
        service = content
        
        #if self.debug:
        #    print ("\nEvent\n time: " + repr(time) + " receiver  " + repr(receiver) + " service " + repr(service) + " node " + repr(node) + " flow_id " + repr(flow_id) + " destination " + repr(data_destination) + " status " + repr(status)) 

        if node == receiver and status == self.REQUEST and exec_destination == -1:
            # Find the least congested node in the network
            minFinTime = float('inf')
            optimal_node = -1
            min_vm_indx = 0
            for node in self.compSpots.keys():
                cs = self.compSpots[node]
                fin_time, vm_indx = cs.getFinishTime(service, time)
                if minFinTime > fin_time:
                    min_vm_indx = vm_indx
                    minFinTime = fin_time
                    optimal_node = node

            if self.debug:
                print ("Optimal node: " + repr(optimal_node) + " " + repr(min_vm_indx) + " " + repr(minFinTime))
            self.controller.start_session(time, receiver, service, log, flow_id)
            # Retrieve the data for the service: take the latency of the
            #source_list = self.view.content_source(service)
            if self.debug:
                print ("Source list: " + repr(source_list))
            paths = []
            for source in source_list:
                path = self.view.shortest_path(optimal_node, source)
                # The path should really be reversed but does not matter for the overhead
                self.controller.forward_content_path(optimal_node, source, flow_id, path)
                paths.append(path)
            pathDelay = self.view.path_delay(node, optimal_node)
            longest_path = max(paths, key=len)
            next_node = longest_path[1]
            linkDelay = self.view.link_delay(optimal_node, next_node)
            status = self.REQUEST
            exec_destination = optimal_node
            if self.debug:
                print ("Initial REQUEST:")
                print ("Event\n time: " + repr(time) + " receiver  " + repr(receiver) + " service " + repr(service) + " node " + repr(node) + " flow_id " + repr(flow_id) + " destination " + repr(data_destination) + " exec_destination " + repr(exec_destination) + " status " + repr(status)) 
                print ("\n")
                
            self.controller.add_event(time+pathDelay+linkDelay, receiver, service, next_node, flow_id, longest_path[len(longest_path)-1], exec_destination, source_list, status)

        elif status == self.REQUEST:
            if node == data_destination:
                path = self.view.shortest_path(node, exec_destination)
                next_node = path[1]
                delay = self.view.link_delay(node, next_node)
                status = self.RESPONSE 
                if self.debug:
                    print ("Request reached data_destination: " + repr(data_destination))
                    print ("Event time: " + repr(time) + " receiver  " + repr(receiver) + " service " + repr(service) + " node " + repr(node) + " flow_id " + repr(flow_id) + " destination " + repr(data_destination) + " exec_destination " + repr(exec_destination) + " status " + repr(status)) 
                    print ("\n")
                self.controller.add_event(time+delay, receiver, service, next_node, flow_id, data_destination, exec_destination, source_list, status)

            else:
                path = self.view.shortest_path(node, data_destination)
                next_node = path[1]
                delay = self.view.link_delay(node, next_node)
                if self.debug:
                    print ("Request is on its way to data_destination: " + repr(data_destination))
                    print ("Event time: " + repr(time) + " receiver  " + repr(receiver) + " service " + repr(service) + " node " + repr(node) + " flow_id " + repr(flow_id) + " destination " + repr(data_destination) + " exec_destination " + repr(exec_destination) + " status " + repr(status)) 
                    print ("\n")
                self.controller.add_event(time+delay, receiver, service, next_node, flow_id, data_destination, exec_destination, source_list, status)
        elif status == self.RESPONSE:
            if node == exec_destination:
                # execute the service
                compSpot = self.view.compSpot(node)
                compTime, vm_indx = compSpot.getFinishTime(service, time)
                compSpot.schedule_service(service, vm_indx, time)
                status = self.EXECUTED
                if self.debug:
                    print ("Response reached EXEC_destination: " + repr(exec_destination))
                    print ("Scheduling the execution at vm: " + repr(vm_indx))
                    print ("Event time: " + repr(time) + " receiver  " + repr(receiver) + " service " + repr(service) + " node " + repr(node) + " flow_id " + repr(flow_id) + " destination " + repr(data_destination) + " exec_destination " + repr(exec_destination) + " status " + repr(status)) 
                    print ("\n")
                self.controller.add_event(compTime, receiver, service, node, flow_id, data_destination, exec_destination, source_list, status)
            else:
                path = self.view.shortest_path(node, exec_destination)
                next_node = path[1]
                if self.debug:
                    print ("Response is on its way to Exec_destination: " + repr(exec_destination))
                    print ("Event time: " + repr(time) + " receiver  " + repr(receiver) + " service " + repr(service) + " node " + repr(node) + " flow_id " + repr(flow_id) + " destination " + repr(data_destination) + " exec_destination " + repr(exec_destination) + " status " + repr(status)) 
                    print ("\n")
                delay = self.view.link_delay(node, next_node)
                #self.controller.forward_content_hop(node, next_node, flow_id) DONE above
                self.controller.add_event(time+delay, receiver, service, next_node, flow_id, data_destination, exec_destination, source_list, status)
        elif status == self.EXECUTED:
            if node == receiver:
                if self.debug:
                    print ("Executed response is back to RECEIVER " + repr(receiver))
                    print ("Event time: " + repr(time) + " receiver  " + repr(receiver) + " service " + repr(service) + " node " + repr(node) + " flow_id " + repr(flow_id) + " destination " + repr(data_destination) + " exec_destination " + repr(exec_destination) + " status " + repr(status)) 
                    print ("\n")
                self.controller.end_session(True, time, flow_id)
                return
            else:
                path = self.view.shortest_path(node, receiver)
                next_node = path[1]
                delay = self.view.link_delay(node, next_node)
                if self.debug:
                    print ("Executed Response is on its way back to receiver " + repr(receiver))
                    print ("Event time: " + repr(time) + " receiver  " + repr(receiver) + " service " + repr(service) + " node " + repr(node) + " flow_id " + repr(flow_id) + " destination " + repr(data_destination) + " exec_destination " + repr(exec_destination) + " status " + repr(status)) 
                    print ("\n")
                self.controller.add_event(time+delay, receiver, service, next_node, flow_id, data_destination, exec_destination, source_list, status)
        else:
            print ("Error: This should not happen\n")

@register_strategy('NAIVE')
class NaiveStrategy(Strategy):
    """A distributed approach for service-centric routing
    """
    def __init__(self, view, controller, debug=False, **kwargs):
        super(NaiveStrategy, self).__init__(view,controller)
        self.receivers = view.topology().receivers()
        self.compSpots = self.view.service_nodes()
        self.num_nodes = len(self.compSpots.keys())
        self.num_services = self.view.num_services()
        self.debug = debug
        self.flow_copies = {}
        self.REQUEST = 0
        self.RESPONSE = 1
        self.EXECUTED = 2

    @inheritdoc(Strategy)
    def process_event(self, time, receiver, content, log, node, flow_id, data_destination, exec_destination, source_list, status):
        """
        data_destination : node where the data is to be fetched from
        exec_destination : node where the data is to be executed
        flow_id : Id of the flow that the request/response is part of
        node : the current node at which the request/response arrived
        status: either request=0, response=1, executed=2
        """
        service = content

        if status == self.REQUEST:
            if node == receiver:
                #source_list = self.view.content_source(service)
                if self.debug:
                    print ("Initial REQUEST:")
                    print ("Source list: " + repr(source_list))
                    print ("Event\n time: " + repr(time) + " receiver  " + repr(receiver) + " service " + repr(service) + " node " + repr(node) + " flow_id " + repr(flow_id) + " destination " + repr(data_destination) + " exec_destination " + repr(exec_destination) + " status " + repr(status)) 
                    print ("\n")
                self.flow_copies[flow_id] = len(source_list)
                self.controller.start_session(time, receiver, service, log, flow_id)
            elif node == data_destination:
                status = self.RESPONSE
                self.controller.add_event(time, receiver, service, node, flow_id, data_destination, exec_destination, source_list, status)
                return
            
            #source_list = self.view.content_source(service)
            next_nodes_set = set()
            dest_set = set()
            filtered = 0
            if self.debug:
                print ("Request is on its way to data_destination: " + repr(data_destination))
                print ("Event time: " + repr(time) + " receiver  " + repr(receiver) + " service " + repr(service) + " node " + repr(node) + " flow_id " + repr(flow_id) + " destination " + repr(data_destination) + " exec_destination " + repr(exec_destination) + " status " + repr(status)) 
                print ("\n")
            for source in source_list:
                path = self.view.shortest_path(node, source)
                next_node = path[1]
                if node != receiver and next_node < node: # you always go down in the tree
                    filtered += 1
                else:
                    next_nodes_set.add(next_node)
                    dest_set.add(source)
                if node == receiver:
                    exec_destination = next_node
            
            if len(dest_set) == 1 and data_destination == -1:
                data_destination = next(iter(dest_set))
            for next_node in next_nodes_set:
                linkDelay = self.view.link_delay(node, next_node)
                self.controller.add_event(time+linkDelay, receiver, service, next_node, flow_id, data_destination, exec_destination, source_list, status)

        elif status == self.RESPONSE:
            if node == data_destination:
                if self.debug:
                    print ("Request reached data_destination: " + repr(data_destination))
                    print ("Event time: " + repr(time) + " receiver  " + repr(receiver) + " service " + repr(service) + " node " + repr(node) + " flow_id " + repr(flow_id) + " destination " + repr(data_destination) + " exec_destination " + repr(exec_destination) + " status " + repr(status)) 
                    print ("\n")
                path = self.view.shortest_path(node, exec_destination)
                next_node = path[1]
                linkDelay = self.view.link_delay(node, next_node)
                status = self.RESPONSE
                self.controller.forward_content_hop(node, next_node, flow_id) 
                self.controller.add_event(time+linkDelay, receiver, service, next_node, flow_id, data_destination, exec_destination, source_list, status)
            elif node == exec_destination:
                cs = self.compSpots[node]
                fin_time, vm_indx = cs.getFinishTime(service, time)
                if self.debug:
                    print ("Response reached EXEC_destination: " + repr(exec_destination))
                    print ("Scheduling the execution at vm: " + repr(vm_indx))
                    print ("Event time: " + repr(time) + " receiver  " + repr(receiver) + " service " + repr(service) + " node " + repr(node) + " flow_id " + repr(flow_id) + " destination " + repr(data_destination) + " exec_destination " + repr(exec_destination) + " status " + repr(status)) 
                    print ("\n")
                cs.schedule_service(service, vm_indx, time)
                status = self.EXECUTED
                self.controller.add_event(fin_time, receiver, service, node, flow_id, data_destination, exec_destination, source_list, status)
            else:
                path = self.view.shortest_path(node, exec_destination)
                next_node = path[1]
                linkDelay = self.view.link_delay(node, next_node)
                if self.debug:
                    print ("Response is on its way to Exec_destination: " + repr(exec_destination))
                    print ("Event time: " + repr(time) + " receiver  " + repr(receiver) + " service " + repr(service) + " node " + repr(node) + " flow_id " + repr(flow_id) + " destination " + repr(data_destination) + " exec_destination " + repr(exec_destination) + " status " + repr(status)) 
                    print ("\n")
                self.controller.add_event(time+linkDelay, receiver, service, next_node, flow_id, data_destination, exec_destination, source_list, status)
        elif status == self.EXECUTED:
            if node == receiver:
                if self.debug:
                    print ("Executed response is back to RECEIVER " + repr(receiver))
                    print ("Event time: " + repr(time) + " receiver  " + repr(receiver) + " service " + repr(service) + " node " + repr(node) + " flow_id " + repr(flow_id) + " destination " + repr(data_destination) + " exec_destination " + repr(exec_destination) + " status " + repr(status)) 
                    print ("\n")
                self.flow_copies[flow_id] -= 1
                if self.flow_copies[flow_id] == 0:
                    self.controller.end_session(True, time, flow_id)
                    del self.flow_copies[flow_id]
                return
            else:
                if self.debug:
                    print ("Executed response is back to RECEIVER " + repr(receiver))
                    print ("Event time: " + repr(time) + " receiver  " + repr(receiver) + " service " + repr(service) + " node " + repr(node) + " flow_id " + repr(flow_id) + " destination " + repr(data_destination) + " exec_destination " + repr(exec_destination) + " status " + repr(status)) 
                    print ("\n")
                path = self.view.shortest_path(node, receiver)
                next_node = path[1]
                linkDelay = self.view.link_delay(node, next_node)
                self.controller.add_event(time+linkDelay, receiver, service, next_node, flow_id, data_destination, exec_destination, source_list, status)
        else:
            print ("Error: this should not happen!")
