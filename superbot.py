# coding: utf-8

import sys, os
import time
import hashlib
import cgi

crontable = []
outputs = []

# Make this better later:
commands = ('anon', 'anonymous')

YT_DEV_ID = "Slack-UtilityBot"
ANON_CHAT = '#anon-chat'
ANON_RECENT_FILE = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'anon-recent.txt')
ANON_ID_REGEN_TIME_SECONDS = 20*60 # 20 minutes

def process_hello(data):
	print "\033[42mSuperbot has been initialized\033[0m"

def process_message(data):
	if data.has_key('text'):
		text = data['text']
		command = text[:text.index(' ')]
		body = text[text.index(' ')+1:]
		if command not in commands:
			return

		print "Command \033[36m{}\033[0m: \033[33m{}\033[0m".format(command, body)
		if command in ('anon', 'anonymous'):
			identifier = get_unique_identifier(data['user'])
			print "Unique identifier for \033[32m{}\033[0m: \033[35m{}\033[0m".format(data['user'], identifier)
			output = "*{}:* {}".format(identifier, cgi.escape(body))
			outputs.append([ANON_CHAT, output])
		print

def get_unique_identifier(userID):
	nowTime = int(time.time())
	
	with open(ANON_RECENT_FILE) as f:
		lines = f.readlines()

	newgen = True
	i=0

	while i < len(lines):
		# Ignore comments
		line = lines[i].lstrip()
		if len(line) == 0 or line[0] == '#':
			i+=1
			continue

		# All lines should be 3 items, space-separated
		line = lines[i].split()
		if not(len(line) == 3 and line[1].isdigit() and int(line[1]) < nowTime):
			# If the line doesn't meet the format, remove it
			lines.pop(i)
			continue

		thisID, lastTime, identifier = line[0], int(line[1]), line[2]
		
		# Find the user id, if it already exists
		if thisID == userID:
			lines.pop(i)
			# If the user has anonymously posted recently,
			# use their existing unique identifier
			if lastTime + ANON_ID_REGEN_TIME_SECONDS > nowTime:
				newgen = False
			break
		i+=1

	if newgen:
		m = hashlib.md5()
		m.update(str(userID))
		m.update(str(nowTime))
		# Get nice and readable identifier, cutting off after 8 hex digits
		identifier = m.hexdigest()[:8]
	
	newline = str(userID) + ' ' + str(nowTime) + ' ' + str(identifier)
	lines.append(newline)

	with open(ANON_RECENT_FILE, 'w') as f:
		f.write('\n'.join(lines))

	return identifier


def youtube_random_song():
	# YOUTUBE PLAYLIST RANDOM SONG
	import json
	import gdata.youtube
	import gdata.youtube.service

	# Use these APIs:
	# https://developers.google.com/youtube/1.0/developers_guide_python
	# https://developers.google.com/youtube/v3/docs/search/list
	# https://developers.google.com/youtube/v3/docs/playlistItems/list

	yt_service = gdata.youtube.service.YouTubeService()

	# Turn on HTTPS/SSL access.
	# Note: SSL is not available at this time for uploads.
	yt_service.ssl = True
	yt_service.developer_key = YT_DEV_ID
	with open('../credentials.json') as f:
		yt_service.client_id = json.loads(f.read())['youtube']['key'] 

