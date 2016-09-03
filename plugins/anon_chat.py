# coding: utf-8
# Ben Chapman-Kish

import sys, os
import logging
import json

import time
import hashlib

import random
import names

this_dir = os.path.dirname(os.path.realpath(__file__))

# To do: use im.list to determine if a message was in a DM

class AnonChat(object):
	def __init__(self, superbot):
		self.sb = superbot

		# Add plugin-specific config support later

		self.send_commands = ('anon', 'anon-say', 'anon-send')
		self.regen_commands = ('anon-regen', 'anon-reset', 'anon-clear')
		self.identify_commands = ('anon-id', 'anon-identify', 'anon-whoami')
		self.help_commands = ('anon-help', 'anon-commands')
		self.commands = self.send_commands + self.regen_commands + self.identify_commands + self.help_commands
		
		self.anon_chat = '#anon-chat'
		self.regen_time = 20*60 # 20 minutes
		self.hash_cutoff = 6

		self.users = {}

	def __repr__(self):
		return "AnonChat(send_commands={}, regen_commands={}, identify_commands={}, help_commands={}, anon_chat='{}', hash_cutoff={}, regen_time={}, self.users={})"\
			.format(self.send_commands, self.regen_commands, self.identify_commands, self.help_commands, self.anon_chat, self.hash_cutoff, self.regen_time, self.users)
	__str__ = __repr__

	def handle_event(self, data):
		if data["type"] == "message" and 'text' in data:
			
			addressed, start = self.sb.message_addressed(data)
			if not addressed:
				return

			text = data['text'][start:]

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

			if command in self.send_commands and isinstance(body, str):
				color, name = self.get_unique_identifier(data['user'])

				#attachment = json.dumps([{
				#	"fallback": body,
				#	"color": '#'+color,
				#	"text": body
				#	}])

				kwargs = {'channel': self.anon_chat, 'username': name, 'as_user': 'false', 'text': body}#, 'attachments': attachment}
				self.sb.api_call('chat.postMessage', kwargs)
				
				#output = "*{}:* {}".format(identifier, body)
				#outputs.append([self.send_chat, output])

				self.sb.log("User \033[32m{}\033[0m: Color \033[35m{}\033[0m, Name \033[36m{}\033[0m".format(data['user'], color, name))

			elif command in self.regen_commands:
				color, name = self.generate_identifier(data['user'])
				message = "Your new anonymous ID is " + name
				self.sb.send_message(data['channel'], message)

			elif command in self.identify_commands:
				color, name = self.get_unique_identifier(data['user'])
				message = "Your current anonymous ID is " + name
				self.sb.send_message(data['channel'], message)

			elif command in self.help_commands:
				message = "*SuperBot anonymous chat plugin*\nAvailable commands are:\n" + \
'_' + self.send_commands[0] + ' [message]_: Anonymously send the message to ' + self.anon_chat + '\n' + \
'_' + self.regen_commands[0] + '_: Regenerate your anonymous unique identifier\n' + \
'_' + self.identify_commands[0] + '_: Show your current anonymous unique identifier\n' + \
'_' + self.help_commands[0] + '_: Display this help message'
				self.sb.send_message(data['channel'], message)

			self.sb.log()

	def remove_expired_identifiers(self):
		for userID in self.users.keys():
			lastTime = self.users[userID][0]
			if lastTime + self.regen_time < time.time():
				self.users.pop(userID)

	def generate_identifier(self, userID):
		now = time.time()
		m = hashlib.md5()
		m.update(userID.encode('utf-8'))
		m.update(str(now).encode('utf-8'))

		# Get nice identifier that works as a hex color
		color = m.hexdigest()[:6]

		# Get a random name too just cause
		random.seed(m.digest())
		name = names.get_first_name()

		self.users[userID] = (now, color, name)
		return (color, name)

	def get_unique_identifier(self, userID):
		if userID in self.users:
			return self.users[userID][1:]
		else:
			return self.generate_identifier(userID)

Plugin = AnonChat