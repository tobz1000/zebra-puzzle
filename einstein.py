#!/usr/bin/python
import itertools

'''
Now with classes!

There are five houses in five different colors in a row. In each house lives a person with a different nationality. The five owners drink a certain type of beverage, smoke a certain brand of cigar and keep a certain pet. No owners have the same pet, smoke the same brand of cigar, or drink the same beverage. Other facts:

1. The Brit lives in the red house.
2. The Swede keeps dogs as pets.
3. The Dane drinks tea.
4. The green house is on the immediate left of the white house.
5. The green house's owner drinks coffee.
6. The owner who smokes Pall Mall rears birds.
7. The owner of the yellow house smokes Dunhill.
8. The owner living in the center house drinks milk.
9. The Norwegian lives in the first house.
10. The owner who smokes Blends lives next to the one who keeps cats.
11. The owner who keeps the horse lives next to the one who smokes Dunhill.
12. The owner who smokes Bluemasters drinks beer.
13. The German smokes Prince.
14. The Norwegian lives next to the blue house.
15. The owner who smokes Blends lives next to the one who drinks water.

The question is: who owns the fish?
'''

class Puzzle:

	no_of_houses = 5
	# Max times to try each fact
	max_cycles = 20

	class House():
		def __init__(self, pos):
			self.props = {}
			self.props['pos'] = pos

		def __str__(self):
			ret = ''
			for k, v in self.props.iteritems():###
				ret += k + ' ' + str(v) + '\n'
			return ret

		def prop_found(self, key):
			val = self.props.get(key)
			return val is not None and not isinstance(val, list)

		def set_value(self, key, val):
			self.props[key] = val

		def add_possible(self, key, val):
			if not self.props.has_key(key):
				self.props[key] = []

			if not self.prop_found(key) and not val in self.props[key]:
				self.props[key] += [ val ]

		def remove_possible(self, key, val):
			if val in self.props.get(key):
				self.props[key].remove(val)

			if len(self.props[key]) is 1:
				self.set_value(key, val)

	def set_facts(self, perm=None):
		perm = perm or self.perm
		self.facts = [
			# 1. The Brit lives in the red house.
			('nat', 'bri', 'col', 'red'),

			# 2. The Swede keeps dogs as pets.
			('nat', 'swe', 'pet', 'dog'),

			# 3. The Dane drinks tea.
			('nat', 'dan', 'dri', 'tea'),

			# 4. The green house is on the immediate left of the white house.
			('col', 'gre', 'col', 'whi', -1),

			# 5. The green house's owner drinks coffee.
			('col', 'gre', 'dri', 'cof'),

			# 6. The owner who smokes Pall Mall rears birds.
			('smo', 'pal', 'pet', 'bir'),

			# 7. The owner of the yellow house smokes Dunhill.
			('col', 'yel', 'smo', 'dun'),

			# 8. The owner living in the center house drinks milk.
			('pos', 2, 'dri', 'mil'),

			# 9. The Norwegian lives in the first house.
			('nat', 'nor', 'pos', 0),

			# 10. The owner who smokes Blends lives next to the one who keeps cats.
			('smo', 'ble', 'pet', 'cat', perm[0]),

			# 11. The owner who keeps the horse lives next to the one who smokes Dunhill.
			('pet', 'hor', 'smo', 'dun', perm[1]),

			# 12. The owner who smokes Bluemasters drinks beer.
			('smo', 'blu', 'dri', 'bee'),

			# 13. The German smokes Prince.
			('nat', 'ger', 'smo', 'pri'),

			# 14. The Norwegian lives next to the blue house.
			('nat', 'nor', 'col', 'blu', perm[2]),

			# 15. The owner who smokes Blends lives next to the one who drinks water.
			('smo', 'ble', 'dri', 'wat', perm[3])
		]

	def populate_houses(self, facts=None):
		facts = facts or self.facts

		for h in self.houses:
			h.add_possible('pet', 'fis')
			for f in facts:
				h.add_possible(f[0], f[1])
				h.add_possible(f[2], f[3])

	# rel = find house to the right (positive) or left (negative)
	# of the house with key=val.
	def find_house(self, key, val, rel=None):
		f = filter(lambda house: house.props.get(key) == val, self.houses)

		if len(f) is not 1:
			return None

		if rel:
			rel_pos = f[0].props['pos'] + rel
			if rel_pos < 0 or rel_pos >= self.no_of_houses:
				self.finish(False, "Tried to access invalid house position (pos {})".format(rel_pos))
				return None
			return self.find_house('pos', rel_pos)
		else:
			return f[0]

	# Returns whether or not to try and add the other way
	def try_add_one_way(self, key1, val1, key2, val2, rel):
		if self.finished:
			return

		house = self.find_house(key1, val1, rel)

		if house is None:
			return True

		if house.prop_found(key2):
			# Already has value; only error out if value is different
			if house.props[key2] is not val2:
				self.finish(False, "Can't add {} of {} to house {}, already has value of {}".format(key2, val2, house.props['pos'], house.props[key2]))
			return
		else:
			if not val2 in house.props[key2]:
				self.finish(False, "Can't add {} of {} to house {}; value removed from possible list.".format(key2, val2, house.props['pos']))
				return

		h = self.find_house(key2, val2)
		if h:
			self.finish(False, "Can't add {} of {} to house {}, value already at house {}".format(key2, val2, house.props['pos'], h.props['pos']))
			return

		self.changed_last_cycle = True
		house.set_value(key2, val2)

		for h in self.houses:
			if h is not house:
				h.remove_possible(key2, val2)

	def try_fact(self, key1, val1, key2, val2, rel=0):
		(self.try_add_one_way(key1, val1, key2, val2, rel) and
		self.try_add_one_way(key2, val2, key1, val1, -rel))

	def finish(self, solved, message=None):
		if self.finished:
			return
		self.finished = True
		self.solved = solved
		self.message = message

	def __str__(self):
		ret = 'Puzzle {}\tCycle\t{}\tFact\t{}/{}\n{}\t{}\n'.format(
				self.perm,
				self.no_of_cycles,
				self.current_fact,
				len(self.facts),
				"RUNNING" if not self.finished else "SOLVED" if self.solved else "FAILED",
				self.message or '')

		for prop in ('pos', 'col', 'nat', 'dri', 'smo', 'pet'):
			ret += prop + '\t'
			for house in self.houses:
				if house.prop_found(prop):
					ret += "{}\t".format(house.props[prop])
				else:
					ret += "{}\t".format('|' * len(house.props[prop]))
			ret += '\n'
		return ret

	def __init__(self, perm):
		self.perm = perm
		self.no_of_cycles = 0
		self.current_fact = 0
		self.finished = False
		self.solved = False
		self.message = None
		self.set_facts()
		self.houses = []
		for i in range(self.no_of_houses):
			self.houses += [ self.House(i) ]

		self.populate_houses()

		while not self.finished:
			self.no_of_cycles += 1
			self.changed_last_cycle = False
			for n, f in enumerate(self.facts):
				self.current_fact = n + 1
				if self.finished:
					break
				self.try_fact(*f)
				print self
				if self.finished:
					break
			if not self.changed_last_cycle:
				self.finish(False, "No new information added on the last cycle.")

def main():
	for perm in itertools.product(*tuple([[-1, 1]] * 4)):
		Puzzle(perm)

if __name__ == '__main__':
	main()
