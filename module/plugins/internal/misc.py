# -*- coding: utf-8 -*-
#
# @TODO: Move to misc directory in 0.4.10

from __future__ import with_statement

# import HTMLParser  #@TODO: Use in 0.4.10
import datetime
import hashlib
import itertools
import os
import re
import shutil
import socket
import string
import subprocess
import sys
import time
import traceback
import urllib
import urlparse
import zlib
from email.header import decode_header as decode_rfc2047_header
from htmlentitydefs import name2codepoint

from module.network.HTTPRequest import HTTPRequest
from module.plugins.Plugin import Abort

try:
    import simplejson as json
except ImportError:
    import json

try:
    from functools import reduce
except ImportError:
    reduce = reduce

try:
    import send2trash
except ImportError:
    pass


#@TODO: Remove in 0.4.10
class misc(object):
    __name__ = "misc"
    __type__ = "plugin"
    __version__ = "0.69"
    __status__ = "stable"

    __pattern__ = r'^unmatchable$'
    __config__ = []

    __description__ = """Dummy utils class"""
    __license__ = "GPLv3"
    __authors__ = [("Walter Purcaro", "vuolter@gmail.com")]


class Config(object):

    def __init__(self, plugin):
        self.plugin = plugin

    def set(self, option, value, plugin=None):
        """
        Set config value for current plugin

        :param option:
        :param value:
        :return:
        """
        self.plugin.pyload.api.setConfigValue(plugin or self.plugin.classname, option, value, section="plugin")

    def get(self, option, default=None, plugin=None):
        """
        Returns config value for current plugin

        :param option:
        :return:
        """
        try:
            return self.plugin.pyload.config.getPlugin(plugin or self.plugin.classname, option)

        except KeyError:
            self.plugin.log_debug("Config option `%s` not found, use default `%s`" % (
            option, default))  # @TODO: Restore to `log_warning` in 0.4.10
            return default


class DB(object):

    def __init__(self, plugin):
        self.plugin = plugin

    def store(self, key, value):
        """
        Saves a value persistently to the database
        """
        entry = json.dumps(value, ensure_ascii=False).encode('base64')
        self.plugin.pyload.db.setStorage(self.plugin.classname, key, entry)

    def retrieve(self, key=None, default=None):
        """
        Retrieves saved value or dict of all saved entries if key is None
        """
        entry = self.plugin.pyload.db.getStorage(self.plugin.classname, key)

        if key:
            if entry is None:
                value = default
            else:
                value = json.loads(entry.decode('base64'))
        else:
            if not entry:
                value = default
            else:
                value = dict((k, json.loads(v.decode('base64')))
                             for k, v in entry.items())

        return value

    def delete(self, key):
        """
        Delete entry in db
        """
        self.plugin.pyload.db.delStorage(self.plugin.classname, key)
        self.plugin.pyload.db.commit()


class Expose(object):
    """
    Used for decoration to declare rpc services
    """

    def __new__(cls, fn, *args, **kwargs):
        hookManager.addRPC(fn.__module__, fn.__name__, fn.__doc__)
        return fn


class Periodical(object):

    def __init__(self, plugin, task=lambda x: x, interval=None):
        self.plugin = plugin
        self.task = task
        self.cb = None
        self.interval = interval

    def set_interval(self, value):
        newinterval = max(0, value)

        if newinterval != value:
            return False

        if newinterval != self.interval:
            self.interval = newinterval

        return True

    def start(self, interval=None, threaded=False, delay=0):
        if interval is not None and self.set_interval(interval) is False:
            return False
        else:
            self.cb = self.plugin.pyload.scheduler.addJob(max(1, delay), self._task, [threaded], threaded=threaded)
            return True

    def restart(self, *args, **kwargs):
        self.stop()
        return self.start(*args, **kwargs)

    def stop(self):
        try:
            return self.plugin.pyload.scheduler.removeJob(self.cb)

        except Exception:
            return False

        finally:
            self.cb = None

    stopped = property(lambda self: self.cb is None)

    def _task(self, threaded):
        try:
            self.task()

        except Exception, e:
            self.plugin.log_error(_("Error performing periodical task"), e)

        if not self.stopped:
            self.restart(threaded=threaded, delay=self.interval)


class SimpleQueue(object):

    def __init__(self, plugin, storage="queue"):
        self.plugin = plugin
        self.storage = storage

    def get(self):
        return self.plugin.db.retrieve(self.storage, default=[])

    def set(self, value):
        return self.plugin.db.store(self.storage, value)

    def delete(self):
        return self.plugin.db.delete(self.storage)

    def add(self, item):
        queue = self.get()
        if item not in queue:
            return self.set(queue + [item])
        else:
            return True

    def remove(self, item):
        queue = self.get()
        try:
            queue.remove(item)

        except ValueError:
            pass

        if isinstance(queue, list):
            return self.delete()

        return self.set(queue)


def lock(fn):
    def new(*args, **kwargs):
        args[0].lock.acquire()
        try:
            return fn(*args, **kwargs)

        finally:
            args[0].lock.release()

    return new


def threaded(fn):
    def run(*args, **kwargs):
        hookManager.startThread(fn, *args, **kwargs)

    return run


def sign_string(message, pem_private, pem_passphrase="", sign_algo="SHA384"):
    """
    Generate a signature for string using the `sign_algo` and `RSA` algorithms
    """
    from Crypto.PublicKey import RSA
    from Crypto.Signature import PKCS1_v1_5
    from binascii import b2a_hex

    if sign_algo not in ("MD5", "SHA1", "SHA256", "SHA384", "SHA512"):
        raise ValueError("Unsupported Signing algorithm")

    priv_key = RSA.importKey(pem_private, passphrase=pem_passphrase)
    signer = PKCS1_v1_5.new(priv_key)
    digest = getattr(__import__('Crypto.Hash', fromlist=[sign_algo]), sign_algo).new()
    digest.update(message)
    return b2a_hex(signer.sign(digest))


def format_time(value):
    dt = datetime.datetime(1, 1, 1) + \
         datetime.timedelta(seconds=abs(int(value)))
    days = ("%d days" % (dt.day - 1)) if dt.day > 1 else ""
    tm = ", ".join("%d %ss" % (getattr(dt, attr), attr)
                   for attr in ("hour", "minute", "second")
                   if getattr(dt, attr))
    return days + (" and " if days and tm else "") + tm


def format_size(value):
    for unit in ('B', 'KiB', 'MiB', 'GiB', 'TiB', 'PiB'):
        if abs(value) < 1024.0:
            return "%3.2f %s" % (value, unit)
        else:
            value /= 1024.0

    return "%.2f %s" % (value, 'EiB')


def compare_time(start, end):
    start = map(int, start)
    end = map(int, end)

    if start == end:
        return True

    now = list(time.localtime()[3:5])

    if start < end:
        if now < end:
            return True

    elif now > start or now < end:
        return True

    return False


def free_space(folder):
    if os.name == "nt":
        import ctypes

        free_bytes = ctypes.c_ulonglong(0)
        ctypes.windll.kernel32.GetDiskFreeSpaceExW(ctypes.c_wchar_p(folder),
                                                   None,
                                                   None,
                                                   ctypes.pointer(free_bytes))
        return free_bytes.value

    else:
        s = os.statvfs(folder)
        return s.f_frsize * s.f_bavail


def fsbsize(path):
    """
    Get optimal file system buffer size (in bytes) for I/O calls
    """
    path = fs_encode(path)

    if os.name == "nt":
        import ctypes

        drive = "%s\\" % os.path.splitdrive(path)[0]
        cluster_sectors, sector_size = ctypes.c_longlong(0)

        ctypes.windll.kernel32.GetDiskFreeSpaceW(ctypes.c_wchar_p(drive),
                                                 ctypes.pointer(cluster_sectors),
                                                 ctypes.pointer(sector_size),
                                                 None,
                                                 None)
        return cluster_sectors * sector_size

    else:
        return os.statvfs(path).f_frsize


def uniqify(seq):
    """
    Remove duplicates from list preserving order
    Originally by Dave Kirby
    """
    seen = set()
    seen_add = seen.add
    return [x for x in seq if x not in seen and not seen_add(x)]


def has_method(obj, name):
    """
    Check if function 'name' was defined in obj
    """
    return callable(getattr(obj, name, None))


def html_unescape(text):
    """
    Decode HTML or XML escape character references and entities from a text string
    """

    def fixup(m):
        text = m.group(0)
        if text[:2] == "&#":
            # character reference
            try:
                if text[:3] == "&#x":
                    return unichr(int(text[3:-1], 16))
                else:
                    return unichr(int(text[2:-1]))
            except ValueError:
                pass
        else:
            # named entity
            try:
                name = text[1:-1]
                text = unichr(name2codepoint[name])
            except KeyError:
                pass

        return text  # leave as is

    return re.sub("&#?\w+;", fixup, text)
    # @TODO: Replace in 0.4.10 with:
    # h = HTMLParser.HTMLParser()
    # return h.unescape(text)


def isiterable(obj):
    """
    Check if object is iterable (string excluded)
    """
    return hasattr(obj, "__iter__")


def get_console_encoding(enc):
    if os.name == "nt":
        if enc == "cp65001":  #: aka UTF-8
            enc = "utf8"

        elif enc is None:  #: piped
            enc = "iso-8859-1"

    else:
        enc = "utf8"

    return enc


# Hotfix UnicodeDecodeError: 'ascii' codec can't decode..
def normalize(value):
    import unicodedata
    return unicodedata.normalize('NFKD', value).encode('ascii', 'ignore')


# @NOTE: Revert to `decode` in Python 3
def decode(value, encoding=None, errors='strict'):
    """
    Encoded string (default to own system encoding) -> unicode string
    """
    if isinstance(value, str):
        res = unicode(value, encoding or get_console_encoding(sys.stdout.encoding), errors)

    elif isinstance(value, unicode):
        res = value

    else:
        res = unicode(value)

    return res


def transcode(value, decoding, encoding):
    return value.decode(decoding).encode(encoding)


def encode(value, encoding='utf-8', errors='backslashreplace'):
    """
    Unicode string -> encoded string (default to UTF-8)
    """
    if isinstance(value, unicode):
        res = value.encode(encoding, errors)

    elif isinstance(value, str):
        decoding = get_console_encoding(sys.stdin.encoding)
        if encoding == decoding:
            res = value
        else:
            res = transcode(value, decoding, encoding)

    else:
        res = str(value)

    return res


def rfc2047_dec(value):
    def decode_chunk(m):
        data, enc = decode_rfc2047_header(m.group(0))[0]
        try:
            res = data.decode(enc)
        except (LookupError, UnicodeEncodeError):
            res = m.group(0)

        return res

    return re.sub(r'=\?([^?]+)\?([QB])\?([^?]*)\?=', decode_chunk, value, re.I)


def exists(path):
    path = fs_encode(path)

    if os.name == "nt":
        if path.startswith("\\\\"):
            return os.path.exists('\\\\?\\UNC\\' + path[2:])
        else:
            return os.path.exists('\\\\?\\' + os.path.normpath(os.path.join(os.getcwd(), path)))
    else:
        return os.path.exists(path)


def remove(path, trash=True):
    path = fs_encode(path)

    if not exists(path):
        return

    if trash:
        send2trash.send2trash(path)

    elif os.path.isdir(path):
        shutil.rmtree(path, ignore_errors=True)

    else:
        os.remove(path)


def fsjoin(*args):
    """
    Like os.path.join, but encoding aware
    (for safe-joining see `safejoin`)
    """
    return fs_encode(os.path.join(*args))


def remove_chars(value, repl):
    """
    Remove all chars in repl from string
    """
    if isinstance(repl, unicode):
        for badc in list(repl):
            value = value.replace(badc, "")
        return value

    elif isinstance(value, unicode):
        return value.translate(dict((ord(s), None) for s in repl))

    elif isinstance(value, str):
        return value.translate(string.maketrans("", ""), repl)


def fixurl(url, unquote=None):
    old = url
    url = urllib.unquote(url)
    if isinstance(url, unicode):
        try:
            url = url.encode("latin1").decode("utf8")  #: bugfix urllib
        except UnicodeEncodeError:
            pass

    if unquote is None:
        unquote = url == old

    url = decode(url)

    #: 'unicode-escape' that work with unicode strings too
    url = re.sub(r'\\[uU](\d{4})', lambda x: unichr(int(x.group(1))), url)

    url = html_unescape(url)

    #: '//' becomes '/'
    url = re.sub(r'(?<!:)/{2,}', '/', url).strip().lstrip('.')

    if not unquote:
        url = urllib.quote(url)

    return url


def truncate(name, length):
    max_trunc = len(name) / 2
    if length > max_trunc:
        raise OSError("File name too long")

    trunc = int((len(name) - length) / 3)
    return "%s~%s" % (name[:trunc * 2], name[-trunc:])


if sys.getfilesystemencoding().startswith('ANSI'):
    """
     Use fs_encode before accessing files on disk,
     it will encode the string properly
    """

    def fs_encode(value):
        try:
            value = decode(value)
            value = value.encode('utf-8')
        finally:
            return value

else:
    fs_encode = decode


# @TODO: Recheck in 0.4.10
def safepath(value):
    """
    Remove invalid characters and truncate the path if needed
    """
    if os.name == "nt":
        unt, value = os.path.splitunc(value)
    else:
        unt = ""
    drive, filename = os.path.splitdrive(value)
    filename = os.path.join(os.sep if os.path.isabs(filename) else "", *map(safename, filename.split(os.sep)))
    path = unt + drive + filename

    try:
        if os.name != "nt":
            return

        length = len(path) - 259
        if length < 1:
            return

        dirname, basename = os.path.split(filename)
        name, ext = os.path.splitext(basename)
        path = unt + drive + dirname + truncate(name, length) + ext

    finally:
        return path


def safejoin(*args):
    """
    os.path.join + safepath
    """
    return safepath(os.path.join(*args))


def safename(value):
    """
    Remove invalid characters
    """
    # repl = '<>:"/\\|?*' if os.name == "nt" else '\0/\\"'
    repl = '<>:"/\\|?*\0'
    name = remove_chars(value, repl)
    return name


def parse_name(value, safechar=True):
    path = urllib.unquote(decode(value))

    try:
        path = path.encode('latin1').decode('utf8')
    except (UnicodeEncodeError, UnicodeDecodeError):
        pass

    #: 'unicode-escape' that work with unicode strings too
    path = re.sub(r'\\[uU](\d{4})', lambda x: unichr(int(x.group(1))), path)

    #: Decode HTML escape
    path = html_unescape(path)

    #: Decode rfc2047
    path = rfc2047_dec(path)

    #: Remove redundant '/'
    path = re.sub(r'(?<!:)/{2,}', '/', path).strip().lstrip('.')
    path = path.replace('?', '_') # ? is bad for filenames

    url_p = urlparse.urlparse(path.rstrip('/'))
    name = (url_p.path.split('/')[-1] or
            url_p.query.split('=', 1)[::-1][0].split('&', 1)[0] or
            url_p.netloc.split('.', 1)[0])

    name = os.path.basename(name)

    return safename(name) if safechar else name


def parse_size(value, unit=""):  #: returns bytes
    m = re.match(r'((?:[\d.,]*)\d)\s*([\w^_]*)', str(value).lower())

    if m is None:
        return 0

    if re.match(r'\d{1,3}(?:,\d{3})+(?:\.\d+)?$', m.group(1)):
        size = float(m.group(1).replace(',', ''))

    elif re.match(r'\d+,\d{2}$', m.group(1)):
        size = float(m.group(1).replace(',', '.'))

    elif re.match(r'\d+(?:\.\d+)?$', m.group(1)):
        size = float(m.group(1))

    else:
        return 0  #: Unknown format

    unit = (unit.strip().lower() or m.group(2) or "byte")[0]

    if unit == "b":
        return int(size)

    sizeunits = ['b', 'k', 'm', 'g', 't', 'p', 'e']
    sizemap = dict((u, i * 10) for i, u in enumerate(sizeunits))
    magnitude = sizemap[unit]

    i, d = divmod(size, 1)
    integer = int(i) << magnitude
    decimal = int(d * (1024 ** (magnitude / 10)))

    return integer + decimal


def str2int(value):
    try:
        return int(value)
    except:
        pass

    ones = ("zero", "one", "two", "three", "four", "five", "six", "seven", "eight",
            "nine", "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen",
            "sixteen", "seventeen", "eighteen", "nineteen")
    tens = ("", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety")

    o_tuple = [(w, i) for i, w in enumerate(ones)]
    t_tuple = [(w, i * 10) for i, w in enumerate(tens)]

    numwords = dict(o_tuple + t_tuple)
    tokens = re.split(r'[\s\-]+', value.lower())

    try:
        return sum(numwords[word] for word in tokens)
    except:
        return 0


def parse_time(value):
    if re.search("(?:(?:this|a|an|next)\s+day)|today|daily", value):
        seconds = seconds_to_midnight()

    else:
        _re = re.compile(r'(\d+| (?:this|an?) )\s*(day|hr|hour|min|sec|)', re.I)
        seconds = sum((int(v) if v.strip() not in ("this", "a", "an") else 1) *
                      {'day': 86400, 'hr': 3600, 'hour': 3600, 'min': 60, 'sec': 1, '': 1}[u.lower()]
                      for v, u in _re.findall(value))
    return seconds


def timestamp():
    return int(time.time() * 1000)


def check_module(module):
    try:
        __import__(module)

    except Exception:
        return False

    else:
        return True


def check_prog(command):
    pipe = subprocess.PIPE
    try:
        subprocess.call(command, stdout=pipe, stderr=pipe)

    except Exception:
        return False

    else:
        return True


def isexecutable(filename):
    file = fs_encode(filename)
    return os.path.isfile(file) and os.access(file, os.X_OK)


def which(filename):
    """
    Works exactly like the unix command which
    Courtesy of http://stackoverflow.com/a/377028/675646
    """
    dirname, basename = os.path.split(filename)

    if dirname:
        return filename if isexecutable(filename) else None

    else:
        for path in os.environ['PATH'].split(os.pathsep):
            filename = os.path.join(path.strip('"'), filename)
            if isexecutable(filename):
                return filename


def format_exc(frame=None):
    """
    Format call-stack and display exception information (if available)
    """
    exc_info = sys.exc_info()
    exc_desc = u""

    callstack = traceback.extract_stack(frame)
    callstack = callstack[:-1]

    if exc_info[0] is not None:
        exception_callstack = traceback.extract_tb(exc_info[2])

        # @NOTE: Does this exception belongs to us?
        if callstack[-1][0] == exception_callstack[0][0]:
            callstack = callstack[:-1]
            callstack.extend(exception_callstack)
            exc_desc = decode("".join(traceback.format_exception_only(exc_info[0], exc_info[1])))

    msg = u"Traceback (most recent call last):\n"
    msg += decode("".join(traceback.format_list(callstack)))
    msg += exc_desc

    return msg


def seconds_to_nexthour(strict=False):
    now = datetime.datetime.today()
    nexthour = now.replace(minute=0 if strict else 1, second=0, microsecond=0) + datetime.timedelta(hours=1)
    return (nexthour - now).seconds


def seconds_to_midnight(utc=None, strict=False):
    if isinstance(utc, int):
        now = datetime.datetime.utcnow() + datetime.timedelta(hours=utc)
    else:
        now = datetime.datetime.today()

    midnight = now.replace(hour=0, minute=0 if strict else 1, second=0, microsecond=0) + datetime.timedelta(days=1)

    return (midnight - now).seconds


def search_pattern(pattern, value, flags=0):
    try:
        pattern, reflags = pattern

    except ValueError:
        reflags = 0

    except TypeError:
        return None

    try:
        return re.search(pattern, value, reflags | flags)
    except TypeError:
        return None


def replace_patterns(value, rules):
    for r in rules:
        try:
            pattern, repl, flags = r

        except ValueError:
            pattern, repl = r
            flags = 0

        value = re.sub(pattern, repl, value, flags)

    return value


# @TODO: Remove in 0.4.10 and fix exp in CookieJar.setCookie
def set_cookie(cj, domain, name, value, path='/', exp=time.time() + 180 * 24 * 3600):
    args = map(encode, [domain, name, value, path]) + [int(exp)]
    return cj.setCookie(*args)


def set_cookies(cj, cookies):
    for cookie in cookies:
        if not isinstance(cookie, tuple):
            continue

        if len(cookie) != 3:
            continue

        set_cookie(cj, *cookie)


def parse_html_header(header):
    hdict = {}
    _re = r'[ ]*(?P<key>.+?)[ ]*:[ ]*(?P<value>.+?)[ ]*\r?\n'

    for key, value in re.findall(_re, header):
        key = key.lower()
        if key in hdict:
            header_key = hdict.get(key)
            if isinstance(header_key, list):
                header_key.append(value)
            else:
                hdict[key] = [header_key, value]
        else:
            hdict[key] = value

    return hdict


def parse_html_tag_attr_value(attr_name, tag):
    m = re.search(r'%s\s*=\s*(["\']?)((?<=")[^"]+|(?<=\')[^\']+|[^>\s"\'][^>\s]*)\1' % attr_name, tag, re.I)
    return m.group(2) if m else None


def parse_html_form(attr_filter, html, input_names={}):
    attr_str = "" if callable(attr_filter) else attr_filter
    for form in re.finditer(r'(?P<TAG><form[^>]*%s.*?>)(?P<CONTENT>.*?)</?(form|body|html).*?>' % attr_str, html,
                            re.I | re.S):
        if callable(attr_filter) and not attr_filter(form.group('TAG')):
            continue

        inputs = {}
        action = parse_html_tag_attr_value("action", form.group('TAG'))

        for inputtag in re.finditer(r'(<(input|textarea).*?>)([^<]*(?=</\2)|)',
                                    re.sub(re.compile(r'<!--.+?-->', re.I | re.S), "", form.group('CONTENT')),
                                    re.I | re.S):

            name = parse_html_tag_attr_value("name", inputtag.group(1))
            if name:
                value = parse_html_tag_attr_value("value", inputtag.group(1))
                if not value:
                    inputs[name] = inputtag.group(3) or ""
                else:
                    inputs[name] = value

        if not input_names:
            #: No attribute check
            return action, inputs
        else:
            #: Check input attributes
            for key, value in input_names.items():
                if key in inputs:
                    if isinstance(value, basestring) and inputs[key] == value:
                        continue
                    elif isinstance(value, tuple) and inputs[key] in value:
                        continue
                    elif hasattr(value, "search") and re.match(value, inputs[key]):
                        continue
                    else:
                        break  #: Attibute value does not match
                else:
                    break  #: Attibute name does not match
            else:
                return action, inputs  #: Passed attribute check

    return None, None  #: No matching form found


def chunks(iterable, size):
    it = iter(iterable)
    item = list(itertools.islice(it, size))
    while item:
        yield item
        item = list(itertools.islice(it, size))


def renice(pid, value):
    if not value or os.name == "nt":
        return

    try:
        Popen(["renice", str(value), str(pid)],
              stdout=subprocess.PIPE,
              stderr=subprocess.PIPE,
              bufsize=-1)
    except Exception:
        pass


def forward(source, destination):
    try:
        bufsize = 1024
        bufdata = source.recv(bufsize)
        while bufdata:
            destination.sendall(bufdata)
            bufdata = source.recv(bufsize)
    finally:
        destination.shutdown(socket.SHUT_WR)


def compute_checksum(filename, hashtype):
    file = fs_encode(filename)

    if not exists(file):
        return None

    buf = fsbsize(filename)

    if hashtype in ("adler32", "crc32"):
        hf = getattr(zlib, hashtype)
        last = 0

        with open(file, "rb") as f:
            for chunk in iter(lambda: f.read(buf), ''):
                last = hf(chunk, last)

        return "%x" % last

    elif hashtype in hashlib.algorithms_available:
        h = hashlib.new(hashtype)

        with open(file, "rb") as f:
            for chunk in iter(lambda: f.read(buf * h.block_size), ''):
                h.update(chunk)

        return h.hexdigest()

    else:
        return None


def copy_tree(src, dst, overwrite=False, preserve_metadata=False):
    pmode = preserve_metadata or overwrite is None
    mtime = os.path.getmtime
    copy = shutil.copy2 if pmode else shutil.copy

    if preserve_metadata and not exists(dst):
        return shutil.copytree(src, dst)

    for src_dir, dirs, files in os.walk(src, topdown=False):
        dst_dir = src_dir.replace(src, dst, 1)

        if not exists(dst_dir):
            os.makedirs(dst_dir)
            if pmode:
                shutil.copystat(src_dir, dst_dir)

        elif pmode:
            if overwrite or overwrite is None and mtime(src_dir) > mtime(dst_dir):
                shutil.copystat(src_dir, dst_dir)

        for filename in files:
            src_file = fsjoin(src_dir, filename)
            dst_file = fsjoin(dst_dir, filename)

            if exists(dst_file):
                if overwrite or overwrite is None and mtime(src_file) > mtime(dst_file):
                    os.remove(dst_file)
                else:
                    continue

            copy(src_file, dst_dir)


def move_tree(src, dst, overwrite=False):
    mtime = os.path.getmtime

    for src_dir, dirs, files in os.walk(src, topdown=False):
        dst_dir = src_dir.replace(src, dst, 1)
        del_dir = True

        if not exists(dst_dir):
            os.makedirs(dst_dir)
            shutil.copystat(src_dir, dst_dir)

        elif overwrite or overwrite is None and mtime(src_dir) > mtime(dst_dir):
            shutil.copystat(src_dir, dst_dir)

        else:
            del_dir = False

        for filename in files:
            src_file = fsjoin(src_dir, filename)
            dst_file = fsjoin(dst_dir, filename)

            if exists(dst_file):
                if overwrite or overwrite is None and mtime(src_file) > mtime(dst_file):
                    os.remove(dst_file)
                else:
                    continue

            shutil.move(src_file, dst_dir)

        if not del_dir:
            continue

        try:
            os.rmdir(src_dir)
        except OSError:
            pass


"""
subprocess.Popen doesn't support unicode on Windows
## https://bugs.python.org/issue19264
"""
if os.name != "nt":
    from subprocess import Popen

else:
    import ctypes
    import subprocess
    import _subprocess
    from ctypes import byref, windll, c_char_p, c_wchar_p, c_void_p, Structure, sizeof, c_wchar, WinError
    from ctypes.wintypes import BYTE, WORD, LPWSTR, BOOL, DWORD, LPVOID, HANDLE

    ##
    ## Types
    ##
    CREATE_UNICODE_ENVIRONMENT = 0x00000400
    LPCTSTR = c_char_p
    LPTSTR = c_wchar_p
    LPSECURITY_ATTRIBUTES = c_void_p
    LPBYTE = ctypes.POINTER(BYTE)


    class STARTUPINFOW(Structure):
        _fields_ = [
            ("cb", DWORD),
            ("lpReserved", LPWSTR),
            ("lpDesktop", LPWSTR),
            ("lpTitle", LPWSTR),
            ("dwX", DWORD),
            ("dwY", DWORD),
            ("dwXSize", DWORD),
            ("dwYSize", DWORD),
            ("dwXCountChars", DWORD),
            ("dwYCountChars", DWORD),
            ("dwFillAtrribute", DWORD),
            ("dwFlags", DWORD),
            ("wShowWindow", WORD),
            ("cbReserved2", WORD),
            ("lpReserved2", LPBYTE),
            ("hStdInput", HANDLE),
            ("hStdOutput", HANDLE),
            ("hStdError", HANDLE),
        ]


    LPSTARTUPINFOW = ctypes.POINTER(STARTUPINFOW)


    class PROCESS_INFORMATION(Structure):
        _fields_ = [
            ("hProcess", HANDLE),
            ("hThread", HANDLE),
            ("dwProcessId", DWORD),
            ("dwThreadId", DWORD),
        ]


    LPPROCESS_INFORMATION = ctypes.POINTER(PROCESS_INFORMATION)


    class DUMMY_HANDLE(ctypes.c_void_p):
        def __init__(self, *args, **kwargs):
            super(DUMMY_HANDLE, self).__init__(*args, **kwargs)
            self.closed = False

        def Close(self):
            if not self.closed:
                windll.kernel32.CloseHandle(self)
                self.closed = True

        def __int__(self):
            return self.value


    CreateProcessW = windll.kernel32.CreateProcessW
    CreateProcessW.argtypes = [LPCTSTR, LPTSTR, LPSECURITY_ATTRIBUTES,
                               LPSECURITY_ATTRIBUTES, BOOL, DWORD, LPVOID, LPCTSTR,
                               LPSTARTUPINFOW, LPPROCESS_INFORMATION, ]
    CreateProcessW.restype = BOOL


    def CreateProcess(executable, args, _p_attr, _t_attr, inherit_handles, creation_flags, env, cwd, startup_info):
        """
        Create a process supporting unicode executable and args for win32
        Python implementation of CreateProcess using CreateProcessW for Win32
        """
        si = STARTUPINFOW(
            dwFlags=startup_info.dwFlags,
            wShowWindow=startup_info.wShowWindow,
            cb=sizeof(STARTUPINFOW),
            hStdInput=0 if startup_info.hStdInput is None else int(startup_info.hStdInput),
            hStdOutput=0 if startup_info.hStdOutput is None else int(startup_info.hStdOutput),
            hStdError=0 if startup_info.hStdError is None else int(startup_info.hStdError),
        )

        wenv = None
        if env is not None:
            ## LPCWSTR seems to be c_wchar_p, so let's say CWSTR is c_wchar
            env = (u"".join([u"%s=%s\0" % (k, v)
                             for k, v in env.items()])) + u"\0"
            wenv = (c_wchar * len(env))()
            wenv.value = env

        pi = PROCESS_INFORMATION()
        creation_flags |= CREATE_UNICODE_ENVIRONMENT

        if CreateProcessW(executable, args, None, None, inherit_handles, creation_flags,
                          wenv, cwd, byref(si), byref(pi)):
            return (DUMMY_HANDLE(pi.hProcess), DUMMY_HANDLE(pi.hThread), pi.dwProcessId, pi.dwThreadId)
        raise WinError()


    class Popen(subprocess.Popen):
        """
        This supersedes Popen and corrects a bug in cPython implementation
        """

        def _execute_child(self, args, executable, preexec_fn, close_fds,
                           cwd, env, universal_newlines,
                           startupinfo, creationflags, shell, to_close,
                           p2cread, p2cwrite,
                           c2pread, c2pwrite,
                           errread, errwrite):

            if not isinstance(args, subprocess.types.StringTypes):
                args = subprocess.list2cmdline(args)

            if startupinfo is None:
                startupinfo = subprocess.STARTUPINFO()
            if shell:
                startupinfo.dwFlags |= _subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = _subprocess.SW_HIDE
                comspec = os.environ.get("COMSPEC", u"cmd.exe")
                args = u'%s /c "%s"' % (comspec, args)
                if _subprocess.GetVersion() >= 0x80000000 or os.path.basename(comspec).lower() == "command.com":
                    w9xpopen = self._find_w9xpopen()
                    args = u'"%s" %s' % (w9xpopen, args)
                    creationflags |= _subprocess.CREATE_NEW_CONSOLE

            super(Popen, self)._execute_child(args, executable, preexec_fn, close_fds,
                                              cwd, env, universal_newlines,
                                              startupinfo, creationflags, False, to_close,
                                              p2cread, p2cwrite,
                                              c2pread, c2pwrite,
                                              errread, errwrite)


    _subprocess.CreateProcess = CreateProcess


class BIGHTTPRequest(HTTPRequest):
    """
    Overcome HTTPRequest's load() size limit to allow
    loading very big web pages by overriding HTTPRequest's write() function
    """

    # @TODO: Add 'limit' parameter to HTTPRequest in v0.4.10
    def __init__(self, cookies=None, options=None, limit=1000000):
        self.limit = limit
        HTTPRequest.__init__(self, cookies=cookies, options=options)

    def write(self, buf):
        """ writes response """
        if self.limit and self.rep.tell() > self.limit or self.abort:
            rep = self.getResponse()
            if self.abort:
                raise Abort()
            f = open("response.dump", "wb")
            f.write(rep)
            f.close()
            raise Exception("Loaded Url exceeded limit")

        self.rep.write(buf)
