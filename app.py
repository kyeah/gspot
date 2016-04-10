import asyncio
import config
import json
import logging
import re
import spotipy.util as util
import sys

from getpass import getpass
from gmusicapi import Mobileclient
from spotipy import Spotify

logging.basicConfig(filename='.log', level=logging.INFO)

def strip_feat(s):
    return re.sub(r"\(feat.*\)", "", s)

def strip_ft(s):
    return re.sub(r"ft\. .*", "", s)

def strip_amp(s):
    return re.sub("&.*", "", s)

def pprint(stuff):
    print(json.dumps(stuff, indent=4, separators=(',', ': ')))

def chunker(seq, size):
    return (seq[pos:pos + size] for pos in range(0, len(seq), size))

def get_google_library(g):
    dic = {}
    for song in g.get_all_songs():
        dic[song['id']] = song
    return dic

def login_google():
    g = Mobileclient()
    logged_in = g.login(config.auth['GOOGLE_EMAIL'], 
                        config.auth['GOOGLE_PASSWORD'],
                        Mobileclient.FROM_MAC_ADDRESS)

    if not g.is_authenticated():
        logging.error("Invalid Google email/password; exiting.")
        sys.exit(1)

    logging.info("Retrieving Google Music playlists")
    g.playlists = g.get_all_user_playlist_contents()

    logging.info("Retrieving Google Music library")
    g.library = get_google_library(g)

    return g

def login_spotify():
    scope = 'playlist-modify-public playlist-modify-private'
    token = util.prompt_for_user_token(config.auth['SPOTIFY_EMAIL'], scope)

    if not token:
        logging.error("Invalid Spotify token; exiting.")
        sys.exit(1)

    s = Spotify(auth=token)
    s.username = config.auth['SPOTIFY_USERNAME']

    playlists = s.user_playlists(s.username)['items']
    s.playlists = {}

    for sl in playlists:
        s.playlists[sl['name']] = sl

    s.playlist_names = s.playlists.keys()
    return s

@asyncio.coroutine
def transfer_playlist(g, s, playlist):

    spotlist = {}
    if playlist['name'] not in s.playlist_names:
        logging.info("Creating playlist '%s'" % playlist['name'])
        spotlist = s.user_playlist_create(s.username, playlist['name'])
    else:
        logging.info("Updating playlist '%s'" % playlist['name'])
        spotlist = s.playlists[playlist['name']]

    tasks = []
    for track in playlist['tracks']:
        if float(track['creationTimestamp']) > float(config.since):
            future = asyncio.ensure_future(find_track_id(g, s, track))
            tasks.append(future)

    done, _ = yield from asyncio.wait(tasks)

    track_id_results = [task.result() for task in done]
    track_ids = [track_id for (ok, track_id) in track_id_results if ok]
    not_found = [track_info for (ok, track_info) in track_id_results if not ok]
    for nf in not_found:
        logging.warning("Track not found for '%s': '%s'" % (playlist['name'], nf))

    spotinfo = s.user_playlist(s.username, playlist_id=spotlist['id'])
    spottracks = [x['track']['id'] for x in spotinfo['tracks']['items']]
    new_ids = [x for x in track_ids if x not in spottracks]

    logging.info("Adding %d new tracks to '%s'!!!!!!" % (len(new_ids), playlist['name']))
    for group in chunker(new_ids, 100):
        s.user_playlist_add_tracks(s.username, spotlist['id'], group)

@asyncio.coroutine
def find_track_id(g, s, track):
    name = ""
    artist = ""
    if "name" in track:
        name = track['title']
        artist = track['artist']
    else:
        if track['trackId'].startswith('T'):
            tr = g.get_track_info(track['trackId'])
            name = tr['title']
            artist = tr['artist']
        else:
            name = g.library[track['trackId']]['title']
            artist = g.library[track['trackId']]['artist']

    results = s.search('track:%s artist:%s' % (name, artist))['tracks']['items']
    if len(results) > 0:
        return (True, results[0]['id'])
    else:
        name = strip_feat(name)
        artist = strip_feat(strip_amp(artist))
        results = s.search('track:%s artist:%s' % (name, artist))['tracks']['items']
        if len(results) > 0:
            return (True, results[0]['id'])
        else:
            return (False, "%s - %s" % (name, artist))

def main():

    g = login_google()
    s = login_spotify()

    if len(sys.argv) > 1:
        g.playlists = [p for p in g.playlists
                       if p['name'] in sys.argv[1:] 
                       and float(p['lastModifiedTimestamp']) > float(config.since)]

    # Transfer playlists
    print("time to transfer some playlistssss")
    tasks = []
    for playlist in g.playlists:
        future = asyncio.ensure_future(transfer_playlist(g, s, playlist))
        tasks.append(future)

    loop = asyncio.get_event_loop()
    loop.run_until_complete(asyncio.wait(tasks))
    loop.close()

if __name__ == '__main__':
    main()
