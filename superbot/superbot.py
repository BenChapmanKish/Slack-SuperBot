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
		print str(self)+" connected to Slack"

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
					print "Command \033[36m{}\033[0m: \033[33m{}\033[0m".format(command, body)
					self.do_command(data, command, body)
					print
