#!/usr/bin/env python
#-*- coding:utf-8 -*-

"""
BetterGame:
Ben made several significant improvements
over Toshi's game that quoted Professor Oak
once, then slept for eternity.
"""

import sys
import time
import random

class TimeSleepQuotePrinter(object):
	"""
	This class prints a random quote at regular intervals.
	"""
	def __init__(self, time_interval=60, join_char=" "):
		self._time_interval = time_interval
		self._quotes = []
		self._join_char = join_char
	
	# For debugging purposes
	def __repr__(self):
		return "TimeSleepQuotePrinter(time_interval={}, quotes={})".format(self._time_interval, self._quotes)
	
	__str__ = __repr__
	
	# Allow referencing as a container
	def __len__(self):
		return len(self._quotes)
	
	def __getitem__(self, key):
		return self._quotes[key]
	
	def __setitem__(self, key, value):
		self._quotes[key] = value
	
	# Determine equality
	def __eq__(self, other):
		if hasattr(other, "_time_interval") and self._time_interval == other._time_interval	and \
		hasattr(other, "_quotes") and hasattr(other._quotes, "__getitem__") and \
		len(set(self._quotes) ^ set(other._quotes)) == 0:
			return True
		
		return False
	
	def __ne__(self, other):
		return not(self.__eq__(other))
		
	
	# Convenient protected methods for modifying the quote container
	def addQuote(self, *quote):
		if len(quote) == 1:
			self._quotes.append(quote[0])
		else:
			self._quotes.append(quote)
	
	def getRandomQuote(self):
		quote = random.choice(self._quotes)
		if isinstance(quote, (list, tuple)):
			quote = self._join_char.join(quote)
		return quote
	
	# Wait for the time
	def waitTime(self, wait_time=None):
		if not wait_time:
			wait_time = self._time_interval
		try:
			time.sleep(wait_time)
		except KeyboardInterrupt:
			print
			sys.exit(0)
		
	def mainLoop(self):
		"""
		Perform the instance's main loops, by
		printing a random quote from the internal
		list of quotes, then sleeping for the time
		interval specified when itinialized.
		"""
		
		while True:
			print self.getRandomQuote()
			self.waitTime()

	
class ProfessorOakQuoter(TimeSleepQuotePrinter):
	"""
	A modified TimeSleepQuotePrinter that specifically quotes Professor Oak.
	"""
	def __init__(self, time_interval=60, join_char="\n\t"):
		TimeSleepQuotePrinter.__init__(self, time_interval, join_char)
	
	def mainLoop(self):
		print
		while True:
			print "Oak's words echoed:"
			print "\t" + self.getRandomQuote() + "\n"
			self.waitTime()


def main():
	"""
	Create Prof. Oak quotes and run the main loop.
	"""
	quoter = ProfessorOakQuoter()
	
	quoter.addQuote("There is a time and place for everything, But not now.")
	quoter.addQuote("You can't use that here!")
	quoter.addQuote("My name is Oak! People call me the Pokémon Prof.")
	quoter.addQuote("The early bird catches the worm, or in this case the Pokémon.")
	quoter.addQuote("You look more like you're ready for bed, not for Pokémon training.")
	quoter.addQuote("Tell me about yourself, are you a boy or a girl?")
	quoter.addQuote("As a child, I played a lot of video games", "and was known as Flying Fingers Sammy.")
	
	quoter.mainLoop()
	return 0

if __name__ == '__main__':
	sys.exit(main())
