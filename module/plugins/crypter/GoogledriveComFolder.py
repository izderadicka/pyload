# -*- coding: utf-8 -*

from module.network.HTTPRequest import BadHeader

from ..internal.Crypter import Crypter
from ..internal.misc import json


class GoogledriveComFolder(Crypter):
    __name__ = "GoogledriveComFolder"
    __type__ = "crypter"
    __version__ = "0.14"
    __status__ = "testing"

    __pattern__ = r'https?://(?:www\.)?drive\.google\.com/(?:folderview\?.*id=|drive/(?:.+?/)?folders/)(?P<ID>[-\w]+)'
    __config__ = [("activated", "bool", "Activated", True),
                  ("use_premium", "bool", "Use premium account if available", True),
                  ("folder_per_package", "Default;Yes;No", "Create folder for each package", "Default"),
                  ("max_wait", "int", "Reconnect if waiting time is greater than minutes", 10),
                  ("dl_subfolders", "bool", "Download subfolders", False),
                  ("package_subfolder", "bool", "Subfolder as a seperate package", False)]

    __description__ = """Drive.google.com folder decrypter plugin"""
    __license__ = "GPLv3"
    __authors__ = [("Walter Purcaro", "vuolter@gmail.com"),
                   ("GammaC0de", "nitzo2001[AT]yahoo[DOT]com")]

    NAME_PATTERN = r"folderName: '(?P<N>.+?)'"
    OFFLINE_PATTERN = r'<TITLE>'

    API_URL = "https://www.googleapis.com/drive/v3/"
    API_KEY = "AIzaSyB68u-qFPP9oBJpo1DWAPFE_VD2Sfy9hpk"

    def api_response(self, cmd, **kwargs):
        kwargs['key'] = self.API_KEY
        try:
            json_data = json.loads(self.load("%s%s" % (self.API_URL, cmd),
                                             get=kwargs))
            self.log_debug("API response: %s" % json_data)
            return json_data

        except BadHeader, e:
            try:
                json_data = json.loads(e.content)
                self.log_error("API Error: %s" % cmd,
                               json_data['error']['message'],
                               "ID: %s" % self.info['pattern']['ID'],
                               "Error code: %s" % e.code)

            except ValueError:
                self.log_error("API Error: %s" % cmd,
                               e,
                               "ID: %s" % self.info['pattern']['ID'],
                               "Error code: %s" % e.code)
            return None

    def enum_folder(self, folder_id):
        links = []
        json_data = self.api_response("files", q="'%s' in parents" % folder_id,
                                      pageSize=100,
                                      fields="files/id,files/mimeType,nextPageToken",
                                      supportsAllDrives="true",
                                      includeItemsFromAllDrives="true")

        if json_data is None:
            self.fail("API error")

        if 'error' in json_data:
            self.fail(json_data['error']['message'])

        for _f in json_data.get('files', []):
            if _f['mimeType'] != "application/vnd.google-apps.folder":
                links.append("https://drive.google.com/file/d/" + _f['id'])

            elif self.config.get('dl_subfolders'):
                if self.config.get('package_subfolder'):
                    links.append(
                        "https://drive.google.com/drive/folders/" + _f['id'])

                else:
                    links.extend(self.enum_folder(_f['id']))

        next_page = json_data.get('nextPageToken', None)
        while next_page:
            json_data = self.api_response("files", q="'%s' in parents" % folder_id,
                                          pageToken=next_page,
                                          pageSize=100,
                                          fields="files/id,files/mimeType,nextPageToken",
                                          supportsAllDrives="true",
                                          includeItemsFromAllDrives="true")

            if json_data is None:
                self.fail("API error")

            if 'error' in json_data:
                self.fail(json_data['error']['message'])

            for _f in json_data.get('files', []):
                if _f['mimeType'] != "application/vnd.google-apps.folder":
                    links.append("https://drive.google.com/file/d/" + _f['id'])

                elif self.config.get('dl_subfolders'):
                    if self.config.get('package_subfolder'):
                        links.append(
                            "https://drive.google.com/drive/folders/" + _f['id'])

                    else:
                        links.extend(self.enum_folder(_f['id']))

            next_page = json_data.get('nextPageToken', None)

        return links

    def decrypt(self, pyfile):
        links = []

        json_data = self.api_response("files/%s" % self.info['pattern']['ID'],
                                      supportsAllDrives="true")
        if json_data is None:
            self.fail("API error")

        if 'error' in json_data:
            if json_data['error']['code'] == 404:
                self.offline()

            else:
                self.fail(json_data['error']['message'])

        pack_name = json_data.get('name', pyfile.package().name)

        links = self.enum_folder(self.info['pattern']['ID'])

        if links:
            self.packages = [(pack_name, links, pack_name)]
