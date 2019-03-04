import common
import syntax
import types

def primitive_types():
    return [
        ('_→_', types.Fun(
                  domain=types.Set(),
                  codomain=types.Fun(
                    domain=types.Set(),
                    codomain=types.Set()
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

        # TODO: extend environment for recursive definitions
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
        self._typenv.define(lhs.name, types.fresh_kind(arity))

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

        free_vars = set([])
        for var in decl.type.free_variables():
            if not self._typenv.is_defined(var):
                free_vars.add(var)

        closed_type = decl.type
        for var in free_vars:
            closed_type = syntax.Forall(var=var, body=closed_type)

        self._typenv.open_scope()
        kind = self.check_kind(closed_type)

        try:
            types.unify(kind, types.Set())
        except types.UnificationFailure:
            self.fail('expected-atomic-kind',
                      type=decl.type,
                      kind=kind,
                      position=decl.type.position)

        #for var in free_vars:
        #    print("{var} :: {kind}".format(
        #          var=var,
        #          kind=self._typenv.local_value(var)))
        #print("constructor :: {kind}".format(kind=kind))
        self._typenv.close_scope()
        if not self.constructor_returns_instance(type_name, decl.type):
            self.fail('constructor-must-return-instance',
                      type_name=type_name,
                      constructor_name=constructor_name,
                      type=decl.type,
                      position=decl.type.position)

        self._env.define(constructor_name, closed_type)

        ## DEBUG
        for rib in self._typenv._ribs:
            for k, v in rib.items():
                print(k, v)
        for rib in self._env._ribs:
            for k, v in rib.items():
                print(k, v)
        ## END DEBUG
 
    def check_kind(self, expr):
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
            kfun = self.check_kind(expr.fun)
            karg = self.check_kind(expr.arg)
            kres = types.Metavar(prefix='t')
            try:
                types.unify(kfun, types.Fun(domain=karg, codomain=kres))
            except types.UnificationFailure as e:
                self.fail('kinds-do-not-unify',
                          kind1=e.type1,
                          kind2=e.type2,
                          position=expr.position)
            return kres
        elif expr.is_forall():
            self._typenv.define(expr.var, types.Metavar(prefix='t'))
            return self.check_kind(expr.body)
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

    def check_expr(self, decl):
        pass

    def fail(self, msg, **args):
        raise common.LangException(
                'typechecker',
                msg,
                **args
              )

