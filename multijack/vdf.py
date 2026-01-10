class VdfParseError(ValueError):
    pass


def get_value(data, key):
    keys = key.split(".")
    for k in keys:
        if isinstance(data, dict) and k in data:
            data = data[k]
        else:
            return None
    return data


def set_value(data, key, value):
    keys = key.split(".")
    current = data
    for k in keys[:-1]:
        if k not in current or not isinstance(current[k], dict):
            current[k] = {}
        current = current[k]
    current[keys[-1]] = value


def _tokenize_vdf(text):
    tokens = []
    length = len(text)
    i = 0

    while i < length:
        ch = text[i]

        if ch.isspace():
            i += 1
            continue

        if ch == "/" and i + 1 < length:
            next_ch = text[i + 1]
            if next_ch == "/":
                i += 2
                while i < length and text[i] not in "\r\n":
                    i += 1
                continue
            if next_ch == "*":
                i += 2
                while i + 1 < length and not (text[i] == "*" and text[i + 1] == "/"):
                    i += 1
                i += 2
                continue

        if ch in "{}":
            tokens.append(ch)
            i += 1
            continue

        if ch == '"':
            i += 1
            value_chars = []
            while i < length:
                ch = text[i]
                if ch == '"':
                    i += 1
                    break
                if ch == "\\" and i + 1 < length:
                    i += 1
                    escape = text[i]
                    if escape == "n":
                        value_chars.append("\n")
                    elif escape == "t":
                        value_chars.append("\t")
                    elif escape == "r":
                        value_chars.append("\r")
                    else:
                        value_chars.append(escape)
                    i += 1
                    continue
                value_chars.append(ch)
                i += 1
            else:
                raise VdfParseError("Unterminated string in VDF data.")
            tokens.append("".join(value_chars))
            continue

        start = i
        while i < length and not text[i].isspace() and text[i] not in "{}":
            i += 1
        tokens.append(text[start:i])

    return tokens


def read_vdf(file_path):
    with open(file_path, "r", encoding="utf-8") as file:
        content = file.read()

    tokens = _tokenize_vdf(content)
    data = {}
    stack = [data]
    current = data
    pending_key = None

    for token in tokens:
        if token == "{":
            if pending_key is None:
                raise VdfParseError("Unexpected '{' without a key.")
            new_dict = {}
            current[pending_key] = new_dict
            stack.append(current)
            current = new_dict
            pending_key = None
        elif token == "}":
            if len(stack) == 1:
                raise VdfParseError("Unexpected '}' without matching '{'.")
            current = stack.pop()
            pending_key = None
        else:
            if pending_key is None:
                pending_key = token
            else:
                current[pending_key] = token
                pending_key = None

    if pending_key is not None:
        raise VdfParseError(f"Key '{pending_key}' missing value.")
    if len(stack) != 1:
        raise VdfParseError("Unclosed '{' block in VDF data.")

    return data


def _escape_vdf_string(value):
    if value is None:
        return ""
    value = str(value)
    value = value.replace("\\", "\\\\")
    value = value.replace('"', '\\"')
    value = value.replace("\n", "\\n")
    value = value.replace("\t", "\\t")
    value = value.replace("\r", "\\r")
    return value


def save_vdf(data, file_path):
    def write_dict(current, indent=0):
        lines = []
        prefix = "\t" * indent
        for key, value in current.items():
            if isinstance(value, dict):
                lines.append(f'{prefix}"{_escape_vdf_string(key)}"')
                lines.append(f"{prefix}{{")
                lines.extend(write_dict(value, indent + 1))
                lines.append(f"{prefix}}}")
            else:
                lines.append(
                    f'{prefix}"{_escape_vdf_string(key)}"\t\t"{_escape_vdf_string(value)}"'
                )
        return lines

    with open(file_path, "w", encoding="utf-8") as file:
        file.write("\n".join(write_dict(data)) + "\n")
