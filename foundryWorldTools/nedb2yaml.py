#! /usr/local/bin/python3
"""
A command-line utility for converting a nedb (jsonlines) file to a yaml
file containing a document for each json object. nedb2yaml.py reads a nedb
file given as a command-line parameter and prints the corresponding YAML 
structure on standard out. nedb2yaml is useful as a git diff textconv. 
For more information see 
https://git-scm.com/docs/git-diff-files#Documentation/git-diff-files.txt---textconv

"""
import jsonlines
import yaml
import sys
from pathlib import Path

def nedb2yaml(nedbfile):
    output = []
    with jsonlines.open(nedbfile) as reader:
        for line in reader:
            output.append(yaml.dump(line, indent=2))
    return output

def show_help():
    print(
        f"{__doc__}",
        f"USAGE:\n  {Path(sys.argv[0]).name} <filename>"
        )
    

if __name__ == '__main__':
    if len(sys.argv) == 2:
        if sys.argv[1] in ("-h","--help"):
            show_help()
            sys.exit(0)
        nedbfile = Path(sys.argv[1])
        if nedbfile.exists():
            output = nedb2yaml(nedbfile)
            print("---\n".join(output))
            sys.exit(0)
        else:
            print(f"Error: File '{nedbfile}' does not exist!")
            show_help()
            sys.exit(1)
    else:
        print(f"\nError: {sys.argv[0]} requires 1 parameter, the path of a nedb file.")
        show_help()
        sys.exit(1)
        
