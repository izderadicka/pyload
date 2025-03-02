# -*- coding: utf-8 -*-

from ..internal.Crypter import Crypter
from ..internal.misc import json


class YoutubeComFolder(Crypter):
    __name__ = "YoutubeComFolder"
    __type__ = "crypter"
    __version__ = "1.12"
    __status__ = "testing"

    __pattern__ = r'https?://(?:www\.|m\.)?youtube\.com/(?P<TYPE>user|playlist|view_play_list)(/|.*?[?&](?:list|p)=)(?P<ID>[\w\-]+)'
    __config__ = [("activated", "bool", "Activated", True),
                  ("use_premium", "bool", "Use premium account if available", True),
                  ("folder_per_package", "Default;Yes;No", "Create folder for each package", "Default"),
                  ("likes", "bool", "Grab user (channel) liked videos", False),
                  ("favorites", "bool", "Grab user (channel) favorite videos", False),
                  ("uploads", "bool", "Grab channel unplaylisted videos", True)]

    __description__ = """Youtube.com channel & playlist decrypter plugin"""
    __license__ = "GPLv3"
    __authors__ = [("Walter Purcaro", "vuolter@gmail.com"),
                   ("GammaC0de", "nitzo2001[AT]yahoo[DOT]com")]

    API_KEY = "AIzaSyB68u-qFPP9oBJpo1DWAPFE_VD2Sfy9hpk"

    def api_response(self, method, **kwargs):
        kwargs['key'] = self.API_KEY
        json_data = self.load("https://www.googleapis.com/youtube/v3/" + method, get=kwargs)
        return json.loads(json_data)

    def get_channel(self, user):
        channels = self.api_response("channels",
                                     part="id,snippet,contentDetails",
                                     forUsername=user,
                                     maxResults=50)
        if channels['items']:
            channel = channels['items'][0]
            return {'id': channel['id'],
                    'title': channel['snippet']['title'],
                    'relatedPlaylists': channel['contentDetails']['relatedPlaylists'],
                    'user': user}  #: One lone channel for user?

    def get_playlist(self, playlist_id):
        playlists = self.api_response("playlists",
                                      part="snippet",
                                      id=playlist_id)
        if playlists['items']:
            playlist = playlists['items'][0]
            return {'id': playlist_id,
                    'title': playlist['snippet']['title'],
                    'channelId': playlist['snippet']['channelId'],
                    'channelTitle': playlist['snippet']['channelTitle']}

    def _get_playlists(self, playlist_id, token=None):
        if token:
            playlists = self.api_response("playlists",
                                          part="id",
                                          maxResults=50,
                                          channelId=playlist_id,
                                          pageToken=token)
        else:
            playlists = self.api_response("playlists",
                                          part="id",
                                          maxResults=50,
                                          channelId=playlist_id)

        for playlist in playlists['items']:
            yield playlist['id']

        if "nextPageToken" in playlists:
            for item in self._get_playlists(playlist_id, playlists['nextPageToken']):
                yield item

    def get_playlists(self, ch_id):
        return map(self.get_playlist, self._get_playlists(ch_id))

    def _get_videos_id(self, playlist_id, token=None):
        if token:
            playlist = self.api_response("playlistItems",
                                         part="contentDetails",
                                         maxResults=50,
                                         playlistId=playlist_id,
                                         pageToken=token)
        else:
            playlist = self.api_response("playlistItems",
                                          part="contentDetails",
                                          maxResults=50,
                                          playlistId=playlist_id)

        for item in playlist['items']:
            yield item['contentDetails']['videoId']

        if "nextPageToken" in playlist:
            for item in self._get_videos_id(playlist_id, playlist['nextPageToken']):
                yield item

    def get_videos_id(self, p_id):
        return list(self._get_videos_id(p_id))

    def decrypt(self, pyfile):
        if self.info['pattern']['TYPE'] == "user":
            self.log_debug("Url recognized as Channel")
            channel = self.get_channel(self.info['pattern']['ID'])

            if channel:
                playlists = self.get_playlists(channel['id'])
                self.log_debug('%s playlists found on channel "%s"' % (len(playlists), channel['title']))

                relatedplaylist = dict((p_name, self.get_playlist(p_id))
                                       for p_name, p_id in channel['relatedPlaylists'].items())

                self.log_debug("Channel's related playlists found = %s" % relatedplaylist.keys())

                relatedplaylist['uploads']['title'] = "Unplaylisted videos"
                relatedplaylist['uploads']['checkDups'] = True  #: checkDups flag

                for p_name, p_data in relatedplaylist.items():
                    if self.config.get(p_name):
                        p_data['title'] += " of " + user
                        playlists.append(p_data)

            else:
                playlists = []

        else:
            self.log_debug("Url recognized as Playlist")
            playlists = [self.get_playlist(self.info['pattern']['ID'])]

        if not playlists:
            self.fail(_("No playlist available"))

        addedvideos = []
        urlize = lambda x: "https://www.youtube.com/watch?v=" + x
        for p in playlists:
            p_name = p['title']
            p_videos = self.get_videos_id(p['id'])

            self.log_debug('%s videos found on playlist "%s"' % (len(p_videos), p_name))

            if not p_videos:
                continue
            elif "checkDups" in p:
                p_urls = [urlize(v_id)
                          for v_id in p_videos
                          if v_id not in addedvideos]

                self.log_debug('%s videos available on playlist "%s" after duplicates cleanup' % (len(p_urls), p_name))

            else:
                p_urls = map(urlize, p_videos)

            self.packages.append((p_name, p_urls, p_name))

            addedvideos.extend(p_videos)
