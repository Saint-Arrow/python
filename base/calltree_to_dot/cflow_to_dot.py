# cflow_to_dot.py

import re
import sys

def parse_cflow(cflow_output):
    calltree = {}
    stack = []
    
    for line in cflow_output.splitlines():
        indent_level = len(line) - len(line.lstrip())
        match = re.match(r'(\w+)\(', line)
        
        if match:
            function_name = match.group(1)
            
            if not stack:
                stack.append(function_name)
            else:
                caller = stack[-1]
                if caller not in calltree:
                    calltree[caller] = []
                calltree[caller].append(function_name)
                
                # Adjust stack based on indentation level
                while len(stack) > indent_level:
                    stack.pop()
                stack.append(function_name)
        else:
            print(f"Warning: Skipping line that does not match expected format: {line}")
    
    return calltree

def calltree_to_dot(calltree, filename="calltree.dot"):
    with open(filename, 'w') as f:
        f.write("digraph CallTree {\n")
        for caller, callees in calltree.items():
            for callee in callees:
                f.write(f'    "{caller}" -> "{callee}";\n')
        f.write("}\n")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python cflow_to_dot.py <cflow_output_file>")
        sys.exit(1)
    
    cflow_output_file = sys.argv[1]
    
    with open(cflow_output_file, 'r') as f:
        cflow_output = f.read()
    
    calltree = parse_cflow(cflow_output)
    calltree_to_dot(calltree)