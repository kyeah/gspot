Gspot
=======

Sync and share Google Music playlists with all of your new-age Spotify friends.

# Installation

`sudo pip install -r requirements.txt`

# Configuration

Use config.py to configure your accounts and sync settings. 

## Account Authorization

Gspot requires you to log into Google and provide a Spotify authorization token.

```python
auth = {
  "GOOGLE_EMAIL": "goofus@hotmail.com",
  "GOOGLE_PASSWORD": "totally_insecure_text_password",
  "SPOTIFY_EMAIL": "goofus@hotmail.com",
  "SPOTIFY_USERNAME: "1262877625",
}
```

Your Spotify username can be found in the URL of one of your playlists. For example,

`https://play.spotify.com/user/<username>/playlist/3TkXkxeATeck7XRbQdqX7W`

Instead of logging into Spotify, gspot will walk you through creating an access token.

If you are having difficulties with Google authorization, try allowing [less secure apps](https://www.google.com/settings/security/lesssecureapps).

## Selective Synchronization

By default, gspot will synchronize all of your Google Music playlists to Spotify. You can specify specific playlists to synchronize or exclude through the config.

```python
playlists = {
  "Chill",
  "Hella Chill",
  "Aww yeah",
}
```

```python
exclude = {
  "Not Chill",
  "Secret Stash",
}
```