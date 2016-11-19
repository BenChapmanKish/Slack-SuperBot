# coding: utf-8
# Ben Chapman-Kish
# 2016-11-17

import sys, os
import argparse
import json
import time
import random
import markovify
import re
from slackclient import SlackClient
sys.dont_write_bytecode = True

this_dir = os.path.dirname(os.path.realpath(__file__))

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

		self.ignore_self = self.config.get("ignore_self", True)
		self.allowed_channels = self.ignored_users = []
		if "ignored_users" in self.config:
			self.ignored_users = map(str.lower, self.config["ignored_users"])
		if "allowed_channels" in self.config:
			self.allowed_channels = map(str.lower, self.config["allowed_channels"])

		self.slack_message_limit = self.config.get("slack_message_limit", 10) # hundreds of messages to train with
		self.rand_post_chance = self.config.get("rand_post_chance", 0)
		self.min_wait = self.config.get("min_wait", 0)
		self.last_post = 0

		self.default_channel = self.config.get("default_channel", "#random")
		self.state_size = self.config.get("state_size", 2)
		self.retrain_interval = self.config.get("retrain_interval", None)
		self.train_pool = self.config.get("train_pool", True)

		self.max_tries = self.config.get("max_tries", 10000)
		self.max_overlap_total = self.config.get("max_overlap_total", 10)
		self.max_overlap_ratio = self.config.get("max_overlap_ratio", 0.5)

		self.reddit_post_limit = self.config.get("reddit_post_limit", 100)
		self.reddit_ignore_mod = self.config.get("reddit_ignore_mod", True)
		self.reddit_title_train = self.config.get("reddit_title_train", True)
		self.reddit_self_train = self.config.get("reddit_self_train", True)
		self.reddit_link_train = self.config.get("reddit_link_train", False)
		self.reddit_comment_train = self.config.get("reddit_comment_train", True)
		self.reddit_session = None

		self.avg_comment_len = 1
		self.training_messages = []
		self.model = None

		self.prepare_training()

		if len(self.training_messages) == 0:
			print("Nothing to train from!")
			sys.exit(1)

		self.make_model()

	def __repr__(self):
		return "{}".format(self.name)
	__str__ = __repr__

	def post_message(self, channel, message):
		kwargs = {'channel': channel, 'username': self.name, 'as_user': 'false', 'text': message}
		if self.icon:
			kwargs['icon_url'] = self.icon

		response = self.handler.slack_client.server.api_call('chat.postMessage', **kwargs)
		return json.loads(response)

	def handle_event(self, data):
		if data['type'] == 'message' and 'text' in data:
			if 'user' in data:
				user = self.handler.get_username(data['user'])
			elif 'username' in data:
				user = data['username']
			channel = data['channel']

			if self.ignore_self and user.lower() == self.name:
				return

			if user.lower() not in list(self.ignored_users) and \
			(self.allowed_channels and self.handler.get_channel(channel).lower() in self.allowed_channels):

				if random.random() < self.rand_post_chance:
					if self.min_wait:
						now = int(time.time())
						if now < self.last_post + self.min_wait:
							return
						self.last_post = now
					self.create_message(channel)

	def time_action(self, now):
		if random.random() < self.rand_post_chance:
			if self.min_wait:
				if now < self.last_post + self.min_wait:
					return
				self.last_post = now
			self.create_message(self.default_channel)
		if self.retrain_interval != None and now > self.last_trained + self.retrain_interval:
			self.training_messages = []
			self.prepare_training()
			self.make_model()

	def prepare_training(self):
		self.thread_done = 0
		self.total_threads = 0
		self.thread_go = True

		if "train_channels" in self.config:
			print("Training from channels:", self.config["train_channels"])
			if self.config["train_channels"] == "all":
				channels = self.api_call('channels.list')['channels']
				for channel in channels:
					self.train_from_channel(channel['id'])

			else:
				for channel in self.config["train_channels"]:
					self.train_from_channel(channel)

		if "train_files" in self.config:
			print("Training from files:", self.config["train_files"])
			for filename in self.config["train_files"]:
				self.train_from_file(filename)

		if "train_wiki_pages" in self.config:
			print("Training from wikipedia articles:", self.config["train_wiki_pages"])
			for page in self.config["train_wiki_pages"]:
				self.train_from_wikipedia(page)
		if "train_wiki_random" in self.config:
			print("Training from", self.config["train_wiki_random"], "random wikipedia articles:")
			for x in range(self.config["train_wiki_random"]):
				self.train_from_wikipedia()

		if "train_subreddits" in self.config:
			print("Training from subreddits:", self.config["train_subreddits"])
			if self.train_pool:
				from threading import Thread
				for sub in self.config["train_subreddits"]:
					self.total_threads += 1
					t = Thread(target=self.train_from_reddit, args=(sub,))
					t.start()

			else:
				for sub in self.config["train_subreddits"]:
					self.train_from_reddit(sub)

		if "train_random_subs" in self.config:
			print("Training from", int(self.config["train_random_subs"]), "random subreddits")
			for x in range(self.config["train_random_subs"]):
				self.train_from_reddit()

		try:
			while self.thread_done < self.total_threads:
				pass
			time.sleep(0.5)
		except KeyboardInterrupt:
			self.thread_go = False
			print("\nStopped bot instance")



	def make_model(self):
		print(str(self) + ": Creating model...")
		random.shuffle(self.training_messages)
		self.avg_comment_len = sum(map(len, self.training_messages)) / float(len(self.training_messages))
		self.avg_comment_len = min(self.avg_comment_len, 10)
		self.model = TextModel("\n".join(self.training_messages), state_size=self.state_size)
		self.last_trained = time.time()
		return self.model

	def train_from_channel(self, channel):
		latest = time.time()
		if type(channel) == str and len(channel) > 0:
			if channel[0] == '#':
				channel = self.handler.get_channel_id(channel[1:])
			elif channel[0] == '@':
				channel = self.handler.get_user_id(channel[1:])

		for i in range(max(1, self.slack_message_limit)):
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
		for line in lines:
			l = line.strip()
			if l:
				self.training_messages.append(l)

	def train_from_reddit(self, subreddit_name=None):
		if not self.reddit_session:
			import praw
			self.reddit_session = praw.Reddit(user_agent="Slack-SuperBot", \
				client_id=self.handler.tokens['reddit_id'], client_secret=self.handler.tokens['reddit_secret'])

		if subreddit_name:
			subreddit = self.reddit_session.subreddit(subreddit_name)
		else:
			subreddit = self.reddit_session.random_subreddit()
		
		submissions = subreddit.hot(limit=self.reddit_post_limit)

		for sub in submissions:
			if self.train_pool and not self.thread_go:
				break
			if (sub.stickied or sub.distinguished) and self.reddit_ignore_mod:
				continue
			author = (sub.author.name if sub.author else '[deleted]')
			print("\033[35mSubmission by " + author + ":\033[0m " + sub.title)
			if self.reddit_title_train:
				self.training_messages.append(sub.title)
			if sub.is_self and self.reddit_self_train:
				for line in sub.selftext.splitlines():
					l = line.strip()
					if l:
						self.training_messages.append(l)
			elif self.reddit_link_train:
				self.training_messages.append(sub.url)

			if self.reddit_comment_train:
				sub.comments.replace_more()
				comments = sub.comments.list()
				for comment in comments:
					for line in comment.body.splitlines():
						l = line.strip()
						if l:
							self.training_messages.append(l)

		if self.train_pool:
			self.thread_done += 1


	def get_rand_wiki_page(self):
		try:
			try:
				page = wikipedia.page(wikipedia.random())
			except wikipedia.exceptions.DisambiguationError as e:
				try:
					page = wikipedia.page(random.choice(e.options))
				except wikipedia.exceptions.DisambiguationError as e:
					page = self.get_rand_wiki_page()
		except wikipedia.exceptions.PageError:
			page = self.get_rand_wiki_page()

		if (self.train_pool and not self.thread_go) or not page:
			return
		print("\033[35mArticle: \033[0m" + page.title)
		for line in page.content.splitlines():
			if line.split() and not line.startswith('=='):
				self.training_messages.append(line)

		if self.train_pool:
			self.thread_done += 1

	def train_from_wikipedia(self, title=None):
		import wikipedia
		if self.train_pool:
			from threading import Thread
			global wikipedia

		if title:
			try:
				try:
					page = wikipedia.page(title=title)
				except wikipedia.exceptions.DisambiguationError as e:
					try:
						page = wikipedia.page(e.options[0])
					except wikipedia.exceptions.DisambiguationError as e:
						print("\033[43mCould not find wikipedia article for " + title + "\033[0m")
						return
			except wikipedia.exceptions.PageError:
				print("\033[43mCould not find wikipedia article for " + title + "\033[0m")
				return


			print("\033[35mArticle: \033[0m" + page.title)
			for line in page.content.splitlines():
				if line.split() and not line.startswith('=='):
					self.training_messages.append(line)

		else:
			if self.train_pool:
				self.total_threads += 1
				t = Thread(target=self.get_rand_wiki_page)
				t.start()
			else:
				self.get_rand_wiki_page()


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

			new_sentence = self.model.make_sentence(tries=self.max_tries,
			max_overlap_total=self.max_overlap_total,
			max_overlap_ratio=self.max_overlap_ratio)
			if not new_sentence:
				break

			message += " " + new_sentence

		message = message.strip()
		if not message:
			print("\033[43m" + str(self) + " failed to generate message\033[0m")
			return

		for code in ('<!everyone>', '<!channel>', '<!here>'):
			while code in message:
				message = message.replace(code, '@'+code[2:-1])

		mentions = self.handler.user_match.finditer(message)
		if mentions:
			for match in mentions:
				text = match.group()

				if '|' in text:
					end = text.index('|')
				else:
					end = text.index('>')

				username = self.handler.get_username(text[2:end])
				if username:
					message = message.replace(text, '@'+username)

		print("\033[42m" + str(self) + " generated message to send to @" + str(self.handler.get_channel(channel)) + ":\033[0m")
		print(message, '\n')
		
		response = self.post_message(channel, message)



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

		user_mention_regex = r"<@U[A-Z0-9]+(|\|[a-z0-9]+)>"
		self.user_match = re.compile(user_mention_regex)

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
				if reply['type'] == 'message' and 'text' in reply:
					print("\033[44mReceived event:\033[0m")
					print(reply, '\n')

				for bot in self.bots:
					bot.handle_event(reply)

			now = time.time()
			self.autoping(now)
			for bot in self.bots:
				bot.time_action(now)
			time.sleep(.1)

	def autoping(self, now):
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
