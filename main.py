import sys

import syntax
import parser
import typecheck

def run(filename):
    with open(filename) as f:
        source = f.read()
        parse = parser.Parser(source, filename=filename)
        ast = parse.program()
        #print(syntax.pprint(ast))

        checker = typecheck.TypeChecker()
        checker.check_program(ast)

def usage(program):
    sys.stderr.write('Usage: {program} input.fa'.format(program=program))
    sys.exit()

def main(argv):
    if len(argv) == 2:
        run(argv[1])
    else:
        usage(argv[0])

if __name__ == '__main__':
    main(sys.argv)

