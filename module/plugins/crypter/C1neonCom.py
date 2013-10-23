# -*- coding: utf-8 -*-

from module.plugins.internal.DeadCrypter import DeadCrypter


class C1neonCom(DeadCrypter):
    __name__ = "C1neonCom"
    __type__ = "container"
    __pattern__ = r"http://(www\.)?c1neon.com/.*?"
    __version__ = "0.05"
    __description__ = """C1neon.Com Container Plugin"""
    __author_name__ = ("godofdream")
    __author_mail__ = ("soilfiction@gmail.com")