"""
The `FeedCache` class provided by this module adds [thread- and
multiprocess-safe] caching to the `Universal Feed Parser`_.

Usage is as simple as initializing with a path where the database file should be
created, and then calling the `fetch` method with the URL to fetch::

    >>> from feedfetch import FeedCache
    >>> cache = FeedCache('cache.db')
    >>> feed = cache.fetch('https://hnrss.org/newest')
    >>> for entry in feed.entries:
    >>>     # Process feed, etc
    >>>     print(entry.title)
    >>>
    >>> # Fetching a second time will be much faster as it will likely be
    >>> # returned from cache:
    >>> feed = cache.fetch('https://hnrss.org/newest')

If a URL generates an error during fetching or parsing, then an exception is
raised (`URLError`, `FetchError`, or `ParseError`)

For simplicity, HTTP requests are delegated to feedparser (which uses urllib2).

Caching to disk is handled by locking wrappers around the standard library's
`Shelf` class. Two such wrappers are included in the `locked_shelf` module:
`MutexShelf` and the flock-based `RWShelf` (which is used by default).

For a similar module (for Python 2) see Doug Hellmann's feedcache
package/article: http://feedcache.readthedocs.io/en/latest/

.. _Universal Feed Parser: https://pypi.python.org/pypi/feedparser
"""
import feedparser
import logging
from typing import Callable, Optional
from .shelfcache import ShelfCache
from .cache_get import cache_get

logger = logging.getLogger(__name__)


class FeedCache:
    """A wrapper for feedparser which handles caching using a locking wrapper
    around the standard shelve library. Thread and multiprocess safe."""

    class ParseError(Exception):
        pass

    def __init__(self, db_path='fmcache.db', min_age: int=1200,
                 cache: Optional[ShelfCache]=None,
                 cache_get: Callable=cache_get) -> None:
        """
        __init__(self, db_path='fmcache.db', min_age=1200, cache=None)

        By default will create cache database at `db_path`, but if a ShelfCache
        instance is provided as `cache`, will use that instead.

        :param db_path:    Path to the dbm file which holds the cache
        :param min_age:    Minimum time (seconds) to keep feed in hard cache.
            This is overridden by a smaller max-age attribute in the received
            cache-control http header
        :param cache:   The ShelfCache instance to use for caching.
        """
        if cache is None:
            cache = ShelfCache(db_path=db_path, exp_seconds=min_age)
        self.cache = cache
        self.min_age = min_age
        self.cache_get = cache_get

    def fetch(self, url: str) -> feedparser.util.FeedParserDict:
        """Fetch an RSS/Atom feed given a URL.

        Uses `ShelfCache` to handle caching feeds (and sending
        etag/last-modified headers to servers when re-fetching stale feeds.)

        :param url: the url of the feed to fetch

        Returns:
            The parsed feed (or throws an exception if the feed couldn't be
            fetched/parsed)

        Raises:
            ParseError: If feedparser successfully fetched a resource over http,
                but wasn't able to parse it as a feed.
        """
        resp = self.cache_get(self.cache, url=url)
        fetched = feedparser.parse(resp.text)

        parse_err = len(fetched.get('entries')) == 0 and fetched.get('bozo')
        if fetched is None or parse_err:
            logger.info("Parse error ({})"
                        .format(fetched.get('bozo_exception')))
            raise FeedCache.ParseError("Parse error: {}"
                                       .format(fetched.get('bozo_exception')))

        logger.info("Got feed from feedparser {}".format(url))
        logger.debug("Feed: {}".format(fetched))

        return fetched
