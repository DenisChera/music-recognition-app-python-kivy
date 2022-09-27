# from libs.db_mongo import MongoDatabase
import csv
# !/usr/bin/python
import os.path
import shutil
import threading
from pathlib import Path
import urllib
from itertools import zip_longest as izip_longest
from fpdf import FPDF
import re
import numpy as np
import pygame
from kivy.animation import Animation
from kivy.app import App
from kivy.clock import Clock, mainthread
from kivy.core.audio import SoundLoader
from kivy.core.text import LabelBase
from kivy.core.window import Window
from kivy.lang import Builder
from kivy.loader import Loader
from kivy import platform
from kivy.properties import NumericProperty, ObjectProperty, StringProperty
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.image import AsyncImage, Image
from kivy.uix.screenmanager import Screen, ScreenManager, FadeTransition, SlideTransition
from kivy.uix.widget import Widget
from kivymd.app import MDApp
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.screen import MDScreen
from kivymd.uix.tab import MDTabsBase
from lyricsgenius import Genius
from lyricsgenius.api.public_methods import SearchMethods
from lyricsgenius.types import Song
from termcolor import colored
from kivymd_extensions import akivymd
from kivymd.uix.list import IRightBodyTouch

import libs.fingerprint as fingerprint
from libs.config import get_config
from libs.db_sqlite import SqliteDatabase, SQLITE_MAX_VARIABLE_NUMBER
from libs.reader_microphone import MicrophoneReader
from libs.visualiser_console import VisualiserConsole as visual_peak
from libs.visualiser_plot import VisualiserPlot as visual_plot
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from PDF import PDF

genius_access_token = 'uK8aNujohVZzI6BtyovEc7rPndKeRez3MmnqrcH12_qFk0ZFWhcAyCt7VCmk7VKs'
spotipy_client_id = "e761d2ce58134cb3bb5d25fdf508ae6c"
spotipy_client_secret = "8bde749e72c94bbd8e3e883aa1922074"
spotipy_redirect_uri = "https://google.com"

client_credentials_manager = SpotifyClientCredentials(client_id=spotipy_client_id,
                                                              client_secret=spotipy_client_secret)
sp = spotipy.Spotify(client_credentials_manager=client_credentials_manager)
playlist_link = 'https://open.spotify.com/playlist/0JiVp7Z0pYKI8diUV6HJyQ?si=6ce65092e7f84e54'
#playlist_link = "https://open.spotify.com/playlist/5ABHKGoOzxkaa28ttQV9sE?si=c817472e0794450e"
playlist_URI = playlist_link.split("/")[-1].split("?")[0]
track_uris = [x["track"]["uri"] for x in sp.playlist_tracks(playlist_URI)["items"]]
preview_urls = [x["track"]["preview_url"] for x in sp.playlist_tracks(playlist_URI)["items"]]

token = "uK8aNujohVZzI6BtyovEc7rPndKeRez3MmnqrcH12_qFk0ZFWhcAyCt7VCmk7VKs"
#f = open('D:\\kivy mobile app\\top50\\top100.csv')
#reader = csv.reader(f)
# dict_songs = {}
# for row in reader:
#     dict_songs[row[0]] = {'artist': row[1], 'year': row[3], 'beats_per_minute': row[4], 'energy': row[5],
#                           'danceability': row[6], 'popularity': row[13]}

mp_song = 'assets/24kGoldn - Mood (feat. iann dior).wav'

Window.size = (320, 600)
Builder.load_file('main.kv')
LabelBase.register(name="VastShadow", fn_regular="VastShadow-Regular.ttf")
LabelBase.register(name="Flavors", fn_regular="Flavors-Regular.ttf")
LabelBase.register(name="BadScript", fn_regular="BadScript-Regular.ttf")


class MyGenius(Genius):
    def search_song(self, title=None, artist="", song_id=None, get_full_info=True):
        msg = "You must pass either a `title` or a `song_id`."
        if title is None and song_id is None:
            assert any([title, song_id]), msg

        if self.verbose and title:
            if artist:
                print('Searching for "{s}" by {a}...'.format(s=title, a=artist))
            else:
                print('Searching for "{s}"...'.format(s=title))

        if song_id:
            result = self.song(song_id)['song']
        else:
            search_term = "{s} {a}".format(s=title, a=artist).strip()
            # search_response = self.search_all(search_term)

            search_response = SearchMethods.search(self, search_term=search_term, type_="song")
            result = self._get_item_from_search_response(search_response,
                                                         title,
                                                         type_="song",
                                                         result_type="title")

        # Exit search if there were no results returned from API
        # Otherwise, move forward with processing the search results
        if result is None:
            if self.verbose and title:
                print("No results found for: '{s}'".format(s=search_term))
            return None

        # Reject non-songs (Liner notes, track lists, etc.)
        # or songs with uncomplete lyrics (e.g. unreleased songs, instrumentals)
        if self.skip_non_songs and not self._result_is_lyrics(result):
            valid = False
        else:
            valid = True

        if not valid:
            if self.verbose:
                print('Specified song does not contain lyrics. Rejecting.')
            return None

        song_id = result['id']

        # Download full song info (an API call) unless told not to by user
        song_info = result
        if song_id is None and get_full_info is True:
            new_info = self.song(song_id)['song']
            song_info.update(new_info)

        if (song_info['lyrics_state'] == 'complete'
            and not song_info.get('instrumental')):
            lyrics = self.lyrics(song_url=song_info['url'])
        else:
            lyrics = ""

        # Skip results when URL is a 404 or lyrics are missing
        if self.skip_non_songs and not lyrics:
            if self.verbose:
                print('Specified song does not have a valid lyrics. '
                      'Rejecting.')
            return None

        # Return a Song object with lyrics if we've made it this far
        song = Song(self, song_info, lyrics)
        if self.verbose:
            print('Done.')
        return song


genius = MyGenius(token)
genius.remove_section_headers = True  # Remove section headers (e.g. [Chorus]) from lyrics when searching
# genius.excluded_terms = ["(Remix)", "(Live)",
#                          "Today’s Top Hits 9/11/20"]  # Exclude songs with these words in their title

class LoaderImage(AsyncImage):
    Loader.loading_image = 'images/loader.gif'


class Music():
    @staticmethod
    def align_matches(matches):
        db = SqliteDatabase()
        diff_counter = {}
        largest = 0
        largest_count = 0
        song_id = -1

        for tup in matches:
            sid, diff = tup

            if diff not in diff_counter:
                diff_counter[diff] = {}

            if sid not in diff_counter[diff]:
                diff_counter[diff][sid] = 0

            diff_counter[diff][sid] += 1

            if diff_counter[diff][sid] > largest_count:
                largest = diff
                largest_count = diff_counter[diff][sid]
                song_id = sid

        songM = db.get_song_by_id(song_id)

        nseconds = round(float(largest) / fingerprint.DEFAULT_FS *
                         fingerprint.DEFAULT_WINDOW_SIZE *
                         fingerprint.DEFAULT_OVERLAP_RATIO, 5)

        return {
            "SONG_ID": song_id,
            "SONG_NAME": songM[1],
            "CONFIDENCE": largest_count,
            "OFFSET": int(largest),
            "OFFSET_SECS": nseconds
        }

    @staticmethod
    def grouper(iterable, n, fillvalue=None):
        args = [iter(iterable)] * n
        return (filter(None, values)
                for values in izip_longest(fillvalue=fillvalue, *args))

    @staticmethod
    def find_matches(samples, Fs=fingerprint.DEFAULT_FS):
        hashes = fingerprint.fingerprint(samples, Fs=Fs)
        return Music.return_matches(hashes)

    @staticmethod
    def return_matches(hashes):
        mapper = {}
        db = SqliteDatabase()
        for hash, offset in hashes:
            mapper[hash.upper()] = offset
        values = mapper.keys()

        for split_values in map(list, Music.grouper(values, SQLITE_MAX_VARIABLE_NUMBER)):
            # @todo move to db related files
            query = """
        SELECT upper(hash), song_fk, offset
        FROM fingerprints
        WHERE upper(hash) IN (%s)
      """
            query = query % ', '.join('?' * len(split_values))

            x = db.executeAll(query, split_values)
            matches_found = len(x)

            if matches_found > 0:
                msg = '   ** found %d hash matches (step %d/%d)'
                print(colored(msg, 'green') % (
                    matches_found,
                    len(split_values),
                    len(values)
                ))
            else:
                msg = '   ** not matches found (step %d/%d)'
                print(colored(msg, 'red') % (len(split_values), len(values)))

            for hash_code, sid, offset in x:
                # (sid, db_offset - song_sampled_offset)
                if isinstance(offset, bytes):
                    # offset come from fingerprint.py and numpy extraction/processing
                    offset = np.frombuffer(offset, dtype=np.int)[0]
                yield sid, offset - mapper[hash_code]


class Sounds(MDScreen):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.thread = None

    def test(self):
        self.thread = threading.Thread(target=self.main).start()

    @mainthread
    def test2(self):
        self.ids.img.source = 'images/processing-sounds.gif'
        self.ids.img.anim_delay = 0.05
        self.ids.my_label.text = ""

    def main(self):
        app = App.get_running_app()
        nav_drawer = app.root.nav_drawer

        mp_btn = nav_drawer.mp_btn
        details_btn = nav_drawer.details_btn

        print(self.ids)

        self.test2()
        if self.ids.my_md.icon == 'microphone-off':
            self.ids.my_md.icon = 'microphone'

            msg = ' * started recording..'
            print(msg)
            config = get_config()

            seconds = 5

            chunksize = 2 ** 12  # 4096
            channels = 2  # 1=mono, 2=stereo

            record_forever = False
            visualise_console = bool(config['mic.visualise_console'])
            visualise_plot = bool(config['mic.visualise_plot'])

            reader = MicrophoneReader(None)

            reader.start_recording(seconds=seconds,
                                   chunksize=chunksize,
                                   channels=channels)

            msg = ' * started recording..'
            print(colored(msg, attrs=['dark']))

            while True:
                bufferSize = int(reader.rate / reader.chunksize * seconds)

                for i in range(0, bufferSize):
                    nums = reader.process_recording()

                    if visualise_console:
                        msg = colored('   %05d', attrs=['dark']) + colored(' %s', 'green')
                        print(msg % visual_peak.calc(nums))
                    else:
                        msg = '   processing %d of %d..' % (i, bufferSize)
                        print(colored(msg, attrs=['dark']))

                if not record_forever:
                    break

            if visualise_plot:
                data = reader.get_recorded_data()[0]
                visual_plot.show(data)

            reader.stop_recording()

            msg = ' * recording has been stopped'
            print(colored(msg, attrs=['dark']))

            data = reader.get_recorded_data()

            msg = ' * recorded %d samples'
            print(colored(msg, attrs=['dark']) % len(data[0]))

            # reader.save_recorded('test.wav')

            Fs = fingerprint.DEFAULT_FS
            channel_amount = len(data)

            result = set()
            matches = []
            m = Music()
            for channeln, channel in enumerate(data):
                # TODO: Remove prints or change them into optional logging.
                msg = '   fingerprinting channel %d/%d'
                print(colored(msg, attrs=['dark']) % (channeln + 1, channel_amount))

                matches.extend(m.find_matches(channel))

                msg = '   finished channel %d/%d, got %d hashes'
                print(colored(msg, attrs=['dark']) % (channeln + 1,
                                                      channel_amount, len(matches)))

            total_matches_found = len(matches)

            print('')
            # print(total_matches_found)
            music = Music()

            if total_matches_found > 0:
                msg = ' ** totally found %d hash matches'
                print(colored(msg, 'green') % total_matches_found)

                song = music.align_matches(matches)

                if song['CONFIDENCE'] >= 20:

                    msg = ' => song: %s (id=%d)\n'
                    msg += '    offset: %d (%d secs)\n'
                    msg += '    confidence: %d'

                    print(colored(msg, 'green') % (song['SONG_NAME'], song['SONG_ID'],
                                                   song['OFFSET'], song['OFFSET_SECS'],
                                                   song['CONFIDENCE']))

                    x = song['SONG_NAME'].split(' - ')
                    #print("ARTIST " + x[0])
                    #print(x)
                    if (len(x) == 3):
                        y = x[2].split('.wav')
                        sn = x[1] + ' - ' + y[0]
                    else:
                        y = x[1].split('.wav')
                        sn = y[0]
                    print(sn)
                    #print(dict_songs[sn]['artist'])

                    i=0
                    lyrics_found = 1
                    nr_track = 0

                    self.manager.get_screen('second-screen').progr.value = 0


                    for track in sp.playlist_tracks(playlist_URI)["items"]:
                        # URI
                        track_uri = track["track"]["uri"]
                        # print(track_uri)
                        # Track name
                        track_name = track["track"]["name"]
                        print(track_name)
                        #print(sn)
                        artist_name = track["track"]["artists"][0]["name"]
                        print(artist_name)
                        nr_track = nr_track + 1
                        if track_name == sn and artist_name == x[0]:
                            song_target = preview_urls[i]
                            if song_target == None:
                                self.manager.get_screen('third-screen').ringtone_btn.disabled = True
                            else:
                                self.manager.get_screen('third-screen').ringtone_btn.disabled = False

                            # print(track_name)
                            # Main Artist
                            artist_uri = track["track"]["artists"][0]["uri"]
                            artist_info = sp.artist(artist_uri)
                            # print(artist_info['id'])
                            artist_uri = artist_info['uri']
                            results = sp.artist_top_tracks(artist_uri)
                            albums_results = sp.artist_albums(artist_uri, album_type=None, country=None, limit=20, offset=0)
                            dict_album = {}
                            for i in range(0, len(albums_results['items'])):
                                dict_album[albums_results['items'][i]['name']] = []
                                dict_album[albums_results['items'][i]['name']].append(albums_results['items'][i]['release_date'])
                                dict_album[albums_results['items'][i]['name']].append(albums_results['items'][i]['album_type'])
                                dict_album[albums_results['items'][i]['name']].append(albums_results['items'][i]['images'][0]['url'])

                            v = []
                            for keys in dict_album.keys():
                                #print(keys)
                                v.append(keys)

                            nr=0
                            cov = ''
                            for top_track in results['tracks'][:5]:
                                nr = nr+1
                                print('track    : ' + top_track['name'])
                                #print('audio    : ' + top_track['preview_url'])
                                print('cover art: ' + top_track['album']['images'][0]['url'])
                                if top_track['name'] == sn:
                                    cov = top_track['album']['images'][0]['url']
                                print()
                                if nr == 1:
                                    print(self.manager.get_screen('fourth-screen').song1.text)
                                    self.manager.get_screen('fourth-screen').song1.secondary_text = top_track['name']
                                    self.manager.get_screen('fourth-screen').icon1.source = top_track['album']['images'][0]['url']
                                    print(self.manager.get_screen('fourth-screen').icon1.source)
                                elif nr == 2:
                                    self.manager.get_screen('fourth-screen').song2.secondary_text = top_track['name']
                                    self.manager.get_screen('fourth-screen').icon2.source = top_track['album']['images'][0]['url']
                                elif nr == 3:
                                    self.manager.get_screen('fourth-screen').song3.secondary_text = top_track['name']
                                    self.manager.get_screen('fourth-screen').icon3.source = top_track['album']['images'][0]['url']
                                elif nr == 4:
                                    self.manager.get_screen('fourth-screen').song4.secondary_text = top_track['name']
                                    self.manager.get_screen('fourth-screen').icon4.source = top_track['album']['images'][0]['url']
                                elif nr == 5:
                                    self.manager.get_screen('fourth-screen').song5.secondary_text = top_track['name']
                                    self.manager.get_screen('fourth-screen').icon5.source = top_track['album']['images'][0]['url']


                                # Name, popularity, genre
                            artist_name = track["track"]["artists"][0]["name"]
                            artist_pop = artist_info["popularity"]
                            artist_genres = artist_info["genres"]
                            track_release_date = track["track"]["album"]["release_date"]
                            #print(artist_name)
                            # print(artist_genres)
                            # Album
                            album = track["track"]["album"]["name"]
                            # print(album)

                            # Popularity of the track
                            track_pop = track["track"]["popularity"]

                            # print(sp.audio_features(track_uri)[0])
                            #print(sp.artist_top_tracks(artist_info['id'], 'RO'))
                            danceability = sp.audio_features(track_uri)[0]['danceability']
                            energy = sp.audio_features(track_uri)[0]['energy']
                            #popularity = sp.audio_features(track_uri)[0]['popularity']
                            if len(artist_genres) == 0:
                                self.manager.get_screen('fourth-screen').artist_musical_genres.text = "No details available!"
                                self.manager.get_screen('fourth-screen').dim.height = "40dp"
                            elif len(artist_genres) == 1  or len(artist_genres) == 2:
                                self.manager.get_screen('fourth-screen').dim.height = "60dp"
                            elif len(artist_genres) == 3 or len(artist_genres) == 4:
                                self.manager.get_screen('fourth-screen').dim.height = "80dp"
                            elif len(artist_genres) == 5 or len(artist_genres) == 6:
                                self.manager.get_screen('fourth-screen').dim.height = "100dp"
                            elif len(artist_genres) == 7 or len(artist_genres) == 8:
                                self.manager.get_screen('fourth-screen').dim.height = "150dp"
                            if len(artist_genres) != 0:
                                self.manager.get_screen('fourth-screen').artist_musical_genres.text = artist_genres[0]
                                for i in range(1,len(artist_genres)):
                                    self.manager.get_screen('fourth-screen').artist_musical_genres.text = self.manager.get_screen('fourth-screen').artist_musical_genres.text + "\n" + artist_genres[i]

                            song = genius.search_song(track_name, artist_name, get_full_info=False)
                            print(song.lyrics)
                            if not song:
                                lyrics = "No lyrics found!"
                                lyrics_found = 0
                            else:

                                lyrics = song.lyrics
                                #print(lyrics)
                                with open('lyrics.txt', 'w', encoding='utf-8') as f:
                                    f.write(lyrics)
                                    f.close()
                                string = open('lyrics.txt').read()
                                print(string)
                                new_str = re.sub("""[^a-zA-Z0-9\n\.(),'-]""", ' ', string)
                                print()
                                #print(new_str)
                                open('lyrics2.txt', 'w', encoding='utf-8').write(new_str)
                                with open('lyrics2.txt', 'r') as f:
                                    lines = f.readlines()

                                # remove spaces
                                #lines = [line.replace(' ', '') for line in lines]
                                list_of_words = []
                                for i in range(0, len(lines)):
                                    x = lines[i].split()
                                    list_of_words.append(x)
                                    #print(list_of_words)
                                print(list_of_words)
                                #sentence = ' '.join(word[0] for word in list_of_words)
                                sentence = ''
                                for word in list_of_words:
                                    if word!=[]:
                                        for x in word:
                                            #print(x)
                                            sentence = sentence + x + ' '
                                        sentence = sentence + '\n'
                                        #print(sentence)
                                    else:
                                        sentence = sentence + '\n'
                                print(sentence)
                                open('lyrics.txt', 'w', encoding='utf-8').write(sentence)


                                #print(lines)
                                #print(" ".join(lines[2].split()))

                                # finally, write lines in the file
                                # with open('file.txt', 'w', encoding='utf-8') as f:
                                #     f.writelines(lines)

                            break
                        i = i + 1

                    #print(song.song_art_image_url)
                    #print(song.song_art_image_url)

                    # print(sn)
                    # print(dict_songs[sn])




                    if lyrics_found == 0:
                        self.manager.get_screen('third-screen').pdf_btn.disabled = True
                    else:
                        self.manager.get_screen('third-screen').pdf_btn.disabled = False

                    reset_song = SongCover()
                    reset_song.is_playing = False
                    reset_song.playing_state = False

                    listOfGlobals = globals()
                    listOfGlobals['mp_song'] = "assets/" + artist_name + " - " + track_name + ".wav"


                    # pygame.init()
                    # pygame.mixer.init()
                    # pygame.mixer.music.stop()
                    # pygame.mixer.music.load(
                    #     'D:\\kivy mobile app\\wav\\' + artist_name + ' - ' + track_name + '.wav')



                    self.manager.get_screen('second-screen').song_name.text = track_name
                    self.manager.get_screen('second-screen').artist_name.text = artist_name
                    if lyrics_found == 1:
                        self.manager.get_screen('second-screen').cov_img.source = song.song_art_image_url
                        self.manager.get_screen('second-screen').rot_img.source = song.header_image_thumbnail_url
                    else:
                        self.manager.get_screen('second-screen').cov_img.source = 'images/bg-mp.jpg'
                        self.manager.get_screen('second-screen').rot_img.source = cov
                    #self.manager.get_screen('third-screen').det_img.source = song.song_art_image_url
                    self.manager.get_screen('third-screen').year.subtext = track_release_date
                    self.manager.get_screen('third-screen').album.subtext = album
                    self.manager.get_screen('third-screen').energy.subtext = str(energy)
                    self.manager.get_screen('third-screen').danceability.subtext = str(danceability)
                    #self.manager.get_screen('third-screen').popularity.subtext = popularity
                    self.manager.get_screen('third-screen').song.text = artist_name + " - " + track_name
                    self.manager.get_screen('third-screen').my_lyrics.text = lyrics
                    self.manager.get_screen('third-screen').popularity.subtext = '#' + str(nr_track)
                    #self.manager.get_screen('third-screen').song_miniplayer.text = '[b]' + dict_songs[sn]['artist'] + '[/b]' + '\n' + sn
                    self.manager.get_screen('fourth-screen').artist_profile_img.source = artist_info["images"][0]["url"]
                    self.manager.get_screen('fourth-screen').singer_name.text = artist_name

                    self.manager.get_screen('fourth-screen').album1.text = v[0]
                    self.manager.get_screen('fourth-screen').album1.secondary_text = dict_album[v[0]][1]
                    self.manager.get_screen('fourth-screen').album1.tertiary_text = dict_album[v[0]][0]
                    self.manager.get_screen('fourth-screen').icon_album1.source = dict_album[v[0]][2]

                    self.manager.get_screen('fourth-screen').album2.text = v[1]
                    self.manager.get_screen('fourth-screen').album2.secondary_text = dict_album[v[1]][1]
                    self.manager.get_screen('fourth-screen').album2.tertiary_text = dict_album[v[1]][0]
                    self.manager.get_screen('fourth-screen').icon_album2.source = dict_album[v[1]][2]

                    self.manager.get_screen('fourth-screen').album3.text = v[2]
                    self.manager.get_screen('fourth-screen').album3.secondary_text = dict_album[v[2]][1]
                    self.manager.get_screen('fourth-screen').album3.tertiary_text = dict_album[v[2]][0]
                    self.manager.get_screen('fourth-screen').icon_album3.source = dict_album[v[2]][2]

                    self.manager.get_screen('fourth-screen').album4.text = v[3]
                    self.manager.get_screen('fourth-screen').album4.secondary_text = dict_album[v[3]][1]
                    self.manager.get_screen('fourth-screen').album4.tertiary_text = dict_album[v[3]][0]
                    self.manager.get_screen('fourth-screen').icon_album4.source = dict_album[v[3]][2]

                    self.manager.get_screen('fourth-screen').album5.text = v[4]
                    self.manager.get_screen('fourth-screen').album5.secondary_text = dict_album[v[4]][1]
                    self.manager.get_screen('fourth-screen').album5.tertiary_text = dict_album[v[4]][0]
                    self.manager.get_screen('fourth-screen').icon_album5.source = dict_album[v[4]][2]

                    self.manager.get_screen('fourth-screen').followers.text = str(artist_info['followers']['total']) + " followers"


                    #print(self.manager.get_screen('fourth-screen').song1.text)
                    #print(self.manager.get_screen('fourth-screen').song2.text)
                    #print(self.manager.get_screen('fourth-screen').artist_profile_img.source)
                    #print(self.manager.get_screen('fourth-screen').icon1.source)
                    music = SoundLoader.load(
                        'assets/' + artist_name + ' - ' + track_name + '.wav')
                    print(music.length / 60)
                    dur1 = music.length / 60
                    dur2 = (dur1 - int(dur1)) * 100
                    dur1 = int(dur1)
                    dur2 = int(dur2)

                    if(dur2 > 60):
                        dur3  = dur2 - 60
                        dur1 = dur1 + 1
                        dur2 = dur3
                    #print("min " + str(minutes) + " seconds " + str(seconds))
                    self.manager.get_screen('third-screen').duration.subtext = str(dur1) + " min. " + str(
                        dur2) + " sec."
                    self.ids.my_md.icon = 'microphone-off'
                    self.ids.my_label.text = artist_name + '-' + track_name
                    mp_btn.disabled = False
                    details_btn.disabled = False
                    self.ids.img.source = ''
                    #self.ids.img.anim_delay = 0.7
                    self.manager.current = 'second-screen'

                else:
                    msg = ' ** not matches found at all, confidence is: %d'
                    print(colored(msg, 'red') % song['CONFIDENCE'])
                    self.ids.my_label.text = 'Song not found!\n Please try again.'
                    self.ids.my_md.icon = 'microphone-off'
                    mp_btn.disabled = True
                    details_btn.disabled = True
                    self.ids.img.source = ''
                    #self.ids.img.anim_delay = 0.7
            else:
                self.ids.my_label.text = 'Song not found!\n Please try again.'
                self.ids.img.source = ''
                #self.ids.img.anim_delay = 0.7
                mp_btn.disabled = True
                details_btn.disabled = True

            self.ids.my_md.icon = 'microphone-off'
            #self.ids.my_label.text = "Tap the button for listening ..."
            #self.ids.img.source = 'D:\\kivy mobile app\\images\\transparent.png'
            #self.ids.img.source = 'D:\\kivy mobile app\\images\\transparent.png'
            #self.ids.img.anim_delay = 0.7
            #if self.thread:



    def printreleased(self):
        print("released")

    def open_nav_drawer(self, app):
        main_screen = app.root
        print(main_screen)
        nav_drawer = main_screen.nav_drawer
        nav_drawer.set_state('toggle')


class MusicScreen(Screen):
    pass

class WelcomeScreen(MDScreen):
    def __init__(self, **kw):
        super().__init__(**kw)
        Clock.schedule_once(self.update_progress)

    def update_progress(self, dt):
        self.ids.progress_bar.start()


class DetailsScreen(MDBoxLayout):
    if platform == 'win':
        output_path = f'{str(Path.home() / "Downloads")}'
    elif platform == 'android':
        from android.storage import primary_external_storage_path
        output_path = f'{str(primary_external_storage_path())}/'
    def download_pdf(self):
        if self.pdf_btn.disabled == False:
            # title = self.song.text + ' (Lyrics)'
            # pdf_target = "https://drive.google.com/file/d/1SX2Pp9KH1XyGA6GeWo1RGeFDVfTRlhEv/view?usp=sharing"
            # req = urllib.request.urlopen(pdf_target)
            # file = open(self.output_path + 'Lyrics/' + title + ".pdf", "wb")
            # file.write(req.read())
            # file.close()
            pdf = PDF('P', 'mm', 'Letter')

            # get total page numbers
            pdf.alias_nb_pages(alias='nb')

            # Set auto page break
            pdf.set_auto_page_break(auto=True, margin=15)

            # Add Page
            title = self.song.text + ' (Lyrics)'

            pdf.song_title = title
            pdf.add_page()

            # pdf.print_chapter('Lyrics', 'lyrics.txt')

            pdf.chapter_body('lyrics.txt')

            pdf.output(title + '.pdf')

            source = title + '.pdf'

            try:
                shutil.move(source, self.output_path+'\\Lyrics\\' +title + '.pdf')
                print(source+ " was moved")
            except FileNotFoundError:
                print(source+ " was not found")
            # file.write(txt)
            # file.close()

    def download_mp3(self):
        if self.ringtone_btn.disabled == False:
            i=0
            for track in sp.playlist_tracks(playlist_URI)["items"]:
                # URI
                track_name = track["track"]["name"]
                # print(track_name)
                if track_name == self.screen_mng.get_screen('second-screen').song_name.text:
                    song_target = preview_urls[i]
                    print(preview_urls[i])
                    if song_target != None:
                        songs_name = self.screen_mng.get_screen('second-screen').artist_name.text + " - " + self.screen_mng.get_screen('second-screen').song_name.text + " (ringtone)"
                        urllib.request.urlretrieve(song_target, "{}\\{}{}".format(self.output_path + "\\Ringtone", str(songs_name), ".mp3"))

                i = i + 1

    # def download_wav(self):
    #     directory = "D:\\kivy mobile app\\wav_ringtones"
    #     i = 0
    #     for track in sp.playlist_tracks(playlist_URI)["items"]:
    #         # URI
    #         track_name = track["track"]["name"]
    #         # print(track_name)
    #         if track_name == self.screen_mng.get_screen('second-screen').song_name.text:
    #             song_target = preview_urls[i]
    #             if song_target != None:
    #                 songs_name = self.screen_mng.get_screen(
    #                     'second-screen').artist_name.text + " - " + self.screen_mng.get_screen('second-screen').song_name.text + " (ringtone)"
    #                 urllib.request.urlretrieve(song_target, "{}\\{}{}".format(directory, str(songs_name), ".wav"))
    #             else:
    #                 print("The ringtone was not found!")
    #
    #         i = i + 1



        #print(self.screen_mng.get_screen('second-screen').song_name.text)
#     music = SoundLoader.load('D:\\kivy mobile app\\wav\\Imagine Dragons - Believer.wav')
#     progress = Animation(value=music.length, d=music.length, t='linear')
#     #pygame.init()
#     #pygame.mixer.init()
#     playing_state = False
#     is_playing = False
#     def play_music_from_details_screen(self, widget):
#         self.widget = widget
#         self.progress.start(widget)
#         txt = self.song_miniplayer.text
#         x = txt.split("\n")
#         sn = x[1]
#         a1 = x[0].split("[b]")
#         an = a1[1].split("[/b]")
#         if self.play_details.icon == 'play-outline' and self.is_playing == False:
#             music = SoundLoader.load(
#                 'D:\\kivy mobile app\\wav\\' + an[0] + ' - ' + sn + '.wav')
#             pygame.mixer.music.load(
#                 'D:\\kivy mobile app\\wav\\' + an[0] + ' - ' + sn + '.wav')
#             self.progress = Animation(value=music.length, d=music.length, t='linear')
#             pygame.mixer.music.play()
#             self.is_playing = True
#             self.play_details.icon = 'pause'
#             self.progress_details.max = self.screen_mng.get_screen('second-screen').progr.max
#             self.progress_details.min = self.screen_mng.get_screen('second-screen').progr.min
#             #self.screen_mng.get_screen('second-screen').progress = self.progress
#             self.screen_mng.get_screen('second-screen').play_pause.icon = self.play_details.icon
#             #print(self.screen_mng.get_screen('second-screen').play_pause.icon)
#
#             self.progress.start(widget)
#             #self.anim.start(self)
#
#             # self.rotate()
#         elif self.play_details.icon == 'pause' and not self.playing_state:
#             pygame.mixer.music.pause()
#             self.play_details.icon = 'play-outline'
#             #self.screen_mng.get_screen('second-screen').progress = self.progress
#             self.screen_mng.get_screen('second-screen').play_pause.icon = self.play_details.icon
#             self.playing_state = True
#             self.progress.stop(widget)
#             #self.anim.stop(self)
#         else:
#             pygame.mixer.music.unpause()
#             self.play_details.icon = 'pause'
#             #self.screen_mng.get_screen('second-screen').progress = self.progress
#             self.screen_mng.get_screen('second-screen').play_pause.icon = self.play_details.icon
#             self.playing_state = False
#             self.progress.start(widget)
#             #self.anim.start(self)
#             # self.rotate()

class SongDetailsScreen(Screen):
    def on_tab_switch(self, instance_tabs, instance_tab, instance_tab_label, tab_text):
        instance_tab.ids.label.text = tab_text


class ArtistDetailsScreen(MDScreen):
    def change_screen(self):
        self.manager.current = 'third-screen'


class RoundedImage(Widget):
    texture = ObjectProperty(None)
    source = StringProperty('')

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        Clock.schedule_once(self.create_texture, 1)

    def create_texture(self, *args):
        image = Image(source=self.source, allow_stretch=True, keep_ratio=False,
            size_hint=(None, None), size=self.size)
        self.texture = image.texture

class SongCover(MDBoxLayout):
    music = SoundLoader.load(mp_song)
    print(music.length)
    angle = NumericProperty()
    anim = Animation(angle=-360, d=3, t='linear')
    anim += Animation(angle=0, d=0, t='linear')
    progress = Animation(value=music.length, d=music.length, t='linear')
    anim.repeat = True
    pygame.init()
    pygame.mixer.init()
    playing_state = False
    is_playing = False

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        pygame.mixer.music.stop()
        pygame.mixer.music.load(mp_song)
        #Clock.schedule_once(self.stop_music, 0)

    def rotate(self):
        # print(self.song_name.text)
        # print(ScreenManager().get_screen('second-screen').song_name.text)
        if self.anim.have_properties_to_animate(self):
            self.anim.stop(self.widget)
            # self.progress.stop(self.widget)
        else:
            self.anim.start(self)
            # self.progress.start(self.widget)

    def play_music(self, widget):
        self.widget = widget
        self.progress.start(widget)
        self.img.source = 'images/giphy.gif'

        if self.progr.value < self.progr.max:
            if self.is_playing == False:
                music = SoundLoader.load(
                    mp_song)
                pygame.mixer.music.load(
                    mp_song)
                #print("Se reda melodia")
                #self.progress = Animation(value=music.length, d=music.length, t='linear')
                pygame.mixer.music.play()
                self.is_playing = True
                self.play_pause.icon = 'pause'
                self.progr.max = music.length
                self.progr.min = 0
                self.progress.start(widget)
                self.anim.start(self)
                # self.rotate()
            elif self.is_playing == True and not self.playing_state:
                pygame.mixer.music.pause()
                self.play_pause.icon = 'play-outline'
                self.playing_state = True

                self.progress.stop(widget)
                self.img.source = 'transparent.png'
                self.anim.stop(self)
            else:
                pygame.mixer.music.unpause()
                self.play_pause.icon = 'pause'
                self.playing_state = False
                self.progress.start(widget)
                self.anim.start(self)
                # self.rotate()

        else:
            self.widget = widget
            self.progress.stop(self.widget)
            pygame.mixer.music.stop()
            self.play_pause.icon = 'play-outline'
            self.is_playing = False
            self.progr.value = 0
            self.img.source = 'transparent.png'
            self.anim.stop(self)

    def stop_music(self, widget):
        self.widget = widget
        self.progress.stop(self.widget)
        pygame.mixer.music.stop()
        self.play_pause.icon = 'play-outline'
        self.is_playing = False
        self.progr.value = 0
        self.img.source = 'transparent.png'
        self.anim.stop(self)
        # self.rotate()

    def my_update_func(self):
        print("clock")


    def pause2(self):
        if not self.playing_state:
            pygame.mixer.music.pause()
            self.playing_state = True
        else:
            pygame.mixer.music.unpause()
            self.playing_state = False


class Tab(FloatLayout, MDTabsBase):
    pass

class ContentNavigationDrawer(MDScreen):
    pass

class MainScreen(MDScreen):
    pass

    def navigate_to(self, screen_name):
        self.screen_manager.current = screen_name
        self.nav_drawer.set_state("close")


class MainApp(MDApp):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.main_screen = MainScreen()
        self.sm = self.main_screen.screen_manager

    def build(self):
        self.theme_cls.primary_palette = 'Blue'
        self.theme_cls.theme_style = 'Light'
        if platform == 'android':
            from android.permissions import request_permissions, Permission
            request_permissions([Permission.READ_EXTERNAL_STORAGE, Permission.WRITE_EXTERNAL_STORAGE])

        return self.main_screen

    def on_start(self):
        Clock.schedule_once(self.change_screen, 10)  # Delay for 10 seconds

    def change_screen(self, dt):
        self.sm.current = "first-screen"



MainApp().run()
