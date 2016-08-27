# coding: utf-8

import sys, os
import time
import hashlib
this_dir = os.path.dirname(os.path.realpath(__file__))
sys.path.append(this_dir)
from superbot import SuperBot

crontable = []
outputs = []

class AnonBot(SuperBot):
	def __init__(self, commands):
		SuperBot.__init__(self, commands)
		self.chat = '#anon-chat'
		self.recent_file = os.path.join(this_dir, 'anon-recent.txt')
		self.regen_time = 20*60 # 20 minutes

	def __repr__(self):
		return "AnonBot(commands={}, chat='{}', recent_file='{}', regen_time={})".format(self.commands, self.chat, self.recent_file, self.regen_time)
	__str__ = __repr__

	def do_command(self, data, command, body):
		identifier = self.get_unique_identifier(data['user'])
		print "Unique identifier for \033[32m{}\033[0m: \033[35m{}\033[0m".format(data['user'], identifier)
		output = "*{}:* {}".format(identifier, body)
		outputs.append([self.chat, output])

	def get_unique_identifier(self, userID):
		nowTime = int(time.time())
		
		with open(self.recent_file) as f:
			lines = f.readlines()

		newgen = True
		i=0

		while i < len(lines):
			# Ignore comments
			line = lines[i].lstrip()
			if len(line) == 0 or line[0] == '#':
				i+=1
				continue

			# All lines should be 3 items, space-separated
			line = lines[i].split()
			if not(len(line) == 3 and line[1].isdigit() and int(line[1]) < nowTime):
				# If the line doesn't meet the format, remove it
				lines.pop(i)
				continue

			thisID, lastTime, identifier = line[0], int(line[1]), line[2]
			
			# Find the user id, if it already exists
			if thisID == userID:
				lines.pop(i)
				# If the user has anonymously posted recently,
				# use their existing unique identifier
				if lastTime + self.regen_time > nowTime:
					newgen = False
				break
			i+=1

		if newgen:
			m = hashlib.md5()
			m.update(str(userID))
			m.update(str(nowTime))
			# Get nice and readable identifier, cutting off after 8 hex digits
			identifier = m.hexdigest()[:8]
		
		newline = str(userID) + ' ' + str(nowTime) + ' ' + str(identifier)
		lines.append(newline)

		with open(self.recent_file, 'w') as f:
			f.write('\n'.join(lines))

		return identifier


anonbot = AnonBot(('anon', 'anonymous'))

def process_hello(data):
	anonbot.process_hello(data)

def process_message(data):
	print data
	anonbot.process_message(data)

	
