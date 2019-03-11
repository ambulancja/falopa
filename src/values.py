import common

####

class Value:

    def is_thunk(self):
        return False

    def is_integer_constant(self):
        return False

    def is_rigid_structure(self):
        return False

    def is_flex_structure(self):
        return False

    def is_primitive(self):
        return False

    def is_closure(self):
        return False

    def is_rigid(self):
        return False

    def is_decided(self):
        return True

    def representative(self):
        return self

class Metavar(Value):

    def __init__(self, prefix='x', **kwargs):
        self.prefix = prefix
        self.index = common.fresh_index()
        self._indirection = None

    def representative(self):
        if self._indirection is None:
            return self
        else:
            self._indirection = self._indirection.representative()
            return self._indirection

    def instantiate(self, value):
        assert self._indirection is None
        self._indirection = value

    def uninstantiate(self):
        self._indirection = None

    def show(self):
        if self._indirection is None:
            return '?{prefix}{index}'.format(
                       prefix=self.prefix,
                       index=self.index
                   )
        else:
            return self._indirection.show()

    def is_instantiated(self):
        return self._indirection is not None

class Thunk(Value):
    "Represents a suspended computation."

    def __init__(self, expr, env):
        self.expr = expr
        self.env = env

    def show(self):
        return '<thunk {expr} {env}>'.format(expr=self.expr, env=self.env)

    def is_thunk(self):
        return True

    def is_decided(self):
        return False

class IntegerConstant(Value):
    "Represents a number."

    def __init__(self, value):
        self.value = value

    def show(self):
        return '{n}'.format(n=self.value)

    def is_integer_constant(self):
        return True

    def is_rigid(self):
        return True

class RigidStructure(Value):
    "Represents a constructor applied to a number of arguments."

    def __init__(self, constructor, args):
        self.constructor = constructor
        self.args = args

    def show(self):
        return ' '.join([self.constructor] +
                        [arg.show() for arg in self.args])

    def is_rigid_structure(self):
        return True

    def is_rigid(self):
        return True

def unit():
    return RigidStructure(common.VALUE_UNIT, [])

class FlexStructure(Value):
    "Represents a symbolic variable applied to a number of arguments."

    def __init__(self, symbol, args):
        self.symbol = symbol
        self.args = args

    def show(self):
        return ' '.join([self.symbol.show()] +
                        [arg.show() for arg in self.args])

    def is_flex_structure(self):
        return True

    def is_decided(self):
        # The value is decided if the symbol is flex, that is,
        # it has NOT been instantiated yet.
        return not self.symbol.is_instantiated()

class Primitive(Value):
    """"Represents a partially applied (but *not* fully applied) primitive.
        such as (_>>_ foo) or (_+_ 10)."""

    def __init__(self, name, args):
        self.name = name
        self.args = args

    def is_primitive(self):
        return True

    def is_rigid(self):
        return True

class Closure(Value):
    "Represents a closure (lambda function enclosed in an environment)."

    def __init__(self, var, body, env):
        self.var = var
        self.body = body
        self.env = env

    def show(self):
        return '<closure>'

    def is_closure(self):
        return True

    def is_rigid(self):
        return True

