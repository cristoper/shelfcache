"""
This module provides a function, `cache_get`  which wraps the :meth:`get()`
method from the `requests package`_ and provides persistent (thread and
multiprocess-safe) caching to disk through `ShelfCache`.

It transparently handles retrieving resources from the cache, validating them,
re-fetching stale resources including using etag and last-modified headers when
possible, and updating cached resources.

Resources (even when stale) are never deleted from the cache. Pruning must be
done separately, if needed (see the :meth:`prune_expired`, :meth:`prune_old`,
and :meth:`clear` methods of `shelfcache`)

Usage is as simple as first initializing a ShelfCache object with a path where
the database file should be created and a default expiration time for cached
resources (seconds), and then calling the `cache_get` function with the URL to
fetch::

    >>> from shelfcache import cache_get, ShelfCache
    >>> cache = ShelfCache('path/to/cache.db', exp_seconds=1200)
    >>> response = cache_get(cache, url='https://hnrss.org/newest')
    >>> response.status_code
    200
    >>> len(response.text)
    18236

See the requests package documentation for how to use the response object:
http://docs.python-requests.org/en/master/user/quickstart/#response-content

.. _requests package: http://docs.python-requests.org/en/master/r
"""
import requests
import re
import logging
from .shelfcache import ShelfCache
from typing import Callable

NOT_MODIFIED = 304

logger = logging.getLogger(__name__)


def cache_get(cache: ShelfCache, url: str, headers=None,
              get_meth: Callable=requests.get, **kwargs) -> requests.Response:
    """
    A wrapper around `requests.get()` which uses an on-disk cache.

    Note that `url` must include all of its query sring fields (there is not
    `params` parameter like with `requests.get()`

    If the url is in the cache and it is still fresh then it is returned
    directly. Items are valid for `cache.exp_seconds` or for the max-age
    specified in the cache-control header returned by the server, whichever
    is less.

    If the item in the cache has expired, it is re-fetched from the remote
    server (using etag and/or last-modified headers if available so that the
    server can return a cached version).

    When the response is received from the server, then the feed is updated
    in the on-disk cache.

    :param cache: The ShelfCache to handle the cache
    :param url: the url of the resource to fetch
    :param get_meth: The method which is called to issue the HTTP get request.
        By default this is requests.get but is injectable mostly for testing
        purposes.
    :pram **kwargs: All keyword args are passed to `requests.get()`

    Returns:
        The requested resource. The requests package will raise exceptions
        on network errors.
    """
    etag = None
    lastmod = None
    if headers is None: headers = {}

    logger.info("Fetching item for url: {}".format(url))
    item = cache.get(url)
    if item:
        logger.info("Got resource from cache for url: {}".format(url))
        cached, expired = item.data, item.expired
        if not expired:
            # If cache is fresh, use it without further ado
            logger.info("Returning fresh item found in cache: {}"
                        .format(url))
            return cached

        logger.info("Stale item found in cache: {}".format(url))
        etag = cached.headers.get('etag')
        etag = etag.lstrip('W/') if etag else None  # strip weak etag
        lastmod = cached.headers.get('last-modified')
    else:
        logger.info("No item in cache for url: {}".format(url))

    # Cache wasn't fresh in db, so we'll request it, but give origin etag
    # and/or last-modified headers (if available) so we only fetch and
    # parse it if it is new/updated.
    logger.info("Fetching from remote {}".format(url))

    # Add if-none-match and/or if-modified-since headers
    if etag:
        headers['If-None-Match'] = etag
    if lastmod:
        headers['If-Modified-Since'] = lastmod

    fetched = get_meth(url, headers=headers, **kwargs)
    fetched.raise_for_status()
    logger.info("Got resource from remote for  {}".format(url))
    logger.debug("Resource: {}".format(fetched))

    if fetched.status_code == NOT_MODIFIED:
        # Source says feed is still fresh
        logger.info("Server says resource is still fresh: {}".format(url))
        new_headers = fetched.headers
        fetched = cached
        fetched.headers = new_headers

    # Add to/update cache with new expire_dt
    # Using max-age parsed from cache-control header, if it exists
    cc_header = fetched.headers.get('cache-control') or ''
    ma_match = re.search('max-age=(\d+)', cc_header)
    if ma_match:
        if cache.exp_seconds < 0:
            min_age = int(ma_match.group(1))
        else:
            min_age = min(int(ma_match.group(1)), cache.exp_seconds)
    else:
        min_age = cache.exp_seconds
    logger.info("Saving resource for {} with exp_seconds: {}"
                .format(url, min_age))
    cache.create_or_update(url, data=fetched, exp_seconds=min_age)
    return fetched
