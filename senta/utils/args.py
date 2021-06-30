#   Copyright (c) 2019 PaddlePaddle Authors. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Arguments for configuration."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import argparse
import logging

import six


def str2bool(v):
    """
    str2bool
    """
    # because argparse does not support to parse "true, False" as python
    # boolean directly
    return v.lower() in ("true", "t", "1")


class ArgumentGroup(object):
    """ArgumentGroup"""

    def __init__(self, parser, title, des):
        self._group = parser.add_argument_group(title=title, description=des)

    def add_arg(self, name, type, default, help, positional_arg=False, **kwargs):
        """add_arg"""
        prefix = "" if positional_arg else "--"
        type = str2bool if type == bool else type
        self._group.add_argument(
            prefix + name,
            default=default,
            type=type,
            help=help + ' Default: %(default)s.',
            **kwargs)


def print_arguments(args):
    """print_arguments"""
    logging.info("-----------  Configuration Arguments -----------")
    for arg, value in sorted(six.iteritems(vars(args))):
        logging.info("%s: %s" % (arg, value))
    logging.info("------------------------------------------------")


def build_common_arguments():
    """build_common_arguments"""
    parser = argparse.ArgumentParser(__doc__)
    model_g = ArgumentGroup(parser, "model", "model configuration and paths.")
    model_g.add_arg("mode", str, "train", "train,predict,eval")
    model_g.add_arg("param_path", str, None, "path to parameter file describing the model to be trained")
    model_g.add_arg("log_dir", str, "log", "log dir")
    model_g.add_arg("paddle_version", str, "1.5.2", "paddle_fluid version code")

    args = parser.parse_args()
    return args
