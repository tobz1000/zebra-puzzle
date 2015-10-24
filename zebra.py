#!/usr/bin/python3
import itertools
import termcolor
import argparse
import copy

"""
"Zebra Puzzle"-solver. Almost works I think.

TODO:

	*Improve string output:
		* For non-verbose, show small counter of current guess-combo,
		e.g. "2->3->3->_->_->_->0->1->_->_". Write "final" facts in green.
			* Number would be value of lowest rel in the Fact.
		* Try showing conflicts/add since last print on the Houses grid
	* Improve reading of facts.txt:
		* Scan for '?'s first, and get number of vars to permutate from this
		count.
		* Probably best move the scan outside of Puzzle, pass a dictionary of
		facts:relative-position to the Puzzle constructor.
			* Doing this would then require another way to easily identify
			which permutation we're on. Maybe just a name passed to the
			constructor? e.g. "left-left-right"
		* (Not necessary for the puzzle but would be cool) support arbitrary
		possible positions in fact file, instead of just '?' = -1/+1.
			* e.g.: "nat nor, pet fis -1 -2"  <-- fish could be either one or
			two to the left of Norway.
	* Make clue-strings available in output
	* Unify 'props': currently work as a dict in Houses, and as a tuple (which
	is used as a dict-key) in Facts. Slightly confusing :)
	* Cleanup the use of 'is' and '==': limit 'is' to conceptual instance
	checks, not equality checks for literals/ints etc.
"""

class Puzzle:
	"""A run of a set of facts, with a pre-determined permutation for any
	unknowns in those facts. May/will fail if that permutation is not the
	correct one."""
	no_of_houses = 5

	class PuzzleFinish(Exception):
		"""Exception thrown when a puzzle cannot continue. Either it's solved
		or an invalid action has occurred."""
		def __init__(self, solved, message=None):
			self.solved = solved
			self.message = message


	class House():
		"""A house with each of the proprties, to be given values."""
		def __init__(self, pos, puzzle_inst):
			self.puzzle_inst = puzzle_inst
			self.props = {}
			self.props['pos'] = pos

		def __str__(self):
			return "House {}".format(self.props['pos'])

		def prop_found(self, key):
			"""Return whether a particular property has been determined for this
			house."""
			val = self.props.get(key)
			return val is not None and not isinstance(val, list)

		def set_prop_value(self, key, val):
			"""Set a property with a given value, and remove this value from the
			possible values for other houses."""
			for house in self.puzzle_inst.houses:
				if house is not self:
					house.remove_possible(key, val)

			self.props[key] = val

		def add_possible(self, key, val):
			"""Populate the list of possible values of a property with the given
			key."""
			if not key in self.props:
				self.props[key] = []

			if not self.prop_found(key) and not val in self.props[key]:
				self.props[key] += [ val ]

		# TODO: This currently does bad things if the house doesn't have enough
		# possible values. Exception caught for debug.
		def remove_possible(self, key, val):
			"""Rule out a possible value of a property. Will set a property's
			value if only one possibility remains."""
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
		"""A collection of properties, with their relative position to one
		another, in terms of which house they occupy.

		The collection is centred arbitrarily and can be adjusted, before
		applying the properties to Houses."""
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
			"""Adjust the "rel" value of each property by 'adj'. This keeps
			the information in the fact the same, but allows the relation to be
			centred on a particular element."""
			for p, r in self.props.items():
				self.props[p] += adj

		def try_add_transitive(self, other):
			"""Attempt to combine this fact with another fact. If they have any
			properties in common, align their relative positions on this
			property and add the new properties to this fact. Does not change
			the other fact."""
			for p1, r1 in self.props.items():
				for p2, r2 in other.props.items():
					if p1 == p2:
						self.adjust_rel_values(r2 - r1)
						self.props.update(other.props)
						return True
			return False

	def __init__(self, facts_file, perm):
		self.finished = False
		self.solved = False
		self.message = None
		self.perm = perm
		self.houses = []
		self.facts = []
		self.get_initial_facts(facts_file)
		for i in range(self.no_of_houses):
			self.houses += [ self.House(i, self) ]

		self.populate_houses()

		print("{}".format('#' * 80, perm))

		try:
			self.combine_facts()
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


	def __str__(self):
		"""Returns the Puzzle status & any error message, and the Houses grid &
		list of clues side-by-side."""
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

	def houses_str_gen(self):
		"""Shows the value of each House property in a grid, or the number of
		remaining possible values for a property in a bar graph.
		Yields the line length for the grid, then yields the lines one by
		one."""
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

	def facts_str_gen(self):
		"""Shows a list of facts: each of their properties, the current relative
		position tied to each, and colours to denote status:
		White: unused
		Grey: Currently inserted
		Green: Finally inserted (definitely correct for this permutation)
		Red: Currently in use (e.g. half-way through inserting when an error
		occurred).
		Yields the line length for the grid, then yields the lines one by
		one."""
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

	def get_initial_facts(self, facts_file):
		"""Read in initial facts from a file. Properties are separate by commas,
		relative positions may be optionally supplied (assumed 0 otherwise). A
		relative position of "?" will take the Puzzle's first unused permutation
		value."""
		perm_i = iter(self.perm)
		f = open(facts_file, 'r')

		for line in f:
			if line[0] in '#\n':
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

	def combine_facts(self, facts=None):
		"""Recursive: take first from list, combine if poss; move onto reduced
		list."""
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

	def populate_houses(self):
		"""Fill the "possible values" lists for each property in each House."""
		for h in self.houses:
			for fact in self.facts:
				for key, val in fact.props:
					h.add_possible(key, val)

	# rel = find house to the right (positive) or left (negative)
	# of the house with key=val.
	def find_house(self, key, val, rel=None):
		"""Find the house with the key property value, if any. Returns None if
		more than one House is found (which shouldn't happen).
		If 'rel' is specified, the house relative left/rightto the one found
		is returned."""
		f = list(h for h in self.houses if h.props.get(key) == val)
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
		"""Set the value of a property on a given House, raising a PuzzleFinish
		if it's invalid."""
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
		"""Insert fact if it's definitely true (for this Puzzle's permutation at
		least)."""
		for prop, rel in fact.props.items():
			house = self.find_house(*prop)
			if house is not None:
				fact.adjust_rel_values(house.props['pos'] - rel)
				self.insert_fact(fact)
				fact.final = True
				return

	def insert_fact(self, fact):
		"""Insert all the properties of the given fact at their respective
		relative positions (rel=0 goes to House 0)."""
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

	def next_unused_fact(self):
		return next((f for f in self.facts if not f.used), None)

	def try_insert_next_fact(self):
		"""Recursive with guess_facts: used by a new Puzzle copy which attempts
		to insert the next Fact, and calls back to guess_facts if successful."""
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
		"""Recursive with try_insert_next_fact: alters the position of the next
		Fact to the first possible relative position, then copies the entire
		Puzzle at each position to see if the Fact is insertable. When/if the
		copy fails, moves the fact to the next possible position and tries again
		with a new copy."""
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

verbose = False

def main():
	ap = argparse.ArgumentParser(description='"Zebra Puzzle" solver.')
	ap.add_argument('facts_file', help='File location of facts to parse.',
			nargs='?', default='zebra.txt')
	ap.add_argument('-v', dest='verbose', action='store_true',
			help='Print verbose output.')
	args = ap.parse_args()

	global verbose
	verbose = args.verbose

	for perm in itertools.product(*([-1, 1],) * 4):
		Puzzle(args.facts_file, perm)

if __name__ == '__main__':
	main()
