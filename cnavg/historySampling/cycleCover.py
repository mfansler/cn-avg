# Copyright (c) 2012, Daniel Zerbino
# All rights reserved.
# 
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are
# met:
# 
# (1) Redistributions of source code must retain the above copyright
# notice, this list of conditions and the following disclaimer. 
# 
# (2) Redistributions in binary form must reproduce the above copyright
# notice, this list of conditions and the following disclaimer in
# the documentation and/or other materials provided with the
# distribution.  
# 
# (3)The name of the author may not be used to
# endorse or promote products derived from this software without
# specific prior written permission.
# 
# THIS SOFTWARE IS PROVIDED BY THE AUTHOR ``AS IS'' AND ANY EXPRESS OR
# IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY DIRECT,
# INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
# HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT,
# STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING
# IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
#!/usr/bin/env python

"""Producing an initial flow history underlying a metagenomic net flow change"""

import random
import copy
from cnavg.flows.edge import Edge
from cnavg.flows.cycle import Cycle
from cnavg.flows.flows import Event
from cnavg.history.history import History

import cnavg.avg.graph as avg
import cnavg.avg.module as module
import cnavg.history.euclidian as euclidian
import cnavg.history.constrained as constrained

import itertools
from heapq import *
from types import *

MIN_FLOW=1e-10
MIN_CYCLE_FLOW=1e-2

########################################
## Closing off pseudo-telomeres:
########################################
def extractPseudoTelomereCycle(module, edges):
	firstNode = edges[0].start
	lastNode = edges[-1].finish
	if firstNode == lastNode:
		return module, edges
	else:
		nextNode = module[lastNode].twin
		edge1 = Edge(lastNode, nextNode, edges[0].value, 0)	
		module.removeEdgeFlow(edge1)
		followingNode = module[nextNode].partner
		edge2 = Edge(nextNode, followingNode, -edges[0].value, -1)	
		module.removeEdgeFlow(edge2)
		return extractPseudoTelomereCycle(module, edges + [edge1, edge2])

def closePseudoTelomere(data, index):
	module, history = data
	PT = random.choice(list(module.pseudotelomeres))
	twin = module[PT].twin
	edge1 = Edge(PT, twin, -module.segments[PT][index], index)
	edge2 = Edge(twin, module[twin].partner, module.segments[PT][index], -1)
	module.removeEdgeFlow(edge1)
	module.removeEdgeFlow(edge2)
	module, edges = extractPseudoTelomereCycle(module, [edge1, edge2])
	cycle = Cycle(edges)
	event = Event(cycle)
	history.absorbEvent(event)
	return module, history

def closePseudoTelomeres(module, history):
	if len(module.pseudotelomeres) == 0:
		return module, history
	else:
		pseudotelomere = random.choice(list(module.pseudotelomeres))
		segmentCount = len(module.segments[pseudotelomere])
		return reduce(closePseudoTelomere, range(segmentCount), (module, history))

#############################################
## Pre-compute signed node adjacencies
#############################################

nodeAdjacenciesTable = None

def realValue(adjacency, module):
	if adjacency[3] == -1:
		return module[adjacency[0]].edges[adjacency[1]]
	else:
		return -module.segments[adjacency[0]][adjacency[3]]

def nodePairAdjacency(node, nodeB, module):
	return (node, nodeB, module[node].edges[nodeB], -1)

def nodePairSegment(node, index, module):
	return (node, module[node].twin, -module.segments[node][index], index)

def nodeAdjacencies(node, module):
	adjacencies = [nodePairAdjacency(node, X, module) for X in module[node].edges]
	segments = [nodePairSegment(node, X, module) for X in range(len(module.segments[node]))]
	return adjacencies + segments

def computeNodeAdjacencies(module):
	return dict((X, nodeAdjacencies(X, module)) for X in module.nodes())

#############################################
## Search for small edge
#############################################

def positiveNeighbourhood(node, module, missingEdges=None):
	return filter(lambda X: X[2] > MIN_FLOW and (missingEdges == None or (X[0], X[1], X[3]) not in missingEdges), nodeAdjacenciesTable[node])

def negativeNeighbourhood(node, module, missingEdges=None):
	return filter(lambda X: X[2] < -MIN_FLOW and (missingEdges == None or (X[0], X[1], X[3]) not in missingEdges), nodeAdjacenciesTable[node])

def phasedNeighbourhood(node, module, value, missingEdges=None):
	if value > 0:
		return [X[1] for X in positiveNeighbourhood(node, module, missingEdges)] 
	else:
		return [X[1] for X in negativeNeighbourhood(node, module, missingEdges)] 

def oppositeNeighbourhood(node, module, value, missingEdges=None):
	if value > 0:
		return [X[1] for X in negativeNeighbourhood(node, module, missingEdges)] 
	else:
		return [X[1] for X in positiveNeighbourhood(node, module, missingEdges)] 

def adjacencies(module):
	return sum(nodeAdjacenciesTable.values(), [])

def minimumEdge(module):
	hairpins = filter(lambda X: X[0] == X[1], nodeAdjacenciesTable[module.stub])
	outlets = filter(lambda X: X[0] != X[1] and abs(X[2]) > MIN_FLOW, nodeAdjacenciesTable[module.stub])
	if len(hairpins) == 1 and len(outlets) == 1:
		res = outlets[0]
		return Edge(res[1], res[0], res[2]/2, res[3])

	edges = filter(lambda X: X[0] != X[1] and abs(X[2]) > MIN_FLOW, adjacencies(module))
	if len(edges) == 0:
		return None
	else:
		res = min(edges, key=lambda X: abs(X[2]))
		return Edge(res[0], res[1], res[2], res[3])

#############################################
## Dijkstra
#############################################

def add_node(distance, node, counter, count, taskfinder, todo):
    if count is None:
	count = counter.next()
    entry = [distance, count, node]
    taskfinder[node] = entry 
    heappush(todo, entry)	

def getNextNode(todo, taskfinder):
    while len(todo) > 0:
	distance, count, node = heappop(todo)
	if count != 0:
	    del taskfinder[node]
            return (distance, node)
    return (None, None)

def redistanceNode(priority, task, taskfinder, todo, counter):
    entry = taskfinder[task]
    add_node(priority, task, counter, entry[1], taskfinder, todo)
    entry[1] = 0
	
def computeEvenDistances(origin, value, graph, missingEdges=None):
    counter = itertools.count(1)
    distances = dict(((node, -1) for node in graph))
    status = dict(((node, 0) for node in graph))
    steps = set()
    taskfinder = dict()
    todo = [] 
    add_node(0, origin, counter, None, taskfinder, todo)

    distances[origin] = 0
    while len(todo) > 0: 
	(dist, node) = getNextNode(todo, taskfinder)

	if dist is None:
	    break
        status[node] = 2

	for node2 in oppositeNeighbourhood(node, graph, value, missingEdges):
	    if node2 in steps:
		    continue
	    steps.add(node2)

	    for node3 in phasedNeighbourhood(node2, graph, value, missingEdges):
		    if node3 == origin:
			    continue
		    newdist = dist + 1 

		    if status[node3] > 1:
			continue
		    elif status[node3] == 1 and newdist < distances[node3]:
			redistanceNode(newdist, node3, taskfinder, todo, counter)
			distances[node3] = newdist
		    elif status[node3] == 0:
			status[node3] = 1 
			distances[node3] = newdist 
			add_node(newdist, node3, counter, None, taskfinder, todo)

    return distances

def computeOddDistances(node, value, graph, missingEdges, blockTwin=False):
    counter = itertools.count(1)
    distances = dict(((node, -1) for node in graph))
    status = dict(((node, 0) for node in graph))
    steps = set()
    taskfinder = {}
    todo = [] 

    steps.add(node)
    for node2 in oppositeNeighbourhood(node, graph, value, missingEdges):
	if status[node2] > 0:
		continue
	# Quick and dirty trick to prevent the creation of small diploid cycles
	if blockTwin and node2 == graph[node].twin:
		continue
	status[node2] = 1 
	distances[node2] = 1
	add_node(1, node2, counter, None, taskfinder, todo)

    while len(todo) > 0: 
	(dist, node) = getNextNode(todo, taskfinder)
	if dist is None:
	    break
        status[node] = 2

	for node2 in phasedNeighbourhood(node, graph, value, missingEdges):
	    if node2 in steps:
		    continue
	    steps.add(node2) 

	    for node3 in oppositeNeighbourhood(node2, graph, value, missingEdges):
		    newdist = dist + 1 

		    if status[node3] > 1:
			continue
		    elif status[node3] == 1 and newdist < distances[node3]:
			redistanceNode(newdist, node3, taskfinder, todo, counter)
			distances[node3] = newdist
		    elif status[node3] == 0:
			status[node3] = 1 
			distances[node3] = newdist 
			add_node(newdist, node3, counter, None, taskfinder, todo)


    return distances

def dijkstra(node, value, graph, missingEdges=None, blockTwin=False):
    evenDistances = computeEvenDistances(node, value, graph, missingEdges)
    oddDistances = computeOddDistances(node, value, graph, missingEdges, blockTwin)
    return dict((X, (evenDistances[X], oddDistances[X])) for X in graph)

#############################################
## Heuristic propagation
#############################################

def signedEdges(node, module, sign, missingEdges=None):
	return filter(lambda X: X[2] * sign > MIN_FLOW, nodeAdjacenciesTable[node])

def nodeDistances(node, module, distances, sign, phase, missingEdges):
	if phase:
		return map(lambda X: distances[X[1]][1], signedEdges(node, module, sign, missingEdges))
	else:
		return map(lambda X: distances[X[1]][0], signedEdges(node, module, sign, missingEdges))

def minDist(node, module, distances, sign, phase, missingEdges=None):
	candidates = filter(lambda X: X >= 0, nodeDistances(node, module, distances, sign, phase, missingEdges))
	if len(candidates) == 0:
		return None
	return min(candidates)

def nextNodes(node, module, distances, sign, phase, missingEdges=None):
	dist = minDist(node, module, distances, sign, phase)
	if dist is None:
		return None
	edges = signedEdges(node, module, sign, missingEdges)
	if phase:
		return filter(lambda X: distances[X[1]][1] == dist, edges)
	else:
		return filter(lambda X: distances[X[1]][0] == dist, edges)

def chooseNextNode(node, module, distances, sign, phase, missingEdges=None):
	vals = nextNodes(node, module, distances, sign, phase, missingEdges=None)
	if vals is None:
		return None
	else:
		return random.choice(vals)

def signf(val):
	if val > 0:
		return 1
	else:
		return -1

def extendCycle(cycle, module, distances, sign, missingEdges=None):
	edgeData = chooseNextNode(cycle[-1].finish, module, distances, signf(cycle.value * sign), sign > 0, missingEdges)
	if edgeData is None or abs(realValue(edgeData,module)) <= MIN_FLOW:
		return None, module
	edge = Edge(edgeData[0], edgeData[1], edgeData[2], edgeData[3])
	edge.value = cycle.value * sign
	module.removeEdgeFlow(edge)
	cycle.append(edge)

	if len(cycle) % 2 == 0 and edge.finish == cycle[0].start:	
		return cycle, module
	else:
		return extendCycle(cycle, module, distances, -sign)

def extractCycle(edge, module):
	module.removeEdgeFlow(edge)
	distances = dijkstra(edge.start, edge.value, module, blockTwin=(edge.index >= 0))
	cycle, module = extendCycle(Cycle([edge]), module, distances, -1)
	if cycle is None:
		# Failed path lost in approximation (Random search above)
		return None, module
	else:
		# Job succeeded
		return Event(cycle), module

def pickOutCycle(module):
	global nodeAdjacenciesTable
	nodeAdjacenciesTable = computeNodeAdjacencies(module)
	edge = minimumEdge(module) 
	if edge is None:
		# Job finished
		return None, None
	else:
		return extractCycle(edge, module)

def pickOutCycles(module, history):
	event, newModule = pickOutCycle(module)
	while newModule is not None:
		if event is not None:
			if len(history.events) % 100 == 0:
				print 'CYCLE', len(history.events)
			if len(history.events) > 10000:
				print module
				print history.events[-1]
				edge = minimumEdge(module) 
				print edge
				print edge.value
				assert False
			history.absorbEvent(event)
		event, newModule = pickOutCycle(module)
	return history

########################################
## Filter out low value cycles
########################################

def highFlowHistory(history, cactusHistory, net):
	res = euclidian.EuclidianHistory(history.module)
	cactusHistory.update(net, res)
	events = list(sorted(history.events, key=lambda X: -X.ratio))
	for event in events:
		if event.ratio > MIN_CYCLE_FLOW:
			cactusHistory.absorbEvent(res, event)
	cactusHistory.updateCNVs(net, res)
	return res

########################################
## Finding an initial net history
########################################

def seedHistory(cactusHistory, net, cnvs):
	M = module.Module(net, cactusHistory.cactus, cnvs)
	H = History(M)
	MC = copy.copy(M)
	MC, H1 = closePseudoTelomeres(MC, H)
	H2 = pickOutCycles(MC, H1)
	H3 = highFlowHistory(H2, cactusHistory, net)
	return H3

########################################
## Finding an initial cactus graph history
########################################

def propagateInitialHistory_Chain(chain, history, cnvs):
	return reduce(lambda X, Y: propagateInitialHistory_Net(Y, X, cnvs), history.cactus.chains2Nets[chain], history) 

def propagateInitialHistory_Net(net, history, cnvs):
	seedHistory(history, net, cnvs)
	return reduce(lambda X,Y: propagateInitialHistory_Chain(Y, X, history.chainCNVs[Y]), history.cactus.nets2Chains[net], history)

###############################################
## Master function
###############################################

def initialHistory(cactus):
	print "Extracting initial history from Cactus"
	return propagateInitialHistory_Net(cactus.rootNet, constrained.ConstrainedHistory(cactus), [])

###############################################
## Unit test
###############################################

def main():
	G = avg.randomNearEulerianGraph(10)
	C = cactus.Cactus(G)
	N = normalized.NormalizedCactus(C)
	O = oriented.OrientedCactus(N)
	print O
	print '>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>'
	H = initialHistory(O)
	print H
	H.validate()

if __name__ == "__main__":
	import cnavg.cactus.graph as cactus
	import cnavg.cactus.oriented as oriented
	import cnavg.cactusSampling.sampling as normalized
	main()
