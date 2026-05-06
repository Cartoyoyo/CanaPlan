# -*- coding: utf-8 -*-
# Minimal extract from AnotherDXF2Shape/fnc4ADXF2Shape.py
# Only what is needed by clsDXFTools and clsDBase.


def DecodeDXFUTF(aktText):
    a = ""
    s = aktText
    while s.upper().find('\\U+') != -1:
        p = s.upper().find('\\U+')
        a = a + s[0:p]
        u = s[p+3:p+7]
        b = bytearray.fromhex(u)
        a = a + b.decode("UTF-16-BE")
        s = s[s.upper().find('\\U+')+7:]
    return a + s
