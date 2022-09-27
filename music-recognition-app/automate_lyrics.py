import os
import json
import time
import urllib
import sys
import warnings

import requests
from fpdf import FPDF

import spotipy
from spotipy import Spotify
from spotipy.oauth2 import SpotifyClientCredentials
from urllib.request import urlretrieve
from pydub import AudioSegment

# Src = "D:\\kivy mobile app\\mp3\\The Weeknd - Blinding Lights.mp3"
# dst = "D:\\kivy mobile app\\wav\\The Weeknd - Blinding Lights.wav"
#
# sound = AudioSegment.from_file(Src)
# sound.export(dst, format="wav")

from urllib3.util import url

genius_access_token = 'uK8aNujohVZzI6BtyovEc7rPndKeRez3MmnqrcH12_qFk0ZFWhcAyCt7VCmk7VKs'
spotipy_client_id = "e761d2ce58134cb3bb5d25fdf508ae6c"
spotipy_client_secret = "8bde749e72c94bbd8e3e883aa1922074"
spotipy_redirect_uri = "https://google.com"

#
# scope = 'user-read-private'
# oauth_object = spotipy.SpotifyOAuth(client_id=spotipy_client_id,client_secret=spotipy_client_secret,redirect_uri=spotipy_redirect_uri,scope=scope)
# #print(oauth_object)
#
# token_dict = oauth_object.get_access_token()
# token = token_dict['access_token']
# print(token_dict)
#
# spotify_object = spotipy.Spotify(auth=token)
#
# genius_object = lg.Genius(genius_access_token)
#
# print(spotify_object)


#Authentication - without user

client_credentials_manager = SpotifyClientCredentials(client_id=spotipy_client_id, client_secret=spotipy_client_secret)
sp = spotipy.Spotify(client_credentials_manager = client_credentials_manager)

playlist_link = "https://open.spotify.com/playlist/0JiVp7Z0pYKI8diUV6HJyQ?si=6ce65092e7f84e54"
artist_uri = "spotify:artist:6fWVd57NKTalqvmjRd2t8Z"
results = sp.artist_albums(artist_uri, album_type=None, country=None, limit=20, offset=0)
print(results['items'][6]['images'][0]['url'])
print(results['items'][19]['name'] + " " + results['items'][19]['release_date'])
dict_album={}
print(len(results['items']))

for i in range(0, len(results['items'])):
    dict_album[results['items'][i]['name']] = []
    dict_album[results['items'][i]['name']].append(results['items'][i]['release_date'])
    dict_album[results['items'][i]['name']].append(results['items'][i]['album_type'])
    dict_album[results['items'][i]['name']].append(results['items'][i]['images'][0]['url'])
    #dict_album[results['items'][i]['name']].append(results['items'][i]['image'])
print(dict_album.keys())
v=[]
for keys in dict_album.keys():
    print(keys)
    v.append(keys)

print(dict_album[v[0]][0])


# for track in results['tracks'][:5]:
#     print('track    : ' + track['name'])
#     print('audio    : ' + track['preview_url'])
#     print('cover art: ' + track['album']['images'][0]['url'])
#     print()

print()
print()



playlist_URI = playlist_link.split("/")[-1].split("?")[0]
print(playlist_URI)
res = len(sp.playlist_tracks(playlist_URI)["items"])
print("res=", res)
track_uris = [x["track"]["uri"] for x in sp.playlist_tracks(playlist_URI)["items"]]
preview_urls = [x["track"]["preview_url"] for x in sp.playlist_tracks(playlist_URI)["items"]]
print(len(preview_urls))
print(preview_urls)
print(len(track_uris))
i=0
for track in sp.playlist_tracks(playlist_URI)["items"]:
    # URI
    track_uri = track["track"]["uri"]
    #print(track_uri)
    # Track name
    track_name = track["track"]["name"]
    print(track_name)
    #print(i)
    #print(preview_urls[i])
    #track_name = track["track"]
    #print(track_name)
    # Main Artist
    artist_uri = track["track"]["artists"][0]["uri"]
    #print(artist_uri)
    artist_info = sp.artist(artist_uri)
    #print(artist_info['followers']['total'])
    #print(artist_info["images"][0]["url"])

    # Name, popularity, genre
    artist_name = track["track"]["artists"][0]["name"]
    print(artist_name)
    artist_pop = artist_info["popularity"]
    artist_genres = artist_info["genres"]
    #print(artist_name)
    #print(artist_genres)
    # Album
    album = track["track"]["album"]["name"]
    #print(album)

    # Popularity of the track
    track_pop = track["track"]["popularity"]

    #print(sp.audio_features(track_uri)[0])
    #print(sp.audio_features(track_uri)[0]['danceability'])
    #print(sp.artist_top_tracks(artist_info['id'], 'RO'))


    directory = "D:\\kivy mobile app\\ringtones"
#print(preview_urls)


    a = 'track{}'.format(i+1)
    #print(a)
    song_target = preview_urls[i]
    # if song_target != None:
    #     songs_name = artist_name + " - " + track_name
    #     urllib.request.urlretrieve(song_target, "{}\\{}{}".format(directory, str(songs_name), ".wav"))

    i = i+1


url = "https://pdfhost.io/v/5nOyxwZfM_output"
response = requests.get(url)
if response.status_code == 200:
    file_path = os.path.join("C:\\Users\\Denis\\Downloads\\Lyrics", 'test.pdf')
    with open(file_path, 'wb') as f:
        f.write(response.content)

# with open('lyrics.txt', 'w') as f:
#     f.write('saaaaa')


#Ed%20Sheeran%20-%20Perfect
#Ed%20Sheeran%20-%20Perfect%20Duet%20(with%20Beyoncé)
