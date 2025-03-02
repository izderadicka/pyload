# -*- coding: utf-8 -*-

import base64
import re
import urllib

from ..internal.Hoster import Hoster
from ..internal.misc import json


class CloudMailRu(Hoster):
    __name__ = "CloudMailRu"
    __type__ = "hoster"
    __version__ = "0.05"
    __status__ = "testing"

    __pattern__ = r'https?://cloud\.mail\.ru/dl\?q=(?P<QS>.+)'
    __config__ = [("activated", "bool", "Activated", True),
                  ("use_premium", "bool", "Use premium account if available", True),
                  ("fallback", "bool","Fallback to free download if premium fails", True),
                  ("chk_filesize", "bool", "Check file size", True),
                  ("max_wait", "int", "Reconnect if waiting time is greater than minutes", 10)]

    __description__ = """Cloud.mail.ru hoster plugin"""
    __license__ = "GPLv3"
    __authors__ = [("GammaC0de", "nitzo2001[AT]yahoo[DOT]com")]

    OFFLINE_PATTERN = r'"error":\s*"not_exists"'

    def get_info(self, url="", html=""):
        info = super(CloudMailRu, self).get_info(url, html)

        qs = re.match(self.__pattern__, url).group('QS')
        file_info = json.loads(base64.b64decode(qs))

        info.update({
            'name': urllib.unquote_plus(file_info['n']).encode('latin1').decode('utf8'),
            'size': file_info['s'],
            'u': file_info['u']
        })

        return info

    def setup(self):
        self.chunk_limit = -1
        self.resume_download = True
        self.multiDL = True

    def process(self, pyfile):
        self.download(self.info['u'], disposition=False)
