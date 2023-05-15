import datetime
import json
import os

from config import RESULTS_FOLDER


def serialize_sets(obj):
    if isinstance(obj, set):
        return list(obj)
    return obj


def seconds_to_human(seconds):
    time = str(datetime.timedelta(seconds=seconds))
    if '.' in time:
        time = time[:time.index('.')]
    return time


def get_steam_data(d, value):
    steam_id = None
    name_list = set()
    for steam, names in d.items():
        if any(value.replace(" ", "") == name.replace(" ", "") for name in names):
            if steam_id is None:
                steam_id = steam
            name_list.update(set(names))
    if steam_id is not None:
        d[steam_id] = name_list

    return steam_id, name_list


def create_steam_name_list(steam_list):
    name_dict = {}

    with open(steam_list, encoding="utf-8") as file:
        for line in file:
            parts = line.strip().split("\t")
            if len(parts) != 2:
                continue
            steam_id = parts[0]
            name = parts[1]
            if steam_id in name_dict:
                name_dict[steam_id].append(name)
            else:
                name_dict[steam_id] = [name]

    return name_dict


def open_replay_stat_file(mission_url_hash):
    cache_results_file = os.path.join(RESULTS_FOLDER, mission_url_hash)
    if os.path.exists(cache_results_file):
        with open(cache_results_file, encoding="utf-8") as f:
            statistic_result = json.load(f)
        return statistic_result, cache_results_file
    else:
        return False, cache_results_file


def get_player_squad_name(player_name):
    # Squad tag parsing logic for a main pattern "[<Squad>]<Player>", "~" is for recruits specific players on RBC
    # '=]B[=', 'Dw.', 'St.', 'UN' - specific non-pattern squad titles
    if '=]B[=' in player_name:
        squad_name = 'B'
    elif any(i in player_name for i in ["=UN=", '-UN-', '|UN|', '[UN]']):
        squad_name = 'UN'
    elif 'Dw.' in player_name:
        squad_name = 'Dw'
    elif 'St.' in player_name:
        squad_name = 'St'
    elif "[" in player_name and "]" in player_name:
        squad_name = player_name.split("[")[1].split("]")[0].strip('~')
    else:
        squad_name = None
    return squad_name
