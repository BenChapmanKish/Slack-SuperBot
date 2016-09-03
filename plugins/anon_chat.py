# coding: utf-8
# Ben Chapman-Kish

import sys, os
import logging
import json

import time
import hashlib

this_dir = os.path.dirname(os.path.realpath(__file__))

# To do: use im.list to determine if a message was in a DM

class AnonChat(object):
	def __init__(self, superbot):
		self.sb = superbot

		# Add plugin-specific config support later

		self.send_commands = ('anon', 'anon-say', 'anon-send')
		self.regen_commands = ('anon-regen', 'anon-reset', 'anon-clear')
		self.commands = self.send_commands + self.regen_commands
		
		self.send_chat = '#anon-chat'
		self.regen_time = 20*60 # 20 minutes
		self.hash_cutoff = 6

		self.users = {}

	def __repr__(self):
		return "AnonChat(send_commands={}, regen_commands={}, send_chat='{}', hash_cutoff={}, regen_time={}, self.users={}, verbose={})"\
			.format(self.send_commands, self.regen_commands, self.send_chat, self.hash_cutoff, self.regen_time, self.users, self.verbose)
	__str__ = __repr__

	def debug(self, text=None, ansi_code=None, force=False):
		if self.verbose or force:
			if text:
				if ansi_code:
					print '\033['+str(ansi_code)+'m' + text + '\033[0m'
				else:
					print text
			else:
				print

	def handle_event(self, data):
		if data["type"] == "message" and data.has_key('text'):
			text = data['text']
			
			if text.startswith(self.sb.usercode):
				# @superbot
				start=11 # even thouugh the len is 12
			elif text.startswith(self.sb.username):
				start=7
			else:
				im_channels = self.sb.api_call('im.list')
				return

			# Ignore first char after mention
			text=text[start+2:]
			if ' ' in text:
				command = text[:text.index(' ')]
				body = text[text.index(' ')+1:]
			else:
				command = text
				body = None

			if command not in self.commands:
				return

			self.sb.log("Command \033[36m{}\033[0m".format(command))
			
			self.remove_expired_identifiers()

			if command in self.send_commands and isinstance(body, basestring):
				identifier = self.get_unique_identifier(data['user'])

				fallback = "{}: {}".format(identifier, body)

				color = '#' + identifier[:6]

				attachment = json.dumps([{
					"fallback": fallback,
					"color": color,
					"text": body
					}])

				kwargs = {'channel': self.send_chat, 'username': 'anonymous', 'as_user': 'false', 'attachments': attachment}
				self.sb.api_call('chat.postMessage', kwargs)
				
				#output = "*{}:* {}".format(identifier, body)
				#outputs.append([self.send_chat, output])

				self.sb.log("Unique identifier for \033[32m{}\033[0m: \033[35m{}\033[0m".format(data['user'], identifier))

			elif command in self.regen_commands:
				self.generate_identifier(data['user'])
			
			self.sb.log()

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
		identifier = m.hexdigest()[:self.hash_cutoff]
		self.users[userID] = (now, identifier)
		return identifier

	def get_unique_identifier(self, userID):
		if self.users.has_key(userID):
			return self.users[userID][1]
		else:
			return self.generate_identifier(userID)

Plugin = AnonChat