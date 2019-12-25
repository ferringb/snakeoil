from operator import attrgetter

def GetAttrProxy(target):
    def reflected_getattr(self, attr):
        return getattr(object.__getattribute__(self, target), attr)
    return reflected_getattr


def contains(self, key):
    """
    return True if key is in self, False otherwise
    """
    try:
        # pylint: disable=pointless-statement
        self[key]
        return True
    except KeyError:
        return False


def get(self, key, default=None):
    """
    return ``default`` if ``key`` is not in self, else the value associated with ``key``
    """
    try:
        return self[key]
    except KeyError:
        return default

_sentinel = object()

_attrlist_getter = attrgetter("__attr_comparison__")
def generic_attr_eq(inst1, inst2):
    """
    compare inst1 to inst2, returning True if equal, False if not.

    Comparison is down via comparing attributes listed in inst1.__attr_comparison__
    """
    if inst1 is inst2:
        return True
    for attr in _attrlist_getter(inst1):
        if getattr(inst1, attr, _sentinel) != \
            getattr(inst2, attr, _sentinel):
            return False
    return True


def generic_attr_ne(inst1, inst2):
    """
    compare inst1 to inst2, returning True if different, False if equal.

    Comparison is down via comparing attributes listed in inst1.__attr_comparison__
    """
    if inst1 is inst2:
        return False
    for attr in _attrlist_getter(inst1):
        if getattr(inst1, attr, _sentinel) != getattr(inst2, attr, _sentinel):
            return True
    return False


def reflective_hash(attr):
    """
    default __hash__ implementation that returns a pregenerated hash attribute

    :param attr: attribute name to pull the hash from on the instance
    :return: hash value for instance this func is used in.
    """
    def __hash__(self):
        return getattr(self, attr)
    return __hash__


class _raw_internal_jit_attr(object):
    """See _native_internal_jit_attr; this is an implementation detail of that"""

    __slots__ = ("storage_attr", "function", "_setter", "singleton", "use_singleton")

    def __init__(self, func, attr_name, singleton=None,
                 use_cls_setattr=False, use_singleton=True):
        """
        :param func: function to invoke upon first request for this content
        :param attr_name: attribute name to store the generated value in
        :param singleton: an object to be used with getattr to discern if the
            attribute needs generation/regeneration; this is controllable so
            that consumers can force regeneration of the hash (if they wrote
            None to the attribute storage and singleton was None, it would regenerate
            for example).
        :param use_cls_setattr: if True, the target instances normal __setattr__ is used.
            if False, object.__setattr__ is used.  If the instance is intended as immutable
            (and this is enforced by a __setattr__), use_cls_setattr=True would be warranted
            to bypass that protection for caching the hash value
        :type use_cls_setattr: boolean
        """
        if bool(use_cls_setattr):
            self._setter = setattr
        else:
            self._setter = object.__setattr__
        self.function = func
        self.storage_attr = attr_name
        self.singleton = singleton
        self.use_singleton = use_singleton

    def __get__(self, instance, obj_type):
        if instance is None:
            # accessed from the class, rather than a running instance.
            # access ourself...
            return self
        if not self.use_singleton:
            obj = self.function(instance)
            self._setter(instance, self.storage_attr, obj)
        else:
            try:
                obj = object.__getattribute__(instance, self.storage_attr)
            except AttributeError:
                obj = self.singleton
            if obj is self.singleton:
                obj = self.function(instance)
                self._setter(instance, self.storage_attr, obj)
        return obj



