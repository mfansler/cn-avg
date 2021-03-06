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

"""Cactus graph normalization, ie ensuring the flow is constant across all blocks in a chain"""

import sys
import cnavg.avg.graph as avg
import cnavg.cactus.graph as cactus
import random
import math

def randomChoice(vector):
	if len(vector) == 0:
		return None
	else:
		total = sum(X[0] for X in vector)
		target = random.uniform(0, total)
		cumulative = 0
		for index in range(len(vector)):
			cumulative += vector[index][0]
			if cumulative >= target:
				return vector[index][1]

##########################################
## Normalized Cactus 
##########################################

class NormalizedCactus(cactus.Cactus):
	"""Cactus graph such that the flow is uniform across all blocks in a chain"""

	def __init__(self, cactus):
		self.copy(cactus)
		self.normalize()

	#########################################
	## Test
	#########################################

	def chainMean(self, chain, index):
		return sum(block.copynumber(self, index) * block.length() for block in chain) / sum(block.length() for block in chain)

	def Test(self, chainA, chainB, index):
		meanA = self.chainMean(chainA, index)
		meanB = self.chainMean(chainB, index)
		return abs(meanA - meanB) > 0.1 * min(abs(meanA), abs(meanB)) and all(abs(meanA - B.copynumber(self, index)) < abs(meanB - B.copynumber(self, index)) for B in chainA)

	##########################################
	## Test for normalization
	##########################################
	def testSegment(self, indexA, indexB, chain):
		ploidy = chain[indexA].ploidy(self)
		if not all(chain[X].ploidy(self) == ploidy for X in range(indexA, indexB)):
			return []
			
		chainA = cactus.Chain(chain[indexA:indexB])
		chainB = cactus.Chain(chain[indexB:] + chain[:indexA])
		if self.chainIsPloidyDetermined(chain) and not all(self.Test(chainA, chainB, index) for index in range(ploidy)):
			return []

		length = indexB - indexA
		weight = math.exp(length)
		return [(weight, cactus.Chain(chain[indexA:indexB]))]

	def nodeCutpoints2(self, index, chain):
		return map(lambda X: self.testSegment(X, index, chain), range(index))

	def nodeCutpoints(self, index, chain):
		return sum(self.nodeCutpoints2(index, chain), [])

	def cutpoints2(self, chain):
		return map(lambda X: self.nodeCutpoints(X, chain), range(len(chain)))

	def cutpoints(self, chain):
		return sum(self.cutpoints2(chain), [])

	def chainIsUnnormalized(self, chain):
		if len(chain) > 1:
			return self.cutpoints(chain)
		else:
			return []

	def unnormalizedChains(self):
		return sum(map(self.chainIsUnnormalized, self.chains), [])

	def unnormalizedChain(self):
		return randomChoice(self.unnormalizedChains())

	##########################################
	## Pinching
	##########################################
	def pinchUnnormalizedChain(self, chain):
		if len(chain) == 1:
			mergedNets = set((self.nodeNet(N) for N in chain[0].nodes))
		elif len(chain) == 2:
			startNets = set((self.nodeNet(N) for N in chain[0].nodes))
			endNets = set((self.nodeNet(N) for N in chain[-1].nodes))
			mergedNets = startNets ^ endNets
		else:
			startNets = set((self.nodeNet(N) for N in chain[0].nodes))
			endNets = set((self.nodeNet(N) for N in chain[-1].nodes))
			insideNets = set((self.nodeNet(N) for B in chain[1:-1] for N in B.nodes))
			mergedNets = (startNets | endNets) - insideNets

		return filter(lambda X: X not in mergedNets, self.nets) + [cactus.Net(reduce(lambda X, Y: X | set(Y.groups), mergedNets, set()))]

	def pinchChain(self, chain):
		# Updating the Nets structures
		self.nets = self.pinchUnnormalizedChain(chain)
		self.groupNet = dict((G, N) for N in self.nets for G in N.groups)

		# Updating the Chains structures
		groups = [G for N in self.nets for G in N.groups]
		blocks = self.computeBlocks(groups)
		self.nodeBlock = dict((N, B) for B in set(P[1] for X in blocks.values() for P in X) for N in B.nodes)
		self.chains = self.computeChains(blocks)
		self.blockChain = dict((B, C) for C in self.chains for B in C)
		assert all(X in self.blockChain for X in self.nodeBlock.values())

		return self

	##########################################
	## Test
	##########################################
	def blocksAreFullyNormalized(self, cactus, chain):
		for index in range(chain[0].ploidy(cactus)):
			return map(lambda X: X.copynumber(cactus, index) == chain[0].copynumber(cactus, index) , chain)

	def chainIsFullyNormalized(self, cactus, chain):
		assert all(self.blocksAreFullyNormalized(cactus, chain))
		return True

	def chainsAreFullyNormalized(self):
		return map(lambda X: self.chainIsFullyNormalized(self, X), self.chains)

	def chainIsPloidyDetermined(self, chain):
		ploidy = chain[0].ploidy(self)
		return all(X.ploidy(self) == ploidy for X in chain)

	def chainsArePloidyDetermined(self):
		return map(self.chainIsPloidyDetermined, self.chains)

	def isFullyNormalized(self):
		assert all(self.chainsArePloidyDetermined())
		assert all(self.chainsAreFullyNormalized())
		return True

	##########################################
	## Master function
	##########################################
	def normalize(self):
		"""Normalizes an arbitrary cactus graph"""
		current = self
		while True:
			chain = current.unnormalizedChain()
			if chain is None:
				return current 
			else:
				current = current.pinchChain(chain)

##########################################
## Unit Test
##########################################

def main():
	G = avg.randomEulerianGraph(100)
	C = cactus.Cactus(G)
	print C 
	print '>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>'
	N = NormalizedCactus(C)
	print N
	for c in N.chains:
		print c
	assert N.isFullyNormalized()

if __name__ == "__main__":
	main()
