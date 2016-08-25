# coding: utf-8

import sys, json

import rtmbot

import gdata.youtube
import gdata.youtube.service

YT_CLIENT_ID = "Slack-UtilityBot"

with open('../CREDENTIALS.json') as f:
	CREDENTIALS = f.read()

yt_service = gdata.youtube.service.YouTubeService()

# Turn on HTTPS/SSL access.
# Note: SSL is not available at this time for uploads.
yt_service.ssl = True
yt_service.developer_key = CREDENTIALS['youtube']['key']
yt_service.client_id = YT_CLIENT_ID 

slack_key = CREDENTIALS['slack']['key']
