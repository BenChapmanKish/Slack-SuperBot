#!/usr/bin/env python
import os
import sys
from argparse import ArgumentParser

import yaml
from rtmbot import RtmBot

this_dir = os.path.dirname(os.path.realpath(__file__))

def parse_args():
	parser = ArgumentParser()
	parser.add_argument(
		'-c',
		'--config',
		help='Full path to config file.',
		metavar='path'
	)
	return parser.parse_args()

# load args with config path
args = parse_args()
config = yaml.load(open(os.path.join(this_dir, (args.config or 'rtmbot.conf'))))
bot = RtmBot(config)
try:
	bot.start()
except KeyboardInterrupt:
	sys.exit(0)
