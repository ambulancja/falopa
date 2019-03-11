import syntax
import environment

class Thunk:

    def __init__(self, expr, env):
        self.expr = expr
        self.env = env

class Evaluator:

    def __init__(self):
        self._constructors = set()

    def eval(self, program):
        for data_decl in program.data_declarations:
            for constructor in data_decl.constructors:
                self._constructors.add(constructor.name)
        env = environment.PersistentEnvironment()
        yield from self.eval_expression(program.body, env)

    def eval_expression(self, expr, env):
        if expr.is_integer_constant():
            yield expr
        elif expr.is_variable():
            yield from self.eval_variable_or_constructor(expr, env)
        elif expr.is_let():
            yield from self.eval_let(expr, env)
        else:
            raise Exception(
                    'Evaluation not implemented for {cls}.'.format(
                       cls=type(expr)
                    )
                  )

    def eval_let(self, expr, env):
        extended_env = env.extended()
        exprs = []
        for decl in expr.declarations:
            if not decl.is_definition():
                continue
            extended_env.define(decl.lhs.name, Thunk(decl.rhs, env))
        yield from self.eval_expression(expr.body, extended_env)

    def eval_variable_or_constructor(self, expr, env):
        if env.is_defined(expr.name):
            thunk = env.value(expr.name)
            for value in self.eval_expression(thunk.expr, thunk.env):
                env.define(expr.name, value)
                yield value
                env.define(expr.name, thunk)
        elif expr.name in self._constructors:
            yield syntax.Constructor(name=expr.name, position=expr.position)
        else:
            raise Exception(
                    'Name {name} is not a variable nor a constructor.'.format(
                      name=expr.name
                    )
                  )

