# -*- coding: utf-8 -*
"""maintain a dictionary of parameters"""

import json
import os

import six


def _get_dict_from_environ_or_json_or_file(args, env_name):
    if args == '':
        return None
    if args is None:
        s = os.environ.get(env_name)
    else:
        s = args
        if os.path.exists(s):
            s = open(s).read()
    if isinstance(s, six.string_types):
        try:
            r = eval(s)
        except SyntaxError as e:
            raise ValueError('json parse error: %s \n>Got json: %s' %
                             (repr(e), s))
        return r
    else:
        return s  # None


def parse_file(filename):
    """parse_file"""
    d = _get_dict_from_environ_or_json_or_file(filename, None)
    if d is None:
        raise ValueError('file(%s) not found' % filename)
    return d


def evaluate_file(filename):
    """evaluate_file"""
    # logging.info(
    #     f"error loading _jsonnet (this is expected on Windows), treating {filename} as plain json"
    # )
    # logging.info(filename)
    with open(filename, "r") as evaluation_file:
        return evaluation_file.read()


def from_file(filename):
    """from_file"""
    file_dict = json.loads(evaluate_file(filename), strict=False)
    return file_dict


def replace_none(params):
    """replace_none"""
    if params == "None":
        return None
    elif isinstance(params, dict):
        for key, value in params.items():
            params[key] = replace_none(value)
            if key == "split_char" and isinstance(value, str):
                try:
                    value = chr(int(value, base=16))
                    print("ord(value): ", ord(value))
                except Exception:
                    pass
                params[key] = value
        return params
    elif isinstance(params, list):
        return [replace_none(value) for value in params]
    return params
