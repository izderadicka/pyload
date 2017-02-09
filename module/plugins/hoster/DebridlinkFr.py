f# -*- coding: utf-8 -*-

import pycurl
import time
import Crypto.Hash.SHA

from module.plugins.internal.MultiHoster import MultiHoster
from module.plugins.internal.misc import json


def args(**kwargs):
    return kwargs


class DebridlinkFr(MultiHoster):
    __name__    = "DebridlinkFr"
    __type__    = "hoster"
    __version__ = "0.01"
    __status__  = "testing"

    __pattern__ = r'^unmatchable$'
    __config__  = [("activated"    , "bool", "Activated"                                        , True ),
                   ("use_premium"  , "bool", "Use premium account if available"                 , True ),
                   ("fallback"     , "bool", "Fallback to free download if premium fails"       , False),
                   ("chk_filesize" , "bool", "Check file size"                                  , True ),
                   ("max_wait"     , "int" , "Reconnect if waiting time is greater than minutes", 10   ),
                   ("revert_failed", "bool", "Revert to standard download if fails"             , True )]

    __description__ = """Debrid-slink.fr multi-hoster plugin"""
    __license__     = "GPLv3"
    __authors__     = [("GammaC0de", "nitzo2001[AT]yahoo[DOT]com")]

    API_URL = "https://debrid-link.fr/api"


    def api_request(self, method, data=None, get={}, post={}):

        session = self.account.info['data'].get('session', None)
        if session:
            ts = str(int(time.time() - float(session['tsd'])))

            sha1 = Crypto.Hash.SHA.new()
            sha1.update(ts + method + session['key'])
            sign = sha1.hexdigest()

            self.req.http.c.setopt(pycurl.HTTPHEADER, ["X-DL-TOKEN: " + session['token'],
                                                       "X-DL-SIGN: " + sign,
                                                       "X-DL-TS: " + ts])

        json_data = self.load(self.API_URL + method, get=get, post=post)

        return json.loads(json_data)


    def handle_premium(self, pyfile):
        res = self.api_request("/downloader/add", post=args(link=pyfile.url))

        if res['result'] == "OK":
            self.link = res['value']['downloadLink']

