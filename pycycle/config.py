# -*- coding: utf-8 -*-
# Copyright NXP 2020

import json
import os
from typing import List


def load_config(file_name: str) -> object:
    """The function load .pycycle configuration file, if exist
    :param file_name: absolute path of the file to be loaded
    :return: list of package levels, each level is represented by list of packages in the level"""
    if not os.path.isfile(file_name):
        return list()
    with open(file_name) as f:
        lines = f.readlines()
    j = json.loads(''.join(lines))
    if j.get("pycycle_configuration_file_format", None) is None:
        return list()
    return j["package_levels"]
