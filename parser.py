import bisect

import common
import token
import lexer
import syntax

DEFAULT_PRECEDENCE = 200

class PrecedenceLevel(object):

    def __init__(self, fixity, precedence):
        self._fixity = fixity
        self._precedence = precedence
        self._operators = set([])

    def key(self):
        return self._precedence, self._fixity

    def fixity(self):
        return self._fixity

    def declare_operator(self, name):
        self._operators.add(name)

    def operators(self):
        return self._operators

def is_prefix(list1, list2):
    return len(list1) <= len(list2) and list2[:len(list1)] == list1

def is_binary_operator(name):
    parts = lexer.operator_to_parts(name)
    return len(parts) == 3 \
       and parts[0] == '' \
       and parts[1] != '' \
       and parts[2] == ''

class PrecedenceTable(object):

    def __init__(self):
        self._table = {}
        self._table_keys = []
        self._operators = set([])
        self._parts = set([])

    def declare_operator(self, fixity, precedence, name, position=None):
        if not common.is_operator(name):
            self.fail('not-an-operator', name=name, position=position)
        if name in self._operators:
            self.fail('operator-already-exists', name=name,
                                                 position=position)

        for part in lexer.operator_to_parts(name):
            if part != '':
                self._parts.add(part)

        self._operators.add(name)
        key = precedence, fixity

        if key not in self._table:
            self._table[key] = PrecedenceLevel(fixity, precedence)
            self._table_keys = sorted(self._table.keys())
        self._table[key].declare_operator(name)

    def fixity(self, key):
        return self._table[key].fixity()

    def is_declared_operator(self, name):
        return name in self._operators

    def is_declared_part(self, name):
        return name in self._parts

    def is_status_in_level(self, key, status):
        level = self._table[key]
        for operator in level.operators():
            if status == lexer.operator_to_parts(operator):
                return True
        return False

    def is_status_prefix_in_level(self, key, status):
        if status in [[], ['']]:
            return True
        level = self._table[key]
        for operator in level.operators():
            if is_prefix(status, lexer.operator_to_parts(operator)):
                return True
        return False

    def is_binop_in_level(self, key, name):
        level = self._table[key]
        for operator in level.operators():
            if lexer.operator_to_parts(operator) == ['', name, '']:
                return True
        return False

    def first_level(self):
        if len(self._table_keys) == 0:
            return None
        else:
            return self._table_keys[0]

    def next_level(self, key):
        index = bisect.bisect_left(self._table_keys, key)
        if index < len(self._table_keys) - 1:
            return self._table_keys[index + 1]
        else:
            return None

    def fail(self, msg, **args):
        raise common.LangException(
                'parser',
                msg,
                **args
              )

class Parser(object):

    def __init__(self, source, filename='...'):
        self._token_stream = lexer.Lexer(source, filename=filename).tokens()
        self._prectable = PrecedenceTable()
        self.next_token()

        # Primitive operators
        self.declare_operator(token.INFIXR, 50, '_→_')
        self.declare_operator(token.INFIXR, 100, '_<>_')
        self.declare_operator(token.INFIXR, 150, '_>>_')

    def program(self):
        position = self.current_position()
        self.match(token.BEGIN)
        data_declarations = []
        value_declarations = []
        while self._token.type() == token.DELIM:
            self.match(token.DELIM)
            for decl in self.toplevel_declaration():
                if decl.is_data_declaration():
                    data_declarations.append(decl)
                else:
                    value_declarations.append(decl)
        self.match(token.END)
        self.match(token.EOF)
        return syntax.Program(
                 data_declarations=data_declarations,
                 body=syntax.Let(declarations=value_declarations,
                                 body=syntax.Variable(name="main"),
                                 position=position),
                 position=position,
               )

    def toplevel_declaration(self):
        if self._token.type() in [token.INFIX, token.INFIXR, token.INFIXL]:
            self.fixity_declaration()
            return []
        elif self._token.type() == token.DATA:
            return [self.data_declaration()]
        else:
            return [self.value_declaration()]

    def fixity_declaration(self):
        position = self.current_position()
        fixity = self._token.type()
        self.match_any([token.INFIX, token.INFIXR, token.INFIXL])
        precedence = self.num()
        name = self._token.value() # Do not use self.id() here.
        self.match(token.ID)
        if fixity in [token.INFIXL, token.INFIXR] and \
           not is_binary_operator(name):
            self.fail('must-be-binary-operator', name=name)
        self.declare_operator(fixity, precedence, name, position=position)

    def data_declaration(self):
        position = self.current_position()
        self.match(token.DATA)
        lhs = self.expression()
        self.match(token.WHERE)
        constructors = self.constructor_declarations()
        return syntax.DataDeclaration(lhs=lhs,
                                      constructors=constructors,
                                      position=position)

    def value_declarations(self):
        declarations = []
        self.match(token.BEGIN)
        while self._token.type() == token.DELIM:
            self.match(token.DELIM)
            declarations.append(self.value_declaration())
        self.match(token.END)
        return declarations

    def value_declaration(self):
        if self._token.type() != token.ID:
            self.fail('expected-value-declaration', got=self._token)
        tok = self._token
        self.next_token()
        if self._token.type() == token.COLON:
            self.unshift(tok)
            return self.type_declaration()
        else:
            self.unshift(tok)
            return self.declaration()

    def type_declaration(self):
        position = self.current_position()
        name = self._token.value() # Do not use self.id() here.
        self.match(token.ID)
        if common.is_operator(name) and not self.is_declared_operator(name):
            self.declare_operator(token.INFIX, DEFAULT_PRECEDENCE, name)

        self.match(token.COLON)
        type = self.expression()
        return syntax.TypeDeclaration(name=name, type=type, position=position)

    def declaration(self):
        position = self.current_position()
        lhs = self.expression()
        self.match(token.EQ)
        rhs = self.expression()
        if self._token.type() == token.WHERE:
            self.match(token.WHERE)
            where = self.value_declarations()
        else:    
            where = []
        return syntax.Declaration(lhs=lhs, rhs=rhs, where=where,
                                  position=position)

    def constructor_declarations(self):
        self.match(token.BEGIN)
        decls = []
        while self._token.type() == token.DELIM:
            self.match(token.DELIM)
            decls.append(self.type_declaration())
        self.match(token.END)
        return decls

    def id(self):
        name = self._token.value()
        if self.is_operator_part():
            self.fail('operator-part-is-not-a-variable', name=name)
        self.match(token.ID)
        if common.is_operator(name) and not self.is_declared_operator(name):
            self.fail('undeclared-operator', name=name)
        return name

    def num(self):
        tok = self._token
        self.match(token.NUM)
        return tok.value()

    def expression(self):
        return self.expression_mixfix()

    def expression_mixfix(self, level=0):
        if level == 0:
            level = self._prectable.first_level()
        if level is None:
            return self.application()
        fixity = self._prectable.fixity(level)
        if fixity == token.INFIX:
            return self.expression_infix(level)
        elif fixity == token.INFIXL:
            return self.expression_infixl(level)
        elif fixity == token.INFIXR:
            return self.expression_infixr(level)
        else:
            print(fixity)
            raise Exception('Fixity not implemented.')

    def expression_infix(self, level):
        position = self.current_position()
        status = []
        children = []
        while not self.end_of_expression():
            tokval = self._token.value()
            must_read_part = (
              (len(status) == 0
               and self.is_operator_part()
               and self._prectable.is_status_prefix_in_level(level, [tokval]))
              or
              (len(status) > 0 and status[-1] == '')
            )
            if must_read_part:
                status.append(tokval)
                if not self.is_operator_part() or \
                   not self._prectable.is_status_prefix_in_level(level, status):
                    if len(status) == 2:
                        status.pop()
                        break
                    else:
                        self.fail('expected-operator-part',
                                  status=lexer.operator_from_parts(status))
                self.next_token()
            else:
                status.append('')
                next_level = self._prectable.next_level(level)
                children.append(self.expression_mixfix(level=next_level))
            if self._prectable.is_status_in_level(level, status):
                expr = syntax.Variable(name=lexer.operator_from_parts(status))
                for arg in children:
                    expr = syntax.Application(fun=expr, arg=arg,
                                              position=position)
                return expr
        if status == ['']:
            return children[0]
        self.fail('cannot-parse-expression')

    def expression_infixl(self, level):
        position = self.current_position()
        next_level = self._prectable.next_level(level)
        expr = self.expression_mixfix(level=next_level)
        while self.is_operator_part() and \
              self._prectable.is_binop_in_level(level, self._token.value()):
            op = lexer.operator_from_parts(['', self._token.value(), ''])
            operator = syntax.Variable(name=op, position=position)
            self.next_token()
            arg = self.expression_mixfix(level=next_level)
            expr = syntax.Application(
                     fun=syntax.Application(
                           fun=operator,
                           arg=expr,
                           position=position),
                     arg=arg,
                     position=position)
        return expr

    def expression_infixr(self, level):
        position = self.current_position()
        next_level = self._prectable.next_level(level)
        expr = self.expression_mixfix(level=next_level)
        if self.is_operator_part() and \
           self._prectable.is_binop_in_level(level, self._token.value()):
            op = lexer.operator_from_parts(['', self._token.value(), ''])
            operator = syntax.Variable(name=op, position=position)
            self.next_token()
            arg = self.expression_mixfix(level=level)
            return syntax.Application(
                     fun=syntax.Application(
                           fun=operator,
                           arg=expr,
                           position=position),
                     arg=arg,
                     position=position)
        else:
            return expr

    def end_of_expression(self):
        return self._token.type() in [
            token.EQ,
            token.WHERE,
            token.DELIM,
            token.RPAREN,
            token.END,
        ]

    def application(self):
        position = self.current_position()
        expr = self.atom()
        while not self.end_of_application():
            arg = self.atom()
            expr = syntax.Application(fun=expr, arg=arg, position=position)
        return expr

    def end_of_application(self):
        return self.is_operator_part() or self.end_of_expression()

    def atom(self):
        position = self.current_position()
        if self._token.type() == token.LPAREN:
            self.match(token.LPAREN)
            expr = self.expression()
            self.match(token.RPAREN)
            return expr
        elif self._token.type() == token.NUM:
            return syntax.IntegerConstant(value=self.num(), position=position)
        elif self._token.type() == token.ID:
            return syntax.Variable(name=self.id(), position=position)
        elif self._token.type() == token.UNDERSCORE:
            self.next_token()
            return syntax.Wildcard(position=position)
        self.fail('expected-atom', got=self._token)

    ##

    def declare_operator(self, fixity, precedence, name, position=None):
        if position is None:
            position = self._token.position()
        self._prectable.declare_operator(fixity, precedence, name,
                                         position=position)

    def is_declared_operator(self, name):
        return self._prectable.is_declared_operator(name)

    def match(self, type):
        if self._token.type() == type:
            self.next_token() 
        else:
            self.fail('token-mismatch', expected=type, got=self._token)

    def match_any(self, types):
        if self._token.type() in types:
            self.next_token() 
        else:
            self.fail('token-mismatch', expected=types, got=self._token)

    def unshift(self, token):
        prev_token = self._token
        prev_stream = self._token_stream
        def g():
            yield prev_token
            yield from prev_stream
        self._token_stream = g()
        self._token = token

    def current_position(self):
        return self._token.position()

    def next_token(self):
        try:
            self._token = next(self._token_stream)
        except StopIteration:
            pass

    def is_operator_part(self):
        return self._token.type() == token.ID and \
               self._prectable.is_declared_part(self._token.value())

    def fail(self, msg, **args):
        raise common.LangException(
                'parser',
                msg,
                position=self._token.position(),
                **args
              )

if __name__ == '__main__':
    import sys

    parser = Parser(sys.stdin.read())
    print(syntax.pprint(parser.program()))

