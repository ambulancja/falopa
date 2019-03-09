
class Evaluator:

    def eval(self, expr):
        if expr.is_integer_constant():
            yield expr
        else:
            raise Exception(
                    'Evaluation not implemented for {cls}.'.format(
                       cls=type(expr)
                    )
                  )

