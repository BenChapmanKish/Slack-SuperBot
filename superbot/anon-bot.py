# coding: utf-8
# Ben Chapman-Kish

import sys, os
import time
import hashlib

this_dir = os.path.dirname(os.path.realpath(__file__))
sys.path.append(this_dir)
from basebot import BaseBot

crontable = []
outputs = []
api_calls = []

# To do: use im.list to determine if a message was in a DM

class AnonBot(BaseBot):
	def __init__(self, verbose=True):
		self.send_commands = ('anon', 'anon-say', 'anon-send')
		self.regen_commands = ('anon-regen', 'anon-reset', 'anon-clear')

		BaseBot.__init__(self, self.send_commands + self.regen_commands, verbose)
		
		self.send_chat = '#anon-chat'
		self.regen_time = 20*60 # 20 minutes
		self.hash_cutoff = 10

		self.users = {}

	def __repr__(self):
		return "AnonBot(send_commands={}, regen_commands={}, send_chat='{}', hash_cutoff={}, regen_time={}, self.users={}, verbose={})"\
			.format(self.send_commands, self.regen_commands, self.send_chat, self.hash_cutoff, self.regen_time, self.users, self.verbose)
	__str__ = __repr__

	def do_command(self, data, command, body=None):
		self.remove_expired_identifiers()

		if command in self.send_commands and isinstance(body, basestring):
			identifier = self.get_unique_identifier(data['user'])

			fallback = "{}: {}".format(identifier, body)

			attachment = '''[
				{
					"fallback": "'''+fallback+'''",
					"color": "#'''+identifier+'''",
					"text": "'''+body+'''"
				}
			]'''

			kwargs = {'channel': self.send_chat, 'username': 'anonymous', 'as_user': 'false', 'attachments': attachment}
			api_calls.append(['chat.postMessage', kwargs])
			
			#output = "*{}:* {}".format(identifier, body)
			#outputs.append([self.send_chat, output])

			self.debug("Unique identifier for \033[32m{}\033[0m: \033[35m{}\033[0m".format(data['user'], identifier))

		elif command in self.regen_commands:
			self.generate_identifier(data['user'])

	def remove_expired_identifiers(self):
		for userID in self.users.iterkeys():
			lastTime = self.users[userID][0]
			if lastTime + self.regen_time < time.time():
				self.users.pop(userID)

	def generate_identifier(self, userID):
		now = time.time()
		m = hashlib.md5()
		m.update(str(userID))
		m.update(str(now))

		# Get nice identifier that works as a hex color
		identifier = m.hexdigest()[:6]
		self.users[userID] = (now, identifier)
		return identifier

	def get_unique_identifier(self, userID):
		if self.users.has_key(userID):
			return self.users[userID][1]
		else:
			return self.generate_identifier(userID)



anonbot = AnonBot()

def process_hello(data):
	anonbot.process_hello(data)

def process_message(data):
	anonbot.process_message(data)
