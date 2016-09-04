#!/usr/bin/env bash
eval `ssh-agent -s`
ssh-add
nohup ./run-bot.sh > /dev/null 2>&1 &
