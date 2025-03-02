# -*- coding: utf-8 -*-

import time

import pycurl
from module.network.HTTPRequest import BadHeader

from ..internal.misc import json
from ..internal.MultiAccount import MultiAccount


def args(**kwargs):
    return kwargs


class RealdebridCom(MultiAccount):
    __name__ = "RealdebridCom"
    __type__ = "account"
    __version__ = "0.62"
    __status__ = "testing"

    __config__ = [("mh_mode", "all;listed;unlisted", "Filter hosters to use", "all"),
                  ("mh_list", "str", "Hoster list (comma separated)", ""),
                  ("mh_interval", "int", "Reload interval in hours", 12)]

    __description__ = """Real-Debrid.com account plugin"""
    __license__ = "GPLv3"
    __authors__ = [("Devirex Hazzard", "naibaf_11@yahoo.de"),
                   ("GammaC0de", "nitzo2001[AT]yahoo[DOT]com")]

    TUNE_TIMEOUT = False

    # See https://api.real-debrid.com/
    API_URL = "https://api.real-debrid.com"

    def api_response(self, api_type, method, get={}, post={}):
        if api_type == "rest":
            endpoint = "/rest/1.0"
        elif api_type == "oauth":
            endpoint = "/oauth/v2"
        else:
            raise ValueError("Illegal API call type")

        self.req.http.c.setopt(pycurl.USERAGENT, "pyLoad/%s" % self.pyload.version)

        try:
            json_data = self.load(self.API_URL + endpoint + method, get=get, post=post)

        except BadHeader, e:
            json_data = e.content

        return json.loads(json_data)


    def _refresh_token(self, client_id, client_secret, refresh_token):
        res = self.api_response("oauth", "/token",
                                post=args(client_id=client_id,
                                          client_secret=client_secret,
                                          code=refresh_token,
                                          grant_type="http://oauth.net/grant_type/device/1.0"))

        if 'error' in res:
            self.log_error(_("You have to use GetRealdebridToken.py to authorize pyLoad: https://github.com/pyload/pyload/files/4406037/GetRealdebridToken.zip"))
            self.fail_login()

        return res['access_token'], res['expires_in']


    def grab_hosters(self, user, password, data):
        api_data = self.api_response("rest", "/hosts/status", args(auth_token=data['api_token']))
        hosters = [x[0] for x in api_data.items() if x[1]['supported'] == 1]
        return hosters

    def grab_info(self, user, password, data):
        api_data = self.api_response("rest", "/user", args(auth_token=data['api_token']))

        premium_remain = api_data["premium"]
        premium = premium_remain > 0
        validuntil = time.time() + premium_remain if premium else -1

        return {'validuntil': validuntil,
                'trafficleft': -1,
                'premium': premium}

    def signin(self, user, password, data):
        user = user.split('/')
        if len(user) != 2:
            self.log_error(_("You have to use GetRealdebridToken.py to authorize pyLoad: https://github.com/pyload/pyload/files/4406037/GetRealdebridToken.zip"))
            self.fail_login()

        client_id, client_secret = user

        if 'api_token' not in data:
            api_token, timeout = self._refresh_token(client_id, client_secret, password)
            data['api_token'] = api_token
            self.timeout = timeout - 5 * 60  #: Five minutes less to be on the safe side

        api_token = data['api_token']

        account = self.api_response("rest", "/user", args(auth_token=api_token))

        if account.get('error_code') == 8:  #: Token expired? try to refresh
            api_token, timeout = self._refresh_token(client_id, client_secret, password)
            data['api_token'] = api_token
            self.timeout = timeout - 5 * 60  #: Five minutes less to be on the safe side

        elif 'error' in account:
            self.log_error(account['error'])
            self.fail_login()
