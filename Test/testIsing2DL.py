import sys
sys.path.append('../TensorNetwork/')
from network import Network
from latticeNode import latticeNode
import numpy as np
from scipy.integrate import quad
import cProfile

def IsingSolve(nX, nY, h, J):
	network = Network()

	# Place to store the tensors
	lattice = [[] for i in range(nX)]
	onSite = [[] for i in range(nX)]
	bondV = [[] for i in range(nX)]
	bondH = [[] for i in range(nY)]
	bondL0 = [[] for i in range(nX)]
	bondL1 = [[] for i in range(nX)]
	bondL2 = [[] for i in range(nX)]
	bondL3 = [[] for i in range(nX)]


	# Each lattice site has seven indices of width five, and returns zero if they are unequal and one otherwise.
	for i in range(nX):
		for j in range(nY):
			lattice[i].append(latticeNode(2,network))

	# Each on-site term has one index of width two, and returns exp(-h) or exp(h) for 0 or 1 respectively.
	for i in range(nX):
		for j in range(nY):
			arr = np.zeros((2))
			arr[0] = np.exp(-h)
			arr[1] = np.exp(h)
			onSite[i].append(network.addNodeFromArray(arr))
			lattice[i][j].addLink(onSite[i][j],0)

	# Each bond term has two indices of width two and returns exp(-J*(1+delta(index0,index1))/2).
	for i in range(nX):
		for j in range(nY):
			arr = np.zeros((2,2))
			arr[0][0] = np.exp(-J)
			arr[1][1] = np.exp(-J)
			arr[0][1] = np.exp(J)
			arr[1][0] = np.exp(J)
			bondV[i].append(network.addNodeFromArray(np.copy(arr)))
			bondH[i].append(network.addNodeFromArray(np.copy(arr)))

	# Add L-bonds
	for i in range(nX):
		for j in range(nY):
			arr = np.zeros((2,2,2))
			arr += 1./7
			arr[1,1,1] = 0
			bondL0[i].append(network.addNodeFromArray(np.copy(arr)))
			bondL1[i].append(network.addNodeFromArray(np.copy(arr)))
			bondL2[i].append(network.addNodeFromArray(np.copy(arr)))
			bondL3[i].append(network.addNodeFromArray(np.copy(arr)))


	# Attach bond terms
	for i in range(nX):
		for j in range(nY):
			lattice[i][j].addLink(bondV[i][j],0)
			lattice[i][j].addLink(bondV[i][(j+1)%nY],1)
			lattice[i][j].addLink(bondH[i][j],0)
			lattice[i][j].addLink(bondH[(i+1)%nX][j],1)

			lattice[i][j].addLink(bondL0[i][j],0)
			lattice[i][j].addLink(bondL0[i][(j+1)%nY],1)
			lattice[i][j].addLink(bondL0[(i+1)%nX][j],2)

			lattice[i][j].addLink(bondL1[i][j],0)
			lattice[i][j].addLink(bondL1[i][(j-1)%nY],1)
			lattice[i][j].addLink(bondL1[(i+1)%nX][j],2)

			lattice[i][j].addLink(bondL2[i][j],0)
			lattice[i][j].addLink(bondL2[i][(j+1)%nY],1)
			lattice[i][j].addLink(bondL2[(i-1)%nX][j],2)

			lattice[i][j].addLink(bondL3[i][j],0)
			lattice[i][j].addLink(bondL3[i][(j-1)%nY],1)
			lattice[i][j].addLink(bondL3[(i-1)%nX][j],2)


	network.trace()

	counter = 0
	while len(network.topLevelLinks()) > 0:
		network.merge(mergeL=True,compress=True)

		if counter%20 == 0:
			print len(network.topLevelNodes()),network.topLevelSize(), network.largestTopLevelTensor()
		counter += 1

	return np.log(list(network.topLevelNodes())[0].tensor().array()) + list(network.topLevelNodes())[0].logScalar()

def exactIsing(J):
	k = 1/np.sinh(2*J)**2
	def f(x):
		return np.log(np.cosh(2*J)**2 + (1/k)*np.sqrt(1+k**2-2*k*np.cos(2*x)))
	inte = quad(f,0,np.pi)[0]

	return np.log(2)/2 + (1/(2*np.pi))*inte

print IsingSolve(20,20,0,0.5)/400

#print cProfile.run('print IsingSolve(10,10,0,0.5)/100')

exit()

print IsingSolve(7,7,4.0,0)/49,np.log(np.exp(4) + np.exp(-4))

for j in np.linspace(-1,1,num=10):
	q = IsingSolve(10,10,0,j)/100
	print(j,q,exactIsing(j))
