# coding: utf-8
# Ben Chapman-Kish
# 2016-11-17

# TODO: Comment and document this file like crazy

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
		if not text.endswith((".", "?", "!", ",")):
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
		"""
			Config properties that the bot considers:

			name
			icon

			default_channel
			slack_message_limit
			training_users
			ignored_users
			allowed_channels
			ignore_self

			block_user_mentions
			block_links

			rand_post_chance
			min_wait
			retrain_interval

			state_size
			max_tries
			max_overlap_ratio
			max_overlap_total

			

			train_channels
			train_channels_ignore
			train_files
			train_wiki_pages
			train_wiki_random



			train_subreddits_default
			train_subreddits
			train_random_subs


			post_sort
			post_time
			post_limit_total
			post_limit

			ignore_mod
			ignore_nsfw

			title_train
			self_train
			link_train
			comment_train
		"""

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
		self.allowed_channels = []
		self.training_users = []
		self.ignored_users = []
		
		if "ignored_users" in self.config:
			self.ignored_users = list(map(str.lower, self.config["ignored_users"]))

		if "training_users" in self.config:
			self.training_users = list(map(str.lower, self.config["training_users"]))

		if "allowed_channels" in self.config:
			self.allowed_channels = list(map(str.lower, self.config["allowed_channels"]))

		self.slack_message_limit = self.config.get("slack_message_limit", 10) # as hundreds of messages to train with
		self.rand_post_chance = self.config.get("rand_post_chance", 0)
		self.min_wait = self.config.get("min_wait", 0)
		self.last_post = 0

		self.default_channel = self.config.get("default_channel", "#random")
		self.state_size = self.config.get("state_size", 2)
		self.retrain_interval = self.config.get("retrain_interval", None)
		self.train_threading = self.handler.train_threading

		self.max_tries = self.config.get("max_tries", 10000)
		self.max_overlap_total = self.config.get("max_overlap_total", 10)
		self.max_overlap_ratio = self.config.get("max_overlap_ratio", 0.5)

		self.block_user_mentions = self.config.get("block_user_mentions", True)
		self.block_links = self.config.get("block_links", False)

		self.reddit_config = {}

		self.reddit_config['post_sort'] = self.config.get("reddit_post_sort", "hot") # 'hot', 'new', 'controversial', 'top'
		self.reddit_config['post_time'] = self.config.get("reddit_post_time", "all") # 'all', 'day', 'hour', 'month', 'week', 'year'
		self.reddit_config['post_limit_total'] = self.config.get("reddit_post_limit_total", 50) # total posts to train from
		self.reddit_config['post_limit'] = self.config.get("reddit_post_limit", None) # posts per subreddit to train from (overrides total)

		self.reddit_config['ignore_mod'] = self.config.get("reddit_ignore_mod", True)
		self.reddit_config['ignore_nsfw'] = self.config.get("reddit_ignore_nsfw", True)

		self.reddit_config['title_train'] = self.config.get("reddit_title_train", True)
		self.reddit_config['self_train'] = self.config.get("reddit_self_train", True)
		self.reddit_config['link_train'] = self.config.get("reddit_link_train", False)
		self.reddit_config['comment_train'] = self.config.get("reddit_comment_train", True)

		self.reddit_session = None

		self.avg_comment_len = 1
		self.training_messages = []
		self.sent_messages = set()
		self.model = None

		self.prepare_training()

		if len(self.training_messages) == 0:
			print("\033[31mNothing to train from!\033[0m")
			sys.exit(1)

		self.make_model()

	def __repr__(self):
		return (self.name if self.name else type(self).__name__)
	__str__ = __repr__

	def post_message(self, channel, message):
		kwargs = {'channel': channel, 'username': self.name, 'as_user': 'false', 'text': message}
		if self.icon:
			kwargs['icon_url'] = self.icon

		response = self.handler.slack_client.server.api_call('chat.postMessage', **kwargs)
		return json.loads(response)

	def handle_event(self, data):
		if 'type' in data and data['type'] == 'message' and 'text' in data:
			if 'user' in data:
				user = self.handler.get_username(data['user'])
			elif 'username' in data:
				user = data['username']
			channel = data['channel']

			if self.ignore_self and user.lower() == self.name:
				return

			if user.lower() not in self.ignored_users and \
			(self.allowed_channels and self.handler.get_channel(channel).lower() in self.allowed_channels):

				if random.random() < self.rand_post_chance / 100.0:
					if self.min_wait:
						now = int(time.time())
						if now < self.last_post + self.min_wait:
							return
						self.last_post = now
					self.create_message(channel)

	def time_action(self, now):
		if random.random() < self.rand_post_chance / 100.0:
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
		if self.train_threading:
			from threading import Thread
			global Thread
			self.thread_done = 0
			self.total_threads = 0
			self.thread_go = True

		print("\033[42m" + str(self) + ": Preparing to train...\033[0m")

		if "train_channels" in self.config:
			if self.config["train_channels"] == "all":
				channels = self.api_call('channels.list')['channels']
				for channel in channels:
					if "train_channels_ignore" in self.config:
						if '#'+channel['name'] in self.config['train_channels_ignore']:
							continue
					print("\033[44mChannel: #" + str(channel['name']) + "\033[0m")
					self.train_from_channel(channel['id'])

			else:
				for channel in self.config["train_channels"]:
					print("\033[44mChannel: " + str(channel) + "\033[0m")
					self.train_from_channel(channel)

		if "train_files" in self.config:
			if self.config["train_files"] == "all":
				files = os.listdir(self.directory)
				for filename in files:
					if filename[0] != '.' and filename.endswith('.txt'):
						print("\033[44mFile: " + filename + "\033[0m")
						self.train_from_file(os.path.join(self.directory, filename))
			else:
				for filename in self.config["train_files"]:
					print("\033[44mFile: " + filename + "\033[0m")
					self.train_from_file(os.path.join(self.directory, filename))

		if "train_wiki_pages" in self.config:
			for page in self.config["train_wiki_pages"]:
				self.train_from_wikipedia(page)
		if "train_wiki_random" in self.config:
			for x in range(self.config["train_wiki_random"]):
				self.train_from_wikipedia()

		

		if "train_subreddits_default" in self.config:
			config = self.reddit_config
			if not self.reddit_config['post_limit']:
				config['post_limit'] = self.reddit_config['post_limit_total'] / len(self.config["train_subreddits_default"])

			if self.train_threading:
				for sub in self.config["train_subreddits_default"]:
					self.total_threads += 1
					t = Thread(target=self.train_from_reddit, args=(config, sub))
					t.start()

			else:
				for sub in self.config["train_subreddits_default"]:
					self.train_from_reddit(config, sub)

		if "train_subreddits" in self.config:
			reddit_config = {}
			reddit_config.update(self.reddit_config)
			if not self.reddit_config['post_limit']:
				reddit_config['post_limit'] = self.reddit_config['post_limit_total'] / len(self.config["train_subreddits"])

			if self.train_threading:
				for sub in self.config["train_subreddits"]:
					config = {}
					config.update(reddit_config)
					config.update(sub)
					print(config)

					if 'name' not in config:
						print("\033[31mError: No name in training subreddit\033[0m")
						sys.exit(-1)

					self.total_threads += 1
					t = Thread(target=self.train_from_reddit, args=(config, config['name']))
					t.start()

			else:
				for sub in self.config["train_subreddits"]:
					config = {}
					config.update(reddit_config)
					config.update(sub)
					print(config)

					if 'name' not in config:
						print("\033[31mError: No name in training subreddit\033[0m")
						sys.exit(-1)

					self.train_from_reddit(config, config['name'])

		if "train_random_subs" in self.config:
			for x in range(self.config["train_random_subs"]):
				self.train_from_reddit(self.config)

		

		if self.train_threading:
			try:
				while self.thread_done < self.total_threads:
					pass
			except KeyboardInterrupt:
				self.thread_go = False
				print("\nStopped bot training")
			finally:
				time.sleep(0.5)



	def make_model(self):
		print("\033[42m" + str(self) + ": Creating model...\033[0m")
		random.shuffle(self.training_messages)
		self.avg_comment_len = sum(map(len, self.training_messages)) / float(len(self.training_messages))
		self.avg_comment_len = min(self.avg_comment_len, 10)
		self.model = TextModel("\n".join(self.training_messages), state_size=self.state_size)
		self.last_trained = time.time()
		return self.model
	
	def add_training_message(self, message):
		if message.count(' ') > self.state_size:
			self.training_messages.append(message)

	def train_from_channel(self, channel):
		latest = time.time()
		if type(channel) == str and len(channel) > 0:
			if channel[0] == '#':
				channel = self.handler.get_channel_id(channel[1:])
			elif channel[0] == '@':
				channel = self.handler.get_user_id(channel[1:])

		usercache={}

		for i in range(max(1, self.slack_message_limit)):
			response = self.api_call('channels.history', {"channel": channel, "count": 100, "latest": latest})
			if not response['ok']:
				print(response)
				sys.exit(1)
			for m in response['messages']:
				if m['type'] == 'message' and 'text' in m:
					if 'user' in m:
						if m['user'] in usercache:
							user = usercache[m['user']]
						else:
							user = self.handler.get_username(m['user']).lower()
							usercache[m['user']] = user
					elif 'username' in m:
						user = m['username'].lower()
					else:
						continue

					if self.training_users:
						if user in self.training_users:
							self.add_training_message(m['text'])
					elif user not in self.ignored_users:
						self.add_training_message(m['text'])
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
				self.add_training_message(l)

	def train_from_reddit(self, config, subreddit_name=None):
		if not self.reddit_session:
			import praw
			self.reddit_session = praw.Reddit(user_agent="Slack-SuperBot", \
				client_id=self.handler.tokens['reddit_id'], client_secret=self.handler.tokens['reddit_secret'])

		if subreddit_name:
			subreddit = self.reddit_session.subreddit(subreddit_name)
		else:
			subreddit = self.reddit_session.random_subreddit()
			while config['ignore_nsfw'] and subreddit.over18:
				subreddit = self.reddit_session.random_subreddit()

		print("\033[44mSubreddit: " + str(subreddit.display_name) + "\033[0m")
		
		if config['post_sort'] in ('new', 0):
			submissions = subreddit.new(limit=config['post_limit'])
		elif config['post_sort'] in ('hot', 1):
			submissions = subreddit.hot(limit=config['post_limit'])
		elif config['post_sort'] in ('top', 2):
			submissions = subreddit.top(limit=config['post_limit'], time_filter=config['post_time'])
		elif config['post_sort'] in ('controversial', 3):
			submissions = subreddit.controversial(limit=config['post_limit'], time_filter=config['post_time'])
		else:
			print("\033[43mUnrecognized subreddit sort:", config['post_sort'], "\033[0m")
			return

		for sub in submissions:
			if self.train_threading and not self.thread_go:
				break
			elif config['ignore_mod'] and (sub.stickied or sub.distinguished):
				continue
			elif config['ignore_nsfw'] and sub.over_18:
				continue

			author = (sub.author.name if sub.author else '[deleted]')
			print("\033[35mSubmission by " + author + ":\033[0m " + sub.title)
			if config['title_train']:
				self.add_training_message(sub.title)
			if config['self_train']:
				if sub.is_self:
					for line in sub.selftext.splitlines():
						l = line.strip()
						if l:
							self.add_training_message(l)
			elif config['link_train']:
				self.add_training_message(sub.url)

			if config['comment_train']:
				sub.comments.replace_more()
				comments = sub.comments.list()
				for comment in comments:
					for line in comment.body.splitlines():
						l = line.strip()
						if l:
							self.add_training_message(l)

		if self.train_threading:
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

		if (self.train_threading and not self.thread_go) or not page:
			return
		print("\033[44mArticle: " + page.title + "\033[0m")
		for line in page.content.splitlines():
			if line.split() and not line.startswith('=='):
				self.add_training_message(line)

		if self.train_threading:
			self.thread_done += 1

	def train_from_wikipedia(self, title=None):
		import wikipedia
		if self.train_threading:
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
					self.add_training_message(line)

		else:
			if self.train_threading:
				self.total_threads += 1
				t = Thread(target=self.get_rand_wiki_page)
				t.start()
			else:
				self.get_rand_wiki_page()


	def create_message(self, orig_channel):
		if not self.model:
			return

		channel = orig_channel
		if type(channel) == str and len(channel) > 0:
			if channel[0] == '#':
				channel = self.handler.get_channel_id(channel[1:])
			elif channel[0] == '@':
				channel = self.handler.get_user_id(channel[1:])

		for i in range(5): # Temporary hardcoded value, make parameter later

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
			if not self.handler.letters.search(message):
				print("\033[43m" + str(self) + " failed to generate message\033[0m")
				return

			if message not in self.sent_messages:
				self.sent_messages.add(message)
				break


		if self.block_user_mentions:
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

		if self.block_links:
			message = message.replace('http://', '').replace('https://', '')

		print("\033[42m" + str(self) + " generated message to send to " + str(orig_channel) + ":\033[0m")
		print(message, '\n')
		
		response = self.post_message(channel, message)



class MarkovBotHandler(object):
	def __init__(self, credentials, config={}):
		"""
			Config properties that the handler considers:

			base_path
			test_mode
			no_break
			ignored_bots
			specified_bots
			train_threading


			Credential tokens that can/must be defined:

			slack
			reddit_id
			reddit_secret
		"""
		# set the config object
		self.config = config

		# set slack token
		self.tokens = credentials
		self.token = self.tokens['slack']

		# set working directory for loading plugins or other files
		self.directory = self.config.get('base_path', this_dir)
		self.test_mode = self.config.get('test_mode', False)
		self.no_break = self.config.get('no_break', False)
		self.ignored_bots = self.config.get('ignored_bots', [])
		self.train_threading = self.config.get("train_threading", True)

		self.specified_bots = self.config.get('specified_bots', [])
		for x in range(len(self.specified_bots)):
			if self.specified_bots[x][-1] == '/':
				self.specified_bots[x] = self.specified_bots[x][:-1]
		
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
		self.letters = re.compile('[a-zA-Z]')

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
				if item in self.ignored_bots:
					print("\033[33mIgnoring " + item + "\033[0m")
					continue
				if item not in self.specified_bots:
					continue

				bot_dir = os.path.join(self.directory, item)
				config = {}
				if os.path.isfile(os.path.join(bot_dir, 'config.json')):
					config = json.load(open(os.path.join(bot_dir, 'config.json')))
					if config.get('ignore', False) and not self.specified_bots:
						print("\033[33mIgnoring " + item + "\033[0m")
						continue

				if self.test_mode:
					config['rand_post_chance'] = 100
					config['min_wait'] = 1
				self.bots.append(MarkovBot(self, bot_dir, config))


	def start(self):
		print("Connecting to Slack...")
		self.connect()
		self.find_bots()
		print("Successfully initialized", len(self.bots), "bots")

		while True:
			for reply in self.slack_client.rtm_read():
				if 'type' in reply and reply['type'] == 'message' and 'text' in reply:
					print("\033[44mReceived event:\033[0m")
					print(reply, '\n')

				for bot in self.bots:
					if self.no_break:
						try:
							bot.handle_event(reply)
						except Exception as e:
							print("\033[31mException in bot " + str(bot) + ":\033[0m")
							print(e)
					else:
						bot.handle_event(reply)

			now = time.time()
			self.autoping(now)

			for bot in self.bots:
				if self.no_break:
					try:
						bot.time_action(now)
					except Exception as e:
						print("\033[31mException in bot " + str(bot) + ":\033[0m")
						print(e)
				else:
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
	parser.add_argument('--no-break', dest='no_break', help="Ignore errors caused by specific bot configurations", action='store_true')
	parser.add_argument('--base_path', help='Base path for markov bots', default=this_dir, type=str)
	parser.add_argument('--train-threading', dest='train_threading', help='Train with threading', action='store_true')
	parser.add_argument('-t', '--test-mode', dest='test_mode', help='Run bots at high speeds for testing', action='store_true')
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
