# coding: utf-8
# Ben Chapman-Kish
# 2016-11-17

import sys, os
import argparse
import json
import time
import random
import markovify
from slackclient import SlackClient
sys.dont_write_bytecode = True

this_dir = os.path.dirname(os.path.realpath(__file__))

MAX_OVERLAP_RATIO = 0.5
MAX_OVERLAP_TOTAL = 10


class TextModel(markovify.Text):
	# stolen from subreddit simulator
    def test_sentence_input(self, sentence):
        return True

    def _prepare_text(self, text):
        text = text.strip()
        if not text.endswith((".", "?", "!")):
            text += "."
        return text

    def sentence_split(self, text):
        lines = text.splitlines()
        text = " ".join([self._prepare_text(line)
            for line in lines if line.strip()])
        return markovify.split_into_sentences(text)


class MarkovBot(object):
	# This was going to be fully abstract, but then I decided it wasn't worth it
	def __init__(self, handler, directory, config={}):
		self.handler = handler
		self.directory = directory
		self.config = config
		if not config and os.path.isfile(os.path.join(directory, 'config.json')):
			self.config.update(json.load(open(os.path.join(directory, 'config.json'))))

		self.send_message = self.handler.send_message
		self.api_call = self.handler.api_call

		self.name = self.config.get("name", "Unnamed Markov Bot")
		self.icon = self.config.get("icon", None)

		#self.ignore_self = self.config.get("ignore_self", True)
		self.allowed_channels = self.ignored_users = []
		if "ignored_users" in self.config:
			self.ignored_users = map(str.lower, self.config["ignored_users"])
		if "allowed_channels" in self.config:
			self.allowed_channels = map(str.lower, self.config["allowed_channels"])

		self.rand_post_chance = self.config.get("rand_post_chance", 0)
		self.min_wait = self.config.get("min_wait", 0)
		self.last_post = 0

		self.default_channel = self.config.get("default_channel", "random")
		self.state_size = self.config.get("state_size", 2)

		self.avg_comment_len = 1
		self.training_messages = []

		if "training_channels" in self.config:
			for channel in self.config["training_channels"]:
				self.train_from_channel(channel)
		if "training_files" in self.config:
			for filename in self.config["training_files"]:
				self.train_from_file(filename)
		
		if len(self.training_messages) == 0:
			print("Nothing to train from!")
			sys.exit(1)

		self.model = self.make_model()

	def __repr__(self):
		return "{}(name={})"\
			.format(type(self).__name__, self.name)
	__str__ = __repr__

	def post_message(self, channel, message):
		kwargs = {'channel': channel, 'username': self.name, 'as_user': 'false', 'text': message}
		if self.icon:
			kwargs['icon_url'] = self.icon

		response = self.handler.slack_client.server.api_call('chat.postMessage', **kwargs)
		return json.loads(response)

	def handle_event(self, data):
		if data['type'] == 'message' and 'text' in data:
			print("\033[43mReceived event:\033[0m")
			print(data, '\n')

			if 'user' in data:
				user = self.handler.get_username(data['user'])
			elif 'username' in data:
				user = data['username']
			channel = data['channel']

			if user.lower() not in list(self.ignored_users) and \
			(self.allowed_channels and self.handler.get_channel(channel).lower() in self.allowed_channels):

				if random.random() < self.rand_post_chance:
					if self.min_wait:
						now = int(time.time())
						if now < self.last_post + self.min_wait:
							return
						self.last_post = now
					self.create_message(channel)

	def time_action(self):
		if random.random() < self.rand_post_chance:
			if self.min_wait:
				now = int(time.time())
				if now < self.last_post + self.min_wait:
					return
				self.last_post = now
			self.create_message(self.default_channel)

	def make_model(self):
		print(str(self) + ": Creating model...")
		random.shuffle(self.training_messages)
		self.avg_comment_len = sum(map(len, self.training_messages)) / float(len(self.training_messages))
		return TextModel("\n".join(self.training_messages), state_size=self.state_size)

	def train_from_channel(self, channel):
		latest = time.time()
		if type(channel) == str and len(channel) > 0:
			if channel[0] == '#':
				channel = self.handler.get_channel_id(channel[1:])
			elif channel[0] == '@':
				channel = self.handler.get_user_id(channel[1:])

		for i in range(10): # train with 1000 messages
			response = self.api_call('channels.history', {"channel": channel, "count": 100, "latest": latest})
			if not response['ok']:
				print(response)
				sys.exit(1)
			for m in response['messages']:
				if m['type'] == 'message' and 'text' in m:
					self.training_messages.append(m['text'])
			if not response['has_more']:
				break
			latest = response['messages'][-1]['ts']

	def train_from_file(self, filename):
		with open(os.path.join(self.directory, filename)) as f:
			lines = f.readlines()
		messages = []
		for l in lines:
			if l.strip():
				self.training_messages.append(l)

	def create_message(self, channel):
		if not self.model:
			return

		if type(channel) == str and len(channel) > 0:
			if channel[0] == '#':
				channel = self.handler.get_channel_id(channel[1:])
			elif channel[0] == '@':
				channel = self.handler.get_user_id(channel[1:])

		# stolen from subreddit simulator:
		message = ""
		while True:
			portion_done = len(message) / float(self.avg_comment_len)
			continue_chance = 1.0 - portion_done
			continue_chance = max(0, continue_chance)
			continue_chance += 0.1
			if random.random() > continue_chance:
				break

			new_sentence = self.model.make_sentence(tries=10000,
			max_overlap_total=MAX_OVERLAP_TOTAL,
			max_overlap_ratio=MAX_OVERLAP_RATIO)

			message += " " + new_sentence

		message = message.strip()

		print("\033[42mGenerated message to send to " + channel + ":\033[0m")
		print(message)
		
		response = self.post_message(channel, message)
		print(response)
		print()


class MarkovBotHandler(object):
	def __init__(self, credentials, config={}):
		# set the config object
		self.config = config

		# set slack token
		self.tokens = credentials
		self.token = self.tokens['slack']

		# set working directory for loading plugins or other files
		self.directory = self.config.get('base_path', this_dir)
		
		if self.directory.startswith('~'):
			path = os.path.join(os.path.expanduser('~'), self.directory)
			self.directory = os.path.expanduser(path)
		elif not self.directory.startswith('/'):
			path = os.path.join(os.getcwd(), self.directory)
			self.directory = os.path.abspath(path)

		self.last_ping = 0
		self.slack_client = None

		self.bots = []


	def connect(self):
		"""Convenience method that creates Server instance"""
		self.slack_client = SlackClient(self.token)
		self.slack_client.rtm_connect()

	def send_message(self, channel, message=None):
		channel = self.slack_client.server.channels.find(channel)
		if channel is not None and message is not None:
			channel.send_message(message)
			return True
		return False

	def api_call(self, method, kwargs={}):
		if method is not None:
			response = self.slack_client.server.api_call(method, **kwargs)
			return json.loads(response)


	def get_username(self, user_id):
		for member in self.api_call('users.list')['members']:
			if member['id'] == user_id.upper():
				return member['name']

	def get_user_id(self, username):
		for member in self.api_call('users.list')['members']:
			if member['name'].lower() == username.lower():
				return member['id']

	def get_channel(self, channel_id):
		for channel in self.api_call('channels.list')['channels']:
			if channel['id'] == channel_id.upper():
				return channel['name']

	def get_channel_id(self, channel_name):
		for channel in self.api_call('channels.list')['channels']:
			if channel['name'].lower() == channel_name.lower():
				return channel['id']


	def find_bots(self):
		for item in os.listdir(self.directory):
			if os.path.isdir(item):
				if 'specified_bots' in self.config:
					if item not in self.config['specified_bots']:
						continue

				bot_dir = os.path.join(self.directory, item)
				config = {}
				if os.path.isfile(os.path.join(bot_dir, 'config.json')):
					config = json.load(open(os.path.join(bot_dir, 'config.json')))
					if config.get('ignore', False) and 'specified_bots' not in self.config:
						continue

				self.bots.append(MarkovBot(self, bot_dir, config))


	def start(self):
		print("Connecting to Slack...")
		self.connect()
		self.find_bots()
		print("Successfully initialized", len(self.bots), "bots")
		while True:
			for reply in self.slack_client.rtm_read():
				for bot in self.bots:
					bot.handle_event(reply)
			self.autoping()
			for bot in self.bots:
				bot.time_action()
			time.sleep(.1)

	def autoping(self):
		# hardcode the interval to 3 seconds
		now = int(time.time())
		if now > self.last_ping + 3:
			self.slack_client.server.ping()
			self.last_ping = now


def get_config():
	config = {}

	parser = argparse.ArgumentParser()
	parser.add_argument('--credentials', help='Credentials', type=str)
	parser.add_argument('--config', help='Config', default='config.json', type=str)
	parser.add_argument('--base_path', help='Base path for markov bots', default=this_dir, type=str)
	parser.add_argument('-b', '--specify-bot', dest='specified_bots', help='Specify a bot to run, ignoring other bots', action='append', type=str)
	parsed = parser.parse_args()

	if os.path.isfile(parsed.config):
		config = json.load(open(parsed.config))

	for arg, val in vars(parsed).items():
		if val:
			config[arg] = val
	
	return config
	

def main():
	config = get_config()
	credentials = json.load(open((config['credentials'] if 'credentials' in config else 'credentials.json')))
	bot = MarkovBotHandler(credentials, config)
	try:
		bot.start()
	except KeyboardInterrupt:
		print("\nStopped bot instance")

if __name__ == '__main__':
	main()
