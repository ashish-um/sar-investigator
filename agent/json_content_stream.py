"""Incrementally decode only the top-level content string of a JSON envelope."""

import json


class JSONContentStream:
    def __init__(self):
        self.raw = ""
        self.position = None
        self.closed = False

    def _find_content(self):
        decoder = json.JSONDecoder()
        pos = 0

        def whitespace(index):
            while index < len(self.raw) and self.raw[index].isspace():
                index += 1
            return index

        pos = whitespace(pos)
        if pos == len(self.raw) or self.raw[pos] != "{":
            return
        pos += 1
        try:
            while True:
                pos = whitespace(pos)
                key, pos = decoder.raw_decode(self.raw, pos)
                pos = whitespace(pos)
                if pos == len(self.raw) or self.raw[pos] != ":":
                    return
                pos = whitespace(pos + 1)
                if pos == len(self.raw):
                    return
                if key == "content":
                    if self.raw[pos] != '"':
                        raise ValueError("The content field must be a string")
                    self.position = pos + 1
                    return
                _, pos = decoder.raw_decode(self.raw, pos)
                pos = whitespace(pos)
                if pos == len(self.raw) or self.raw[pos] != ",":
                    return
                pos += 1
        except json.JSONDecodeError:
            return  # Wait for another delta to finish the current key/value.

    def feed(self, delta):
        self.raw += delta
        if self.position is None:
            self._find_content()
        if self.position is None or self.closed:
            return ""
        text = []
        escapes = {'"': '"', "\\": "\\", "/": "/", "b": "\b", "f": "\f", "n": "\n", "r": "\r", "t": "\t"}
        while self.position < len(self.raw):
            pos = self.position
            char = self.raw[pos]
            if char == '"':
                self.closed = True
                break
            if char == "\\":
                if pos + 1 == len(self.raw):
                    break
                escape = self.raw[pos + 1]
                if escape == "u":
                    if len(self.raw) < pos + 6:
                        break
                    value = int(self.raw[pos + 2:pos + 6], 16)
                    width = 6
                    if 0xD800 <= value <= 0xDBFF:
                        if len(self.raw) < pos + 12:
                            break
                        low = int(self.raw[pos + 8:pos + 12], 16)
                        if self.raw[pos + 6:pos + 8] != "\\u" or not 0xDC00 <= low <= 0xDFFF:
                            raise ValueError("Invalid Unicode surrogate pair")
                        value = 0x10000 + ((value - 0xD800) << 10) + low - 0xDC00
                        width = 12
                    elif 0xDC00 <= value <= 0xDFFF:
                        raise ValueError("Unpaired Unicode surrogate")
                    text.append(chr(value))
                else:
                    if escape not in escapes:
                        raise ValueError("Invalid JSON escape")
                    text.append(escapes[escape])
                    width = 2
                self.position += width
            else:
                text.append(char)
                self.position += 1
        return "".join(text)
