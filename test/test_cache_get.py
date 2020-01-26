import requests
import requests.exceptions
from shelfcache import cache_get
import unittest
from unittest.mock import MagicMock
from shelfcache.shelfcache import CacheResult

NOT_MODIFIED = 304
OK = 200

ATOM_PATH = 'test/test_atom.xml'


def mock_shelfcache(return_value=None):
    """Helper function to create a mocked ShelfCache instance.

    Args:
        return_value: the value returned by the mocked shelf.get() method
    """
    mock_shelf = MagicMock()
    mock_shelf.exp_seconds = -1
    mock_get = MagicMock(return_value=return_value)
    mock_shelf.get = mock_get
    return mock_shelf


def build_response(status=OK, etag='etag', modified='modified', max_age=None):
    """Make a requests.Response object suitable for testing.

    Args:
        status: HTTP status
        exp-time: cache expire time (set to future for fresh cache, past for
            stale cache (defaults to stale))
        etag: etag cache-control header
        modified: last-modified cache-control header

    Returns:
        A Response instance populated according to the arguments.
    """
    headers = {'last-modified': modified, 'etag': etag, 'Cache-Control':
               'max-age={}'.format(max_age)}
    test_response = requests.Response()
    test_response.status_code = status
    test_response.headers = headers
    return test_response


def build_getter(return_value):
    """Build a mock requests.get method.

    Args:
        return_value: the value to be returned by the call to `get()`
        (probably a requests.Response object.

    Returns:
        A MagicMock instance spec'd to requests.get
    """
    mock_getter = MagicMock(spec=requests.get)
    mock_getter.return_value = return_value
    return mock_getter


class TestCacheGet(unittest.TestCase):

    def test_new(self):
        """Simulate a URL not in the cache, and verify that cache_get tries to
        fetch it over http."""
        # setup mock locked_shelf:
        new = build_response()
        mock_shelf = mock_shelfcache(None)

        # setup mock requests.get method
        mock_getter = build_getter(new)

        # DUT:
        resp = cache_get(mock_shelf, url='fake_url', get_meth=mock_getter)

        self.assertEqual(resp, new)
        mock_getter.assert_called_once_with('fake_url', headers={})

    def test_fresh(self):
        """Simulate a freshly cached resource and verify that cache_get returns
        it."""
        # setup mock locked_shelf:
        fresh = build_response()
        mock_shelf = mock_shelfcache(CacheResult(data=fresh,
                                                 expired=False))

        # setup mock requests.get method
        mock_getter = build_getter(fresh)

        # DUT:
        resp = cache_get(mock_shelf, url='fake_url', get_meth=mock_getter)

        self.assertEqual(resp, fresh)
        # since resource is fresh, assert that the http client is not called:
        mock_getter.assert_not_called()

    def test_stale_not_modified(self):
        """Simulate a stale cached item and verify that cache_get fetches it and
        then asks the remote server for an updated."""
        # setup mocked ShelfCache
        stale = build_response(status=NOT_MODIFIED)
        mock_shelf = mock_shelfcache(CacheResult(data=stale,
                                                 expired=True))

        # setup mock requests.get method
        mock_getter = build_getter(stale)

        # DUT:
        resp = cache_get(mock_shelf, url='fake_url', get_meth=mock_getter)

        h = {'If-None-Match': 'etag', 'If-Modified-Since': 'modified'}
        mock_getter.assert_called_once_with('fake_url', headers=h)
        self.assertEqual(resp, stale)

    def test_stale_modified(self):
        """Simulate a stale cached item and verify that cache_get fetches it and
        then updates with new resource from server."""
        # setup mocked ShelfCache
        stale = build_response(status=OK)
        mock_shelf = mock_shelfcache(CacheResult(data=stale,
                                                 expired=True))

        # setup mock requests.get method (and mock headers so we can verify
        # that the cache-control header was used)
        mock_headers = MagicMock(spec=dict)
        mock_headers.get.return_value = 'max-age=10'
        new = build_response(status=OK)
        new.headers = mock_headers
        mock_getter = build_getter(new)

        # instantiate DUT:
        resp = cache_get(mock_shelf, url='fake_url', get_meth=mock_getter)

        h = {'If-None-Match': 'etag', 'If-Modified-Since': 'modified'}
        mock_getter.assert_called_once_with('fake_url', headers=h)
        mock_headers.get.assert_called_with('cache-control')

        # Make sure resource was updated:
        mock_shelf.create_or_update.assert_called_with('fake_url',
                                                       data=new,
                                                       exp_seconds=10)
        self.assertEqual(resp, new)

    def test_404(self):
        """Simulate fetching a non-existent resource."""
        # setup mocked ShelfCache
        feed404 = build_response(status=404)
        mock_shelf = mock_shelfcache(None)

        # setup mock requests.get
        mock_getter = build_getter(feed404)

        with self.assertRaises(requests.exceptions.HTTPError) as e:
            cache_get(mock_shelf, url='http://notfound/', get_meth=mock_getter)
        self.assertEqual(404, e.exception.response.status_code)
        mock_getter.assert_called_once_with('http://notfound/', headers={})
