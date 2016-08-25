# coding: utf-8

import sys, json

import gdata.youtube
import gdata.youtube.service

# This is a plugin for python-rtmbot
# If one would prefer, we could use SlackClient instead

YT_CLIENT_ID = "Slack-UtilityBot"

# Put your slack and youtube credentials in a json file
with open('../credentials.json') as f:
	CREDENTIALS = json.loads(f.read())

crontable = []
outputs = []

########################################
# ANONYMOUS CHANNEL WITH UNIQUE IDENTIFIERS

# https://api.slack.com/bot-users

# This hasn't been made yet

########################################




########################################
# YOUTUBE PLAYLIST RANDOM SONG

# Use these APIs:
# https://developers.google.com/youtube/1.0/developers_guide_python
# https://developers.google.com/youtube/v3/docs/search/list
# https://developers.google.com/youtube/v3/docs/playlistItems/list

yt_service = gdata.youtube.service.YouTubeService()

# Turn on HTTPS/SSL access.
# Note: SSL is not available at this time for uploads.
yt_service.ssl = True
yt_service.developer_key = CREDENTIALS['youtube']['key']
yt_service.client_id = YT_CLIENT_ID 

slack_key = CREDENTIALS['slack']['key']

########################################
