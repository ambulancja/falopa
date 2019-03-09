import common
import syntax
import kinds

def primitive_types():
    return [
        (common.OP_ARROW,
                kinds.Fun(
                  domain=kinds.Set(),
                  codomain=kinds.Fun(
                    domain=kinds.Set(),
                    codomain=kinds.Set()
                  )
                )
        ),
        (common.TYPE_INT, kinds.Set()),
        (common.TYPE_UNIT, kinds.Set()),
    ]

def primitive_values():
    return [
        (common.OP_ALTERNATIVE,
            syntax.Forall(
                var='a',
                body=syntax.function(
                    syntax.Variable(name='a'),
                    syntax.function(
                        syntax.Variable(name='a'),
                        syntax.Variable(name='a'))))),
        (common.OP_SEQUENCE,
            syntax.Forall(
                var='a',
                body=syntax.Forall(
                    var='b',
                    body=syntax.function(
                        syntax.Variable(name='a'),
                        syntax.function(
                            syntax.Variable(name='b'),
                            syntax.Variable(name='b')))))),
        (common.OP_UNIFY,
            syntax.Forall(
                var='a',
                body=syntax.function(
                    syntax.Variable(name='a'),
                    syntax.function(
                        syntax.Variable(name='a'),
                        syntax.primitive_type_unit())))),
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

    def current_scope(self):
        return self._ribs[-1]

    def all_values_in_parent_scopes(self):
        values = set()
        for rib in self._ribs[:-1]:
            values |= set(rib.values())
        return values

class TypeChecker:

    def __init__(self):
        self._typenv = Environment()
        for type_name, kind in primitive_types():
            self._typenv.define(type_name, kind)
        self._env = Environment()
        for value_name, type in primitive_values():
            self._env.define(value_name, type)

    def check_program(self, program):
        # Check that data declaration LHSs are well-formed.
        for decl in program.data_declarations:
            self.check_data_declaration_lhs(decl)

        # Check that data declaration RHSs are well-formed.
        for decl in program.data_declarations:
            self.check_data_declaration_rhs(decl)

        # Check the expression of the main program
        t_body, e_body = self.check_expr(program.body)
        return syntax.Program(
                 data_declarations=program.data_declarations,
                 body=e_body,
                 position=program.position,
               )

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
        return syntax.forall_many(free_vars, type)

    def check_type_has_atomic_kind(self, type):
        kind = self.check_type_kind(type)
        try:
            kinds.unify(kind, kinds.Set())
        except common.UnificationFailure:
            self.fail('expected-atomic-kind',
                      type=type,
                      kind=kind,
                      position=type.position)
 
    def check_type_kind(self, expr):
        # Possible types are:
        #   variables (including the arrow operator)
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
            except common.UnificationFailure as e:
                self.fail('kinds-do-not-unify',
                          kind1=e.kind1,
                          kind2=e.kind2,
                          position=expr.position)
            return kres
        elif expr.is_forall():
            self._typenv.define(expr.var, kinds.Metavar(prefix='t'))
            return self.check_type_kind(expr.body)
        self.fail('expected-a-type',
                  got=expr.show(),
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
            return self.check_let(expr)
        elif expr.is_variable():
            return self.check_variable(expr)
        elif expr.is_application():
            return self.check_application(expr)
        elif expr.is_fresh():
            return self.check_fresh(expr)
        elif expr.is_integer_constant():
            return self.check_integer_constant(expr)
        else:
            print(expr)
            raise Exception('NOT IMPLEMENTED')
            return 'TODO:TYPE' , expr  ### TODO

    def check_variable(self, expr):
        if not self._env.is_defined(expr.name):
            self.fail('unbound-variable',
                      name=expr.name,
                      position=expr.position)
        var_type = self._env.value(expr.name)
        while var_type.is_forall():
            var_type = var_type.forall_eliminate()
        return var_type, expr

    def check_application(self, expr):
        t_fun, e_fun = self.check_expr(expr.fun)
        t_arg, e_arg = self.check_expr(expr.arg)
        t_res = syntax.Metavar(prefix='t', position=expr.position)
        self.unify_types(t_fun, syntax.function(t_arg, t_res))
        return (t_res,
                syntax.Application(fun=e_fun, arg=e_arg,
                                   position=expr.position))

    def check_fresh(self, expr):
        self._env.open_scope()
        self._env.define(expr.var, syntax.Metavar(prefix='t',
                                                  position=expr.position))
        t_body, e_body = self.check_expr(expr.body)
        self._env.close_scope()
        return (t_body,
                syntax.Fresh(var=expr.var, body=e_body,
                             position=expr.position))

    def check_integer_constant(self, expr):
        return syntax.primitive_type_int(), expr

    def check_let(self, expr):
        # Check kinds and extend environment
        # to allow for recursive definitions.
        declared_names = set()
        definitions = {}
        definition_keys = []
        self._env.open_scope()
        type_declarations = []
        for decl in expr.declarations:
            if decl.is_type_declaration():
                decl = self.check_type_declaration(decl)
                declared_names.add(decl.name)
                type_declarations.append(decl)
            elif decl.is_definition():
                head = decl.lhs.application_head()
                if not head.is_variable():
                    self.fail('declaration-head-is-not-variable',
                               head=head,
                               position=decl.position)
                declared_names.add(head.name)
                if head.name not in definitions:
                    definition_keys.append(head.name)
                    definitions[head.name] = []
                definitions[head.name].append(decl)
                if not self._env.is_locally_defined(head.name):
                    self._env.define(head.name,
                                     syntax.Metavar(prefix='t',
                                                    position=decl.position))
            else:
                raise Exception('Check for declaration not implemented.')

        defined_names = set(definitions.keys())
        if declared_names != defined_names:
            missing = declared_names - defined_names
            self.fail('name-declared-but-not-defined',
                       name=missing.pop(),
                       position=expr.position)

        e_decls = []
        for name in definition_keys:
            e_decls.append(self.desugar_definition(name, definitions[name]))

        self.generalize_types_in_current_scope()
        self.check_declared_instantiate_real(type_declarations) 

        body_type, desugared_body = self.check_expr(expr.body)

        # To reconstruct the final AST
        desugared_declarations = []
        for e_decl in e_decls:
            t_decl = syntax.TypeDeclaration(
                         name=e_decl.lhs.name,
                         type=self._env.value(e_decl.lhs.name),
                         position=e_decl.position
                     )
            desugared_declarations.append(t_decl)
            desugared_declarations.append(e_decl)

        self._env.close_scope()
        return (body_type,
                syntax.Let(declarations=desugared_declarations,
                           body=desugared_body,
                           position=expr.position))

    def check_type_declaration(self, decl):
        if self._env.is_locally_defined(decl.name):
            self.fail('value-already-defined', name=decl.name,
                      position=decl.position)
        closed_type = self.close_type(decl.type)
        self._typenv.open_scope()
        self.check_type_has_atomic_kind(closed_type)
        self._typenv.close_scope()
        return syntax.TypeDeclaration(name=decl.name,
                                      type=closed_type,
                                      position=decl.position)

    def desugar_definition(self, name, equations):
        position = equations[0].position
        alternatives = []

        patterns_0 = equations[0].lhs.application_args()
        params = [syntax.fresh_variable(position=position)
                    for pat in patterns_0]

        definition_type = self._env.value(name)

        self._env.open_scope() # Definition scope

        param_types = []
        for param in params:
            param_type = syntax.Metavar(prefix='t', position=position)
            self._env.define(param, param_type)
            param_types.append(param_type)
        result_type = syntax.Metavar(prefix='t', position=position)

        self.unify_types(
          definition_type,
          syntax.function_many(param_types, result_type)
        )

        for equation in equations:
            alternatives.append(
              self.desugar_equation(params, param_types, result_type, equation)
            )

        rhs = syntax.lambda_many(
                [param.name for param in params],
                syntax.alternative_many(alternatives, position=position),
                position=position,
              )
        self._env.close_scope() # Definition scope
        return syntax.Definition(
                 lhs=syntax.Variable(name=name,
                                     position=position),
                 rhs=rhs,
                 where=[],
                 position=position)

    def desugar_equation(self, params, param_types, result_type, equation):
        position = equation.position
        patterns = equation.lhs.application_args()
        body = equation.rhs
        if len(patterns) != len(params):
            self.fail('equations-arity-mismatch',
                      name=name,
                      position=position)
        self._env.open_scope() # Equation scope
        fvs = set()
        for var in syntax.free_variables_list(patterns):
            if not self._env.is_defined(var):
                fvs.add(var)
                self._env.define(var, syntax.Metavar(prefix="t",
                                                     position=position))

        # TODO: force binding by prefixing a variable with "."

        if len(equation.where) == 0:
            d_type, d_body = self.check_expr(body)
        else:
            d_type, d_body = self.check_let(
              syntax.Let(declarations=equation.where, body=body,
                         position=position)
            )
        self.unify_types(d_type, result_type)

        unif_goals = []
        for param, pattern, t_param in zip(params, patterns, param_types):
            t_pattern, e_pattern = self.check_expr(pattern)
            self.unify_types(t_param, t_pattern)
            unif_goals.append(syntax.unify(param, e_pattern))

        alternative = syntax.fresh_many(
                        fvs,
                        syntax.sequence_many1(unif_goals, d_body)
                      )
        self._env.close_scope() # Equation scope
        return alternative

    def generalize_types_in_current_scope(self):
        forbidden_metavars = set()
        for value in self._env.all_values_in_parent_scopes():
            forbidden_metavars |= value.free_metavars()
        scope = self._env.current_scope()
        for var in scope:
            type = self._env.value(var)
            generalized_metavars = type.free_metavars() - forbidden_metavars
            for metavar in generalized_metavars:
                type = type.forall_introduce(metavar)
            self._env.define(var, type)

    def check_declared_instantiate_real(self, type_declarations):
        # Check that user-defined type declarations instantiate the
        # actual type.
        for decl in type_declarations:
            user_type = decl.type
            actual_type = self._env.value(decl.name)
            while user_type.is_forall():
                var = syntax.fresh_variable(user_type.var,
                                            position=decl.position)
                user_type = user_type.forall_eliminate(var)
            while actual_type.is_forall():
                actual_type = actual_type.forall_eliminate() # metavar
            self.unify_types(actual_type, user_type)

    def unify_types(self, t1, t2):
        try:
            syntax.unify_types(t1, t2)
        except common.UnificationFailure as e:
            self.fail(e.reason, position=t1.position, **e.kwargs)

    def fail(self, msg, **args):
        raise common.LangException(
                'typechecker',
                msg,
                **args
              )

