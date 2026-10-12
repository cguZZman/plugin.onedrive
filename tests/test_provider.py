import unittest

import stubs  # noqa: F401
import kodistubs
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

    def test_search_filter_does_not_leak_into_listings(self):
        d = FakeOneDrive({"/drives/drv/search(q='x')": {'value': []}, '/drives/drv/items/f/children': {'value': []}})
        d.search('x')
        d.get_folder_items(item_id='f')
        self.assertEqual(d.calls[0][1]['filter'], 'file ne null')
        self.assertNotIn('filter', d.calls[1][1])


if __name__ == '__main__':
    unittest.main()
