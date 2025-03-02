# -*- coding: utf-8 -*-

import base64
import re
import urllib

from ..internal.Hoster import Hoster
from ..internal.misc import json, set_cookie


class GofileIo(Hoster):
    __name__ = "GofileIo"
    __type__ = "hoster"
    __version__ = "0.01"
    __status__ = "testing"

    __pattern__ = r"https?://(?:www\.)?gofile\.io/dl\?q=(?P<QS>.+)"
    __config__ = [
        ("enabled", "bool", "Activated", True),
        ("use_premium", "bool", "Use premium account if available", True),
        ("fallback", "bool", "Fallback to free download if premium fails", True),
        ("chk_filesize", "bool", "Check file size", True),
        ("max_wait", "int", "Reconnect if waiting time is greater than minutes", 10),
    ]

    __description__ = """Gofile.io downloader plugin"""
    __license__ = "GPLv3"
    __authors__ = [("GammaC0de", "nitzo2001[AT]yahoo[DOT]com")]

    URL_REPLACEMENTS = [("http://", "https://")]

    API_URL = "https://api.gofile.io/"

    def api_request(self, method, **kwargs):
        json_data = self.load(self.API_URL + method, get=kwargs)
        return json.loads(json_data)

    def get_info(self, url="", html=""):
        info = super(GofileIo, self).get_info(url, html)

        qs = re.match(self.__pattern__, url).group('QS')
        file_info = json.loads(base64.b64decode(qs))

        info.update({
            'name': urllib.unquote_plus(file_info['n']).encode('latin1').decode('utf8'),
            'size': file_info['s'],
            'md5': file_info['m'],
            'u': file_info['u'],
            "token": file_info["t"]
        })

        return info

    def setup(self):
        self.chunk_limit = -1
        self.resume_download = True
        self.multiDl = True

    def process(self, pyfile):
        token = self.info["token"]
        set_cookie(self.req.cj, "gofile.io", "accountToken", token)
        self.download(self.info["u"], disposition=False)
