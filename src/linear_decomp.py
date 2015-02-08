# Copyright (c) 2015, Daniel Zerbino

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


import numpy as np

ROUNDING_ERROR=1e-10

class Mapping(dict):
	def __init__(self, cycles):
		for index, element in enumerate(list(set(sum(cycles, [])))):
			self[element] = index

	def unitaryVector(self, cycle):
		vector = np.zeros(len(self))
		for index in range(len(cycle)):
			if index % 2 == 0:
				vector[self[cycle[index]]] += 1
			else:
				vector[self[cycle[index]]] -= 1
		return vector
 
class ReferenceVectors(object):
	def __init__(self, cycles):
		self.mappings = Mapping(cycles) 
		vectors = np.array([self.mappings.unitaryVector(cycle) for cycle in cycles])
		self.q_base, self.r_triangle = np.linalg.qr(vectors.T, mode='full')

	def canExplain(self, cycle):
		## If new dimensions present
		if any(X not in self.mappings for X in cycle):
			return False

		## Represent as Euclidian vector
		vector = self.mappings.unitaryVector(cycle)

		## Project onto pre-existing vectors base you can do this on the orthonormal matrix
		projections = self.q_base.T.dot(vector)
		if np.linalg.norm(vector - self.q_base.dot(projections)) > ROUNDING_ERROR * np.linalg.norm(vector):
			return False

		weights = np.linalg.lstsq(self.r_triangle, projections)[0]

		if all(abs(X - round(X)) < ROUNDING_ERROR for X in weights) and all(round(X) >= 0 for X in weights): 
			return True
		else:
			return False

def main():
	A = range(6)
	B = range(6,12)
	RV = ReferenceVectors([A,B])
	assert RV.canExplain(range(6)) == True
	assert RV.canExplain(range(12)) == True
	assert RV.canExplain(range(1,12) + [0]) == False
	assert RV.canExplain(range(2,12)) == False
	assert RV.canExplain(range(14)) == False

if __name__ == "__main__":
	main()
