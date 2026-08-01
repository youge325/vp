"""Extract Rust production source without letting test-only items keep code alive."""

from __future__ import annotations

import re

_CFG_TEST = re.compile(r"#\s*\[\s*cfg\s*\(\s*test\s*\)\s*\]")
_CONTINUES_AFTER_BLOCK = frozenset({"const", "let", "static", "type", "use"})


def _lexical_code_mask(text: str) -> str:
    """Return a same-length view with comments and literal bodies blanked."""
    result = list(text)
    index = 0
    block_depth = 0
    state = "code"
    raw_hashes = 0
    while index < len(text):
        char = text[index]
        next_char = text[index + 1] if index + 1 < len(text) else ""
        if state == "line_comment":
            if char == "\n":
                state = "code"
            else:
                result[index] = " "
            index += 1
            continue
        if state == "block_comment":
            if char == "/" and next_char == "*":
                result[index] = result[index + 1] = " "
                block_depth += 1
                index += 2
            elif char == "*" and next_char == "/":
                result[index] = result[index + 1] = " "
                block_depth -= 1
                index += 2
                if block_depth == 0:
                    state = "code"
            else:
                if char != "\n":
                    result[index] = " "
                index += 1
            continue
        if state in {"string", "char"}:
            delimiter = '"' if state == "string" else "'"
            if char == "\\":
                result[index] = " "
                if index + 1 < len(text):
                    if text[index + 1] != "\n":
                        result[index + 1] = " "
                    index += 2
                else:
                    index += 1
            elif char == delimiter:
                index += 1
                state = "code"
            else:
                if char != "\n":
                    result[index] = " "
                index += 1
            continue
        if state == "raw_string":
            terminator = '"' + ("#" * raw_hashes)
            if text.startswith(terminator, index):
                index += len(terminator)
                state = "code"
            else:
                if char != "\n":
                    result[index] = " "
                index += 1
            continue

        if char == "/" and next_char == "/":
            result[index] = result[index + 1] = " "
            state = "line_comment"
            index += 2
        elif char == "/" and next_char == "*":
            result[index] = result[index + 1] = " "
            state = "block_comment"
            block_depth = 1
            index += 2
        elif char == '"':
            state = "string"
            index += 1
        elif char == "'" and next_char and next_char != " ":
            state = "char"
            index += 1
        elif char == "r":
            raw_match = re.match(r'r(#{0,255})"', text[index:])
            if raw_match:
                raw_hashes = len(raw_match.group(1))
                index += len(raw_match.group(0))
                state = "raw_string"
            else:
                index += 1
        else:
            index += 1
    return "".join(result)


def _skip_attribute(mask: str, start: int) -> int:
    if not mask.startswith("#[", start):
        return start
    depth = 0
    for index in range(start + 1, len(mask)):
        if mask[index] == "[":
            depth += 1
        elif mask[index] == "]":
            depth -= 1
            if depth == 0:
                return index + 1
    return len(mask)


def _test_item_end(mask: str, attribute_end: int) -> int:
    index = attribute_end
    while True:
        while index < len(mask) and mask[index].isspace():
            index += 1
        if mask.startswith("#[", index):
            index = _skip_attribute(mask, index)
            continue
        break
    item_start = index
    keyword_match = re.search(r"[A-Za-z_][A-Za-z0-9_]*", mask[item_start:])
    first_keyword = keyword_match.group(0) if keyword_match else ""
    delimiter_stack: list[str] = []
    matching = {"(": ")", "[": "]", "{": "}"}
    while index < len(mask):
        char = mask[index]
        if char in matching:
            delimiter_stack.append(matching[char])
        elif delimiter_stack and char == delimiter_stack[-1]:
            delimiter_stack.pop()
            if not delimiter_stack and char == "}" and first_keyword not in _CONTINUES_AFTER_BLOCK:
                lookahead = index + 1
                while lookahead < len(mask) and mask[lookahead].isspace():
                    lookahead += 1
                if lookahead < len(mask) and mask[lookahead] in ";,":
                    return lookahead + 1
                return index + 1
        elif not delimiter_stack and char in ";,":
            return index + 1
        index += 1
    return len(mask)


def production_rust_source(text: str) -> str:
    """Blank exact ``#[cfg(test)]`` items while preserving offsets and line numbers."""
    mask = _lexical_code_mask(text)
    ranges: list[tuple[int, int]] = []
    cursor = 0
    while match := _CFG_TEST.search(mask, cursor):
        end = _test_item_end(mask, match.end())
        ranges.append((match.start(), end))
        cursor = max(end, match.end())
    if not ranges:
        return text
    result = list(text)
    for start, end in ranges:
        for index in range(start, end):
            if result[index] not in "\r\n":
                result[index] = " "
    return "".join(result)


__all__ = ["production_rust_source"]
