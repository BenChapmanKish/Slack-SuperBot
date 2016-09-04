#!/usr/bin/env bash
# Ben Chapman-Kish
# 2016-09-03

# In order for this script to work, git must be configured
# to connect with ssh, and the ssh key must be kept in a
# local, loaded keychain (e.g. with ssh-add)

killbot() {
	shopt -s nullglob
	set -- /tmp/superbot*.pid
	if [ "$#" -gt 0 ]; then
		for file in "$@"; do
			kill $(cat $file)
			if [[ -w $file ]]; then
				rm $file
			fi
		done
	fi
}


killbot
git pull origin master
python3 superbot.py &

while true; do
	git fetch origin
	NUM_DIFF=$(git rev-list HEAD...origin/master --count)
	if [[ ! "$NUM_DIFF" -eq 0 ]]; then
		printf "\033[35mChanged detected at $(date +'%y/%m/%d %T')\033[0m\n"
		touch superbot.stop
		killbot

		git merge origin/master
		sleep 1
		printf "\033[33mReloading superbot\033[0m\n"
		rm superbot.stop
		python3 superbot.py &
	fi
	sleep 10
done

killbot
