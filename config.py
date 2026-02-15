"""
Moduole to encapsulate configuration reading.
"""

import json


def read_config():
    config = json.load(open("config.json"))
    return config


def get_user_from_token(config, token):
    for user_name, user_info in config["users"].items():
        if user_info["token"] == token:
            return user_name
    return None
