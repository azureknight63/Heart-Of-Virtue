#!/usr/bin/env python
#
# genericng.py
# Copyright (c) 2001, Chris Gonnerman
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
#
# Redistributions of source code must retain the above copyright
# notice, this list of conditions and the following disclaimer.
#
# Redistributions in binary form must reproduce the above copyright
# notice, this list of conditions and the following disclaimer in the
# documentation and/or other materials provided with the distribution.
#
# Neither the name of the author nor the names of any contributors
# may be used to endorse or promote products derived from this software
# without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS
# FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE
# AUTHOR OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

"""genericng.py -- generic name generator

This module knows how to generate random names.

If run as a command-line program, use the following options:

    nnn -- generate nnn (a number) names and print
           on standard output.

As a module (to be imported) you get the following function:

    generate(minsyl=1, maxsyl=3)
        -- generate a name.  minsyl is the minimum number of
           syllables; maxsyl is the maximum number.

"""

__version__ = "1.0"

import random

consonants = [
    ('b',  2),
    ('c',  2),
    ('ch', 1),
    ('d',  4),
    ('f',  2),
    ('g',  3),
    ('h',  2),
    ('j',  1),
    ('k',  1),
    ('l',  4),
    ('m',  2),
    ('n',  6),
    ('p',  2),
    ('q',  1),
    ('qu', 1),
    ('r',  6),
    ('s',  4),
    ('t',  6),
    ('v',  2),
    ('w',  2),
    ('x',  1),
    ('z',  1),
]

vowels = [
    ('a', 9),
    ('e', 12),
    ('i', 9),
    ('o', 8),
    ('u', 4),
    ('y', 2),
]

def selection(table):

    # sum the table if needed

    if type(table[-1]) is not type(0):
        s = 0
        for i in range(len(table)):
            s += table[i][1]
        table.append(s)
    else:
        s = table[-1]

    # now the selection
    n = random.randrange(s) + 1
    for i in range(len(table)-1):
        n -= table[i][1]
        if n <= 0:
            return table[i][0]

    # should not happen
    return ''

def generate(minsyl = 1, maxsyl = 3):

    numsyl = random.randint(minsyl, maxsyl)

    word = []

    for i in range(numsyl):
        flag = 0
        if random.randrange(100) < 60:
            word.append(selection(consonants))
            flag = 1
        word.append(selection(vowels))
        if not flag or random.randrange(100) < 40:
            word.append(selection(consonants))


    return "".join(word).capitalize()

if __name__ == "__main__":

    import sys

    if len(sys.argv) <= 1 or len(sys.argv) > 2:
        sys.stderr.write(
            "Usage: genericng.py [ nn ]\n")
        sys.exit(0)

    if len(sys.argv) == 2:
        num = int(sys.argv[1])
    else:
        num = 1

    for i in range(num):
        print(generate())

# end of file.
