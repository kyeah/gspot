import asyncio
import config
import logging
import re
import spotipy.util as util
import sys

from getpass import getpass
from gmusicapi import Mobileclient
from spotipy import Spotify

formatter = logging.Formatter("%(asctime)s;%(levelname)s;%(message)s",
                              datefmt="%Y-%m-%d %H:%M:%S")

handler = logging.FileHandler('.log')
handler.setLevel(logging.INFO)
handler.setFormatter(formatter)

log = logging.getLogger(__name__)
log.addHandler(handler)

def strip_feat(s):
    return re.sub(r"\(feat.*\)", "", s)

def strip_ft(s):
    return re.sub(r"ft\. .*", "", s)

def strip_amp(s):
    return re.sub("&.*", "", s)

def chunker(seq, size):
    return (seq[pos:pos + size] for pos in range(0, len(seq), size))

def get_google_library(g):
    dic = {}
    for song in g.get_all_songs():
        dic[song['id']] = song
    return dic

def login_google():
    """ Log into Google and retrieve user library and playlists """

    g = Mobileclient()
    logged_in = g.login(config.auth['GOOGLE_EMAIL'], 
                        config.auth['GOOGLE_PASSWORD'],
                        Mobileclient.FROM_MAC_ADDRESS)

    if not g.is_authenticated():
        log.error("Invalid Google email/password; exiting.")
        sys.exit(1)

    log.info("Retrieving Google Music playlists")
    g.playlists = g.get_all_user_playlist_contents()

    log.info("Retrieving Google Music library")
    g.library = get_google_library(g)

    return g

def login_spotify():
    """ Log into Spotify and retrieve user playlists """

    scope = 'playlist-modify-public playlist-modify-private'
    token = util.prompt_for_user_token(config.auth['SPOTIFY_EMAIL'], scope)

    if not token:
        log.error("Invalid Spotify token; exiting.")
        sys.exit(1)

    s = Spotify(auth=token)
    s.username = config.auth['SPOTIFY_USERNAME']

    playlists = s.user_playlists(s.username)['items']
    s.playlists = {}

    for sl in playlists:
        s.playlists[sl['name']] = sl

    return s

@asyncio.coroutine
def transfer_playlist(g, s, playlist):
    """ Synchronize Google Music playlist to Spotify """
    
    # Retrieve or create associated Spotify playlist
    name = playlist['name']
    spotlist = s.playlists.get(name, None) \
               or s.user_playlist_create(s.username, name)

    action = "Updating" if name in s.playlists else "Creating"
    log.info("%s playlist '%s'" % (action, name))

    # Find Spotify track IDs for each new song
    tasks = []
    for track in playlist['tracks']:
        if float(track['creationTimestamp']) > float(config.since):
            task = asyncio.Task(find_track_id(g, s, track))
            tasks.append(task)

    results = yield from asyncio.gather(*tasks)

    track_ids, not_found = [], []
    for (ok, track_info) in results:
        (track_ids if ok else not_found).append(track_info)

    for nf in not_found:
        log.warning("Track not found for '%s': '%s'" % (name, nf))

    # Filter for songs not yet synchronized to Spotify
    spotlist_info = s.user_playlist(s.username, playlist_id=spotlist['id'])
    spotlist_tracks = [x['track']['id'] for x in spotlist_info['tracks']['items']]
    new_ids = [x for x in track_ids if x not in spotlist_tracks]

    # Add new songs!!!
    log.info("Adding %d new tracks to '%s'!!!!!!" % (len(new_ids), name))
    for group in chunker(new_ids, 100):
        s.user_playlist_add_tracks(s.username, spotlist['id'], group)

@asyncio.coroutine
def find_track_id(g, s, track):
    """ Find Spotify ID for associated Google Music track """

    name, artist = "", ""

    if "name" in track:
        name = track['title']
        artist = track['artist']
    else:
        if track['trackId'].startswith('T'):
            # Retrieve store track info
            tr = g.get_track_info(track['trackId'])
            name = tr['title']
            artist = tr['artist']
        else:
            # Retrieve personal track info
            name = g.library[track['trackId']]['title']
            artist = g.library[track['trackId']]['artist']

    results = s.search('track:%s artist:%s' % (name, artist))['tracks']['items']
    if results:
        return (True, results[0]['id'])
    else:
        # Spotify and Google Music handle collaborations differently :(
        name = strip_feat(name)
        artist = strip_feat(strip_amp(artist))
        results = s.search('track:%s artist:%s' % (name, artist))['tracks']['items']
        if results:
            return (True, results[0]['id'])
        else:
            return (False, "%s - %s" % (name, artist))

def main():

    g = login_google()
    s = login_spotify()

    # Filter playlists by config and last sync
    g.playlists = [p for p in g.playlists
                   if (not config.playlists or 
                       p['name'] in config.playlists)
                   and p['name'] not in config.exclude
                   and float(p['lastModifiedTimestamp']) > float(config.since)]

    # Transfer playlists
    tasks = []
    for playlist in g.playlists:
        future = asyncio.ensure_future(transfer_playlist(g, s, playlist))
        tasks.append(future)

    loop = asyncio.get_event_loop()
    loop.run_until_complete(asyncio.wait(tasks))
    loop.close()

if __name__ == '__main__':
    main()
