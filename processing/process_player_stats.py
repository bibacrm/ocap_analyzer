import json

from config import *
from utils.utils import create_steam_name_list, get_steam_data


def get_player_stats(player_name=None, tag=TVT_MODE_ID, steam_id=None):
    if player_name is not None:
        player = player_name.replace(" ", "")
        player_steam_dict = create_steam_name_list(STEAM_ID_LIST_PATH)
        steam_id, name_list = get_steam_data(player_steam_dict, player_name)
    else:
        player = None

    error_message = ''
    statistic_result = {
        'error_message': error_message,
        'frag_stats': {},
        'tk_stats': {},
        'ks_win_stat': {},
        'ks_missions': {},
        'steam_id': steam_id
    }

    total_file = TOTAL_STATS_FILE
    tag_list = MISSION_TAGS_FOR_TOTAL_STATS
    if tag in MISSION_TAGS_FOR_TOTAL_STATS_IF:
        total_file = TOTAL_STATS_FILE_IF
        tag_list = MISSION_TAGS_FOR_TOTAL_STATS_IF
    elif tag in MISSION_TAGS_FOR_TOTAL_STATS_VTN:
        total_file = TOTAL_STATS_FILE_VTN
        tag_list = MISSION_TAGS_FOR_TOTAL_STATS_VTN

    if os.path.exists(total_file):
        with open(total_file, encoding="utf-8") as f:
            total_stats_result = json.load(f)
    else:
        error_message = f'Total {tag} statistic is missing'
        total_stats_result = {}

    if os.path.exists(total_file):
        with open(MISSION_STATS_FILE, encoding="utf-8") as f:
            mission_stats_result = json.load(f)
    else:
        error_message = 'Missions statistic is missing'
        mission_stats_result = {}

    if player_name is not None:
        frag_stats = total_stats_result.get('frag_stats', {}).get(player, {})
        tk_stats = total_stats_result.get('tk_stats', {}).get(player, {})
    else:
        frag_stats = total_stats_result.get('frag_stats_steam', {}).get(steam_id, {})
        tk_stats = total_stats_result.get('tk_stats_steam', {}).get(steam_id, {})

    if frag_stats == {}:
        statistic_result['error_message'] = f'Statistic is not available - {player_name} - {steam_id}. Mission limit - {TOTAL_STATISTIC_MISSION_LIMIT}'
        return statistic_result

    ks_player_list = (player,) if player_name is not None else frag_stats['name_list']
    ks_win_stat = {
        "win": 0,
        "lost": 0,
        "draw": 0,
        "total": 0,
        "win_rate": 0
    }
    for k, v in total_stats_result.get('ks_win_stat', {}).items():
        if any(player_name.replace(" ", "") == k.replace(" ", "") for player_name in ks_player_list):
            for key, value in v.items():
                ks_win_stat[key] += value
    ks_win_stat['win_rate'] = round(ks_win_stat['win'] / ks_win_stat['total'], 3) if ks_win_stat['total'] > KS_MISSION_LIMIT else 0

    ks_missions = []

    for mission, stat in mission_stats_result.items():
        if stat[0]['tag'] in tag_list:
            if len(stat) > 1:
                for side in stat:
                    if any(player_name.replace(" ", "") == side['ks'].replace(" ", "") for player_name in ks_player_list):
                        mission_data = {
                            'ks_1': stat[0]['ks'],
                            'ks_1_win': stat[0]['win'],
                            'ks_2': stat[1]['ks'],
                            'ks_2_win': stat[1]['win'],
                            'mission_name': stat[0]['mission_name'],
                            'date': stat[0]['date'],
                            'filename': mission,
                            'tag': stat[0]['tag']
                        }
                        ks_missions.append(mission_data)

    statistic_result = {
        'error_message': error_message,
        'frag_stats': frag_stats,
        'tk_stats': tk_stats,
        'ks_win_stat': ks_win_stat,
        'ks_missions': ks_missions,
        'steam_id': steam_id
    }
    return statistic_result
