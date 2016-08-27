# coding: utf-8

crontable = []
outputs = []
api_calls = []

class BaseBot(object):
	def __init__(self, commands, verbose=True):
		self.commands = commands
		self.verbose = verbose

	def __repr__(self):
		return "BaseBot(commands={}, verbose={})".format(self.commands, self.verbose)
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

	def process_hello(self, data):
		self.debug(type(self).__name__ + " connected to Slack", 42)

	def do_command(self, data, command, body):
		raise NotImplementedError

	def process_message(self, data):
		if data.has_key('text'):
			text = data['text']
			
			if text.startswith('<@U249VP6H2>'):
				# @superbot
				start=11
			elif text.startswith('superbot'):
				start=7
			else: return

			# Ignore first char after mention
			text=text[start+2:]
			print text
			if ' ' in text:
				command = text[:text.index(' ')]
				body = text[text.index(' ')+1:]
				if command in self.commands:
					self.debug("Command \033[36m{}\033[0m: \033[33m{}\033[0m".format(command, body))
					self.do_command(data, command, body)
					self.debug()
