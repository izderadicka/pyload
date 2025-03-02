# -*- coding: utf-8 -*-

from ..internal.misc import json
from ..internal.SimpleHoster import SimpleHoster


class VeohCom(SimpleHoster):
    __name__ = "VeohCom"
    __type__ = "hoster"
    __version__ = "0.30"
    __status__ = "testing"

    __pattern__ = r'https?://(?:www\.)?veoh\.com/(?:tv/)?(?:watch|videos)/(?P<ID>v\w+)'
    __config__ = [("activated", "bool", "Activated", True),
                  ("use_premium", "bool", "Use premium account if available", True),
                  ("fallback", "bool",
                   "Fallback to free download if premium fails", True),
                  ("chk_filesize", "bool", "Check file size", True),
                  ("max_wait", "int", "Reconnect if waiting time is greater than minutes", 10)]

    __description__ = """Veoh.com hoster plugin"""
    __license__ = "GPLv3"
    __authors__ = [("Walter Purcaro", "vuolter@gmail.com"),
                   ("GammaC0de", "nitzo2001[AT]yahoo[DOT]com")]

    NAME_PATTERN = r'<meta name="title" content="(?P<N>.*?)"'
    OFFLINE_PATTERN = r'>Sorry, we couldn\'t find the video you were looking for'

    URL_REPLACEMENTS = [
        (__pattern__ + ".*",
         r'https://www.veoh.com/watch/\g<ID>')
    ]

    COOKIES = [("veoh.com", "lassieLocale", "en")]

    def setup(self):
        self.resume_download = True
        self.multiDL = True
        self.chunk_limit = -1

    def handle_free(self, pyfile):
        video_id = self.info['pattern']['ID']
        video_data = json.loads(self.load(r"https://www.veoh.com/watch/getVideo/%s" % video_id))
        pyfile.name = video_data["video"]['title'] + ".mp4"
        self.link = video_data["video"]['src']['HQ']
