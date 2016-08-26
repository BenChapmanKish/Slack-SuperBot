# coding: utf-8

crontable = []
outputs = []

class SuperBot(object):
	def __init__(self, commands):
		self.commands = commands

	def __repr__(self):
		return "SuperBot(commands={})".format(self.commands)
	__str__ = __repr__

	def process_hello(self, data):
		print "\033[42m{} connected to Slack\033[0m".format(self)

	def do_command(self, data, command, body):
		raise NotImplementedError

	def process_message(self, data):
		if data.has_key('text'):
			text = data['text']
			command = text[:text.index(' ')]
			body = text[text.index(' ')+1:]
			if command not in self.commands:
				return

			print "Command \033[36m{}\033[0m: \033[33m{}\033[0m".format(command, body)
			self.do_command(data, command, body)
			print