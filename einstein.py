#!/usr/bin/python3
import itertools
import termcolor
import argparse

'''
Now with classes!

TODO:
	* Create new facts for future cycles:
		* E.g. facts 15 & 10 together imply either (depending on values of
		a + d):
			* Cat-owner drinks water
			* Cat-owner lives 2 to the left/right of water-drinker
		* Raise PuzzleFinish if range of a fact is too great (max-min >= 5)
			* Possibly unnecessary - ultimately covered by invalid-access error
	* Scan in facts from facts.txt to save on all the format-faffing
		* Scan for '?'s first, and get number of vars to permutate from this
		count.
		* Probably best move the scan outside of Puzzle, and save list of dicts
		with '?'s first
	* Make clue-strings available in output
	* Unify 'props': currently work as a dict in Houses, and as a tuple (which
	is used as a dict-key) in Facts. Slightly confusing :)
	* Cleanup use of 'is' and '==': limit 'is' to conceptual instance checks,
	not equality checks for literals/ints etc.

There are five houses in five different colors in a row. In each house lives a
person with a different nationality. The five owners drink a certain type of
beverage, smoke a certain brand of cigar and keep a certain pet. No owners have
the same pet, smoke the same brand of cigar, or drink the same beverage. Other
facts:

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

	class PuzzleFinish(Exception):
		def __init__(self, solved, message=None):
			self.solved = solved
			self.message = message

		def __str__(self):
			return "{}: {}".format(
					"SOLVED" if self.solved else "FAILED",
					self.message or '')


	class House():
		def __init__(self, pos, puzzle_inst):
			self.puzzle_inst = puzzle_inst
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

		def set_prop_value(self, key, val):
			self.puzzle_inst.changed_last_cycle = True

			for house in self.puzzle_inst.houses:
				if house is not self:
					house.remove_possible(key, val)

			self.props[key] = val
			if verbose:
				print(self.puzzle_inst.houses_str(key, val))

		def add_possible(self, key, val):
			if not key in self.props:
				self.props[key] = []

			if not self.prop_found(key) and not val in self.props[key]:
				self.props[key] += [ val ]

		def remove_possible(self, key, val):
			if val in self.props.get(key):
				self.props[key].remove(val)

			if len(self.props[key]) is 1:
				self.set_prop_value(key, val)

	# A dictionary of properties (tuples) with a relative position from one
	# another
	class Fact():
		def __init__(self, props):
			self.props = props

		def __str__(self):
			ret = ''
			for p, r in self.props.items():
				k, v = p
				ret += '{:<3} {:<3} {:>2}; '.format(k, v, r)
			return ret

		def adjust_rel_values(self, adj):
			for p, r in self.props.items():
				self.props[p] += adj

		def try_add_transitive(self, other):
			for p1, r1 in self.props.items():
				for p2, r2 in other.props.items():
					if p1 == p2:
						other.adjust_rel_values(r1 - r2)
						self.props.update(other.props)
						return True
			return False

	def get_initial_facts(self):
		self.facts = []
		perm_i = iter(self.perm)
		f = open('facts.txt', 'r')

		for line in f:
			if line[0] is '#' or line[0] is '\n':
				continue
			toks = line.strip().split()
			if len(toks) < 4:
				continue

			k1, v1, k2, v2 = toks[:4]

			if k1 == 'pos':
				v1 = int(v1)
			if k2 == 'pos':
				v2 = int(v2)

			# Unknown "relative position" values
			if len(toks) > 4:
				if toks[4] == '?':
					rel2 = next(perm_i, 0)
				else:
					rel2 = int(toks[4])
			else:
				rel2 = 0

			self.facts += [ self.Fact({(k1, v1): 0, (k2, v2): rel2}) ]

	def populate_houses(self):
		for h in self.houses:
			h.add_possible('pet', 'fis')
			for fact in self.facts:
				for key, val in fact.props:
					h.add_possible(key, val)

	# rel = find house to the right (positive) or left (negative)
	# of the house with key=val.
	def find_house(self, key, val, rel=None):
		f = list(filter(lambda house: house.props.get(key) == val, self.houses))

		if len(f) is not 1:
			return None

		if rel:
			rel_pos = f[0].props['pos'] + rel
			if rel_pos < 0 or rel_pos >= self.no_of_houses:
				raise self.PuzzleFinish(False, "Tried to access invalid house "
						"position (pos {}).".format(rel_pos))
				return None
			return self.find_house('pos', rel_pos)
		else:
			return f[0]

	def single_prop_add(self, house, key, val):
		if house.prop_found(key):
			# Already has value; only error out if value is different
			if house.props[key] == val:
				return
			else:
				raise self.PuzzleFinish(False, "Can't add {} of {} to house "
						"{}, already has value of {}".format(key, val,
									house.props['pos'], house.props[key]))
		else:
			if not val in house.props[key]:
				raise self.PuzzleFinish(False, "Can't add {} of {} to house "
						"{}, value removed from possible list.".format(key, val,
								house.props['pos']))

		prev_assigned = self.find_house(key, val)
		if prev_assigned:
			raise self.PuzzleFinish(False, "Can't add {} of {} to house "
					"{}, value already at house {}".format(key, val,
								house.props['pos'], prev_assigned.props['pos']))

		house.set_prop_value(key, val)

	def try_fact(self, fact):
		for test_prop, test_rel in fact.props.items():
			test_house = self.find_house(*test_prop)
			if test_house is not None:
				fact.adjust_rel_values(test_house.props['pos'] - test_rel)
				for add_prop, add_rel in fact.props.items():
					add_house = self.find_house(*test_prop, rel=add_rel)
					add_house = self.find_house('pos', add_rel)
					self.single_prop_add(add_house, *add_prop)
				return

	def __str__(self):
		return 'Puzzle {:<16} Cycle {:>2} Fact {:>2}/{:>2}'.format(
				str(self.perm),
				self.no_of_cycles,
				self.current_fact,
				len(self.facts))

	def houses_str(self, colour_key=None, colour_val=None):
		ret = '{}\n'.format(self)
		for key in ('pos', 'col', 'nat', 'dri', 'smo', 'pet'):
			ret += '{:4}'.format(key)
			for house in self.houses:
				val = house.props[key]
				if house.prop_found(key):
					val_fmt = '{:^6}'.format(val)
					if ((key, val) == (colour_key, colour_val)):
						val_fmt = termcolor.colored(val_fmt, 'green')
					ret += val_fmt
				else:
					ret += '{:6}'.format('|' * len(val))
			ret += '\n'
		return ret

	def facts_str(self):
		ret = '{} facts:\n'.format(len(self.facts))
		for n, f in enumerate(self.facts):
			ret += '{:4}. {}\n'.format(n+1, f)
		return ret

	# Recursive: take first from list, combine if poss; move onto reduced list.
	def combine_facts(self, facts=None):
		if facts is None or facts is self.facts:
			# Copy the Puzzle's list on first call for modification
			facts = list(self.facts)

		if len(facts) == 0:
			return

		f1 = facts.pop()
		for f2 in facts:
			if f2.try_add_transitive(f1):
				self.facts.remove(f1)
				break
		self.combine_facts(facts)

	def __init__(self, perm):
		self.perm = perm
		self.no_of_cycles = 0
		self.current_fact = 0
		self.get_initial_facts()
		self.houses = []
		for i in range(self.no_of_houses):
			self.houses += [ self.House(i, self) ]

		self.populate_houses()

		try:
			self.combine_facts()
			if verbose:
				print(self.facts_str())
			while True:
				self.no_of_cycles += 1
				self.changed_last_cycle = False
				for n, f in enumerate(self.facts):
					self.current_fact = n + 1
					self.try_fact(f)
				if not self.changed_last_cycle:
					raise self.PuzzleFinish(False, "No new information added "
							"during cycle #{}.".format(self.no_of_cycles))
		except self.PuzzleFinish as f:
			print("{}\n{}\n{}".format(self, f, '=' * 50 if verbose else ''))

verbose = False

def main():
	ap = argparse.ArgumentParser(
			description='Einstein\'s puzzle-solver.')
	ap.add_argument('-v', dest='verbose', action='store_true',
			help='Print verbose output.')
	args = ap.parse_args()
	global verbose
	verbose = args.verbose
	for perm in itertools.product(*tuple([[-1, 1]] * 4)):
		Puzzle(perm)

if __name__ == '__main__':
	main()
