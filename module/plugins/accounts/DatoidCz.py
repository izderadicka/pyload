# -*- coding: utf-8 -*-

import re

from ..internal.Account import Account


class DatoidCz(Account):
    __name__ = "DatoidCz"
    __type__ = "account"
    __version__ = "0.39"
    __status__ = "testing"

    __description__ = """Datoid.cz account plugin"""
    __license__ = "GPLv3"
    __authors__ = [("GammaC0de", None)]

    def grab_info(self, user, password, data):
        html = self.load("https://datoid.cz/")

        m = re.search(r'"menu-bar-storage"></i> ([\d.,]+) ([\w^_]+)', html)
        trafficleft = self.parse_traffic(m.group(1), m.group(2)) if m else 0

        premium = True
        if trafficleft == 0:
            premium = False
            trafficleft = None

        info = {'validuntil': -1,
                'trafficleft': trafficleft,
                'premium': premium}

        return info

    def signin(self, user, password, data):
        html = self.load("https://datoid.cz/")
        if 'href="/muj-ucet">' in html:
            self.skip_login()

        token_re = r'name="_token_" value="([^"]+)"'
        m = re.search(token_re, html)
        if not m:
            self.fail_login("Cannot find token")
            return

        token = m.group(1)

        html = self.load("https://datoid.cz/",
                         post={'username': user,
                               'password': password,
                               "_do": "signInForm-submit", 
                               "_token_": token})
                               

        if 'href="/muj-ucet">' not in html:
            self.fail_login()


