from heapq import heappush, heappop
import itertools


class PriorityQueue:
    def __init__(self):
        self.pq = []
        self.entry_finder = {}
        self.REMOVED = '<removed-task>'      # placeholder for a removed task
        self.counter = itertools.count()     # unique sequence count
        self.length = 0

    def add(self, task, priority=0):
        'Add a new task or update the priority of an existing task'
        if task in self.entry_finder:
            self.remove(task)
        count = next(self.counter)
        entry = [priority, count, task]
        self.entry_finder[task] = entry
        heappush(self.pq, entry)
        self.length += 1

    def remove(self, task):
        'Mark an existing task as REMOVED.  Raise KeyError if not found.'
        # Silently fail if trying to remove something that isn't there.
        if task in self.entry_finder:
            entry = self.entry_finder.pop(task)
            entry[-1] = self.REMOVED
            self.length -= 1

    def pop(self):
        'Remove and return the lowest priority task. Raise KeyError if empty.'
        while self.pq:
            priority, count, task = heappop(self.pq)
            if task is not self.REMOVED:
                del self.entry_finder[task]
                self.length -= 1
                return task
        raise KeyError('pop from an empty priority queue')
