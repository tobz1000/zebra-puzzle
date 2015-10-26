#!/usr/bin/python3
import itertools
import termcolor
import argparse
import copy

"""
"Zebra Puzzle"-solver.

TODO:
	* Improve reading of facts.txt:
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
		def __init__(self, solved, message=None, highlight=None):
			self.solved = solved
			self.message = message
			self.highlight = highlight

	def handle_finish(self, finish):
		"""Pass back attribute from the exception, and prints out the final
		Puzzle status. Always print verbose version for a solved Puzzle."""
		self.solved = finish.solved
		self.message = finish.message
		self.house_highlight = finish.highlight or {}
		print(self.summary_str(verbose=verbose or self.solved))

	class House():
		"""A house with each of the proprties, to be given values."""
		def __init__(self, pos):
			self.props = {}
			self.props['pos'] = pos

		def __str__(self):
			return "House {}".format(self.props['pos'])

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
			# Whether this Fact is definitely inserted correctly (for this
			# Puzzle perm at least)
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
		self.house_highlight = {}
		self.perm = perm
		self.houses = []
		self.facts = []
		self.get_initial_facts(facts_file)
		for i in range(self.no_of_houses):
			self.houses += [ self.House(i) ]

		if verbose:
			print("{}".format('#' * 80, perm))

		try:
			if not no_combine:
				self.combine_facts()
			# Attach as many facts to house positions as possible
			for f in self.facts:
				self.try_definite_fact(f)
			# Remaining facts: fork the Puzzle, try to insert first Fact at each
			# possible offset of some arbitrary prop. While the insert is
			# successful, recursively attempt this with each following Fact.
			solved_puzzle = self.guess_facts()
			if solved_puzzle is None:
				raise self.PuzzleFinish(False, "Couldn't find a working "
						"combination for remaining Facts")

			# Just completely replace this object with the one that succeeded
			self.__dict__ = solved_puzzle.__dict__
			raise self.PuzzleFinish(True, "Done!")

		except self.PuzzleFinish as f:
			self.finished = True
			self.handle_finish(f)


	def summary_str(self, verbose=False):
		"""Verbose: Returns the Puzzle status & any error message, and the
		Houses grid & list of clues side-by-side.
		Non-verbose: short version of facts positions only"""

		def houses_str_gen():
			"""Shows the value of each House property in a grid, or the number of
			remaining possible values for a property in a bar graph.
			Yields the line length for the grid, then yields the lines one by
			one."""
			key_len = 4
			val_len = 5
			max_len = key_len + val_len * len(self.houses)
			yield max_len
			yield "{:{len}}".format("Houses:", len=max_len)
			# for key in ('pos', 'col', 'nat', 'dri', 'smo', 'pet'):
			for key in (self.all_prop_keys):
				ret = '{:4}'.format(key)
				for house in self.houses:
					highlight = self.house_highlight.get((house, key))
					val = house.props.get(key)
					val = '{:^3}'.format(val) if val is not None else '---'
					val = termcolor.colored(val, None, on_color=highlight)
					ret += ' {} '.format(val)
				yield ret

		def facts_str_gen():
			"""Shows a list of facts: the current relative position tied to each,
			and colours to denote status.
			Shows all props for each fact with its relative position.
			Yields the line length for the block of text, then yields the lines one
			by one."""

			max_len = 0
			lines = []
			for n, f in enumerate(self.facts):
				line = '{:2}. {}'.format(n+1, f)
				max_len = max(max_len, len(line))
				lines += [colour_fact(f, line)]
			yield max_len
			yield "{:{len}}".format('Facts:', len=max_len)
			for line in lines:
				yield line

		def facts_str_short():
			"""Returns the absolute position of inserted Facts, in order - or
			'_' for uninserted - on one line."""
			line = ''
			first_entry = True
			for f in self.facts:
				seg = '{}{}'.format('-' if not first_entry else '',
					f.props[next(iter(f.props))] if f.used or f.in_use else
							'_')
				first_entry = False
				line += colour_fact(f, seg)
			return line

		# Should be used after getting line length
		def colour_fact(fact, text):
			"""White: unused
			Grey: Currently inserted
			Green: Finally inserted (definitely correct for this permutation)
			Red: Currently in use (e.g. half-way through inserting when an error
			occurred)."""
			line_colour = ('green' if fact.final else 'red' if fact.in_use else
					None)
			line_attrs = ['dark'] if fact.used else []
			return termcolor.colored(text, line_colour, attrs=line_attrs)

		ret = 'Puzzle {:16}'.format(str(self.perm))
		if verbose:
			ret += '{:>{pad}}'.format( "SOLVED" if self.solved else
					"FAILED" if self.finished else "UNFINISHED",
					pad=80 - len(ret))
			if self.message:
				ret += '\n{}'.format(self.message)

			# Multiline sections to be placed side-by-side
			sections = (houses_str_gen(), facts_str_gen())

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
		else: # Move back to start of last line
			return '{} {}{}'.format(ret, facts_str_short(), "\033[F\r")

	def get_initial_facts(self, facts_file):
		"""Read in initial facts from a file. Properties are separate by commas,
		relative positions may be optionally supplied (assumed 0 otherwise). A
		relative position of "?" will take the Puzzle's first unused permutation
		value."""
		perm_i = iter(self.perm)
		f = open(facts_file, 'r')
		self.all_prop_keys = set()

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

				self.all_prop_keys |= set((key,))

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
		curr_val = house.props.get(key)
		if curr_val is not None:
			# Already has value; only error out if value is different
			if curr_val == val:
				return
			else:
				raise self.PuzzleFinish(False, "Can't add {} of {} to {}, "
						"already has value of {}".format(key, val, house,
								curr_val), highlight={(house, key): 'on_red'})

		prev_assigned = self.find_house(key, val)
		if prev_assigned:
			raise self.PuzzleFinish(False, "Can't add {} of {} to {}, "
					"value already at {}".format(key, val, house,
							prev_assigned),
					highlight={(house, key): 'on_red',
							(prev_assigned, key): 'on_yellow'})

		house.props[key] = val

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
			self.handle_finish(f)
			return None

		return self.guess_facts()

	def guess_facts(self):
		"""Recursive with try_insert_next_fact: alters the position of the next
		Fact to the first possible relative position, then copies the entire
		Puzzle at each position to see if the Fact is insertable. When/if the
		copy fails, moves the fact to the next possible position and tries again
		with a new copy."""
		fact = self.next_unused_fact()
		if fact is None:
			return self

		# Take an arbitrary prop and try all possible positions
		pivot_prop = next(iter(fact.props))
		for i in range(0, self.no_of_houses):
			fact.adjust_rel_values(i - fact.props[pivot_prop])
			p_cpy = copy.deepcopy(self)
			final_p_cpy = p_cpy.try_insert_next_fact()
			if final_p_cpy is not None:
				return final_p_cpy
		return None

verbose = False

def main():
	ap = argparse.ArgumentParser(description='"Zebra Puzzle" solver.')
	ap.add_argument('facts_file', help='File location of facts to parse.',
			nargs='?', default='zebra.txt')
	ap.add_argument('-v', dest='verbose', action='store_true',
			help='Print verbose output.')
	ap.add_argument('-C', dest='no_combine', action='store_true',
			help='Don\'t combine clues.')
	args = ap.parse_args()

	global verbose, no_combine
	verbose = args.verbose
	no_combine = args.no_combine

	last_puzzle = None

	# Hacky: read through file once just to find number of unknowns.
	unknown_count = 0
	f = open(args.facts_file, 'r')
	for line in f:
		if line[0] in '#\n':
			continue
		unknown_count += line.count('?')


	for perm in itertools.product(*([-1, 1],) * unknown_count):
		if last_puzzle is None or not last_puzzle.solved:
			last_puzzle = Puzzle(args.facts_file, perm)

	# More hacky: overwrite last Puzzle status in non-verbose mode with failure
	# message
	if not verbose and not last_puzzle.solved:
		print("{:80}".format("Unable to find a solution :("))

if __name__ == '__main__':
	main()
