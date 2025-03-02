# -*- coding: utf-8 -*-

import re

from module.network.HTTPRequest import BadHeader
from module.PyFile import PyFile

from ..captcha.ReCaptcha import ReCaptcha
from ..internal.Account import Account
from ..internal.Captcha import Captcha
from ..internal.misc import json


class FileboomMe(Account):
    __name__ = "FileboomMe"
    __type__ = "account"
    __version__ = "0.04"
    __status__ = "testing"

    __description__ = """Fileboom.me account plugin"""
    __license__ = "GPLv3"
    __authors__ = [("GammaC0de", "nitzo2001[AT]yahoo[DOT]com")]

    RECAPTCHA_KEY = "6LcYcN0SAAAAABtMlxKj7X0hRxOY8_2U86kI1vbb"

    API_URL = "https://fileboom.me/api/v2/"
    #: Actually this is Keep2ShareCc API, see https://github.com/keep2share/api

    def api_response(self, method, **kwargs):
        html = self.load(self.API_URL + method,
                       post=json.dumps(kwargs))
        return json.loads(html)

    def grab_info(self, user, password, data):
        json_data = self.api_response("AccountInfo", auth_token=data['token'])

        return {'validuntil': json_data['account_expires'],
                'trafficleft': json_data['available_traffic'],
                'premium': True if json_data['account_expires'] else False}

    def signin(self, user, password, data):
        if 'token' in data:
            try:
                json_data = self.api_response("test", auth_token=data['token'])

            except BadHeader, e:
                if e.code == 403:  #: Session expired
                    pass

                else:
                    raise
            else:
                self.skip_login()

        try:
            json_data = self.api_response("login", username=user, password=password)

        except BadHeader, e:
            if e.code == 406:  #: Captcha needed
                # dummy pyfile
                pyfile = PyFile(self.pyload.files, -1, "https://fileboom.me", "https://fileboom.me", 0, 0, "", self.classname, -1, -1)
                pyfile.plugin = self

                errors = [json.loads(m.group(0)).get('errorCode', 0) for m in re.finditer(r'{[^}]+}', e.content)]
                if 33 in errors:  #: ERROR_RE_CAPTCHA_REQUIRED
                    #: Recaptcha
                    self.captcha = ReCaptcha(pyfile)
                    for i in range(10):
                        json_data = self.api_response("RequestReCaptcha")
                        if json_data['code'] != 200:
                            self.log_error(_("Request reCAPTCHA API failed"))
                            self.fail_login(_("Request reCAPTCHA API failed"))

                        re_captcha_response = self.captcha.challenge(self.RECAPTCHA_KEY, version="2js", secure_token=False)
                        try:
                            json_data = self.api_response("login",
                                                          username=user,
                                                          password=password,
                                                          re_captcha_challenge=json_data['challenge'],
                                                          re_captcha_response=re_captcha_response)

                        except BadHeader, e:
                            if e.code == 406:
                                errors = [json.loads(m.group(0)).get('errorCode', 0) for m in re.finditer(r'{[^}]+}', e.content)]
                                if 31 in errors:  #: ERROR_CAPTCHA_INVALID
                                    self.captcha.invalid()
                                    continue

                                else:
                                    self.log_error(e.content)
                                    self.fail_login(e.content)

                            else:
                                self.log_error(e.content)
                                self.fail_login(e.content)

                        else:
                            self.captcha.correct()
                            data['token'] = json_data['auth_token']
                            break

                    else:
                        self.log_error(_("Max captcha retries reached"))
                        self.fail_login(_("Max captcha retries reached"))

                elif 30 in errors:  #: ERROR_CAPTCHA_REQUIRED
                    #: Normal captcha
                    self.captcha = Captcha(pyfile)
                    for i in range(10):
                        json_data = self.api_response("RequestCaptcha")
                        if json_data['code'] != 200:
                            self.log_error(_("Request captcha API failed"))
                            self.fail_login(_("Request captcha API failed"))

                        captcha_response = self.captcha.decrypt(json_data['captcha_url'])
                        try:
                            json_data = self.api_response("login",
                                                          username=user,
                                                          password=password,
                                                          captcha_challenge=json_data['challenge'],
                                                          captcha_response=captcha_response)

                        except BadHeader, e:
                            if e.code == 406:
                                errors = [json.loads(m.group(0)).get('errorCode', 0) for m in re.finditer(r'{[^}]+}', e.content)]
                                if 31 in errors:  #: ERROR_CAPTCHA_INVALID
                                    self.captcha.invalid()
                                    continue

                                else:
                                    self.log_error(e.content)
                                    self.fail_login(e.content)

                            else:
                                self.log_error(e.content)
                                self.fail_login(e.content)

                        else:
                            self.captcha.correct()
                            data['token'] = json_data['auth_token']
                            break

                    else:
                        self.log_error(_("Max captcha retries reached"))
                        self.fail_login(_("Max captcha retries reached"))

                else:
                    self.log_error(e.content)
                    self.fail_login(e.content)

            else:
                self.log_error(e.content)
                self.fail_login(e.content)

        else:
            #: No captcha
            data['token'] = json_data['auth_token']

    """
     @NOTE: below are methods
      necessary for captcha to work with account plugins
    """
    def check_status(self):
        pass

    def retry_captcha(self, attemps=10, wait=1, msg=_("Max captcha retries reached")):
        self.captcha.invalid()
        self.fail_login(msg=_("Invalid captcha"))
