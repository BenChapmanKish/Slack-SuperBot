# coding: utf-8

import sys, os
import cgi
this_dir = os.path.dirname(os.path.realpath(__file__))
sys.path.append(this_dir)
from superbot import SuperBot

crontable = []
outputs = []

YT_DEV_ID = "Slack-UtilityBot"

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

