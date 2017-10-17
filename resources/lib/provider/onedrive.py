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
from clouddrive.common.remote.provider import Provider
from clouddrive.common.utils import Utils


class OneDrive(Provider):
    __api_url = 'https://graph.microsoft.com/v1.0'
    
    def __init__(self):
        super(OneDrive, self).__init__('onedrive')
        
    def _get_api_url(self):
        return self.__api_url

    def _get_request_headers(self):
        return None
    
    def get_account(self, request_params={}, access_tokens={}):
        me = self.get('/me', request_params=request_params, access_tokens=access_tokens)
        if not me:
            raise Exception('NoAccountInfo')
        return { 'id' : me['id'], 'name' : me['displayName']}
    
    def get_drives(self, request_params={}, access_tokens={}):
        response = self.get('/drives', request_params=request_params, access_tokens=access_tokens)
        drives = []
        drives_id_list  =[]
        for drive in response['value']:
            drives_id_list.append(drive['id'])
            drives.append({
                'id' : drive['id'],
                'name' : Utils.get_safe_value(drive, 'name', ''),
                'type' : drive['driveType']
            })
        
        response = self.get('/me/drives', request_params=request_params, access_tokens=access_tokens)
        for drive in response['value']:
            if not drive['id'] in drives_id_list:
                drives_id_list.append(drive['id'])
                drives.append({
                    'id' : drive['id'],
                    'name' : Utils.get_safe_value(drive, 'name', ''),
                    'type' : drive['driveType']
                })
        return drives
    
    def get_drive_type_name(self, drive_type):
        if drive_type == 'personal':
            return 'OneDrive Personal'
        if drive_type == 'business':
            return 'OneDrive for Business'
        if drive_type == 'documentLibrary':
            return ' SharePoint Document Library'
        return drive_type
    
    