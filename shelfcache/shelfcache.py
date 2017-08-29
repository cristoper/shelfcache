"""
The `ShelfCache` class in this module implements a generic thread- and
multiprocess-safe key-value caching store. The values can be any object which
can be pickled.

When retrieving values (which is achieved with the :meth:`get` method),
ShelfCache will always return the cached data along with a boolean indicating
whether it is expired or not. Application code can then decide what to do with
the data.

No automatic database size management is done while saving or retrieving values,
but applications/scripts can make use of the :meth:`prune_expired`,
:meth:`prune_old`, and :meth:`clear` methods to delete old items.

Caching to disk is handled by a locking wrapper around the standard library's
`Shelf <https://docs.python.org/3/library/shelve.html>`_ class. Two
implementations of the wrapper are included in the `locked_shelf` module:
`MutexShelf` and the flock-based `RWShelf` (which is used by ShelfCache by
default).

For a similar approach (for Python 2) -- which implements caching on top of a
locking wrapper around the shelve library -- see Doug Hellmann's feedcache
package/article: http://feedcache.readthedocs.io/en/latest/
"""
from .locked_shelf import LockedShelf, RWShelf
from datetime import datetime, timedelta
from typing import Type, Optional, NamedTuple, Any
import logging

logger = logging.getLogger(__name__)


CacheResult = NamedTuple('CacheResult', [('data', Any), ('expired', bool)])
"""
The type returned when getting an item from the cache.

:param data: The data field contains the actual cached data
:param bool expired: A boolean indicating whether the cached data has expired
    (True==expired; False==fresh)
"""


class Item:
    """A wrapper class so we can add metadata to items stored in cache."""
    def __init__(self, data, expire_dt: Optional[datetime]=None) -> None:
        """
        :ivar created_dt: The date the item was first cached
        :ivar update_dt: The date the item was last updated in cache

        :param data: The object to wrap (can be any pickle-able object)
        :param expire_dt: The date the item expires (None means the item never
            expires)
        """
        now = datetime.utcnow()
        self.data = data
        self.created_dt = now
        self.updated_dt = now
        self.expire_dt = expire_dt


class ShelfCache:
    def __init__(self, db_path='shelfcache.db', exp_seconds=-1, shelf_t:
                 Type[LockedShelf]=RWShelf) -> None:
        """
        :param db_path: Path to database (where it will be created if necessary)
        :param exp_seconds: The default expiry time to use for a cached item (in
            seconds). This can be overridden per-item in `create_or_update`. A
            negative number means the item will never expire.
        :param shelf_t: The type of shelf to use (any sublcass of `LockedShelf`,
            ie `MutexShelf` or `RWShelf`)
        """
        self.db_path = db_path
        self.exp_seconds = exp_seconds
        self.shelf_t = shelf_t

    def get(self, key) -> Optional[CacheResult]:
        """
        Get item from database and check if it is expired.
        """
        try:
            with self.shelf_t(self.db_path, flag='r') as shelf:
                val = shelf.get(key)  # type: Optional[Item]
                if val is not None:
                    now = datetime.utcnow()
                    if val.expire_dt is None:
                        expired = False
                    else:
                        expired = val.expire_dt < now
                    return CacheResult(data=val.data, expired=expired)
        except FileNotFoundError:
            logger.info("Cache db file does not exist at {}"
                        .format(self.db_path))
        return None

    def get_item(self, key) -> Optional[Item]:
        """
        Get item from database. Like get(), but return an Item (with all
        metadata) instead of the simpler CacheResult.
        """
        try:
            with self.shelf_t(self.db_path, flag='r') as shelf:
                val = shelf.get(key)  # type: Optional[Item]
                return val
        except FileNotFoundError:
            logger.info("Cache db file does not exist at {}"
                        .format(self.db_path))
        return None

    def __getitem__(self, key) -> CacheResult:
        val = self.get(key)
        if val is None:
            raise KeyError(key)
        return val

    def create_or_update(self, key, data=None,
                         expire_dt: Optional[datetime]=None,
                         exp_seconds: Optional[int]=None) -> None:
        """
        Create or update `key` with the given `data`.

        The expiry datetime of the cached item is set by either `expire_dt` or
        `exp_seconds`. If both are set, `expire_dt` will be used. If neither are
        set, the item will never expire.

        :param key: The key associated with the `data` to cache
        :param data: The data to cache (can be any pickle-able object)
        :param expire_dt: The date the cached item expires.
        :param exp_seconds: The number of seconds into the future that the
            cached item expires.
        """
        item = Item(data=data)
        if expire_dt is None and exp_seconds and exp_seconds > -1:
            expire_dt = item.created_dt + timedelta(seconds=exp_seconds)
        item.expire_dt = expire_dt

        with self.shelf_t(self.db_path, flag='c') as shelf:
            if key in shelf.keys():
                # If this item already exists, preserve its created_dt and
                # update its updated_dt
                item.created_dt = shelf.get(key).created_dt
                item.updated_dt = datetime.utcnow()
                logger.info("Updated item for key: {}".format(key))
            else:
                logger.info("Created item for key: {}".format(key))
            shelf[key] = item

    def __setitem__(self, key, value) -> None:
        """
        Create or update `key` with the given `data`. The item will never
        expire. To set an expiry datetime, use :meth:`create_or_update` instead.
        """
        self.create_or_update(key, data=value)

    def update_expires(self, key, expire_dt: Optional[datetime]=None) -> None:
        """
        Update a cached item's expire_dt without returning the actual data.
        """
        if expire_dt is None:
            expire_dt = datetime.utcnow()
        d, _ = self[key]
        self.create_or_update(key, data=d, expire_dt=expire_dt)

    def replace_data(self, key, data: Optional[object]=None) -> None:
        """
        Update a cached item's data without affecting its expire_dt.
        """
        item = self.get_item(key)
        self.create_or_update(key, data=data, expire_dt=item.expire_dt)

    def delete(self, key: str) -> None:
        """
        Delete `key` from cache database.
        """
        with self.shelf_t(self.db_path, flag='c') as shelf:
            del shelf[key]
            logger.info("Deleted item for key: {}".format(key))

    def __delitem__(self, key) -> None:
        self.delete(key)

    def __prune(self, dt: datetime, field_name='expire_dt') -> int:
        keys_to_delete = []
        with self.shelf_t(self.db_path, flag='c') as shelf:
            for key, item in shelf.items():
                exp_d = getattr(item, field_name)
                if exp_d < dt:
                    keys_to_delete.append(key)

            for k in keys_to_delete:
                del shelf[k]
                logger.info("Pruned item for key: {}".format(key))
        return len(keys_to_delete)

    def prune_expired(self, older_than: Optional[datetime]=None) -> int:
        """
        :param older_than: Delete all items in cache which have expired since
        the given datetime. If `older_than` is None, use datetime.utcnow()

        Returns:
            The number of items that were pruned.
        """
        if older_than is None:
            older_than = datetime.utcnow()
        return self.__prune(older_than, field_name='expire_dt')

    def prune_old(self, older_than: Optional[datetime]=None) -> int:
        """
        :param older_than: Delete all items in cache updated before the
        the given datetime. If `older_than` is None, use datetime.utcnow()

        Returns:
            The number of items that were pruned.
        """
        if older_than is None:
            older_than = datetime.utcnow()
        return self.__prune(older_than, field_name='updated_dt')

    def clear(self) -> None:
        """
        Delete all items in cache.
        """
        with self.shelf_t(self.db_path, flag='c') as shelf:
            shelf.clear()
            logger.info("Deleted all items in cache.")
