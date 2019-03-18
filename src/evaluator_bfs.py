import common
import syntax
import environment
import values

class PrimitiveDescriptor:

    def __init__(self, arity):
        self.arity = arity

def primitive_constructors():
    return set([common.VALUE_UNIT])

def primitive_functions():
    return {
        common.OP_UNIFY: PrimitiveDescriptor(arity=2),
        common.OP_ALTERNATIVE: PrimitiveDescriptor(arity=2),
        common.OP_SEQUENCE: PrimitiveDescriptor(arity=2),
    }

def exception_with(message):
    raise Exception(message)

def check_stragety(strategy):
    assert strategy in ['weak', 'strong']

def is_weak_strategy(strategy):
    strategy == 'weak'

class Evaluator:

    def __init__(self):
        self._constructors = primitive_constructors()
        self._primitives = primitive_functions()
    
    def add_constructors(self, program_declarations):
        for declaration in program_declarations:
            for constructor in declaration.constructors:
                self._constructors.add(constructor.name)

    def eval_program(self, program, strategy='weak'):
        check_stragety(strategy)
        self.add_constructors(program.data_declarations)
        env = environment.PersistentEnvironment()
        yield from (self.eval_expression(program.body, env) if is_weak_strategy(strategy) 
                else self.strong_eval_expression(program.body, env))

    def strong_eval_expression(self, expr, env):
        for value in self.eval_expression(expr, env):
            yield from self.strong_eval_value(value)
    
    def strong_eval_values(self, values):
        if len(values) == 0: yield [] ; return
        for v0 in self.strong_eval_value(values[0]):
            for vs in self.strong_eval_values(values[1:]):
                # NOTE: the values may have lost their decidedness.
                result = [v0] + vs
                if all([w.is_strongly_decided() for w in result]):
                    yield result
                else:
                    yield from self.strong_eval_values(result)

    def eval_expression(self, expr, env):
        yield from (
            self.eval_value(expr) if isinstance(expr, values.Value)
            else self.eval_integer_constant(expr) if expr.is_integer_constant()
            else self.eval_variable_or_constructor(expr, env) if expr.is_variable()
            else self.eval_lambda(expr, env) if expr.is_lambda()
            else self.eval_application(expr, env) if expr.is_application()
            else self.eval_let(expr, env) if expr.is_let()
            else self.eval_fresh(expr, env) if expr.is_fresh()
            else exception_with('Evaluation not implemented for {cls}.'.format(cls=type(expr)))
        )

    def strong_eval_value(self, value):
        yield from (
            self.yield_value(value) if value.is_integer_constant() or value.is_closure()
            else self.strong_eval_expressions(value) if value.is_thunk()
            else self.strong_eval_primitives(value) if value.is_primitive()
            else self.strong_eval_rigid_strutures(value) if value.is_rigid_structure()
            else self.strong_eval_flex_structure(value) if value.is_flex_structure()
            else exception_with('Strong evaluation not implemented for {cls}.'.format(cls=type(value)))
        )

    def yield_value(self, value):
        yield value

    def strong_eval_expressions(self, value):
        for v in self.strong_eval_expression(value.expr, value.env):
            yield v

    def strong_eval_primitives(self, value):
        for vargs in self.strong_eval_values(value.args):
            yield values.Primitive(value.name, vargs)

    def strong_eval_rigid_strutures(self, value):
        for vargs in self.strong_eval_values(value.args):
            yield values.RigidStructure(value.constructor, vargs)

    def strong_eval_flex_structure(self, value):
        for vargs in self.strong_eval_values(value.args):
            yield (values.FlexStructure(value.symbol, vargs) if value.is_decided()
                else self.strong_eval_apply_many(value, vargs))

    def strong_eval_apply_many(self, value, vargs):
        for v in self.apply_many(value.symbol.representative(), vargs):
            yield from self.strong_eval_value(v)

    def eval_integer_constant(self, expr):
        yield values.IntegerConstant(expr.value)

    def eval_variable_or_constructor(self, expr, env):
        if env.is_defined(expr.name):
            yield from self.eval_defined_variable_or_constructor(expr, env)
        else: 
            yield (
                values.RigidStructure(expr.name, []) if expr.name in self._constructors
                else values.Primitive(expr.name, []) if expr.name in self._primitives
                else exception_with('Name {name} is not a variable nor a constructor.'.format(name=expr.name))
            )

    def eval_defined_variable_or_constructor(self, expr, env):
        value0 = env.value(expr.name)
        for value in self.eval_value(value0):
            env.set(expr.name, value)
            yield value
            env.set(expr.name, value0)

    def eval_lambda(self, expr, env):
        yield values.Closure(expr.var, expr.body, env)

    def eval_application(self, expr, env):
        for value in self.eval_expression(expr.fun, env):
            yield from self.apply(value, values.Thunk(expr.arg, env))

    def eval_let(self, expr, env):
        extended_env = env.extended()
        for decl in expr.declarations:
            if not decl.is_definition(): continue
            extended_env.define(decl.lhs.name, values.Thunk(decl.rhs, extended_env))

        yield from self.eval_expression(expr.body, extended_env)

    def eval_fresh(self, expr, env):
        extended_env = env.extended()
        symbol = values.Metavar(prefix=expr.var)
        env.define(expr.var, values.FlexStructure(symbol, []))
        yield from self.eval_expression(expr.body, extended_env)

    def eval_value(self, value):
        yield from (
            self.yield_value(value) if value.is_decided()
            else self.eval_expression(value.expr, value.env) if value.is_thunk()
            else self.eval_flex_structure(value) if value.is_flex_structure()
            else exception_with('Evaluation not implemented for value {cls}.'.format(cls=type(value)))
        )

    def eval_flex_structure(self, value):
        assert value.symbol.is_instantiated()
        yield from self.apply_many(value.symbol.representative(), value.args)

    def apply_many(self, value, vargs):
        yield from (
            self.yield_value(value) if not vargs
            else self.apply_many_aux(value, vargs)
        )
    
    def apply_many_aux(self, value, vargs):
        for v in self.apply(value, vargs[0]):
                yield from self.apply_many(v, vargs[1:])
            
    def apply(self, value, varg):
        yield from (
            self.apply_expressions(value, varg) if value.is_thunk()
            else self.apply_rigid(value, varg) if value.is_rigid_structure()
            else self.apply_flex(value, varg) if value.is_flex_structure()
            else self.apply_closure(value, varg) if value.is_closure()
            else self.apply_primitive(value, varg) if value.is_primitive()
            else exception_with('Application not implemented for {cls}.'.format(cls=type(value)))
        )

    def apply_expressions(self, value, varg):
        for v in self.eval_expression(value.expr, value.env):
                yield from self.apply(v, varg)

    def apply_rigid(self, value, varg):
        yield values.RigidStructure(value.constructor, value.args + [varg])

    def apply_flex(self, value, varg):
        yield values.FlexStructure(value.symbol, value.args + [varg])

    def apply_closure(self, value, varg):
        extended_env = value.env.extended()
        extended_env.define(value.var, varg)
        yield from self.eval_expression(value.body, extended_env)

    def apply_primitive(self, value, varg):
        assert value.name in self._primitives
        vargs = value.args + [varg]

        if len(vargs) < self._primitives[value.name].arity:
            yield values.Primitive(value.name, vargs)
            return

        yield from (
            self.primitive_sequence(*vargs) if value.name == common.OP_SEQUENCE
            else self.primitive_alternative(*vargs) if value.name == common.OP_ALTERNATIVE
            else self.primitive_unify(*vargs) if value.name == common.OP_UNIFY
            else exception_with('Primitive "{name}" not implemented.'.format(name=value.name))
        )

    def primitive_sequence(self, value1, value2):
        for _ in self.eval_value(value1):
            for v2 in self.eval_value(value2): yield v2

    def primitive_alternative(self, val1, val2):
        for v in self.eval_value(val1): yield v
        for v in self.eval_value(val2): yield v

    def primitive_unify(self, val1, val2):
        yield from self.unify([(val1, val2)])

    def unify(self, goals):
        if not goals: yield values.unit() ; return

        (value1, value2) = goals[0]
        goals = goals[1:]

        if not value1.is_decided():
            for v1 in self.eval_value(value1):
                yield from self.unify([(v1, value2)] + goals)
            return

        elif not value2.is_decided():
            for v2 in self.eval_value(value2):
                yield from self.unify([(value1, v2)] + goals)
            return

        if value1.is_integer_constant() and value2.is_integer_constant():
            if value1.value == value2.value: yield from self.unify(goals)

        elif value1.is_rigid_structure() and value2.is_rigid_structure():
            if value1.constructor == value2.constructor and \
               len(value1.args) == len(value2.args):
                subgoals = list(zip(value1.args, value2.args))
                yield from self.unify(subgoals + goals)

        # Same head:
        #    x t1 ... tn == x s1 ... sn
        #elif val1.is_flex_structure() \
        #         and val2.is_flex_structure() \
        #         and val1.symbol == val2.symbol \
        #         and len(val1.args) == len(val2.args):
        #     subgoals = list(zip(val1.args, val2.args))
        #     yield from self.unify(subgoals + goals)
        elif value1.is_flex_structure() and len(value1.args) == 0:
            # TODO: occurs check
            assert not value1.symbol.is_instantiated() # decided
            value1.symbol.instantiate(value2)
            yield from self.unify(goals)
            value1.symbol.uninstantiate()
        elif value1.is_flex_structure() and len(value1.args) > 0:
            # TODO: occurs check
            assert not value1.symbol.is_instantiated() # decided
            new_var = syntax.fresh_variable()
            params = [syntax.fresh_variable() for arg in value1.args]
            term = syntax.lambda_many(
                     [p.name for p in params],
                     syntax.alternative(
                       syntax.sequence_many1(
                         [syntax.unify(p, a)
                            for p, a in zip(params, value1.args)],
                         value2 # body
                       ),
                       syntax.application_many(new_var, params)
                     )
                   )
            env = environment.PersistentEnvironment()
            env.define(new_var.name, 
                       values.FlexStructure(
                         values.Metavar(prefix='F'),
                         []))
            value1.symbol.instantiate(
                values.Thunk(
                    term,
                    env
                )
            )
            yield from self.unify(goals)
            value1.symbol.uninstantiate()
        elif value2.is_flex_structure():
            yield from self.unify([(value2, value1)] + goals)
        else:
            return # Otherwise we fail