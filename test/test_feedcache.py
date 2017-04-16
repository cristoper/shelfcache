from feedfetch import FeedCache
import unittest
from unittest.mock import MagicMock
from feedfetch.shelfcache import ShelfCache, Item, CacheResult
import feedparser
import datetime
from urllib.error import URLError
from http.client import NOT_MODIFIED, OK

ATOM_PATH = 'test/test_atom.xml'


def mock_shelfcache(return_value=None):
    """Helper function to create a mocked RWShelf instance.

    Args:
        return_value: the value returned by the mocked shelf.get() method
    Returns:
        a MagicMock object spec'd to RWShelf
    """
    mock_shelf = MagicMock(spec=ShelfCache)
    mock_get = MagicMock(return_value=return_value)
    mock_shelf.get = mock_get
    return mock_shelf


def build_feed(test_file=ATOM_PATH, status=OK,
               exp_time=datetime.datetime.now(),
               etag='etag', modified='modified', max_age=None):
    """Read an Atom/RSS feed from file and return a Feed object
    suitable for testing.

    Args:
        test_file: Path to file containing test Atom/RSS feed
        status: HTTP status
        exp-time: cache expire time (set to future for fresh cache, past for
            stale cache (defaults to stale))
        etag: etag cache-control header
        modified: last-modified cache-control header

    Returns:
        A Feed instance populated by parsing the contents of
        `test_file`
    """
    with open(test_file, 'r') as f:
        feed = ''.join(f.readlines())
        test_parsed = feedparser.parse(feed)
    test_parsed.etag = etag
    test_parsed['etag'] = etag
    test_parsed.modified = modified
    test_parsed['modified'] = modified
    test_parsed.status = status
    test_parsed['status'] = status
    if max_age:
        test_parsed['headers'] = {'cache-control': 'max-age={}'.format(max_age)}
    return Item(data=test_parsed, expire_dt=exp_time)


def build_parser(return_value):
    """Build a mock feedparser.parse method.

    Args:
        return_value: the value to be returned by the call to `parse()`
        (probably a dictionary representing a parsed feed).

    Returns:
        A MagicMock instance spec'd to feedparser.parse
    """
    mock_parser = MagicMock(spec=feedparser.parse)
    mock_parser.return_value = return_value
    return mock_parser


class TestFetch(unittest.TestCase):

    def test_new(self):
        """Simulate a URL not in the cache, and verify that FeedCache tries to
        fetch it over http."""
        # setup mock locked_shelf:
        new_feed = build_feed()
        mock_shelf = mock_shelfcache(None)

        # setup mock feedparser.parse method
        mock_parser = build_parser(new_feed.data)

        # DUT:
        fc = FeedCache(db_path='dummy', cache=mock_shelf,
                       parse=mock_parser).fetch('fake_url')

        self.assertEqual(fc, new_feed.data)
        mock_parser.assert_called_once_with('fake_url', None, None)

    def test_fresh(self):
        """Simulate a freshly cached feed and verify that FeedCache returns
        it."""
        # setup mock locked_shelf:
        fresh_feed = build_feed()
        mock_shelf = mock_shelfcache(CacheResult(data=fresh_feed.data,
                                                 expired=False))

        # setup mock feedparser.parse method
        mock_parser = build_parser(fresh_feed.data)

        # DUT:
        fc = FeedCache(db_path='dummy', cache=mock_shelf,
                       parse=mock_parser).fetch('fake_url')

        self.assertEqual(fc, fresh_feed.data)
        # since feed is resh, assert that the parser is not called:
        mock_parser.assert_not_called()

    def test_stale_not_modified(self):
        """Simulate a stale cached feed and verify that FeedCache fetches it and
        then asks the remote server for an updated."""
        # setup mocked RWShelf
        stale_feed = build_feed(status=NOT_MODIFIED)
        mock_shelf = mock_shelfcache(CacheResult(data=stale_feed.data,
                                                 expired=True))

        # setup mock feedparser.parse method
        mock_parser = build_parser(stale_feed.data)

        # instantiate DUT:
        fc = FeedCache(db_path='dummy', cache=mock_shelf,
                       parse=mock_parser).fetch('fake_url')

        mock_parser.assert_called_once_with('fake_url', 'etag', 'modified')
        self.assertEqual(fc, stale_feed.data)

    def test_stale_modified(self):
        """Simulate a stale cached feed and verify that FeedCache fetches it and
        then updates with new feed from server."""
        # setup mocked RWShelf
        stale_feed = build_feed(status=OK)
        mock_shelf = mock_shelfcache(CacheResult(data=stale_feed.data,
                                                 expired=True))

        # setup mock feedparser.parse method  (and mock headers so we can verify
        # that FeedCache parsed the cache-control header)
        mock_headers = MagicMock(spec=dict)
        mock_headers.get.return_value = 'max-age=10'
        new_feed = stale_feed.data
        new_feed['headers'] = mock_headers
        new_feed.entries[0].title = "This title was changed on the server"
        mock_parser = build_parser(new_feed)

        # instantiate DUT:
        fc = FeedCache(db_path='dummy', cache=mock_shelf,
                       parse=mock_parser).fetch('fake_url')

        mock_parser.assert_called_once_with('fake_url', 'etag', 'modified')
        mock_headers.get.assert_called_with('cache-control')

        # Make sure feed was updated:
        mock_shelf.create_or_update.assert_called_with('fake_url',
                                                       data=new_feed,
                                                       exp_seconds=10)
        self.assertEqual(fc, new_feed)

    def test_404(self):
        """Simulate fetching a non-existent feed."""
        # setup mocked RWShelf
        feed404 = build_feed(status=404)
        mock_shelf = mock_shelfcache(None)

        # setup mock feedparser.parse method
        mock_parser = build_parser(feed404.data)

        # instantiate DUT:
        fc = FeedCache(db_path='dummy', cache=mock_shelf,
                       parse=mock_parser)

        with self.assertRaises(FeedCache.FetchError) as e:
            fc.fetch('http://notfound/')
        self.assertEqual(404, e.exception.status)
        mock_parser.assert_called_once_with('http://notfound/', None, None)

    def test_fetch_error(self):
        """
        Test case if feedparser returns an object with no `status` attribute (we
        assume some sort of network error occurred).
        """
        # setup mocked RWShelf
        feed_err = build_feed(status=None)
        mock_shelf = mock_shelfcache(None)

        # setup mock feedparser.parse method
        mock_parser = build_parser(feed_err.data)

        # instantiate DUT:
        fc = FeedCache(db_path='dummy', cache=mock_shelf,
                       parse=mock_parser)

        with self.assertRaises(FeedCache.FetchError):
            fc.fetch('http://domain/error')
        mock_parser.assert_called_once_with('http://domain/error', None, None)

    def test_parse_error(self):
        """Simulate a fatal parse error."""
        # setup mocked RWShelf
        error_feed = {}
        error_feed['bozo'] = 1
        error_feed['bozo_exception'] = ("xml.sax._exceptions.SAXParseException"
                                        "('syntax error')")
        error_feed['entries'] = []
        error_feed['feed'] = {}
        error_feed['status'] = 301

        mock_shelf = mock_shelfcache(None)

        # setup mock feedparser.parse method
        mock_parser = build_parser(error_feed)

        # instantiate DUT:
        fc = FeedCache(db_path='dummy', cache=mock_shelf,
                       parse=mock_parser)

        with self.assertRaises(FeedCache.ParseError) as e:
            fc.fetch('http://doamin/notafeed')
            self.assertEqual(404, e.exception['status'])
        mock_parser.assert_called_once_with('http://doamin/notafeed', None,
                                            None)

    def test_DNS_error(self):
        """Give fetch() a non-existing domain name and check that it handles the
        error correctly."""
        # setup mocked RWShelf
        mock_shelf = mock_shelfcache(None)

        # setup mock feedparser.parse method
        mock_parser = build_parser(None)
        mock_parser.side_effect = URLError('Name or service not known')

        # instantiate DUT:
        fc = FeedCache(db_path='dummy', cache=mock_shelf,
                       parse=mock_parser)

        with self.assertRaises(URLError):
            fc.fetch('http://notfound/')

        mock_parser.assert_called_once_with('http://notfound/', None, None)
