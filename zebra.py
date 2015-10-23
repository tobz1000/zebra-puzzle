#!/usr/bin/python3
import itertools
import termcolor
import argparse
import copy

'''
Now with classes!

TODO:
	* Not solved. Improve string output, so state of puzzle shows the
	house-grid, and unused facts. Then print this after 1) inserting definites;
	2) coming to the end of a guess_facts() branch.
		* Small counter of current guess-combo, e.g. "2->3->3->4". Write "final"
				facts in green.
		* Try showing conflicts/add since last print on the Houses grid
	* Improve reading of facts.txt:
		* Scan for '?'s first, and get number of vars to permutate from this
		count.
		* Probably best move the scan outside of Puzzle, and save list of dicts
		with '?'s first
	* Make clue-strings available in output
	* Unify 'props': currently work as a dict in Houses, and as a tuple (which
	is used as a dict-key) in Facts. Slightly confusing :)
	* Cleanup the use of 'is' and '==': limit 'is' to conceptual instance
	checks, not equality checks for literals/ints etc.

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
			return '{}'.format(self.message)


	class House():
		def __init__(self, pos, puzzle_inst):
			self.puzzle_inst = puzzle_inst
			self.props = {}
			self.props['pos'] = pos

		def __str__(self):
			return "House {}".format(self.props['pos'])

		def prop_found(self, key):
			val = self.props.get(key)
			return val is not None and not isinstance(val, list)

		def set_prop_value(self, key, val):
			self.puzzle_inst.changed_last_cycle = True

			for house in self.puzzle_inst.houses:
				if house is not self:
					house.remove_possible(key, val)

			self.props[key] = val

		def add_possible(self, key, val):
			if not key in self.props:
				self.props[key] = []

			if not self.prop_found(key) and not val in self.props[key]:
				self.props[key] += [ val ]

		# TODO: This currently does bad things if the house doesn't have enough
		# possible values. Exception caught for debug.
		def remove_possible(self, key, val):
			if val in self.props.get(key):
				try:
					self.props[key].remove(val)
				except AttributeError:
					print("slot = {}({}) val-to-remove = {}".format(
							self.props[key], len(self.props[key]), val))
					raise

				if len(self.props[key]) is 1:
					self.set_prop_value(key, val)

	# A dictionary of properties (tuples) with a relative position from one
	# another
	class Fact():
		def __init__(self, props):
			self.in_use = False
			self.used = False
			# If this Fact is definitely inserted correctly (for this Puzzle
			# perm at least)
			self.final = False
			self.props = props

		def __str__(self):
			ret = ''
			for p, r in self.props.items():
				k, v = p
				ret += '({:<3} {:<3} {:>2}) '.format(k, v, r)
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
		perm_i = iter(self.perm)
		f = open('facts2.txt', 'r')

		for line in f:
			if line[0] is '#' or line[0] is '\n':
				continue
			props = line.split(',')
			if len(props) < 1:
				continue

			# Keys: a property tuple (key, val); values: relative position of
			# the property.
			prop_dict = {}

			for prop in props:
				kvlist = prop.split()
				if len(kvlist) < 2:
					continue

				key, val = kvlist[:2]

				if key == 'pos':
					val = int(val)

				if len(kvlist) > 2:
					if kvlist[2] == '?':
						rel = next(perm_i, 0)
					else:
						rel = int(kvlist[2])
				else:
					rel = 0

				prop_dict.update({(key, val): rel})

			self.facts += [ self.Fact(prop_dict) ]

	def populate_houses(self):
		for h in self.houses:
			# h.add_possible('pet', 'fis')
			# h.add_possible('pet', 'zeb')
			# h.add_possible('dri', 'wat')
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
				raise self.PuzzleFinish(False, "Can't add {} of {} to {}, "
						"already has value of {}".format(key, val, house,
								house.props[key]))
		else:
			if not val in house.props[key]:
				raise self.PuzzleFinish(False, "Can't add {} of {} to {}, "
						"value removed from possible list.".format(key, val,
								house))

		prev_assigned = self.find_house(key, val)
		if prev_assigned:
			raise self.PuzzleFinish(False, "Can't add {} of {} to {}, "
					"value already at house {}".format(key, val, house,
							prev_assigned.props['pos']))

		house.set_prop_value(key, val)

	def try_definite_fact(self, fact):
		for prop, rel in fact.props.items():
			house = self.find_house(*prop)
			if house is not None:
				fact.adjust_rel_values(house.props['pos'] - rel)
				self.insert_fact(fact)
				fact.final = True
				return

	# Adds each property in a Fact to the House at the corresponding position
	# (e.g. prop with rel=0 goes to House 0)
	def insert_fact(self, fact):
		if fact.used:
			raise self.PuzzleFinish(False, "Tried to reuse Fact {}".format(
					fact))
		fact.in_use = True
		for prop, rel in fact.props.items():
			house = self.find_house('pos', rel)
			if house is None:
				raise self.PuzzleFinish(False, "Tried to add prop {} to "
					"invalid house position ({})".format(prop, rel))
			self.single_prop_add(house, *prop)
		fact.in_use = False
		fact.used = True

	def __str__(self):
		ret = 'Puzzle {}'.format(self.perm)
		ret += '{:>{pad}}'.format( "SOLVED" if self.solved else
				"FAILED" if self.finished else "UNFINISHED",
				pad=80 - len(ret))
		if self.message:
			ret += '\n{}'.format(self.message)

		# Multiline sections to be placed side-by-side
		sections = (
			self.houses_str_gen(),
			self.facts_str_gen())

		# Padding sizes should be first yield
		seg_lens = [None] * len(sections)
		for n, gen in enumerate(sections):
			seg_lens[n] = next(gen)

		for combined_line in itertools.zip_longest(*sections):
			line_text = ''
			for line_seg, seg_len in zip(combined_line, seg_lens):
				# When a generator finishes before the others, zip returns None
				line_seg = line_seg or ''
				line_text += '{:{len}}'.format(line_seg, len=seg_len)
			ret += '\n{}'.format(line_text.rstrip())
		return "{}\n{deco}".format(ret, deco='-' * 80)


	# Yields length of section before any lines
	def houses_str_gen(self):
		key_len = 4
		val_len = 6
		max_len = key_len + val_len * len(self.houses)
		yield max_len
		yield "{:{len}}".format("Houses:", len=max_len)
		for key in ('pos', 'col', 'nat', 'dri', 'smo', 'pet'):
			ret = '{:4}'.format(key)
			for house in self.houses:
				val = house.props[key]
				if house.prop_found(key):
					val_fmt = '{:^6}'.format(val)
					ret += val_fmt
				else:
					ret += '{:6}'.format('|' * len(val))
			yield ret

	# Yields length of section before any lines
	def facts_str_gen(self):
		max_len = 0
		lines = []
		for n, f in enumerate(self.facts):
			line = '{:2}. {}'.format(n+1, f)
			max_len = max(max_len, len(line))
			line_colour = 'green' if f.final else 'red' if f.in_use else 'white'
			line_attrs = ['dark'] if f.used else []
			lines += [termcolor.colored(line, line_colour, attrs=line_attrs)]
		yield max_len
		yield "{:{len}}".format('Facts:', len=max_len)
		for line in lines:
			yield line

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

	def next_unused_fact(self):
		return next((f for f in self.facts if not f.used), None)

	def try_insert_next_fact(self):
		fact = self.next_unused_fact()
		try:
			self.insert_fact(fact)
		except self.PuzzleFinish as f:
			self.solved = f.solved
			self.message = f.message
			if verbose:
				print(self)
			return False

		return self.guess_facts()

	def guess_facts(self):
		fact = self.next_unused_fact()
		if fact is None:
			return True

		# Take an arbitrary prop and try all possible positions
		pivot_prop = next(iter(fact.props))
		for i in range(0, self.no_of_houses):
			fact.adjust_rel_values(i - fact.props[pivot_prop])
			p_cpy = copy.deepcopy(self)
			if p_cpy.try_insert_next_fact():
				return True

		return False

	def __init__(self, perm):
		self.finished = False
		self.solved = False
		self.message = None
		self.perm = perm
		self.houses = []
		self.facts = []
		self.get_initial_facts()
		for i in range(self.no_of_houses):
			self.houses += [ self.House(i, self) ]

		self.populate_houses()

		try:
			# self.combine_facts()
			# Attach as many facts to house positions as possible
			for f in self.facts:
				self.try_definite_fact(f)
			# Remaining facts: fork the Puzzle, try to insert first Fact at each
			# possible offset of some arbitrary prop. While the insert is
			# successful, recursively attempt this with each following Fact.
			if not self.guess_facts():
				raise self.PuzzleFinish(False, "Couldn't find a working "
						"combination for remaining Facts")
		except self.PuzzleFinish as f:
			self.finished = True
			self.solved = f.solved
			self.message = f.message
			print(self)

verbose = False

def main():
	ap = argparse.ArgumentParser(
			description='"Zebra Puzzle" solver.')
	ap.add_argument('-v', dest='verbose', action='store_true',
			help='Print verbose output.')
	args = ap.parse_args()
	global verbose
	verbose = args.verbose
	for perm in itertools.product(*tuple([[-1, 1]] * 3)):
		print("{}".format('#' * 80, perm))
		Puzzle(perm)

if __name__ == '__main__':
	main()
