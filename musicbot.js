/* Musicbot for Slack
 * Ben Chapman-Kish
 * 2016-08-23
 *
 * Looks up song or playlist
 * and puts the link in chat
 */

const YouTube = require('youtube-node'),
	fs = require("fs"),
    readJson = require("r-json");

var yt = new YouTube();

const CREDENTIALS = readJson(__dirname+"/../credentials.json");

yt.setKey(CREDENTIALS.youtube.key);

// Make this search for playlists rather than videos
yt.search('Mouth Sounds', 1, function(error, result) {
  if (error) {
    console.log(error);
  }
  else {
    console.log(JSON.stringify(result, null, 2));
  }
});