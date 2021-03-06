import yaml
import textwrap
import sys

from nodes import Node, StructDefinitionNode
import scope
import typecheck

def printerr(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)

def main(my_yaml):
    try:
        tree = yaml.safe_load(my_yaml)[0]
    except yaml.YAMLError as e:
        printerr(e)
        exit(1)

    scope.definitions = Node.create(tree)
    scope.functions = []
    struct_definitions = []
    for x in scope.definitions:
        if x.nodetype == 'function':
            if x['identifier'].data in scope.function_names:
                printerr("COMPILE ERROR:", f"Function '{x['identifier'].data}' has more than one definition.", sep="\n")
                exit(1)
            else:
                scope.functions.append(x)
                scope.function_names.append(x['identifier'].data)
        elif x.nodetype == 'struct_definition':
            struct_name = x.get_scalar('base_type')
            if (struct_name in typecheck.user_defined_types) or (struct_name in typecheck.standard_types):
                raise scope.SereneTypeError(f"Found duplicate type definition for type '{struct_name}'.")
            else:
                struct_definitions.append(x)
                typecheck.user_defined_types[struct_name] = x.get_type_spec()
        else:
            raise NotImplementedError(x.nodetype)

    if 'main' not in scope.function_names:
        printerr("COMPILE ERROR:", "No 'main()' function is defined.", sep="\n")
        exit(1)

    # struct_forward_declarations = []    # Not currently needed
    struct_definition_code = []

    try:
        sorted_structs = StructDefinitionNode.topological_ordering()
    except (scope.SereneTypeError) as exc:
        printerr("COMPILE ERROR:", exc.message, sep="\n")
        exit(1)
    
    struct_definitions.sort(key=lambda x: sorted_structs.index(x.get_scalar('base_type')), reverse=True)

    try:
        for x in struct_definitions:
            #struct_forward_declarations.append(x.to_forward_declaration())     # Not currently needed
            struct_definition_code.append(x.to_code())
    except (scope.SereneScopeError, scope.SereneTypeError) as exc:
        printerr("COMPILE ERROR:", exc.message, sep="\n")
        printerr("Did not compile.")
        exit(1)
    except Exception as exc:
        printerr(f"At struct definition for '{x.get_scalar('base_type')}':")
        raise exc

    function_code = []
    function_forward_declarations = []
    try:
        for x in scope.functions:
            function_forward_declarations.append(x.to_forward_declaration())
            function_code.append(x.to_code())
    except (scope.SereneScopeError, scope.SereneTypeError) as exc:
        printerr("COMPILE ERROR:", exc.message, sep="\n")
        exit(1)
    except Exception as exc:
        printerr(f"At source line number {scope.line_number}:")
        raise exc

    code = textwrap.dedent("""\
                           #include <iostream>
                           #include <cstdint>
                           #include "../lib/serene_printing.hh"
                           #include "../lib/serene_array.hh"
                           #include "../lib/serene_string.hh"
                           #include "../lib/serene_vector.hh"
                           #include "../lib/serene_locale.hh"
                           
                           """)
    #code += ('\n'.join(struct_forward_declarations)   + '\n\n') if len(struct_forward_declarations) > 0 else ''        #Not currently needed
    code += ('\n'.join(function_forward_declarations) + '\n\n') if len(function_forward_declarations) > 0 else ''
    code += ('\n\n'.join(struct_definition_code)      + '\n\n') if len(struct_definition_code) > 0 else ''
    code += ('\n\n'.join(function_code)               + '\n\n') if len(function_code) > 0 else ''
    code += "int main() {\n    "
    code += "std::cout.imbue(std::locale(std::locale(), new SereneLocale));\n    "  # std::locale is implicitly reference-counted, so "new" is not an issue
    code += "std::cout.setf(std::ios::boolalpha);\n    "
    code += "sn_main();\n    "
    code += "return 0;\n}\n"

    return code
