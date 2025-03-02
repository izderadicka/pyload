# -*- coding: utf-8 -*-

from ..internal.Crypter import Crypter
from ..internal.misc import json


class GooGl(Crypter):
    __name__ = "GooGl"
    __type__ = "crypter"
    __version__ = "0.10"
    __status__ = "testing"

    __pattern__ = r'https?://(?:www\.)?goo\.gl/([a-zA-Z]+/)?\w+'
    __config__ = [("activated", "bool", "Activated", True),
                  ("use_premium", "bool", "Use premium account if available", True),
                  ("folder_per_package", "Default;Yes;No", "Create folder for each package", "Default"),
                  ("max_wait", "int", "Reconnect if waiting time is greater than minutes", 10)]

    __description__ = """Goo.gl decrypter plugin"""
    __license__ = "GPLv3"
    __authors__ = [("stickell", "l.stickell@yahoo.it"),
                   ("Walter Purcaro", "vuolter@gmail.com"),
                   ("GammaC0de", "nitzo2001[AT]yahoo[DOT]com")]

    API_URL = "https://www.googleapis.com/urlshortener/v1/"
    API_KEY = "AIzaSyB68u-qFPP9oBJpo1DWAPFE_VD2Sfy9hpk"

    def api_response(self, cmd, **kwargs):
        kwargs['key'] = self.API_KEY

        json_data = json.loads(self.load("%s%s" % (self.API_URL, cmd),
                                         get=kwargs))
        self.log_debug("API response: %s" % json_data)
        return json_data

    def decrypt(self, pyfile):
        res = self.api_response("url", shortUrl=self.pyfile.url)

        if  res['status'] != "OK":
            self.offline()

        self.packages.append((pyfile.package().name, [res['longUrl']], pyfile.package().folder))