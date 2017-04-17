import requests
from feedfetch import FeedCache
import unittest
from unittest.mock import MagicMock
from feedfetch.shelfcache import ShelfCache, Item, CacheResult
import feedparser
import datetime
from urllib.error import URLError
from http.client import NOT_MODIFIED, OK
from feedfetch.cache_get import cache_get

from test.test_cache_get import build_response, mock_shelfcache

ATOM_PATH = 'test/test_atom.xml'

with open(ATOM_PATH, 'r') as f:
    TEST_FEED = ''.join(f.readlines())


def build_getter(return_value):
    """Build a mock cache_get method.

    Args:
        return_value: the value to be returned by the call to `get()`
        (probably a requests.Response object.

    Returns:
        A MagicMock instance spec'd to cache_get
    """
    mock_getter = MagicMock(spec=cache_get)
    mock_getter.return_value = return_value
    return mock_getter


class TestFetch(unittest.TestCase):
    def test_new(self):
        """Simulate a URL not in the cache, and verify that FeedCache tries to
        fetch it over http."""
        # setup mock locked_shelf:
        new_feed = build_response()
        mock_shelf = mock_shelfcache(None)

        # setup mock feedparser.parse method
        mock_getter = build_getter(new_feed)

        # DUT:
        fc = FeedCache(db_path='dummy', cache=mock_shelf,
                       cache_get=mock_getter).fetch('fake_url')

        parsed = feedparser.parse(new_feed.text)
        self.assertEqual(fc, parsed)
        mock_getter.assert_called_once_with(mock_shelf, url='fake_url')

    def test_fresh(self):
        """Simulate a freshly cached feed and verify that FeedCache returns
        it."""
        # setup mock locked_shelf:
        fresh_feed = build_response()
        mock_shelf = mock_shelfcache(CacheResult(data=fresh_feed,
                                                 expired=False))

        # setup mock feedparser.parse method
        mock_getter = build_getter(fresh_feed)

        # DUT:
        fc = FeedCache(db_path='dummy', cache=mock_shelf,
                       cache_get=mock_getter).fetch('fake_url')

        self.assertEqual(fc, feedparser.parse(fresh_feed.text))

    def test_parse_error(self):
        """Simulate a fatal parse error."""
        # setup mocked RWShelf
        error_feed = MagicMock()
        error_feed.text = "invalid feed"
        mock_shelf = mock_shelfcache(None)

        # setup mock feedparser.parse method
        mock_getter = build_getter(error_feed)

        # instantiate DUT:
        fc = FeedCache(db_path='dummy', cache=mock_shelf,
                       cache_get=mock_getter)

        with self.assertRaises(FeedCache.ParseError):
            fc.fetch('http://doamin/notafeed')
        mock_getter.assert_called_once_with(mock_shelf,
                                            'http://doamin/notafeed')
