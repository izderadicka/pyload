# -*- coding: utf-8 -*-


from ..captcha.ReCaptcha import ReCaptcha
from ..internal.SimpleHoster import SimpleHoster


class FileuploadNet(SimpleHoster):
    __name__ = "FileuploadNet"
    __type__ = "hoster"
    __version__ = "0.08"
    __status__ = "testing"

    __pattern__ = r'https?://(?:www\.)?(en\.)?file-upload\.net/download-\d+/.+'
    __config__ = [("activated", "bool", "Activated", True),
                  ("use_premium", "bool", "Use premium account if available", True),
                  ("fallback", "bool",
                   "Fallback to free download if premium fails", True),
                  ("chk_filesize", "bool", "Check file size", True),
                  ("max_wait", "int", "Reconnect if waiting time is greater than minutes", 10)]

    __description__ = """File-upload.net hoster plugin"""
    __license__ = "GPLv3"
    __authors__ = [("zapp-brannigan", "fuerst.reinje@web.de"),
                   ("GammaC0de", "nitzo2001[AT]yahoo[DOT]com")]

    NAME_PATTERN = r'<title>File-Upload.net - (?P<N>.+?)<'
    SIZE_PATTERN = r'</label><span>(?P<S>[\d.,]+) (?P<U>[\w^_]+)'
    OFFLINE_PATTERN = r'Datei existiert nicht'

    LINK_FREE_PATTERN = r"<a href='(.+?)' title='download' onclick"

    def setup(self):
        self.multiDL = True
        self.chunk_limit = 1

    def handle_free(self, pyfile):
        action, inputs = self.parse_html_form('id="downloadstart"')
        if not inputs:
            self.fail(_("download form not found"))

        self.captcha = ReCaptcha(pyfile)
        captcha_key = self.captcha.detect_key()

        if captcha_key:
            result = self.captcha.challenge(captcha_key, version="2invisible")
            inputs["g-recaptcha-response"] = result
            self.download(action, post=inputs)

        else:
            self.fail(self._("ReCaptcha key not found"))
