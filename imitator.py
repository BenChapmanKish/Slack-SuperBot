# coding: utf-8
# Ben Chapman-Kish
# 2015-10-14

import sys, os
import glob
import argparse
import json
import time
import threading
from importlib import import_module
from slackclient import SlackClient
sys.dont_write_bytecode = True

this_dir = os.path.dirname(os.path.realpath(__file__))

class Imitator(object):
	def __init__(self, credentials, config={}, attachments=None):
		# set the config object
		self.config = config

		# set slack token
		self.tokens = credentials
		self.token = self.tokens.get('slack')
		self.attachments = attachments

		if config.username:
			self.username = self.config.username
		else:
			self.username = input('\033[4mEnter username to imitate:\033[0m ')
		
		if config.icon:
			self.icon = self.config.icon
		else:
			self.icon = input('\033[4mEnter icon url to imitate:\033[0m ')
			

		if config.channel:
			self.channel = self.config.channel
		else:
			self.channel = input('\033[4mEnter channel to talk in:\033[0m ')

		self.kwargs = {'channel': self.channel, 'username': self.username, 'icon_url': self.icon, 'as_user': 'false', 'text': None, 'attachments': self.attachments}
		self.active = True
		self.ready = True
		self.last_ping = 0
		self.slack_client = None
		

	def __repr__(self):
		return "Imitator(username={}, icon={}, channel={})"\
			.format(self.username, self.icon, self.channel)
	__str__ = __repr__

	def connect(self):
		"""Convenience method that creates Server instance"""
		self.slack_client = SlackClient(self.token)
		self.slack_client.rtm_connect()

	def api_call(self, method, kwargs={}):
		if method is not None:
			response = self.slack_client.server.api_call(method, **kwargs)
			return json.loads(response)

	def get_username(self, user_id):
		for member in self.api_call('users.list')['members']:
			if member['id'] == user_id.upper():
				return member['name']

	def start(self):
		self.connect()
		self.getter = threading.Thread(target=self.get_message)
		try:
			self.getter.start()
			self.loop()
		except KeyboardInterrupt:
			self.active = False

	def loop(self):
		try:
			while self.active:
				#for reply in self.slack_client.rtm_read():
				#	self.handle(reply)
				self.autoping()
				if self.kwargs['text']:
					response = self.api_call('chat.postMessage', self.kwargs)
					print('\033[2m' + str(response) + '\033[0m')
					self.kwargs['text'] = None
					self.ready = True
				time.sleep(.1)
		except KeyboardInterrupt:
			self.active = False

	def handle(self, data):
		if data["type"] == "message":
			if data['channel'] in (im['id'] for im in self.api_call('im.list')['ims']) and data['username'] != self.username:
				print(data)

	def autoping(self):
		# hardcode the interval to 3 seconds
		now = int(time.time())
		if now > self.last_ping + 3:
			self.slack_client.server.ping()
			self.last_ping = now

	def get_message(self):
		while self.active:
			try:
				if self.ready:
					text = input("\033[32mEnter next message to send:\033[0m ")
					# todo: replace user mentions and channel references with working links:
					# '<@'+username+'>'
					# channel = self.sb.slack_client.server.channels.find(channel_name)
					# if channel:
					# '<#'+channel.id+'>'
					print("\033[35mAre you sure you want to send this message?\033[0m")
					print(text)
					confirm = input('\033[35m[y]/n:\033[0m ')
					if len(confirm) == 0 or confirm.lower()[0] != 'n':
						self.kwargs['text'] = text
					self.ready = False
			except KeyboardInterrupt:
				self.active = False

	def delete(self, timestamp, channel):
		print(self.api_call('chat.delete', {'as_user': 'false', 'ts': timestamp, 'channel': channel}))

def get_config():
	config = {}

	parser = argparse.ArgumentParser()
	parser.add_argument('--username', help='Username', type=str)
	parser.add_argument('--icon', '--icon_url', dest='icon', help='Icon URL', type=str)
	parser.add_argument('--channel', help='Channel', type=str)
	parser.add_argument('--credentials', help='Credentials', type=str)
	parser.add_argument('--attachments', help='Attachments', type=str)
	parsed = parser.parse_args()
	
	return parsed
	

def main():
	config = get_config()
	credentials = json.load(open(config.credentials or 'credentials.json'))
	if config.attachments or os.path.isfile('attachments.json'):
		attachments = json.load(open(config.attachments or 'attachments.json'))
	else:
		attachments = None
	bot = Imitator(credentials, config, attachments)
	try:
		bot.start()
	except KeyboardInterrupt:
		sys.exit(0)

if __name__ == '__main__':
	main()
