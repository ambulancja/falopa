
class AST:

    def __init__(self, attributes, **kwargs):
        if 'position' in kwargs:
            self.position = kwargs['position']
            del kwargs['position']
        else:
            self.position = None

        assert sorted(kwargs.keys()) == sorted(attributes)
        self._attributes = attributes
        for attr in attributes:
            setattr(self, attr, kwargs[attr])

    def __repr__(self):
        attrs = []
        for attr in self._attributes:
            attrs.append(
                '{attr}={value}'.format(
                    attr=attr,
                    value=repr(getattr(self, attr))
                )
            )
        return '{cls}({attrs})'.format(
                    cls=self.__class__.__name__,
                    attrs=', '.join(attrs)
               )

    def is_data_declaration(self):
        return False

    def is_application(self):
        return False

    def is_variable(self):
        return False

    def is_forall(self):
        return False

    def is_arrow_type(self):
        return self.is_application() and \
               self.fun.is_application() and \
               self.fun.fun.is_variable() and \
               self.fun.fun.name == '_→_'

    def application_head(self):
        expr = self
        while expr.is_application():
            expr = expr.fun
        return expr

    def pprint(self, level=0):
        indent = ' ' * level
        attrs = []
        for attr in self._attributes:
            next_level = level + 2
            attrs.append(
                '{indent}  {attr}={value}\n'.format(
                    attr=attr,
                    value=pprint(getattr(self, attr), level=next_level),
                    indent=indent,
                )
            )
        if len(attrs) == 0:
            args = ''
        else:
            args = '(\n{attrs}{indent})'.format(
              attrs=''.join(attrs),
              indent=indent,
            )

        return self.__class__.__name__ + args

def pprint(x, level=0):
    if isinstance(x, AST):
        return x.pprint(level=level)
    elif isinstance(x, list):
        if len(x) == 0:
            return '[]'
        else:
            return '[\n' + \
                   '\n'.join([
                     (level + 2) * ' ' + pprint(y, level=level + 2)
                     for y in x
                    ]) + \
                    '\n' + level * ' ' + ']'
    else:
        return repr(x)

# Program

class Program(AST):

    def __init__(self, **kwargs):
        AST.__init__(self,
                     ['data_declarations', 'body'],
                     **kwargs)

# Declarations

class DataDeclaration(AST):

    def __init__(self, **kwargs):
        AST.__init__(self, ['lhs', 'constructors'], **kwargs)

    def is_data_declaration(self):
        return True

class TypeDeclaration(AST):

    def __init__(self, **kwargs):
        AST.__init__(self, ['name', 'type'], **kwargs)

class Declaration(AST):

    def __init__(self, **kwargs):
        AST.__init__(self, ['lhs', 'rhs', 'where'], **kwargs)

# Expressions

class Wildcard(AST):

    def __init__(self, **kwargs):
        AST.__init__(self, [], **kwargs)

    def free_variables(self):
        return set([])

class IntegerConstant(AST):

    def __init__(self, **kwargs):
        AST.__init__(self, ['value'], **kwargs)

    def free_variables(self):
        return set([])

class Variable(AST):

    def __init__(self, **kwargs):
        AST.__init__(self, ['name'], **kwargs)

    def is_variable(self):
        return True

    def free_variables(self):
        return set([self.name])

class Application(AST):

    def __init__(self, **kwargs):
        AST.__init__(self, ['fun', 'arg'], **kwargs)

    def is_application(self):
        return True

    def free_variables(self):
        return self.fun.free_variables() | self.arg.free_variables()

class Let(AST):

    def __init__(self, **kwargs):
        AST.__init__(self, ['declarations', 'body'], **kwargs)

    def free_variables(self):
        free_vars = set([])
        for decl in self.declarations:
            # TODO!!! which are the bound variables??
            pass
        free_vars |= self.body.free_vars()

# Only at the type level
class Forall(AST):

    def __init__(self, **kwargs):
        AST.__init__(self, ['var', 'body'], **kwargs)

    def is_forall(self):
        return True

    def free_variables(self):
        return self.body.free_variables() - set([self.var])

