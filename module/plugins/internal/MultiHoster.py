# -*- coding: utf-8 -*-

import re

from .Base import Base
from .misc import replace_patterns
from .Plugin import Fail
from .SimpleHoster import SimpleHoster


class MultiHoster(SimpleHoster):
    __name__ = "MultiHoster"
    __type__ = "hoster"
    __version__ = "0.72"
    __status__ = "stable"

    __pattern__ = r'^unmatchable$'
    __config__ = [("activated", "bool", "Activated", True),
                  ("use_premium", "bool", "Use premium account if available", True),
                  ("fallback", "bool", "Fallback to free download if premium fails", False),
                  ("chk_filesize", "bool", "Check file size", True),
                  ("max_wait", "int", "Reconnect if waiting time is greater than minutes", 10),
                  ("revert_failed", "bool", "Revert to standard download if fails", True)]

    __description__ = """Multi hoster plugin"""
    __license__ = "GPLv3"
    __authors__ = [("Walter Purcaro", "vuolter@gmail.com"),
                   ("GammaC0de", "nitzo2001[AT]yahoo[DOT]com")]

    OFFLINE_PATTERN = r'^unmatchable$'
    TEMP_OFFLINE_PATTERN = r'^unmatchable$'

    LEECH_HOSTER = False
    DIRECT_LINK = None

    def get_info(self, url="", html=""):
        return super(SimpleHoster, self).get_info(url, html)

    def init(self):
        self.PLUGIN_NAME = self.pyload.pluginManager.hosterPlugins.get(self.classname)['name']

    def _log(self, level, plugintype, pluginname, messages, tbframe=None):
        messages = (self.PLUGIN_NAME,) + messages
        return SimpleHoster._log(self, level, plugintype, pluginname, messages, tbframe=tbframe)

    def setup(self):
        self.no_fallback = True
        self.chunk_limit = 1
        self.multiDL = bool(self.account)
        self.resume_download = self.premium

    def _preload(self):
        pass

    def _prepare(self):
        SimpleHoster._prepare(self)

        if self.pyfile.pluginname != self.__name__:
            overwritten_plugin = self.pyload.pluginManager.loadClass("hoster", self.pyfile.pluginname)
            if overwritten_plugin is not None:
                self.pyfile.url = replace_patterns(self.pyfile.url, overwritten_plugin.URL_REPLACEMENTS)

        if self.DIRECT_LINK is None:
            self.direct_dl = self.__pattern__ != r'^unmatchable$' and re.match(self.__pattern__, self.pyfile.url) is not None

        else:
            self.direct_dl = self.DIRECT_LINK

    def _process(self, thread):
        try:
            SimpleHoster._process(self, thread)

        except Fail, e:
            hdict = self.pyload.pluginManager.hosterPlugins.get(self.pyfile.pluginname, {})
            if self.config.get('revert_failed', True) and hdict.get('new_module'):
                tmp_module = hdict.pop('new_module', None)
                tmp_name = hdict.pop('new_name', None)

                self.pyfile.plugin = None
                self.pyfile.initPlugin()

                hdict['new_module'] = tmp_module
                hdict['new_name'] = tmp_name

                self.restart(_("Revert to original hoster plugin"))

            else:
                raise

    def handle_premium(self, pyfile):
        return self.handle_free(pyfile)

    def handle_free(self, pyfile):
        if self.premium:
            raise NotImplementedError

        else:
            self.fail(_("MultiHoster download failed"))
