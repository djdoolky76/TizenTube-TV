# SPDX-License-Identifier: BSD-3-Clause
"""Minimal Android binary-XML label edit, retaining every string index/node."""

import struct


def read_length(data, offset, utf8):
    if utf8:
        first = data[offset]
        if first & 0x80:
            return ((first & 0x7F) << 8) | data[offset + 1], offset + 2
        return first, offset + 1
    first = struct.unpack_from("<H", data, offset)[0]
    if first & 0x8000:
        return ((first & 0x7FFF) << 16) | struct.unpack_from("<H", data, offset + 2)[0], offset + 4
    return first, offset + 2


def write_length(length, utf8):
    if utf8:
        if length > 0x7FFF:
            raise ValueError("String too long")
        return bytes([(length >> 8) | 0x80, length & 0xFF]) if length > 0x7F else bytes([length])
    if length > 0x7FFF:
        return struct.pack("<HH", (length >> 16) | 0x8000, length & 0xFFFF)
    return struct.pack("<H", length)


def rename_manifest_label(data):
    xml_type, xml_header, xml_size = struct.unpack_from("<HHI", data)
    if xml_type != 3 or xml_size != len(data):
        raise RuntimeError("Expected compiled Android XML")
    position = xml_header
    while position < len(data):
        chunk_type, header_size, chunk_size = struct.unpack_from("<HHI", data, position)
        if chunk_size < max(header_size, 8) or position + chunk_size > len(data):
            raise RuntimeError("Invalid XML chunk")
        if chunk_type != 1:
            position += chunk_size
            continue
        count, style_count, flags, strings_start, styles_start = struct.unpack_from("<IIIII", data, position + 8)
        if style_count or styles_start or header_size < 28:
            raise RuntimeError("Styled manifest string pools are unsupported")
        utf8 = bool(flags & 0x100)
        records, replacements = [], 0
        for index in range(count):
            relative = struct.unpack_from("<I", data, position + header_size + index * 4)[0]
            start = position + strings_start + relative
            length, cursor = read_length(data, start, utf8)
            if utf8:
                byte_length, cursor = read_length(data, cursor, True)
            else:
                byte_length = length * 2
            encoding, terminator = ("utf-8", b"\0") if utf8 else ("utf-16-le", b"\0\0")
            end = cursor + byte_length + len(terminator)
            if data[cursor + byte_length:end] != terminator or end > position + chunk_size:
                raise RuntimeError("Invalid string terminator")
            text = data[cursor:cursor + byte_length].decode(encoding, errors="surrogatepass")
            record = data[start:end]
            if text == "TizenTube":
                replacements += 1
                label = "YouTube"
                value = label.encode(encoding)
                record = write_length(len(label.encode("utf-16-le")) // 2, utf8)
                if utf8:
                    record += write_length(len(value), True)
                record += value + terminator
            records.append(record)
        if replacements != 1:
            raise RuntimeError(f"Expected one TizenTube label, found {replacements}")
        offsets, payload = [], bytearray()
        for record in records:
            offsets.append(len(payload))
            payload.extend(record)
        payload.extend(b"\0" * (-len(payload) % 4))
        new_start = header_size + count * 4
        header = bytearray(data[position:position + header_size])
        struct.pack_into("<I", header, 4, new_start + len(payload))
        struct.pack_into("<III", header, 16, flags & ~1, new_start, 0)
        pool = bytes(header) + struct.pack(f"<{count}I", *offsets) + payload
        result = bytearray(data[:position] + pool + data[position + chunk_size:])
        struct.pack_into("<I", result, 4, len(result))
        return bytes(result)
    raise RuntimeError("No manifest string pool found")
