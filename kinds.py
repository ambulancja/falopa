import common

class Type:

    def __init__(self, attributes, **kwargs):
        assert sorted(kwargs.keys()) == sorted(attributes)
        self._attributes = attributes
        for attr in attributes:
            setattr(self, attr, kwargs[attr])

    def representative(self):
        return self

    def is_set(self):
        return False

    def is_fun(self):
        return False

    def is_metavar(self):
        return False

class Set(Type):

    def __init__(self, **kwargs):
        Type.__init__(self, [], **kwargs)

    def __repr__(self):
        return '*'

    def is_set(self):
        return True

    def free_metavars(self):
        return set()

class Fun(Type):

    def __init__(self, **kwargs):
        Type.__init__(self, ['domain', 'codomain'], **kwargs)

    def __repr__(self):
        return '({domain} -> {codomain})'.format(
                   domain=self.domain,
                   codomain=self.codomain
               )

    def is_fun(self):
        return True

    def free_metavars(self):
        return self.domain.free_metavars() | self.codomain.free_metavars()

class Metavar(Type):

    def __init__(self, prefix='x'):
        Type.__init__(self, ['prefix', 'index'],
                            prefix=prefix, index=common.fresh_index())
        self._indirection = None

    def __repr__(self):
        if self._indirection is None:
            return '?{prefix}{index}'.format(
                       prefix=self.prefix,
                       index=self.index
                   )
        else:
            return repr(self._indirection)

    def is_metavar(self):
        return True

    def representative(self):
        if self._indirection is None:
            return self
        else:
            self._indirection = self._indirection.representative()
            return self._indirection

    def instantiate(self, value):
        assert self._indirection is None
        self._indirection = value

    def free_metavars(self):
        if self._indirection is None:
            return set([self])
        else:
            return self._indirection.free_metavars()

# Return a kind of the form:
#   ?k1 -> ... -> ?kn -> *
def fresh_kind(arity):
    kind = Set()
    for i in range(arity):
        kind = Fun(domain=Metavar(prefix='k'), codomain=kind)
    return kind

class UnificationFailure(Exception):

    def __init__(self, reason, **kwargs):
        self.reason = reason
        for attr in kwargs:
            setattr(self, attr, kwargs[attr])

def unify(t1, t2):
    t1 = t1.representative()
    t2 = t2.representative()
    if t1.is_metavar():
        if t1 == t2:
            return
        if t1 in t2.free_metavars():
            raise UnificationFailure('occurs-check', type1=t1, type2=t2)
        t1.instantiate(t2)
    elif t2.is_metavar():
        unify(t2, t1)
    elif t1.is_set() and t2.is_set():
        return
    elif t1.is_fun() and t2.is_fun():
        unify(t1.domain, t2.domain)
        unify(t1.codomain, t2.codomain)
    else:
        raise UnificationFailure('types-do-not-unify', type1=t1, type2=t2)

