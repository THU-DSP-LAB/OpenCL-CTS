#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Generate the "conversions" section of your JSON test list,
marking every sub-test as passed.
usage: python3 generate_conversions_json.py > conversions.json
"""

import itertools
import json

# define the parameter lists exactly as in your bash script
formats     = ["uchar", "char", "ushort", "short", "uint", "int", "float", "double", "ulong", "long"]
saturations = ["", "_sat"]
roundings   = ["", "_rte", "_rtp", "_rtn", "_rtz"]

# build up all test names: <dest><sat><round>_<src>
test_names = [
    f"{dest}{sat}{rnd}_{src}"
    for dest, sat, rnd, src in itertools.product(formats, saturations, roundings, formats)
]

# assemble into the JSON structure
conversions_section = {
    "conversions": {
        name: {"state": "pass", "comment": ""}
        for name in test_names
    }
}

# output to stdout (or write to a file)
print(json.dumps(conversions_section, indent=4, ensure_ascii=False))
