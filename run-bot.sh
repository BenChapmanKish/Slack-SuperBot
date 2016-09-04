#!/usr/bin/env bash
# Ben Chapman-Kish
# 2016-09-03

# In order for this script to work, git must be configured
# to connect with ssh, and the ssh key must be kept in a
# local, loaded keychain (e.g. with ssh-add)

killbot() {
	for file in /tmp/superbot*.pid; do
		kill $(cat $file)
	done
}

killbot

git pull origin master
python3 superbot.py --daemon

while true; do
	git fetch origin
	NUM_DIFF=$(git rev-list HEAD...origin/master --count)
	if [[ ! "$NUM_DIFF" -eq 0 ]]; then
		echo "\033[32mChanged detected at $(date +'%y/%m/%d %T'), reloading superbot\033[0m"
		killbot

		git merge origin/master
		python3 superbot.py --daemon
	fi
	sleep 10
done

killbot
