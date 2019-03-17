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
        yield (self.eval_expression(program.body, env) if is_weak_strategy(strategy) 
                else self.strong_eval_expression(program.body, env))

    def strong_eval_expression(self, expr, env):
        for value in self.eval_expression(expr, env):
            yield from self.strong_eval_value(value)

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
        yield (
            self.strong_eval_expressions(value) if value.is_thunk()
            else value if value.is_integer_constant() or value.is_closure()
            else self.strong_eval_primitives(value) if value.is_primitive()
            else self.strong_eval_rigid_strutures(value) if value.is_rigid_structure()
            else self.strong_eval_flex_structure(value) if value.is_flex_structure()
            else exception_with('Strong evaluation not implemented for {cls}.'.format(cls=type(value)))
        )
            
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

