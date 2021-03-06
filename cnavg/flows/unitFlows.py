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

"""Near-simple flows"""

import sys
import random

import cnavg.avg.graph as avg
import cnavg.avg.balanced as balancedAVG
import cnavg.cactus.graph as cactus
import cnavg.cactusSampling.sampling as normalized
import cnavg.cactus.oriented as oriented
import cnavg.cactus.balanced as balancedCactus
import cnavg.historySampling.cycleCover as cycleCover
from cnavg.history.overlap import Overlap
from cnavg.flows.flows import Event
from cnavg.flows.flows import Cycle

#########################################
## Self overlaps
#########################################

def adjacencyIndex(edge):
	return (min(edge.start, edge.finish), max(edge.start, edge.finish), edge.index)

def cycleAdjacencyIndexes(cycle):
	return [(adjacencyIndex(X[1]), X[0]) for X in enumerate(cycle)]

def sortedCycleAdjacencyIndexes(cycle): 
	return sorted(cycleAdjacencyIndexes(cycle))

def cycleSelfOverlaps(cycle):
	overlaps = []
	indexes = sortedCycleAdjacencyIndexes(cycle)
	for index in range(len(indexes) - 1):
		head = indexes[index]
		next = indexes[index+1]
		if head[0] == next[0]:
			overlaps += [Overlap(None, min(head[1], next[1]), None, max(head[1], next[1]))]
	return overlaps
	
#########################################
## Even overlaps
#########################################

def breakEvenOverlap(event, knot):
	return [Event(Cycle(event.cycle[knot.localCut:knot.remoteCut])), Event(Cycle(event.cycle[knot.remoteCut:] + event.cycle[:knot.localCut]))]

def getEvenOverlapIndices(cycle):
	return filter(lambda X: cycle[X.localCut].start == cycle[X.remoteCut].start, cycleSelfOverlaps(cycle))

def getEvenOverlapIndex(event):
	overlaps = getEvenOverlapIndices(event.cycle)
	if len(overlaps) == 0:
		return None	
	else:
		return random.choice(overlaps)

def breakEvenOverlaps_Event(event):
	knot = getEvenOverlapIndex(event)
	if knot is None:
		return [event]
	else:
		return breakEvenOverlaps(breakEvenOverlap(event, knot))

def breakEvenOverlaps(events):
	return sum(map(breakEvenOverlaps_Event, events),[])

#########################################
## Finding repeat boundaries
#########################################

def getStartOfDirectRepeat(cycle, start1, pos1, start2, pos2):
	next1 = (pos1 - 1) % len(cycle)
	next2 = (pos2 - 1) % len(cycle)
	if next1 == start1 or next2 == start2:
		return pos1, pos2
	elif cycle[next1].start != cycle[next2].start:
		return pos1, pos2
	elif cycle[next1].index != cycle[next2].index:
		return pos1, pos2
	else:
		return getStartOfDirectRepeat(cycle, start1, next1, start2, next2)

def getEndOfDirectRepeat(cycle, start1, pos1, start2,pos2):
	next1 = (pos1 + 1) % len(cycle)
	next2 = (pos2 + 1) % len(cycle)
	if next1 == start1 or next2 == start2:
		return pos1, pos2
	elif cycle[next1].finish != cycle[next2].finish:
		return pos1, pos2
	elif cycle[next1].index != cycle[next2].index:
		return pos1, pos2
	else:
		return getEndOfDirectRepeat(cycle, start1, next1, start2, next2)

def getStartOfReverseRepeat(cycle, start1, pos1, start2, pos2):
	next1 = (pos1 - 1) % len(cycle)
	next2 = (pos2 + 1) % len(cycle)
	if next1 == start1 or next2 == start2:
		return pos1, pos2
	elif cycle[next1].start != cycle[next2].finish:
		return pos1, pos2
	elif cycle[next1].index != cycle[next2].index:
		return pos1, pos2
	else:
		return getStartOfReverseRepeat(cycle, start1, next1, start2, next2)

def getEndOfReverseRepeat(cycle, start1, pos1, start2, pos2):
	next1 = (pos1 + 1) % len(cycle)
	next2 = (pos2 - 1) % len(cycle)
	if next1 == start1 or next2 == start2:
		return pos1, pos2
	elif cycle[next1].finish != cycle[next2].start:
		return pos1, pos2
	elif cycle[next1].index != cycle[next2].index:
		return pos1, pos2
	else:
		return getEndOfReverseRepeat(cycle, start1, next1, start2, next2)

#########################################
## Odd overlaps
#########################################

def splitDirectRedundancy(cycle, split):
	a1, a2 = getStartOfDirectRepeat(cycle, split.localCut, split.localCut, split.remoteCut, split.remoteCut)
	if (a1 - 1) % len(cycle) == split.localCut:
		# Double hairpin loop
		return []
	b1, b2 = getEndOfDirectRepeat(cycle, split.localCut, split.localCut, split.remoteCut, split.remoteCut)
	cycle = cycle.startAt(a1)
	a2 = (a2 - a1) % len(cycle)
	b1 = (b1 - a1) % len(cycle)
	b2 = (b2 - a1) % len(cycle)
	if b1 + 1 < a2 and b2 + 1 < len(cycle): 
		return [Event(Cycle(cycle[b1+1:a2]) + Cycle(cycle[b2+1:]).reverse())]
	elif b1 + 1 >= a2:
		# Fucking weird tandem repeat style craziness
		return [Event(Cycle(cycle[2 * a2:]))]
	else:
		# Symmetrical oddball
		cycle = cycle.startAt(a2)
		a1 = -a2 % len(cycle)
		return [Event(Cycle(cycle[2 * a1:]))]


def splitReverseRedundancy(cycle, split):
	a1, a2 = getStartOfReverseRepeat(cycle, split.localCut, split.localCut, split.remoteCut, split.remoteCut)
	if (a1 - 1) % len(cycle) == split.localCut:
		# Double hairpin loop
		return []
	b1, b2 = getEndOfReverseRepeat(cycle, split.localCut, split.localCut, split.remoteCut, split.remoteCut)
	cycle = cycle.startAt(a1)
	a2 = (a2 - a1) % len(cycle)
	b1 = (b1 - a1) % len(cycle)
	b2 = (b2 - a1) % len(cycle)

	if b2 == 0 and a2 == b1:
		# Tandem dupe passage...?
		return [Event(Cycle(cycle[b1+1:]))]
	else:
		if len(cycle) == 0 or b1 + 1 >= b2 or a2 + 1 >= len(cycle) or cycle[b1+1].value is None or cycle[a2+1].value is None:
			print cycle
			print a2
			print b1
			print b2
			sys.stdout.flush()
		event1 = Event(Cycle(cycle[b1+1:b2]))
		event2 = Event(Cycle(cycle[a2+1:]))
		return [event1, event2]

def splitRedundancy(cycle, split):
	edge1 = cycle[split.localCut]
	edge2 = cycle[split.remoteCut]
	if edge1.start == edge2.start:
		return splitDirectRedundancy(cycle, split)
	else:
		return splitReverseRedundancy(cycle, split)

def destructiveOverlaps(cycle):
	return filter(lambda X: cycle[X.localCut].value == -cycle[X.remoteCut].value, cycleSelfOverlaps(cycle))

def detectRedundancy(event):
	redundancies = destructiveOverlaps(event.cycle)
	if len(redundancies) == 0:
		return None
	else:
		return redundancies[0]

def splitRedundancies_Event(event):
	redundancy = detectRedundancy(event)
	if redundancy is None:
		return [event]
	else:
		return splitEventsRedundancies(splitRedundancy(event.cycle, redundancy)) 

def splitEventsRedundancies(eventList):
	return sum(map(splitRedundancies_Event, eventList), [])

######################################
## Hairpins
######################################

def destructiveOverlap(edge1, edge2):
	return edge1.start == edge2.finish and edge1.finish == edge2.start and edge1.index == edge2.index and edge1.value == -edge2.value

def isHairpinIndex(event, index):
	edge1 = event.cycle[index] 
	edge2 = event.cycle[(index + 1) % len(event.cycle)]
	return destructiveOverlap(edge1, edge2)

def detectHairpin(event):
	for index in range(len(event.cycle)):
		if isHairpinIndex(event, index):
			return index
	return None

def hairpinLength(event, index):
	for length in range(1, len(event.cycle)/2):
		edge1 = event.cycle[(index - length) % len(event.cycle)]
		edge2 = event.cycle[(index + 1 + length) % len(event.cycle)]
		if not destructiveOverlap(edge1, edge2):
			return length
	return len(event.cycle)/2

def fixHairpin(event, index):
	length = hairpinLength(event, index)
	if length < len(event.cycle) / 2:
		res = [Event(Cycle(event.cycle.startAt(index+1)[length:-length]))]
		res[0].validate()
		return res
	else:
		return []

def removeEventHairpins(event):
	hairpin = detectHairpin(event)
	if hairpin is None:
		return [event]
	else:
		return removeEventsHairpins(fixHairpin(event, hairpin))

def removeEventsHairpins(eventList):
	return sum(map(removeEventHairpins, eventList), [])

#########################################
## Master function 
#########################################

def simplifyEventCycles(eventList):
	res = breakEvenOverlaps(splitEventsRedundancies(removeEventsHairpins(eventList)))
	return res

#########################################
## Unit test
#########################################

def isUnitFlow(cycle):
	assert all(cycle[overlap.localCut].value == cycle[overlap.remoteCut].value and cycle[overlap.localCut].start != cycle[remoteCut].start for overlap in cycleSelfOverlaps(cycle))
	return True

def areUnitFlows(cycles):
	assert all(map(isUnitFlow, cycles))
	return True

def main():
	G = avg.randomEulerianGraph(10)
	C = cactus.Cactus(G)
	NC = normalized.NormalizedCactus(C)
	BC = balancedCactus.BalancedCactus(NC)
	OC = oriented.OrientedCactus(BC)
	H = cycleCover.initialHistory(OC)
	assert areUnitFlows(X.cycle for X in H.parent)

if __name__ == "__main__":
	main()
