# -*- coding: utf-8 -*-
"""Computational Spot implementation
This module contains the implementation of a set of VMs residing at a node. Each VM is abstracted as a FIFO queue. 
"""
from __future__ import division
from collections import deque
import random
import abc
import copy

import numpy as np

from icarus.util import inheritdoc

__all__ = [
        'ComputationalSpot'
           ]


class ComputationalSpot(object):
    """ 
    A set of computational resources, where the basic unit of computational resource 
    is a VM. Each VM is bound to run a specific service instance and abstracted as a 
    Queue. The service time of the Queue is extracted from the service properties. 
    """

    def __init__(self, numOfVMs, n_services, services, node, dist=None, measurement_interval = 5, ranking_interval = 20):
        """Constructor

        Parameters
        ----------
        numOfVMs: total number of VMs available at the computational spot
        n_services : size of service population
        services : list of all the services with their attributes
        measurement_interval : perform upstream (i.e., probe) measurement and decide which services to run.
        """
        
        self.numOfVMs = numOfVMs
        if self.numOfVMs == 0:
            self.numOfVMs = 1
            numOfVMs = 1
        #print ("Number of VMs @node: " + repr(node) + " " + repr(self.numOfVMs))
        self.n_services = n_services
        # number of VMs per service
        self.vm_counts = {x : 0 for x in range(0, n_services)}
        # Hypothetical finish time of the last request (i.e., tail of the queue)
        self.virtualTailFinishTime = {x : 0 for x in range(0, n_services)}
        # VM indices of each service
        self.vmIndex = {x : [] for x in range(0, n_services)}
        # VM index to service assignment
        self.vmAssignment = {x: [] for x in range(0, numOfVMs)}
        # Actual VM queue occupancies
        self.vmTailFinishTime = [0.0 for x in range(0, numOfVMs)]
        # VM idle times
        self.idleTime = [0 for x in range(0, numOfVMs)]
        # virtual VM idle times
        self.virtual_idleTime = [0 for x in range(0, n_services)]
        # vm request counts
        self.vm_requests = [0 for x in range(0, numOfVMs)]
        # virtual service requests
        self.virtual_requests = [0 for x in range(0, n_services)]
        
        self.services = services
        self.view = None
        self.node = node

        vm_index = 0
        if dist is None:
            # setup a random set of services to run initially
            for x in range(0, numOfVMs):
                service_index = random.choice(range(0, n_services))
                self.vm_counts[service_index] += 1
                self.vmIndex[service_index].append(vm_index)
                self.vmAssignment[vm_index] = service_index
                vm_index += 1

    def getIdleTime(self, indx, time):
        """
        Parameters
        ----------
        indx : index of the VM
        time    : current time

        Return
        ------
        idle_time : length of the time period, during which the VM has been idle
        """

        if self.vmTailFinishTime[indx] < time:
            self.idleTime[indx] += time - self.vmTailFinishTime[indx]
            self.vmTailFinishTime[indx] = time

        return self.idleTime[indx]

    def getVirtualIdleTime(self, service, time):
        """
        Parameters
        ----------
        service : index of the service
        time : current time

        Return
        ------
        idle_time : length of the time period during which the virtual vm was idle
        """
        
        if self.virtualTailFinishTime[service] < time:
            self.virtual_idleTime[service] += time - self.virtualTailFinishTime[service]
            self.virtualTailFinishTime[service] = time

        return self.virtual_idleTime[service]

    def resetIdleTime(self, indx):
        self.idleTime[indx] = 0.0

    def resetVirtualIdleTime(self, service):
        self.virtual_idleTime[service] = 0.0

    def getFinishTime(self, service, time):
        """
        Parameters
        ----------
        time    : current time

        Return
        ------
        comp_time : is when the task is going to be finished (after queuing + execution)
        vm_index : index of the VM that will execute the task
        """

        serviceTime = self.services[service].service_time

        minFinishTime = float('inf')
        min_index = 0
        for index in range(0, self.numOfVMs):
            if self.vmTailFinishTime[index] < time:
                self.idleTime[index] += time - self.vmTailFinishTime[index]
                self.vmTailFinishTime[index] = time
            if self.vmTailFinishTime[index] < minFinishTime:
                minFinishTime = self.vmTailFinishTime[index]
                min_index = index
        return [minFinishTime+serviceTime, min_index]

    def update_counters(self, time):
        
        for service in range(0, self.n_services):
            if self.vm_counts[service] > 0:
                self.getFinishTime(service, time)
            else:
                self.getVirtualTailFinishTime(service, time)
                
    def reassign_vm(self, vm, service, debug):
        """
        Instantiate service at the given vm
        """
        if self.vmAssignment[vm] == service:
            raise ValueError("Error in reassign_vm: the vm is assigned to the same service")
            
        if self.vm_counts[self.vmAssignment[vm]] == 0:
            raise ValueError("Error in reassign_vm: vmAssignment and service_counts are inconsistent")

        old_service = self.vmAssignment[vm]
        if debug:
            print "Replacing service: " + repr(old_service) + " with: " + repr(service) + " at node: " + repr(self.node) 
        self.vmIndex[old_service].remove(vm)
        self.vmIndex[service].append(vm)
        self.vmAssignment[vm] = service
        self.vm_counts[service] += 1
        self.vm_counts[old_service] -= 1

    def has(self, service):
        """
        Return
        ------
        True: if the service is instantiated at this computational spot
        False: otherwise
        """
        if self.num_services[service] > 0:
            return True
        
        return False

    def getVirtualTailFinishTime(self, service, time):
        """ get finish time of a request in a virtual queue
        """

        finishTime = self.virtualTailFinishTime[service]
        if finishTime < time:
            self.virtual_idleTime[service] += time - finishTime
            self.virtualTailFinishTime[service] = time
            return time
        else:
            return finishTime

    def runVirtualService(self, service, time, deadline, return_delay):
        """ 
        compute hypothetical finish time of a request sent upstream

        Return
        ------
        True: if job can be run successfully 
        False: Otherwise
        """
        serviceTime = self.services[service].service_time
        tailFinish = self.getVirtualTailFinishTime(service, time)
        completion = tailFinish + serviceTime

        if completion + return_delay <= deadline:
            self.virtualTailFinishTime[service] += serviceTime
            self.virtual_requests[service] += 1
            return [True, completion] #Success

        return [False, completion]
    
    def print_stats(self):
        print "Printing Stats for node: " + repr(self.node)
        for service in range(0, self.n_services):
            if self.vm_counts[service] > 0:
                print "\tFor instantiated service: " + repr(service)
                for indx in self.vmIndex[service]:
                    print "\t\t" + repr(self.vm_requests[indx]) + " requests processed on VM " + repr(indx) 
            else:
                print "\tFor stored (uninstantiated) service: " + repr(service)
                print "\t\t" + repr(self.virtual_requests[service]) + " requests virtually processed"

    def perform_measurement(self, service, time, deadline):
        """ perform measurement (i.e., equivalent to sending a probe upstream)
        """
        curr_node = self.node
        path = self.view.shortest_path(curr_node, self.view.content_source(service))
        print ("Path is: " + repr(path))
        latency = 0
        remaining_deadline = deadline
        curr_time = time
        for node in path[1:len(path)-1]:
            cs = self.view.compSpot(node)
            remaining_deadline -= 2*self.view.link_delay(curr_node, node)
            curr_time += self.view.link_delay(curr_node, node)
            if node is 0: # reached the cloud node
                service_time = self.services[service].service_time
                remaining_deadline -= service_time
                if cs.getFinishTime(service, time) > curr_time:
                    remaining_deadline -= cs.getFinishTime(service, time) - curr_time
            elif cs.vm_counts[service] > 0:
                service_time = self.services[service].service_time
                if cs.getFinishTime(service, time) > curr_time:
                    if cs.getFinishTime(service, time) + service_time < curr_time + remaining_deadline:
                        remaining_deadline -= cs.getFinishTime(service, time) + service_time - curr_time
                        break
                else:
                    if curr_time + service_time < curr_time + remaining_deadline:
                        remaining_deadline -= service_time
                        break
            curr_node = node
        
        self.last_measurement_time[service] = time 

    #def process_request(self, service, time, deadline, flow_id):
        """
        perform bookkeeping
        """
        """
        self.arrival_time[flow_id] = time
        self.service_deadline[service] = deadline
        self.deadline[flow_id] = deadline
        """
    def schedule_service(self, service, vm_indx, time):
        """schedule the service to run at this computational spot (place it in the queue).
        Parameter
        ---------
        service : service id (integer)
        vm_indx : the index of the VM that the service request is assigned to.
        """

        
        if self.vmTailFinishTime[vm_indx] < time:
            self.vmTailFinishTime[vm_indx] = time

        self.vmTailFinishTime[vm_indx] += self.services[service].service_time
        self.vm_requests[vm_indx] += 1

    #def process_response(self, service, time, flow_id):
        """Process an arriving response packet

        NOTE: The request was not serviced at this Spot (for whatever reason) and 
        handled upstream (e.g., cloud)

        Parameters
        ----------
        service : service id (integer) 
        time : the arrival time of the service response
        flow_id : the flow identifier (integer) 
        """
        """
        if flow_id in self.virtual_finish.keys():
            self.virtual_requests[service] += 1
            arr_time = self.arrival_time[flow_id]
            elapsed = time - arr_time
            contribution = (time + elapsed - self.virtual_finish[flow_id])/self.deadline[flow_id]
            if contribution < 0:
                print ("Contribution less than 0 for service: " + repr(service) + " at node " + repr(self.node))
                contribution = 0.0
            elif contribution > 1.0:
                contribution = 1.0
            self.virtual_metric[service] += contribution
            self.virtual_finish.pop(flow_id, None)
        else:
            self.forwarded_requests[service] += 1

        self.upstream_service_time[service] = time - self.arrival_time[flow_id]
        self.last_measurement_time[service] = time
        self.arrival_time.pop(flow_id, None)
        self.deadline.pop(flow_id, None)
        """
