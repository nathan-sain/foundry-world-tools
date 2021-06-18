#! /usr/local/bin/python3
"""
A command-line utility for converting a yaml file containing individual documents
into a nedb (jsonlines) file. yaml2nedb.py reads a yaml file given as a command-line
parameter and prints the corresponding nedb file structure on standard out.
"""
import jsonlines
import yaml
import sys
from pathlib import Path

def yaml2nedb(yamlfile):
    output = []
    with open(yamlfile,"r") as reader:
        for obj in yaml.safe_load_all(reader):
            output.append(obj)
    jsonwriter = jsonlines.Writer(sys.stdout,compact=True)
    jsonwriter.write_all(output)

def show_help():
    print(
        f"{__doc__}"
        f"USAGE:\n {Path(sys.argv[0]).name} <filename>"
    )

if __name__ == '__main__':
    if len(sys.argv) == 2:
        if sys.argv[1] in ("-h","--help"):
            show_help()
            sys.exit(0)
        yamlfile = Path(sys.argv[1])
        if yamlfile.exists():
            yaml2nedb(yamlfile)
            sys.exit(0)
        else:
            print(f"Error: File '{yamlfile}' does not exist!")
            show_help()
            sys.exit(1)
    else:
        print(f"\nError: {sys.argv[0]} requires 1 parameter, the path of a yaml file.")
        show_help()
        sys.exit(1)