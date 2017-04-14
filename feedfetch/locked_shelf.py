"""
Locking wrappers around the standard shelve_ class to provide thread- and
multiprocess synchronization.

The shelve docs say:

    "The shelve module does not support _concurrent_ read/write access to
    shelved objects. (Multiple simultaneous read accesses are safe.) When a
    program has a shelf open for writing, no other program should have it open
    for reading or writing. Unix file locking can be used to solve this, but
    this differs across Unix versions and requires knowledge about the database
    implementation used."

But both claims are a little misleading (that threaded access is safe and multi-
process access is unsafe).

With CPython, threaded access to shelved objects will not corrupt the database
(because the GIL makes reads/writes of the shelved dictionary atomic), but not
using a synchronizing lock could still give surprising results (one thread over-
writing a value just set by another thread).

Also, the GNU dbm implementation includes a built-in reader/writer lock which
makes it safe to use from several processes, but it is non-blocking so its use
requires polling on an exception until the read/write is successful. (On most
systems I think using gdbm requires installing an extra pacakge --
`python3-gdbm` on Debian.)

So this module provides two very simple wrappers around shelve which can
synchronize access between threads and/or processes:

* `MutexShelf`: synchronizes both reads and writes with a mutex. The initializer
    takes a lock which can be either a `threading.Lock` (default) or a
    `multiprocessing.Lock`.

* `RWShelf`: uses the OS's `flock` mechanism to provide a shared-exclusive
    lock around shelve a shelve object (works for both threads and processes).

* TODO: A more portable solution than RWShelf would be to implement a
    reader-writer lock in Python. The Standard library does not include one, but
    there are several implementations available on the web. (The only
    disadvantage compared to the system-level flock is that it would only
    synchronize the python program -- but most shelve/dbm databases don't need
    to be read from several programs at once, anyway)

.. _shelve: https://docs.python.org/3/library/shelve.html

"""
import shelve
import threading
import multiprocessing
import logging
import fcntl
from fcntl import flock
from typing import Union
import dbm
import abc
import os.path

logger = logging.getLogger(__name__)
lock_t = Union[threading.Lock, multiprocessing.Lock]


class LockedShelf(metaclass=abc.ABCMeta):
    """
    Abstract base class for LockedShelf implementations.
    """
    @abc.abstractmethod
    def __init__(self, *args, **kwargs):
        pass

    @abc.abstractmethod
    def close(self) -> None:
        pass

    @abc.abstractmethod
    def __enter__(self) -> shelve.Shelf:
        pass

    @abc.abstractmethod
    def __exit__(self, exc_type, exc_value, traceback) -> None:
        pass


class MutexShelf(LockedShelf):
    """
    A heavy-handed approach that acquires a mutex and opens the shelve object
    when initialized, and releases the mutex and closes the shelve when closed.

    Intended to be used as a context manager:

        >>> lock = threading.Lock() # or multiprocessing.Lock()
        >>> with MutexShelf(filename, flag='c', lock) as shelf:
        >>>     shelf[key] = value
    """

    def __init__(self, filename: str, flag: str = 'c',
                 lock: lock_t =threading.Lock()) -> None:
        """
        __init__(self, filename, flag='c', lock=threading.Lock())

        Opens shelf (sets shelve object to `shelf` attribute) and locks database

        :param filename: path to the shelve database file
        :param flag: flag to pass to :py:meth:`dbm.open`
        :param lock: the mutex lock to use (uses a :py:meth:`threading.Lock` by
            default)
        """
        self.lock = lock
        self.lock.acquire()
        logger.info("Acquired lock for {}".format(filename))
        self.shelf = shelve.open(filename, flag)

    def close(self) -> None:
        """
        Closes shelf and releases lock.
        """
        self.shelf.close()
        self.lock.release()
        logger.info("Released lock for shelf")

    def __enter__(self) -> shelve.Shelf:
        """
        Allows the underlying shelve object to be used in a `with` context.
        """
        return self.shelf

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        """
        Close when exiting from `with` context.
        """
        self.close()


class RWShelf(LockedShelf):
    """
    Uses the OS's `flock` mechanism to provide a shared-exclusive lock
    around shelve (so that many readers can access the shelve object at once,
    but only one writer). The nice thing about flock (compared to fnctl/lockf)
    is that its lock is owned by the file so that it can be used to synchronize
    processes (including other programs) AND threads.

    (However, be aware of the shortcomings and non-portability of flock and the
    other Unix locking mechanisms: http://apenwarr.ca/log/?m=201012#13)

    Intended to be used as a context manager:

        >>> with RWShelf(filename, flag='r') as shelf:
        >>>     value = shelf[key] # reader lock (because of 'r' flag)

        >>> with RWShelf(filename, flag='c') as shelf:
        >>>     shelf[key] = value # writer lock (because of non-'r' flag)
    """

    def __init__(self, filename: str, flag: str = 'c') -> None:
        """
        Opens shelf (sets shelve object to `shelf` attribute) and locks
        database. If the database does not exist and the flag is 'r', then
        raises a FileNotFoundError exception; if the flag is other than 'r',
        then the database file is created.

        :param filename: path to the shelve database file
        :param flag: flag to pass to `dbm.open()`
        """
        if flag == 'r':
            ltype = fcntl.LOCK_SH
        else:
            ltype = fcntl.LOCK_EX
            # Create file if it doesn't exist:
            try:
                with shelve.open(filename, 'c'):
                    pass
            except dbm.error:
                # If we got here, then more than one thread/process tried to
                # create the file at the same time and gdbm's own locking threw
                # an exception. It doesn't matter, the threads/procs will be
                # synchronized by the flock below.
                pass

        # Some implementations of dbm add the .db suffix, and some don't
        if os.path.exists(filename):
            created_name = filename
        else:
            created_name = filename + ".db"

        self.fd = open(created_name, 'r+')
        flock(self.fd, ltype)
        logger.info("Acquired lock for {} ({})".format(filename, ltype))
        self.shelf = shelve.open(filename, flag)

    def close(self) -> None:
        """
        Closes shelf and releases lock.
        """
        self.shelf.close()
        self.fd.close()
        logger.info("Released lock for shelf")

    def __enter__(self) -> shelve.Shelf:
        """
        Allows the underlying shelve object to be used in a `with` context.
        """
        return self.shelf

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        """
        Close when exiting from `with` context.
        """
        self.close()
