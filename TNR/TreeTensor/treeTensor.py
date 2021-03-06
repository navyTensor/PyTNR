from operator import mul
from copy import deepcopy
from collections import defaultdict

import itertools as it
import numpy as np
import operator
import networkx

from TNR.Tensor.tensor import Tensor
from TNR.Tensor.arrayTensor import ArrayTensor
from TNR.Network.treeNetwork import TreeNetwork
from TNR.Network.node import Node
from TNR.Network.link import Link
from TNR.Network.bucket import Bucket
from TNR.Network.traceMin import traceMin
from TNR.Utilities.svd import entropy
from TNR.Utilities.graphPlotter import makePlotter

counter0 = 0

from TNR.Utilities.logger import makeLogger
from TNR import config
logger = makeLogger(__name__, config.levels['treeTensor'])


class TreeTensor(Tensor):

    def __init__(self, accuracy):
        self.accuracy = accuracy
        self.network = TreeNetwork(accuracy=accuracy)
        self.externalBuckets = []
        self.optimized = set()

    def addTensor(self, tensor):
        n = Node(tensor, Buckets=[Bucket() for _ in range(tensor.rank)])
        self.network.addNode(n)
        self.externalBuckets.extend(n.buckets)
        if tensor.rank > 3:
            self.network.splitNode(n)
        return n

    def __str__(self):
        s = ''
        s = s + 'Tree Tensor with Shape:' + str(self.shape) + ' and Network:\n'
        s = s + str(self.network)
        return s

    @property
    def array(self):

        arr, logAcc, bdict = self.network.array

        arr *= np.exp(logAcc)

        perm = []
        blist = [b.id for b in self.externalBuckets]

        for b in blist:
            perm.append(bdict[b])

        arr = np.transpose(arr, axes=perm)

        assert arr.shape == tuple(self.shape)
        return arr

    @property
    def shape(self):
        return tuple([b.node.tensor.shape[b.index]
                      for b in self.externalBuckets])

    @property
    def rank(self):
        return len(self.externalBuckets)

    @property
    def size(self):
        if self.rank == 0:
            return 1.
        else:
            s = self.shape[0]
            for q in self.shape[1:]:
                s *= q

            return s

    @property
    def compressedSize(self):
        size = 0
        for n in self.network.nodes:
            size += n.tensor.size
        return size

    def distBetween(self, ind1, ind2):
        n1 = self.externalBuckets[ind1].node
        n2 = self.externalBuckets[ind2].node
        return len(self.network.pathBetween(n1, n2))

    def distBetweenBuckets(self, b1, b2):
        n1 = b1.node
        n2 = b2.node
        return len(self.network.pathBetween(n1, n2))

    def contract(self, ind, other, otherInd, front=True):
        # This method could be vastly simplified by defining a cycle basis
        # class

        # We copy the two networks first. If the other is an ArrayTensor we
        # cast it to a TreeTensor first.
        t1 = deepcopy(self)
        if hasattr(other, 'network'):
            t2 = deepcopy(other)
        else:
            t2 = TreeTensor(self.accuracy)
            t2.addTensor(other)

        # If front == True then we contract t2 into t1, otherwise we contract t1 into t2.
        # This is so we get the index order correct. Thus
        if not front:
            t1, t2 = t2, t1
            otherInd, ind = ind, otherInd

        # Link the networks
        links = []
        for i, j in zip(*(ind, otherInd)):
            b1, b2 = t1.externalBuckets[i], t2.externalBuckets[j]
            assert b1 in t1.network.buckets and b1 not in t2.network.buckets
            assert b2 in t2.network.buckets and b2 not in t1.network.buckets
            links.append(Link(b1, b2))

        # Determine new external buckets list
        for l in links:
            t1.externalBuckets.remove(l.bucket1)
            t2.externalBuckets.remove(l.bucket2)

        extB = t1.externalBuckets + t2.externalBuckets

        # Merge the networks
        toRemove = set(t2.network.nodes)

        for n in toRemove:
            t2.network.removeNode(n)

        for n in toRemove:
            t1.network.addNode(n)

        # Merge any rank-1 or rank-2 objects
        done = set()
        while len(done.intersection(t1.network.nodes)) < len(t1.network.nodes):
            n = next(iter(t1.network.nodes.difference(done)))
            if n.tensor.rank <= 2:
                nodes = t1.network.internalConnected(n)
                if len(nodes) > 0:
                    t1.network.mergeNodes(n, nodes.pop())
                else:
                    done.add(n)
            else:
                done.add(n)

        t1.externalBuckets = extB
        assert t1.network.externalBuckets == set(t1.externalBuckets)

        for n in t1.network.nodes:
            assert n.tensor.rank <= 3

        assert t1.rank == self.rank + other.rank - 2 * len(ind)

        return t1

    def eliminateLoops(self, otherNodes, plot=False):
        global counter0
        tm = traceMin(self.network, otherNodes)

        while len(networkx.cycles.cycle_basis(self.network.toGraph())) > 0:
            if plot:
                plotter = makePlotter('PNG/' + str(counter0))
                plotter = plotter(self.network.toGraph())

            logger.debug('Cycle utility is ' +
                         str(tm.util) +
                         ' and there are ' +
                         str(len(networkx.cycles.cycle_basis(self.network.toGraph()))) +
                         ' cycles remaining.')

            merged = tm.mergeSmall()

            if not merged:
                best = tm.bestSwap()
                tm.swap(best[1], best[2], best[3])

            logger.debug(str(self.network))

        counter0 += 1
        assert len(networkx.cycles.cycle_basis(self.network.toGraph())) == 0

    def trace(self, ind0, ind1):
        '''
        Takes as input:
                ind0	-	A list of indices on one side of their Links.
                ind1	-	A list of indices on the other side of their Links.

        Elements of ind0 and ind1 must correspond, such that the same Link is
        represented by indices at the same location in each list.

        Elements of ind0 should not appear in ind1, and vice-versa.

        Returns a Tensor containing the trace over all of the pairs of indices.
        '''
        arr = self.array

        ind0 = list(ind0)
        ind1 = list(ind1)

        t = deepcopy(self)

        for i in range(len(ind0)):
            b1 = t.externalBuckets[ind0[i]]
            b2 = t.externalBuckets[ind1[i]]

            t.network.trace(b1, b2)

            t.externalBuckets.remove(b1)
            t.externalBuckets.remove(b2)

            for j in range(len(ind0)):
                d0 = 0
                d1 = 0

                if ind0[j] > ind0[i]:
                    d0 += 1
                if ind0[j] > ind1[i]:
                    d0 += 1

                if ind1[j] > ind0[i]:
                    d1 += 1
                if ind1[j] > ind1[i]:
                    d1 += 1

                ind0[j] -= d0
                ind1[j] -= d1

        return t

    def flatten(self, inds):
        '''
        This method merges the listed external indices using a tree tensor
        by attaching the identity tensor to all of them and to a new
        external bucket. It then returns the new tree tensor.
        '''

        buckets = [self.externalBuckets[i] for i in inds]
        shape = [self.shape[i] for i in inds]

        # Create identity array
        shape.append(np.product(shape))
        iden = np.identity(shape[-1])
        iden = np.reshape(iden, shape)

        # Create Tree Tensor holding the identity
        tens = ArrayTensor(iden)
        tn = TreeTensor(self.accuracy)
        tn.addTensor(tens)

        # Contract the identity
        ttens = self.contract(inds, tn, list(range(len(buckets))))

        shape2 = [self.shape[i] for i in range(self.rank) if i not in inds]
        shape2.append(shape[-1])
        for i in range(len(shape2)):
            assert ttens.shape[i] == shape2[i]

        return ttens

    def getIndexFactor(self, ind):
        return self.externalBuckets[ind].node.tensor.scaledArray, self.externalBuckets[ind].index

    def setIndexFactor(self, ind, arr):
        tt = deepcopy(self)
        tt.externalBuckets[ind].node.tensor = ArrayTensor(
            arr, logScalar=tt.externalBuckets[ind].node.tensor.logScalar)
        return tt

    def optimize(self):
        '''
        Optimizes the tensor network to minimize memory usage.
        '''

        logger.info('Optimizing tensor with shape ' + str(self.shape) + '.')

        s2 = 0
        for n in self.network.nodes:
            s2 += n.tensor.size

        logger.info('Stage 1: Contracting Rank-2 Tensors.')

        done = set()
        while len(
            done.intersection(
                self.network.nodes)) < len(
                self.network.nodes):
            n = next(iter(self.network.nodes.difference(done)))
            if n.tensor.rank == 2:
                nodes = self.network.internalConnected(n)
                if len(nodes) > 0:
                    self.network.mergeNodes(n, nodes.pop())
                else:
                    done.add(n)
            else:
                done.add(n)

        logger.info('Stage 2: Contracting Double Links.')

        done = set()
        while len(
            done.intersection(
                self.network.nodes)) < len(
                self.network.nodes):
            n = next(iter(self.network.nodes.difference(done)))
            nodes = self.network.internalConnected(n)
            merged = False
            for n2 in nodes:
                if len(n.findLinks(n2)) > 1:
                    self.network.mergeNodes(n, n2)
                    merged = True
            if not merged:
                done.add(n)

        logger.info('Stage 3: Optimizing Links.')

        while len(
            self.optimized.intersection(
                self.network.internalBuckets)) < len(
                self.network.internalBuckets):
            b1 = next(
                iter(
                    self.network.internalBuckets.difference(
                        self.optimized)))
            b2 = b1.otherBucket
            n1 = b1.node
            n2 = b2.node

            if n1.tensor.rank < 3 or n2.tensor.rank < 3:
                self.optimized.add(b1)
                self.optimized.add(b2)
                continue

            sh1 = n1.tensor.shape
            sh2 = n2.tensor.shape
            s = n1.tensor.size + n2.tensor.size

            logger.debug('Optimizing tensors ' +
                         str(n1.id) +
                         ',' +
                         str(n2.id) +
                         ' with shapes' +
                         str(n1.tensor.shape) +
                         ',' +
                         str(n2.tensor.shape))

            t, buckets = self.network.dummyMergeNodes(n1, n2)
            arr = t.array
            if n1.tensor.rank == 3:
                ss = set([0, 1])
            elif n2.tensor.rank == 3:
                ss = set([2, 3])
            else:
                ss = None

            logger.debug('Computing minimum entropy cut...')
            best = entropy(arr, pref=ss)
            logger.debug('Done.')

            if set(best) != ss and set(best) != set(
                    range(n1.tensor.rank + n2.tensor.rank - 2)).difference(ss):
                n = self.network.mergeNodes(n1, n2)
                nodes = self.network.splitNode(n, ignore=best)

                for b in nodes[0].buckets:
                    self.optimized.discard(b)
                for b in nodes[1].buckets:
                    self.optimized.discard(b)

                if nodes[0] in nodes[1].connectedNodes:
                    assert len(nodes) == 2
                    l = nodes[0].findLink(nodes[1])
                    self.optimized.add(l.bucket1)
                    self.optimized.add(l.bucket2)
                    logger.debug('Optimizer improved to shapes to' +
                                 str(nodes[0].tensor.shape) +
                                 ',' +
                                 str(nodes[1].tensor.shape))
                else:
                    # This means the link was cut
                    logger.debug('Optimizer cut a link. The resulting shapes are ' +
                                 str(nodes[0].tensor.shape) + ', ' + str(nodes[1].tensor.shape))

            else:
                self.optimized.add(b1)
                self.optimized.add(b2)

            logger.debug('Optimization steps left:' + str(-len(self.optimized.intersection(
                self.network.internalBuckets)) + len(self.network.internalBuckets)))

        s1 = 0
        for n in self.network.nodes:
            s1 += n.tensor.size
        logger.info('Optimized network with shape ' +
                    str(self.shape) +
                    ' and ' +
                    str(len(self.network.nodes)) +
                    ' nodes. Size reduced from ' +
                    str(s2) +
                    ' to ' +
                    str(s1) +
                    '.')
