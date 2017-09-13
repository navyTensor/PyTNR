import numpy as np
import time

from TNR.Models.isingModel import IsingModel2Ddisordered
from TNR.Contractors.mergeContractor import mergeContractor
from TNR.Contractors.heuristics import loopHeuristic as heuristic

from TNR.Utilities.logger import makeLogger
from TNR import config
logger = makeLogger(__name__, config.levels['generic'])

def ising2DFreeEnergy(nX, nY, h, J, accuracy):
	n = IsingModel2Ddisordered(nX, nY, h, J, accuracy)
	n = mergeContractor(n, accuracy, heuristic, optimize=True, merge=False, plot=False)
	return n.array[1]/(nX*nY)

h = 1
J = 1
accuracy = 1e-3
size = [(2,2),(2,3),(2,4),(3,3),(2,5),(3,4),(4,4),(3,6),(4,5),(3,7),(3,8),(5,5),(3,9),(4,7),(5,6),(4,8),(5,7),(6,6),(6,7),(7,7),(7,8),(8,8)]#]#,(8,9)]#,(9,9),(9,10),(10,10)]

res = []

for s in size:
	for _ in range(3):
		logger.info('Examining system of size ' + str(s) + ' and J = ' + str(J) + '.')
		start = time.clock()
		f = ising2DFreeEnergy(s[0], s[1], h, J, accuracy)
		end = time.clock()
		res.append((s[0]*s[1], f, end - start))

res = np.array(res)

print(res)

np.savetxt('ising2D_disordered.dat', res)
