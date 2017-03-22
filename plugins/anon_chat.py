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
		self.name_types = ('first', 'male', 'female', 'last')
		self.identify_commands = ('anon-id', 'anon-identify', 'anon-whoami')
		self.help_commands = ('anon-help', 'anon-commands')
		self.commands = self.send_commands + self.regen_commands + self.identify_commands + self.help_commands
		
		self.anon_chat = '#anon-chat'
		self.anon_chat_code = '<#'+self.sb.slack_client.server.channels.find(self.anon_chat).id+'>'
		self.regen_time = 20*60 # 20 minutes
		self.min_regen_wait = 30 # 30 seconds
		self.hash_cutoff = 6

		self.help_message = "*SuperBot anonymous chat plugin*\nAvailable commands are:\n" + \
			'_' + self.send_commands[0] + ' message_: Anonymously send the message to ' + self.anon_chat_code + '\n' + \
			'_' + self.regen_commands[0] + ' [' + '/'.join(self.name_types) + ']_: ' + \
				'Regenerate your anonymous unique identifier (with optional gender/type, default ' + self.name_types[0] + ')\n' + \
			'_' + self.identify_commands[0] + '_: Show your current anonymous unique identifier\n' + \
			'_' + self.help_commands[0] + '_: Display this help message'

		self.users = {}

	def __repr__(self):
		return "AnonChat(anon_chat='{}', hash_cutoff={}, regen_time={}, self.users={})"\
			.format(self.anon_chat, self.hash_cutoff, self.regen_time, self.users)
	__str__ = __repr__

	def handle_event(self, data):
		if data["type"] == "message" and 'text' in data:
			
			addressed, start = self.sb.message_addressed(data)
			if not addressed:
				return

			text = data['text'][start:]

			if ' ' in text:
				command = text[:text.index(' ')].lower()
				body = text[text.index(' ')+1:]
			else:
				command = text.lower()
				body = ""

			if command not in self.commands:
				return

			username = self.sb.get_username(data['user'])
			self.sb.log("User \033[32m{}\033[0m issued command \033[35m{}\033[0m  :  \033[34m{}\033[0m".format(username, command, body))
			

			if command in self.send_commands and len(body) > 0:
				name = self.get_unique_identifier(data['user'])

				#attachment = json.dumps([{
				#	"fallback": body,
				#	"color": '#'+color,
				#	"text": body
				#	}])

				kwargs = {'channel': self.anon_chat, 'username': name, 'as_user': 'false', 'text': body}#, 'attachments': attachment}
				self.sb.api_call('chat.postMessage', kwargs)

			elif command in self.regen_commands:
				if data['user'] in self.users:
					lastTime = self.users[data['user']][0]
					waitTime = lastTime + self.min_regen_wait - time.time()
					if waitTime > 0:
						self.sb.send_message(data['channel'], "Tried regenerating ID too soon. Please wait %d seconds." % waitTime)
						return
				name = self.generate_identifier(data['user'], body.lower())
				if name:
					message = "New anonymous ID for <@" + data['user'] + "> is *" + name + "*"
					self.sb.send_message(data['channel'], message)
				else:
					self.sb.send_message(data['channel'], 'Invalid name type, command failed.')
					self.sb.send_message(data['channel'], self.help_message)

			elif command in self.identify_commands:
				name = self.get_unique_identifier(data['user'])
				message = "Current anonymous ID for <@" + data['user'] + "> is *" + name + "*"
				self.sb.send_message(data['channel'], message)

			elif command in self.help_commands:
				self.sb.send_message(data['channel'], self.help_message)

			self.sb.log()

	def remove_expired_identifiers(self):
		for userID in self.users.keys():
			lastTime = self.users[userID][0]
			if lastTime + self.regen_time < time.time():
				self.users.pop(userID)

	def generate_identifier(self, userID, name_type=None):
		now = time.time()
		m = hashlib.md5()
		m.update(userID.encode('utf-8'))
		m.update(str(now).encode('utf-8'))

		# Get nice identifier that works as a hex color
		#color = m.hexdigest()[:6]

		# Get a random name too just cause
		random.seed(m.digest())
		
		name = None
		
		if name_type in ('male', 'female'):
			name = names.get_first_name(gender=name_type)
		elif name_type == 'last':
			name = names.get_last_name()
		elif name_type in ('first', None):
			name = names.get_first_name()
		else:
			return

		# If this name is taken, recursively regenerate it
		for userdata in self.users.values():
			if name == userdata[1]:
				return self.generate_identifier(userID, name_type)

		self.users[userID] = (now, name)
		return name

	def get_unique_identifier(self, userID):
		self.remove_expired_identifiers()
		if userID in self.users:
			return self.users[userID][1]
		else:
			return self.generate_identifier(userID)

Plugin = AnonChat
