import re
import asyncio
import json
import spotipy.util as util
import sys

from getpass import getpass
from gmusicapi import Mobileclient
from spotipy import Spotify

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

@asyncio.coroutine
def find_track_id(g, s, track, library):
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
            name = library[track['trackId']]['title']
            artist = library[track['trackId']]['artist']

    results = s.search('track:{} artist:{}'.format(name, artist))['tracks']['items']
    if len(results) > 0:
        return (True, results[0]['id'])
    else:
        name = strip_feat(name)
        artist = strip_feat(strip_amp(artist))
        results = s.search('track:{} artist:{}'.format(name, artist))['tracks']['items']
        if len(results) > 0:
            return (True, results[0]['id'])
        else:
            return (False, "{} - {}".format(name, artist))

def main():

    # Google Music
    gmail = input("Enter Google email address: ")
    gpass = getpass("Enter Google password: ")
    g = Mobileclient()

    logged_in = g.login(gmail, gpass, Mobileclient.FROM_MAC_ADDRESS)
    if not g.is_authenticated():
        uprint("Invalid Google username/password")
        sys.exit(1)

    # Spotify
    scope = 'playlist-modify-public playlist-modify-private'
    spotify_email = input("Enter Spotify email: ")
    spotify_username = input("Enter Spotify username: ")
    spotify_token = util.prompt_for_user_token(spotify_email, scope)

    if not spotify_token:
        uprint("Invalid Spotify token")
        sys.exit(1)

    s = Spotify(auth=spotify_token)
    created_since = 0

    # Transfer playlists
    print("gettin' user playlist contents")
    playlists = g.get_all_user_playlist_contents()
    if len(sys.argv) > 1:
        playlists = [p for p in playlists if p['name'] in sys.argv]

    print("gettin' library")
    library = get_google_library(g)

    print("time to transfer some playlistssss")
    spotify_lists = s.user_playlists(spotify_username)['items']
    spotify_dict = {}
    for sl in spotify_lists:
        spotify_dict[sl['name']] = sl
    spotify_list_names = [x['name'] for x in spotify_lists]

    for playlist in playlists:
        print("Transferring playlist '{}'".format(playlist['name']))
        spotlist = {}
        if playlist['name'] not in spotify_list_names:
            print("Creating playlist")
            spotlist = s.user_playlist_create(spotify_username, playlist['name'])
        else:
            print("Found existing playlist")
            spotlist = spotify_dict[playlist['name']]

        tasks = []
        print("Searching for Spotify IDs")
        for track in playlist['tracks']:
            if int(track['creationTimestamp']) > created_since:
                future = asyncio.ensure_future(find_track_id(g, s, track, library))
                tasks.append(future)

        loop = asyncio.get_event_loop()
        done, _ = loop.run_until_complete(asyncio.wait(tasks))
        loop.close()
        track_id_results = [task.result() for task in done]
        track_ids = [track_id for (ok, track_id) in track_id_results if ok]
        not_found = [track_info for (ok, track_info) in track_id_results if not ok]
        for nf in not_found:
            print(nf)

        spotinfo = s.user_playlist(spotify_username, playlist_id=spotlist['id'])
        spottracks = [x['track']['id'] for x in spotinfo['tracks']['items']]
        new_ids = [x for x in track_ids if x not in spottracks]

        print("Adding {} new tracks!!!!!!".format(len(new_ids)))
        for group in chunker(new_ids, 100):
            s.user_playlist_add_tracks(spotify_username, spotlist['id'], group)

if __name__ == '__main__':
    main()
