'''
    OneDrive for Kodi
    Copyright (C) 2015 - Carlos Guzman

    This program is free software; you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation; either version 2 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License along
    with this program; if not, write to the Free Software Foundation, Inc.,
    51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

    Created on Mar 1, 2015
    @author: Carlos Guzman (cguZZman) carlosguzmang@hotmail.com
'''
from clouddrive.common.messaging.listener import CloudDriveMessagingListerner
from clouddrive.common.ui.addon import CloudDriveAddon
from clouddrive.common.utils import Utils
from resources.lib.provider.onedrive import OneDrive
import datetime
from clouddrive.common.cache.simplecache import SimpleCache
import urllib


class OneDriveAddon(CloudDriveAddon, CloudDriveMessagingListerner):
    _provider = OneDrive()
    _extra_parameters = {'expand': 'thumbnails'}
    _cache = None
    
    def __init__(self):
        self._cache = SimpleCache()
        self._cache.enable_mem_cache = False
        super(OneDriveAddon, self).__init__()
        
    def get_provider(self):
        return self._provider
    
    def get_folder_items(self):
        driveid = self._addon_params.get('driveid', [None])[0]
        item_id = self._addon_params.get('item_id', [None])[0]
        if item_id:
            item_driveid = self._addon_params.get('item_driveid', [driveid])[0]
            files = self._provider.get('/drives/'+item_driveid+'/items/' + item_id + '/children', parameters = self._extra_parameters)
        else:
            folder = self._addon_params.get('folder', [None])[0]
            files = self._provider.get('/drives/'+driveid+'/' + folder + '/children', parameters = self._extra_parameters)
        if self.cancel_operation():
            return
        return self.process_files(files)
    
    def process_files(self, files):
        items = []
        for f in files['value']:
            f = Utils.get_safe_value(f, 'remoteItem', f)
            item = self._extract_item(f)
            cache_key = self._addon_id+'-'+'item-'+item['drive_id']+'-'+item['id']
            self._cache.set(cache_key, f, expiration=datetime.timedelta(seconds=30))
            items.append(item)
        if '@odata.nextLink' in files:
            next_files = self._provider.get(files['@odata.nextLink'])
            if self.cancel_operation():
                return
            items.extend(self.process_files(next_files))
        return items
    
    def _extract_item(self, f, include_download_info=False):
        item = {
            'id': f['id'],
            'name': f['name'],
            'name_extension' : Utils.get_extension(f['name']),
            'drive_id' : Utils.get_safe_value(Utils.get_safe_value(f, 'parentReference', {}), 'driveId'),
            'mimetype' : Utils.get_safe_value(Utils.get_safe_value(f, 'file', {}), 'mimeType')
        }
        if 'folder' in f:
            item['folder'] = {}
        if 'video' in f:
            video = f['video']
            item['video'] = {
                'width' : video['width'],
                'height' : video['height'],
                'duration' : video['duration']/1000
            }
        if 'audio' in f:
            audio = f['audio']
            item['audio'] = {
                'tracknumber' : Utils.get_safe_value(audio, 'track'),
                'discnumber' : Utils.get_safe_value(audio, 'disc'),
                'duration' : int(Utils.get_safe_value(audio, 'duration') or '0') / 1000,
                'year' : Utils.get_safe_value(audio, 'year'),
                'genre' : Utils.get_safe_value(audio, 'genre'),
                'album': Utils.get_safe_value(audio, 'album'),
                'artist': Utils.get_safe_value(audio, 'artist'),
                'title': Utils.get_safe_value(audio, 'title')
            }
        if 'image' in f or 'photo' in f:
            item['image'] = {
                'size' : f['size']
            }
        if 'thumbnails' in f and len(f['thumbnails']) > 0:
            thumbnails = f['thumbnails'][0]
            item['thumbnails'] = thumbnails['large']['url']
        if include_download_info:
            item['download_info'] =  {
                'url' : Utils.get_safe_value(f,'@microsoft.graph.downloadUrl'),
                'headers' : {
                    'authorization' : 'Bearer ' + self._provider.get_access_tokens()['access_token']
                }
            }
        return item
    
    def get_item(self, driveid, item_driveid, item_id, find_subtitles=False, include_download_info=False):
        self._provider.configure(self._account_manager, driveid)
        cache_key = self._addon_id+'-'+'item-'+item_driveid+'-'+item_id
        f = self._cache.get(cache_key)
        if not f :
            f = self._provider.get('/drives/'+item_driveid+'/items/' + item_id, parameters = self._extra_parameters)
            self._cache.set(cache_key, f, expiration=datetime.timedelta(seconds=30))
        item = self._extract_item(f, include_download_info)
        if find_subtitles:
            subtitles = []
            parent_id = Utils.get_safe_value(Utils.get_safe_value(f, 'parentReference', {}), 'id')
            search_url = '/drives/'+item_driveid+'/items/' + parent_id + '/search(q=\'{'+urllib.quote(Utils.remove_extension(item['name']))+'}\')'
            files = self._provider.get(search_url)
            for f in files['value']:
                subtitle = self._extract_item(f, include_download_info)
                if subtitle['name_extension'] == 'srt' or subtitle['name_extension'] == 'sub' or subtitle['name_extension'] == 'sbv':
                    subtitles.append(subtitle)
            if subtitles:
                item['subtitles'] = subtitles
        return item

if __name__ == '__main__':
    OneDriveAddon().route()

