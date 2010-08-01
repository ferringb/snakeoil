# Copyright: 2005-2010 Brian Harring <ferringb@gmail.com>
# License: GPL2/BSD

"""
A far more minimal form of file protocol encapsulation location and encoding into it

The primary use for data_source's is to encapsulate the following issues into a single object:

* is the data actually on disk (thus can I use more efficient ops against the file?).
* what is the preferred encoding?
* py3k compatibility concerns (bytes versus text file handles)

Note that under py2k, :py:class:`text_data_source` and :py:class:`bytes_data_source` are
just aliases of :py:class:`data_source`; under py3k however they are seperate classes
doing necessary conversion steps for bytes/text requests.  Use the appropriate one-
it'll save yourself a headache when dealing with py2k/py3k compatibility in the same
codebase.

Finally, note that all file like handles returned from `test_fileobj()` and `bytes_fileobj()`
have a required additional attribute- *exceptions*, either a single Exception class, or a
tuple of Exception classes that can be thrown by that file handle during usage.

This requirement exists purely to allow the consuming code to avoid having to know anything
about the backing of the file like object.

The proper way to use such a filehandle is as follows:

>>> from snakeoil.data_source import data_source
>>> source = data_source("It's a fez. I wear a fez now. Fezes are cool.", mutable=False)
>>> handle = source.text_fileobj()
>>> handle.write("You graffitied the oldest cliff face in the universe.")
Traceback (most recent call last):
TypeError:
>>> # if this where a normal file, it would be an IOError- it's impossible to guess the
>>> # correct exception to intercept, so instead we rely on the handle telling us what
>>> # we should catch;
>>> try:
...   handle.write("You wouldn't answer your phone.")
... except handle.exceptions, e:
...   print "we caught the exception."
we caught the exception.
"""

__all__ = ("base", "data_source", "local_source", "text_data_source",
    "bytes_data_source")

from snakeoil.currying import (pre_curry, alias_class_method, post_curry,
    pretty_docs, alias_class_method)
from snakeoil import compatibility, demandload, stringio, klass
demandload.demandload(globals(), 'codecs')

def _mk_writable_cls(base, name):
    """
    inline mixin of writable overrides

    while a normal mixin is preferable, this is required due to
    differing slot layouts between py2k/py3k base classes of
    stringio.
    """

    class kls(base):

        """
        writable %s StringIO instance suitable for usage as a data_source filehandle

        This adds a callback for updating the original data source, and appropriate
        exceptions attribute
        """ % (name.split("_")[0],)


        base_cls = base
        exceptions = (MemoryError,)
        __slots__ = ('_callback',)

        def __init__(self, callback, data):
            """
            :param callback: functor invoked when this data source is modified;
                the functor takes a single value, the full content of the StringIO
            :param data: initial data for this instance
            """
            if not callable(callback):
                raise TypeError("callback must be callable")
            self.base_cls.__init__(self, data)
            self._callback = callback

        def close(self):
            self.flush()
            if self._callback is not None:
                self.seek(0)
                self._callback(self.read())
                self._callback = None
            self.base_cls.close(self)
    kls.__name__ = name
    return kls


text_wr_StringIO = _mk_writable_cls(stringio.text_writable, "text_wr_StringIO")
bytes_wr_StringIO = _mk_writable_cls(stringio.bytes_writable, "bytes_wr_StringIO")


class text_ro_StringIO(stringio.text_readonly):
    """
    readonly text mode StringIO usable as a filehandle for a data_source

    Specifically this adds the necessary `exceptions` attribute; see
    :py:class:`snakeoil.stringio.text_readonly` for methods details.
    """
    __slots__ = ()
    exceptions = (MemoryError, TypeError)


class bytes_ro_StringIO(stringio.bytes_readonly):
    """
    readonly bytes mode StringIO usable as a filehandle for a data_source

    Specifically this adds the necessary `exceptions` attribute; see
    :py:class:`snakeoil.stringio.bytes_readonly` for methods details.
    """
    __slots__ = ()
    exceptions = (MemoryError, TypeError)


# derive our file classes- we derive *strictly* to append
# the exceptions class attribute for consumer usage.
if compatibility.is_py3k:

    import io

    def open_file(*args, **kwds):
        handle = io.open(*args, **kwds)
        handle.exceptions = (EnvironmentError,)
        return handle

else:
    # have to derive since you can't modify file objects in py2k
    class open_file(file):
        __slots__ = ()
        exceptions = (EnvironmentError,)


class base(object):
    """
    base data_source class; implementations of the protocol are advised
    to derive from this.

    :ivar path: If None, no local path is available- else it's the ondisk path to
      the data
    """
    __slots__ = ("weakref",)

    get_path = path = None

    def text_fileobj(self, writable=False):
        """get a text level filehandle for for this data

        :param writable: whether or not we need to write to the handle
        :raise: TypeError if immutable and write is requested
        :return: file handle like object
        """
        raise NotImplementedError(self, "text_fileobj")

    def bytes_fileobj(self, writable=False):
        """get a bytes level filehandle for for this data

        :param writable: whether or not we need to write to the handle
        :raise: TypeError if immutable and write is requested
        :return: file handle like object
        """
        raise NotImplementedError(self, "bytes_fileobj")

    get_fileobj = alias_class_method("text_fileobj", "get_fileobj",
        "deprecated; use get_text_fileobj instead")

    get_text_fileobj = alias_class_method("text_fileobj",
        doc="deprecated; use text_fileobj directly")
    get_bytes_fileobj = alias_class_method("bytes_fileobj",
        doc="deprecated; use bytes_fileobj directed")


class local_source(base):

    """locally accessible data source

    Literally a file on disk.
    """

    __slots__ = ("path", "mutable", "encoding")

    buffering_window = 32768

    def __init__(self, path, mutable=False, encoding=None):
        """
        :param path: file path of the data source
        :param mutable: whether this data_source is considered modifiable or not
        :param encoding: the text encoding to force, if any
        """
        base.__init__(self)
        self.path = path
        self.mutable = mutable
        self.encoding = encoding

    def get_path(self):
        """deprecated getter to access ``path`` attribute; access ``path``
        directly instead``"""
        return self.path

    @klass.steal_docs(base)
    def text_fileobj(self, writable=False):
        if writable and not self.mutable:
            raise TypeError("data source %s is immutable" % (self,))
        if self.encoding:
            opener = open_file
            if not compatibility.is_py3k:
                opener = codecs.open
            opener = post_curry(opener, buffering=self.buffering_window,
                encoding=self.encoding)
        else:
            opener = post_curry(open_file, self.buffering_window)
        if writable:
            return opener(self.path, "r+")
        return opener(self.path, "r")

    @klass.steal_docs(base)
    def bytes_fileobj(self, writable=False):
        if writable:
            if not self.mutable:
                raise TypeError("data source %s is immutable" % (self,))
            return open_file(self.path, "rb+", self.buffering_window)
        return open_file(self.path, 'rb', self.buffering_window)


class data_source(base):

    """
    base class encapsulating a purely virtual data source lacking an on disk location.

    Whether this be due to transformation steps necessary (pulling the data out of
    an archive for example), or the data being generated on the fly, this classes's
    derivatives :py:class:`text_data_source` and :py:class:`bytes_data_source` are
    likely what you should be using for direct creation.

    :ivar data: the raw data.  should either be a string or bytes depending on your
      derivative
    :ivar path: note that path is None for this class- no on disk location available.
    """

    __slots__ = ('data', 'mutable')

    def __init__(self, data, mutable=False):
        """
        :param data: data to wrap
        :param mutable: should this data_source be updatable?
        """
        base.__init__(self)
        self.data = data
        self.mutable = mutable

    if compatibility.is_py3k:
        def _convert_data(self, mode):
            if mode == 'bytes':
                if isinstance(self.data, bytes):
                    return self.data
                return self.data.encode()
            if isinstance(self.data, str):
                return self.data
            return self.data.decode()
    else:
        def _convert_data(self, mode):
            return self.data

    @klass.steal_docs(base)
    def text_fileobj(self, writable=False):
        if writable:
            if not self.mutable:
                raise TypeError("data source %s is not mutable" % (self,))
            return text_wr_StringIO(self._reset_data,
                self._convert_data('text'))
        return text_ro_StringIO(self._convert_data('text'))

    if compatibility.is_py3k:
        def _reset_data(self, data):
            if isinstance(self.data, bytes):
                if not isinstance(data, bytes):
                    data = data.encode()
            elif not isinstance(data, str):
                data = data.decode()
            self.data = data
    else:
        def _reset_data(self, data):
            self.data = data

    @klass.steal_docs(base)
    def bytes_fileobj(self, writable=False):
        if writable:
            if not self.mutable:
                raise TypeError("data source %s is not mutable" % (self,))
            return bytes_wr_StringIO(self._reset_data,
                self._convert_data('bytes'))
        return bytes_ro_StringIO(self._convert_data('bytes'))


if not compatibility.is_py3k:
    text_data_source = data_source
    bytes_data_source = data_source
else:
    class text_data_source(data_source):

        """
        text data_source

        in py2k, this just wraps a string; in py3k, it'll do autoconversion
        between bytes/text as needed.
        """

        __slots__ = ()

        @klass.steal_docs(data_source)
        def __init__(self, data, mutable=False):
            if not isinstance(data, str):
                raise TypeError("data must be a str")
            data_source.__init__(self, data, mutable=mutable)

        def _convert_data(self, mode):
            if mode != 'bytes':
                return self.data
            return self.data.encode()

    class bytes_data_source(data_source):

        """
        bytes data_source

        in py2k, this just wraps a string; in py3k, it'll do autoconversion
        between bytes/text as needed.
        """

        __slots__ = ()

        @klass.steal_docs(data_source)
        def __init__(self, data, mutable=False):
            if not isinstance(data, bytes):
                raise TypeError("data must be bytes")
            data_source.__init__(self, data, mutable=mutable)

        def _convert_data(self, mode):
            if mode == 'bytes':
                return self.data
            return self.data.decode()


def transfer_data(read_fsobj, write_fsobj, bufsize=(4096 * 16)):
    """
    transfer all remaining data of *read_fsobj* to *write_fsobj*
    """
    data = read_fsobj.read(bufsize)
    while data:
        write_fsobj.write(data)
        data = read_fsobj.read(bufsize)