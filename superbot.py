#!/usr/bin/env python
from __future__ import unicode_literals
import sys
import glob
import os
import time
import logging
import argparse
import yaml

from slackclient import SlackClient

sys.dont_write_bytecode = True

this_dir = os.path.dirname(os.path.realpath(__file__))

'''
Idea for reorganizing this framework:

A SuperBot class that does all the API calls and stuff
would be created, recycling code from RtmBot.

Each plugin has a function that's called when the
slack client's rtm_read receives input. Said function
would be passed the SuperBot instance and the event data.
'''


class SuperBot(object):
	def __init__(self, config):
		'''
			Params:
				- config (dict):
					- SLACK_TOKEN: your authentication token from Slack
					- BASE_PATH (optional: defaults to execution directory) RtmBot will
						look in this directory for plugins.
					- LOGFILE (optional: defaults to superbot.log) The filename for logs, will
						be stored inside the BASE_PATH directory
					- DEBUG (optional: defaults to False) with debug enabled, SuperBot will
						break on errors
		'''
		# set the config object
		self.config = config

		# set slack token
		self.token = config.get('SLACK_TOKEN')

		# set working directory for loading plugins or other files
		self.directory = self.config.get('BASE_PATH', this_dir)
		if not self.directory.startswith('/'):
			path = '{}/{}'.format(os.getcwd(), self.directory)
			self.directory = os.path.abspath(path)

		# establish logging
		log_file = config.get('LOGFILE', 'superbot.log')
		logging.basicConfig(filename=log_file,
							level=logging.INFO,
							format='%(asctime)s %(message)s')
		logging.info('Initialized in: {}'.format(self.directory))
		self.debug = self.config.get('DEBUG', False)

		# initialize stateful fields
		self.last_ping = 0
		self.plugins = []
		self.slack_client = None

	def _dbg(self, debug_string):
		if self.debug:
			logging.info(debug_string)

	def connect(self):
		"""Convenience method that creates Server instance"""
		self.slack_client = SlackClient(self.token)
		self.slack_client.rtm_connect()

	def _start(self):
		self.connect()
		self.load_plugins()
		while True:
			for reply in self.slack_client.rtm_read():
				self.input(reply)
			self.crons()
			self.output()
			self.api_call()
			self.autoping()
			time.sleep(.1)

	def start(self):
		if 'DAEMON' in self.config:
			if self.config.get('DAEMON'):
				import daemon
				with daemon.DaemonContext():
					self._start()
		self._start()

	def autoping(self):
		# hardcode the interval to 3 seconds
		now = int(time.time())
		if now > self.last_ping + 3:
			self.slack_client.server.ping()
			self.last_ping = now

	def input(self, data):
		if "type" in data:
			function_name = "process_" + data["type"]
			self._dbg("got {}".format(function_name))
			for plugin in self.bot_plugins:
				plugin.register_jobs()
				plugin.do(function_name, data)

	def output(self):
		for plugin in self.bot_plugins:
			limiter = False
			for output in plugin.do_output():
				channel = self.slack_client.server.channels.find(output[0])
				if channel is not None and output[1] is not None:
					if limiter:
						time.sleep(.1)
						limiter = False
					channel.send_message(output[1])
					limiter = True

	def api_call(self):
		for plugin in self.bot_plugins:
			limiter = False
			for api_call in plugin.do_api_calls():
				method, kwargs = api_call
				if limiter:
					time.sleep(.1)
				self.slack_client.server.api_call(method, **kwargs)
				limiter = True

	def crons(self):
		for plugin in self.bot_plugins:
			plugin.do_jobs()

	def find_plugins(self):
		self.bot_plugins = []
		sys.path.insert(0, self.directory + '/plugins/')
		for plugin in glob.glob(self.directory + '/plugins/*'):
			sys.path.insert(1, plugin)

		for plugin in glob.glob(self.directory + '/plugins/*.py'):
			logging.info(plugin)
			name = plugin.split('/')[-1][:-3]
			self.plugins.append(name)


class Plugin(object):

	def __init__(self, name, plugin_config=None):
		'''
		A plugin in initialized with:
			- name (str)
			- plugin config (dict) - (from the yaml config)
				Values in config:
				- DEBUG (bool) - this will be overridden if debug is set in config for this plugin
		'''
		if plugin_config is None:
			plugin_config = {}
		self.name = name
		self.jobs = []
		self.module = __import__(name)
		self.module.config = plugin_config
		self.debug = self.module.config.get('DEBUG', False)
		self.register_jobs()
		self.outputs = []
		self.api_calls = []
		if 'setup' in dir(self.module):
			self.module.setup()

	def register_jobs(self):
		if 'crontable' in dir(self.module):
			for interval, function in self.module.crontable:
				self.jobs.append(CronJob(interval, eval("self.module." + function), self.debug))
			logging.info(self.module.crontable)
			self.module.crontable = []
		else:
			self.module.crontable = []

	def do(self, function_name, data):
		if function_name in dir(self.module):
			if self.debug is True:
				# this makes the plugin fail with stack trace in debug mode
				eval("self.module." + function_name)(data)
			else:
				# otherwise we log the exception and carry on
				try:
					eval("self.module." + function_name)(data)
				except Exception:
					logging.exception("problem in module {} {}".format(function_name, data))
		if "catch_all" in dir(self.module):
			if self.debug is True:
				# this makes the plugin fail with stack trace in debug mode
				self.module.catch_all(data)
			else:
				try:
					self.module.catch_all(data)
				except Exception:
					logging.exception("problem in catch all: {} {}".format(self.module, data))

	def do_jobs(self):
		for job in self.jobs:
			job.check()

	def do_output(self):
		output = []
		while True:
			if 'outputs' in dir(self.module):
				if len(self.module.outputs) > 0:
					logging.info("output from {}".format(self.module))
					output.append(self.module.outputs.pop(0))
				else:
					break
			else:
				self.module.outputs = []
		return output

	def do_api_calls(self):
		api_calls = []
		while True:
			if 'api_calls' in dir(self.module):
				if len(self.module.api_calls) > 0:
					logging.info("api call from {}".format(self.module))
					api_calls.append(self.module.api_calls.pop(0))
				else:
					break
			else:
				self.module.api_calls = []
		return api_calls


class CronJob(object):
	def __init__(self, interval, function, debug):
		self.function = function
		self.interval = interval
		self.lastrun = 0
		self.debug = debug

	def __repr__(self):
		return "CronJob(function={}, interval={}, lastrun={})".format(self.function, self.interval, self.lastrun)
	__str__ = __repr__

	def check(self):
		if self.lastrun + self.interval < time.time():
			if self.debug is True:
				# this makes the plugin fail with stack trace in debug mode
				self.function()
			else:
				# otherwise we log the exception and carry on
				try:
					self.function()
				except Exception:
					logging.exception("Problem in job check: {}".format(self.function))
			self.lastrun = time.time()





def parse_args():
	parser = argparse.ArgumentParser()
	parser.add_argument(
		'-c',
		'--config',
		help='Full path to config file.',
		metavar='path'
	)
	return parser.parse_args()

def main():
	# load args with config path
	args = parse_args()
	if args.config:
		confpath = os.path.expanduser(args.config)
	else:
		confpath = os.path.join(this_dir, 'superbot.yml')
	config = yaml.load(open(confpath))

	bot = SuperBot(config)
	try:
		bot.start()
	except KeyboardInterrupt:
		sys.exit(0)

if __name__ == '__main__':
	main()
