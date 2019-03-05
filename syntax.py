import common
import lexer

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

    def is_type_declaration(self):
        return False

    def is_definition(self):
        return False

    def is_application(self):
        return False

    def is_variable(self):
        return False

    def is_let(self):
        return False

    def is_forall(self):
        return False

    def is_metavar(self):
        return False

    def is_atom(self):
        return False

    def is_arrow_type(self):
        return self.is_application() and \
               self.fun.is_application() and \
               self.fun.fun.is_variable() and \
               self.fun.fun.name == common.OP_ARROW

    def application_head(self):
        expr = self
        while expr.is_application():
            expr = expr.fun
        return expr

    def application_args(self):
        expr = self
        args = []
        while expr.is_application():
            args.insert(0, expr.arg)
            expr = expr.fun
        return args

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

    def show(self):
        return self.pprint()

    def showp(self):
        if self.is_atom():
            return self.show()
        else:
            return '(' + self.show() + ')'

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

    def is_type_declaration(self):
        return True

class Definition(AST):

    def __init__(self, **kwargs):
        AST.__init__(self, ['lhs', 'rhs', 'where'], **kwargs)

    def is_definition(self):
        return True

    def show(self):
        lines = [self.lhs.show() + ' = ' + self.rhs.show()]
        if len(self.where) > 0:
          lines.append('  where')
          for decl in self.where:
            lines.append(common.indent(decl.show(), 4))
        return '\n'.join(lines)

# Expressions

class Wildcard(AST):

    def __init__(self, **kwargs):
        AST.__init__(self, [], **kwargs)

    def free_variables(self):
        return set()

    def show(self):
        return '_'

    def is_atom(self):
        return True

class IntegerConstant(AST):

    def __init__(self, **kwargs):
        AST.__init__(self, ['value'], **kwargs)

    def free_variables(self):
        return set()

    def show(self):
        return str(self.value)

    def is_atom(self):
        return True

class Variable(AST):

    def __init__(self, **kwargs):
        AST.__init__(self, ['name'], **kwargs)

    def is_variable(self):
        return True

    def free_variables(self):
        return set([self.name])

    def show(self):
        return self.name

    def is_atom(self):
        return True

def fresh_variable(prefix='x', position=None):
    return Variable(name='{prefix}.{index}'.format(
                            prefix=prefix,
                            index=common.fresh_index(),
                            position=position,
                         ))

class Application(AST):

    def __init__(self, **kwargs):
        AST.__init__(self, ['fun', 'arg'], **kwargs)

    def is_application(self):
        return True

    def free_variables(self):
        return self.fun.free_variables() | self.arg.free_variables()

    def show(self):
        if self.is_arrow_type():
            return self.show_arrow_type()
        head = self.application_head()
        args = self.application_args()
        wrap_head = True
        if head.is_variable():
            arity = self._operator_arity(head.name)
            if arity == 0:
                wrap_head = False
            if len(args) >= arity:
                head = self._show_mixfix(head.name, args[:arity])
                args = args[arity:]
        else:
            head = head.show()
        if len(args) == 0:
            return head
        else:
            if wrap_head:
                head = '(' + head + ')'
            return head + ' ' + ' '.join([arg.showp() for arg in args])

    def _operator_arity(self, opr):
        arity = 0
        for part in lexer.operator_to_parts(opr):
            if part == '':
                arity += 1
        return arity

    def _show_mixfix(self, opr, args):
        res = []
        for part in lexer.operator_to_parts(opr):
            if part == '':
                res.append(args.pop(0).showp())
            else:
                res.append(part)
        return ' '.join(res)

    def show_arrow_type(self):
        parts = []
        res = self
        while res.is_arrow_type():
            parts.append(res.fun.arg.showp())
            res = res.arg
        parts.append(res.show())
        return common.OP_ARROW.join(parts)

def binop(op, e1, e2, position=None):
    if position is None:
        position = e1.position
    return Application(
             fun=Application(
               fun=Variable(name=op, position=position),
               arg=e1,
               position=position
             ),
             arg=e2,
             position=position
           )

def unify(e1, e2, position=None):
    return binop(common.OP_UNIFY, e1, e2, position=position)

def sequence(e1, e2, position=None):
    return binop(common.OP_SEQUENCE, e1, e2, position=position)

def alternative(e1, e2, position=None):
    return binop(common.OP_ALTERNATIVE, e1, e2, position=position)

def sequence_many1(es, body, position=None):
    if position is None:
        position = body.position
    for e in reversed(es):
        body = sequence(e, body, position=position)
    return body

def alternative_many(es, position=None):
    assert len(es) > 0
    if position is None:
        position = es[0].position
    body = es[-1]
    for e in reversed(es[:-1]):
        body = alternative(e, body, position=position)
    return body

class Lambda(AST):

    def __init__(self, **kwargs):
        AST.__init__(self, ['var', 'body'], **kwargs)

    def free_variables(self):
        return self.body.free_variables() - set([self.var])

    def show(self):
        return 'λ {var} . {body}'.format(
                 var=self.var,
                 body=self.body.show()
               )

def lambda_many(vars, body, position=None):
    if position is None:
        position = body.position
    for var in vars:
        body = Lambda(var=var, body=body, position=position)
    return body

class Fresh(AST):

    def __init__(self, **kwargs):
        AST.__init__(self, ['var', 'body'], **kwargs)

    def free_variables(self):
        return self.body.free_variables() - set([self.var])

    def show(self):
        return '? {var} . {body}'.format(
                 var=self.var,
                 body=self.body.show()
               )

def fresh_many(vars, body, position=None):
    if position is None:
        position = body.position
    for var in vars:
        body = Fresh(var=var, body=body, position=position)
    return body

class Let(AST):

    def __init__(self, **kwargs):
        AST.__init__(self, ['declarations', 'body'], **kwargs)

    def is_let(self):
        return True

    def free_variables(self):
        free_vars = set()
        for decl in self.declarations:
            # TODO!!! which are the bound variables??
            pass
        free_vars |= self.body.free_vars()

    def show(self):
        return 'let\n' + \
               '\n'.join([
                 common.indent(decl.show(), 4)
                   for decl in self.declarations
               ]) + '\n in\n' + \
               common.indent(self.body.show(), 4)

# Only at the type level
class Forall(AST):

    def __init__(self, **kwargs):
        AST.__init__(self, ['var', 'body'], **kwargs)

    def is_forall(self):
        return True

    def free_variables(self):
        return self.body.free_variables() - set([self.var])

    def show(self):
        return '∀ {var} . {body}'.format(
                 var=self.var,
                 body=self.body.show()
               )

def forall_many(vars, expr, position=None):
    if position is None:
        position = expr.position
    for var in vars:
        expr = Forall(var=var, body=expr, position=position)
    return expr

class Metavar(AST):

    def __init__(self, prefix='x'):
        AST.__init__(self, ['prefix', 'index'],
                            prefix=prefix, index=common.fresh_index())
        self._indirection = None

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

    def show(self):
        return '?{prefix}{index}'.format(
                 prefix=self.prefix,
                 index=self.index,
               )

def free_variables_list(es):
    fvs = set()
    for e in es:
        fvs |= e.free_variables()
    return fvs

