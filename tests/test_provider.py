import unittest
from urllib.error import HTTPError

import stubs  # noqa: F401
import kodistubs
from clouddrive.common.exception import RequestException
from resources.lib.provider.onedrive import OneDrive

kodistubs.use_temp_profile()


def item(item_id, name, **extra):
    f = {'id': item_id, 'name': name, 'size': 5, 'lastModifiedDateTime': '2026-10-01T10:00:00Z',
         'parentReference': {'driveId': 'drv', 'id': 'parent'}, 'file': {'mimeType': 'video/mp4'},
         '@microsoft.graph.downloadUrl': 'https://download.example.com/' + item_id}
    f.update(extra)
    return f


class FakeOneDrive(OneDrive):
    def __init__(self, pages):
        super(FakeOneDrive, self).__init__()
        self.pages = pages
        self.calls = []
        self._driveid = 'drv'

    def get(self, url, parameters=None, **kwargs):
        self.calls.append((url, dict(parameters or {})))
        if url not in self.pages:
            raise RequestException('Not found', HTTPError(url, 404, 'Not found', None, None), url, None)
        return self.pages[url]


class OneDriveProviderTest(unittest.TestCase):
    def test_pages_follow_next_link(self):
        d = FakeOneDrive({
            '/drives/drv/items/f/children': {'value': [item('a', 'a.mp4')], '@odata.nextLink': 'https://graph/next'},
            'https://graph/next': {'value': [item('b', 'b.mp4')]}})
        self.assertEqual([i['id'] for i in d.get_folder_items(item_id='f', include_download_info=True)], ['a', 'b'])

    def test_item_mapping(self):
        f = item('a', 'Movie.MP4', video={'width': 1280, 'height': 720, 'duration': 90000},
                 thumbnails=[{'large': {'url': 'https://thumb'}}])
        i = FakeOneDrive({})._extract_item(f, include_download_info=True)
        self.assertEqual((i['name_extension'], i['drive_id'], i['parent']), ('mp4', 'drv', 'parent'))
        self.assertEqual(i['video'], {'width': 1280, 'height': 720, 'duration': 90})
        self.assertEqual(i['thumbnail'], 'https://thumb')
        self.assertEqual(i['download_info']['url'], 'https://download.example.com/a')

    def test_shared_items_use_the_remote_item(self):
        shared = {'id': 'local', 'name': 'x', 'remoteItem': item('remote', 'shared.mp4')}
        d = FakeOneDrive({'/drives/drv/sharedWithMe': {'value': [shared]}})
        self.assertEqual(d.get_folder_items(path='sharedWithMe')[0]['id'], 'remote')

    def test_personal_accounts_keep_only_the_default_drive(self):
        drive = lambda drive_id, name: {'id': drive_id, 'name': name, 'driveType': 'personal'}
        # As Graph answers for a migrated account: both lists have the system drives, one with the default drive's id.
        listed = {'value': [drive('guid', 'AEEE102E-0000'), drive('main', 'Bundles_b'), drive('main', 'OneDrive'),
                            drive('archive', 'ODCMetadataArchive')]}
        d = FakeOneDrive({'/drives': listed, '/me/drives': listed, '/me/drive': drive('main', 'OneDrive')})
        self.assertEqual(d.get_drives(), [{'id': 'main', 'name': 'OneDrive', 'type': 'personal'}])

    def test_business_accounts_keep_every_drive(self):
        drive = lambda drive_id, drive_type: {'id': drive_id, 'name': drive_id, 'driveType': drive_type}
        d = FakeOneDrive({
            '/drives': {'value': [drive('library', 'documentLibrary')]},
            '/me/drive': drive('work', 'business'),
            '/me/drives': {'value': [drive('work', 'business'), drive('other', 'business')]}})
        self.assertEqual([x['id'] for x in d.get_drives()], ['library', 'work', 'other'])

    def test_shortcuts_to_shared_folders_keep_their_name(self):
        # "Add to My files": Graph answers the sharer's folder in remoteItem, without a name.
        remote = {'id': 'shared', 'folder': {'childCount': 2}, 'parentReference': {'driveId': 'friend'}}
        d = FakeOneDrive({'/drives/drv/root/children': {'value': [{'id': 'link', 'name': 'Holidays', 'remoteItem': remote}]}})
        [folder] = d.get_folder_items(path='/')
        self.assertEqual((folder['id'], folder['name'], folder['drive_id']), ('shared', 'Holidays', 'friend'))
        self.assertIn('folder', folder)

    def test_paths_continue_through_shortcuts(self):
        # Source mode lists by path: the shortcut is found by path, what's inside it by id in the sharer's drive.
        remote = {'id': 'shared', 'folder': {}, 'parentReference': {'driveId': 'friend'}}
        beach = {'id': 'beach', 'name': '2026 Beach', 'folder': {}, 'parentReference': {'driveId': 'friend', 'id': 'shared'}}
        d = FakeOneDrive({
            '/drives/drv/root:/Holidays:': {'id': 'link', 'name': 'Holidays', 'parentReference': {'driveId': 'drv'}, 'remoteItem': remote},
            '/drives/friend/items/shared/children': {'value': [item('a', 'a.mp4')]},
            '/drives/friend/items/shared:/2026%20Beach:': beach,
            '/drives/friend/items/beach/children': {'value': [item('b', 'b.mp4')]},
            '/drives/friend/items/shared:/2026%20Beach/b.mp4:': item('b', 'b.mp4', parentReference={'driveId': 'friend', 'id': 'beach'})})
        self.assertEqual([i['id'] for i in d.get_folder_items(path='/Holidays')], ['a'])
        self.assertEqual([i['id'] for i in d.get_folder_items(path='/Holidays/2026 Beach')], ['b'])
        b = d.get_item(path='/Holidays/2026 Beach/b.mp4')
        self.assertEqual((b['id'], b['drive_id']), ('b', 'friend'))

    def test_special_folders_are_listed_directly(self):
        d = FakeOneDrive({'/drives/drv/special/photos/children': {'value': [item('p', 'p.jpg')]}})
        self.assertEqual([i['id'] for i in d.get_folder_items(path='special/photos')], ['p'])
        self.assertEqual(len(d.calls), 1)

    def test_missing_paths_are_still_not_found(self):
        d = FakeOneDrive({'/drives/drv/root:/Movies:': {'id': 'm', 'folder': {}, 'parentReference': {'driveId': 'drv'}}})
        with self.assertRaises(RequestException):
            d.get_folder_items(path='/Movies/Nothing')

    def test_folder_signature_sees_replaced_pictures(self):
        listing = lambda *files: FakeOneDrive({'/drives/drv/items/f/children': {'value': list(files)}}).folder_signature(item_id='f')
        a, b = item('a', 'a.jpg'), item('b', 'b.jpg')
        self.assertEqual(listing(a, b), listing(b, a), 'the order does not matter')
        self.assertNotEqual(listing(a, b), listing(a, item('c', 'c.jpg')), 'one removed and another added: same count')
        self.assertNotEqual(listing(a), listing(item('a', 'a.jpg', lastModifiedDateTime='2026-10-31T00:00:00Z')), 'replaced')

    def test_subtitles_come_from_the_video_folder(self):
        d = FakeOneDrive({
            '/drives/drv/items/parent/children': {'value': [item('v', "It's.mkv"), item('s1', "It's.srt"), item('s2', "It's.EN.SRT")],
                                                  '@odata.nextLink': 'https://graph/next'},
            'https://graph/next': {'value': [item('x', "It's 2.srt"), item('n', "It's.nfo"), item('s3', "it's.forced.ass")]}})
        self.assertEqual([s['id'] for s in d.get_subtitles('parent', "It's.mkv")], ['s1', 's2', 's3'])
        self.assertNotIn('search', ' '.join(c[0] for c in d.calls))

    def test_search_filter_does_not_leak_into_listings(self):
        d = FakeOneDrive({"/drives/drv/search(q='x')": {'value': []}, '/drives/drv/items/f/children': {'value': []}})
        d.search('x')
        d.get_folder_items(item_id='f')
        self.assertEqual(d.calls[0][1]['filter'], 'file ne null')
        self.assertNotIn('filter', d.calls[1][1])


if __name__ == '__main__':
    unittest.main()


class PathAddressTest(unittest.TestCase):
    def test_names_in_paths_are_encoded(self):
        from resources.lib.provider.onedrive import OneDrive
        self.assertEqual(OneDrive._path_address('/'), 'root')
        self.assertEqual(OneDrive._path_address('/Apps/Clipchamp Classic'), 'root:/Apps/Clipchamp%20Classic:')
        self.assertEqual(OneDrive._path_address("/Movies/#1 It's 50%?"), "root:/Movies/%231%20It%27s%2050%25%3F:")
        self.assertEqual(OneDrive._path_address('/Apps/Clipchamp%20Classic'), 'root:/Apps/Clipchamp%20Classic:', 'already encoded paths too')
