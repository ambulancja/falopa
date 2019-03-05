import common
import syntax
import kinds

def primitive_types():
    return [
        ('_→_', kinds.Fun(
                  domain=kinds.Set(),
                  codomain=kinds.Fun(
                    domain=kinds.Set(),
                    codomain=kinds.Set()
                  )
                )
        )
    ]

class Environment:

    def __init__(self):
        self._ribs = [{}]

    def define(self, name, value):
        self._ribs[-1][name] = value

    def is_locally_defined(self, name):
        return name in self._ribs[-1]

    def local_value(self, name):
        assert self.is_locally_defined(name)
        return self._ribs[-1][name]

    def is_defined(self, name):
        for i in reversed(range(len(self._ribs))):
            if name in self._ribs[i]:
                return True
        return False

    def value(self, name):
        assert self.is_defined(name)
        for i in reversed(range(len(self._ribs))):
            if name in self._ribs[i]:
                return self._ribs[i][name]

    def open_scope(self):
        self._ribs.append({})

    def close_scope(self):
        self._ribs.pop()

class TypeChecker:

    def __init__(self):
        self._typenv = Environment()
        for type_name, kind in primitive_types():
            self._typenv.define(type_name, kind)
        self._env = Environment()

    def check_program(self, program):
        # Check that data declaration LHSs are well-formed.
        for decl in program.data_declarations:
            self.check_data_declaration_lhs(decl)

        # Check that data declaration RHSs are well-formed.
        for decl in program.data_declarations:
            self.check_data_declaration_rhs(decl)

        # Check the expression of the main program
        self.check_expr(program.body)

    def check_data_declaration_lhs(self, decl):
        arity = 0
        lhs = decl.lhs
        while lhs.is_application():
            if not lhs.arg.is_variable():
                self.fail('data-lhs-arg-variable', got=lhs.arg,
                          position=lhs.position)
            lhs = lhs.fun
            arity += 1
        if not lhs.is_variable():
            self.fail('data-lhs-type-variable', got=lhs,
                      position=lhs.position)

        if self._typenv.is_locally_defined(lhs.name):
            self.fail('data-lhs-type-already-defined', name=lhs.name,
                      position=lhs.position)
        self._typenv.define(lhs.name, kinds.fresh_kind(arity))

    def check_data_declaration_rhs(self, decl):
        type_name = decl.lhs.application_head().name
        for constructor in decl.constructors:
            self.check_constructor_declaration(type_name, constructor)

    def check_constructor_declaration(self, type_name, decl):
        constructor_name = decl.name
        if self._env.is_locally_defined(constructor_name):
            self.fail('constructor-already-defined',
                      name=constructor_name,
                      position=decl.position)
        closed_type = self.close_type(decl.type)
        self._typenv.open_scope()
        self.check_type_has_atomic_kind(closed_type)
        self._typenv.close_scope()
        if not self.constructor_returns_instance(type_name, decl.type):
            self.fail('constructor-must-return-instance',
                      type_name=type_name,
                      constructor_name=constructor_name,
                      type=decl.type,
                      position=decl.type.position)
        self._env.define(constructor_name, closed_type)

    def close_type(self, type):
        free_vars = set([])
        for var in type.free_variables():
            if not self._typenv.is_defined(var):
                free_vars.add(var)
        return syntax.forall(free_vars, type)

    def check_type_has_atomic_kind(self, type):
        kind = self.check_type_kind(type)
        try:
            kinds.unify(kind, kinds.Set())
        except kinds.UnificationFailure:
            self.fail('expected-atomic-kind',
                      type=type,
                      kind=kind,
                      position=type.position)
 
    def check_type_kind(self, expr):
        # Possible types are:
        #   variables     (including _→_)
        #   applications
        #   forall's
        if expr.is_variable():
            if not self._typenv.is_defined(expr.name):
                self.fail('undefined-type',
                          name=expr.name,
                          position=expr.position)
            return self._typenv.value(expr.name)
        elif expr.is_application():
            kfun = self.check_type_kind(expr.fun)
            karg = self.check_type_kind(expr.arg)
            kres = kinds.Metavar(prefix='t')
            try:
                kinds.unify(kfun, kinds.Fun(domain=karg, codomain=kres))
            except kinds.UnificationFailure as e:
                self.fail('kinds-do-not-unify',
                          kind1=e.type1,
                          kind2=e.type2,
                          position=expr.position)
            return kres
        elif expr.is_forall():
            self._typenv.define(expr.var, kinds.Metavar(prefix='t'))
            return self.check_type_kind(expr.body)
        self.fail('expected-a-type',
                  got=expr,
                  position=expr.position)

    def constructor_returns_instance(self, type_name, expr):
        if expr.is_variable():
            return expr.name == type_name
        elif expr.is_arrow_type():
            return self.constructor_returns_instance(type_name, expr.arg)
        elif expr.is_application():
            return self.constructor_returns_instance(type_name, expr.fun)
        elif expr.is_forall():
            return self.constructor_returns_instance(type_name, expr.body)
        else:
            return False

    def check_expr(self, expr):
        if expr.is_let():
            self.check_let(expr)
        else:
            print('KE')

    def check_let(self, expr):
        # Check kinds and extend environment
        # to allow for recursive definitions.
        declared_names = set()
        definitions = {}
        self._env.open_scope()
        for decl in expr.declarations:
            if decl.is_type_declaration():
                self.check_type_declaration(decl)
                declared_names.add(decl.name)
            elif decl.is_definition():
                head = decl.lhs.application_head()
                if not head.is_variable():
                    self.fail('declaration-head-is-not-variable',
                               head=head,
                               position=decl.position)
                declared_names.add(head.name)
                definitions[head.name] = definitions.get(head.name, [])
                definitions[head.name].append(decl)
                if not self._env.is_locally_defined(head.name):
                    self._env.define(head.name, syntax.Metavar(prefix='t'))
            else:
                raise Exception('Check for declaration not implemented.')

        defined_names = set(definitions.keys())
        if declared_names != defined_names:
            missing = declared_names - defined_names
            self.fail('name-declared-but-not-defined',
                       name=missing.pop(),
                       position=expr.position)

        for name in definitions:
            desugared = self.desugar_definitions(name, definitions[name])
            print('Desugared: {d}'.format(d=desugared.show()))
            # TODO: desugar all the definitions into a single one

        ## DEBUG
        #print()
        #for rib in self._env._ribs:
        #    for k, v in rib.items():
        #        print('{k} : {v}'.format(k=k, v=v.show()))
        #        print()
        ## END DEBUG

        ## DEBUG
        #for name in defined_names:
        #    print(name)
        #    for decl in definitions[name]:
        #        print('  {decl}'.format(decl=decl.show()))
        #    print()
        ## END DEBUG

        # TODO: check types
        self._env.close_scope()

    def check_type_declaration(self, decl):
        if self._env.is_locally_defined(decl.name):
            self.fail('value-already-defined', name=decl.name,
                      position=decl.position)
        closed_type = self.close_type(decl.type)
        self._typenv.open_scope()
        self.check_type_has_atomic_kind(closed_type)
        self._typenv.close_scope()
        self._env.define(decl.name, closed_type)

    def desugar_definitions(self, name, decls):
        position = decls[0].position
        alternatives = []
        for decl in decls:
            args = decl.lhs.application_args()
            body = decl.rhs
            params = [
              syntax.fresh_variable(position=position) for arg in args
            ]
            # TODO: unify params with args
            # TODO: check where clause
            alternatives.append(syntax.lambda_([p.name for p in params], body))
        return syntax.Definition(lhs=syntax.Variable(name=name,
                                                     position=position),
                                 rhs=alternatives[0], # TODO: sum alternatives
                                 where=[],
                                 position=position)

    def fail(self, msg, **args):
        raise common.LangException(
                'typechecker',
                msg,
                **args
              )

