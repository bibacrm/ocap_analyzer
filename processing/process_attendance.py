import hashlib
import logging
import datetime
import requests

from config import *
from utils.utils import open_replay_stat_file, get_player_squad_name

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s: %(message)s')


def get_attendance(tag=None):
    response = requests.get(REPLAY_LIST_URL)
    replay_list_data = response.json()

    error_message = ''
    attendance = {}

    tag_list = MISSION_TAGS_FOR_TOTAL_STATS if tag == TVT_MODE_ID else MISSION_TAGS_FOR_TOTAL_STATS_IF
    mission_duration_limit = TVT_DURATION_LIMIT
    if tag == IF_MODE_ID:
        tag_list = MISSION_TAGS_FOR_TOTAL_STATS_IF
        mission_duration_limit = IF_DURATION_LIMIT
    elif tag == VTN_MODE_ID:
        tag_list = MISSION_TAGS_FOR_TOTAL_STATS_VTN
        mission_duration_limit = VTN_DURATION_LIMIT

    file_name_list = [
        r['filename'].strip() for r in replay_list_data if (r['tag'] in tag_list and r['mission_duration'] > mission_duration_limit)
    ]
    hash_list = {
        hashlib.md5((REPLAY_FILE_URL + file_name).encode()).hexdigest(): file_name for file_name in file_name_list
    }

    for mission_url_hash, file_name in hash_list.items():
        attendance[mission_url_hash] = {'teams': {}, 'rotation': {}, 'non_rotation': {}}

        statistic_result, cache_results_file = open_replay_stat_file(mission_url_hash)
        if not statistic_result:
            error_message = f'Some {tag} missions OCAP replays are not processed, please select it on the home page'
            logging.error(error_message)
            break

        for player, data in statistic_result['players'].items():
            if 'is_player' in data:
                if data['is_player'] == 0:
                    continue

            name = data['name']
            team = get_player_squad_name(name)
            if team is None:
                # specific pseudo squad for players without a squad
                team = f'{SQUAD_FOR_NON_SQUAD_PLAYERS}'

            if team not in attendance[mission_url_hash]['teams']:
                attendance[mission_url_hash]['teams'][team] = {'players': 0}
            attendance[mission_url_hash]['teams'][team]['players'] += 1

        attendance[mission_url_hash]['date'] = statistic_result['sides'][0]['date']
        attendance[mission_url_hash]['mission_name'] = statistic_result['sides'][0]['mission_name']
        attendance[mission_url_hash]['players_1'] = statistic_result['sides'][0]['players']
        attendance[mission_url_hash]['players_2'] = statistic_result['sides'][1]['players']
        attendance[mission_url_hash]['players_total'] = (
                attendance[mission_url_hash]['players_1'] + attendance[mission_url_hash]['players_2']
        )

        date_obj = datetime.datetime.strptime(attendance[mission_url_hash]['date'], '%Y-%m-%d')
        weekday_num = date_obj.weekday()
        # Mapping weekday_num to weekday_name
        weekday_names = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
        weekday_name = weekday_names[weekday_num]

        # OCAP filename pattern is "<YYYY>_<MM>_<DD>__<HH>_<MM>_<mission name>.json"
        file_name_split = file_name.split('_')
        mission_time = f'{file_name_split[4]}:{file_name_split[5]}'
        mission_hour = file_name_split[4]

        attendance[mission_url_hash]['mission_time'] = mission_time
        attendance[mission_url_hash]['tag'] = tag
        attendance[mission_url_hash]['weekday_name'] = weekday_name

        rotation_attendance = {'1': {}, '2': {}}
        rotation_team_list = {}

        if tag == 'tvt':
            if weekday_name in ['Fri', 'Sat'] and int(mission_hour) > 20:
                tvt_tag = '2'
            else:
                tvt_tag = '1'
            attendance[mission_url_hash]['tag'] = tvt_tag
            rotation_team_list = TVT_1_ROTATION_TEAMS if tvt_tag == '1' else TVT_2_ROTATION_TEAMS
        elif tag == 'if':
            rotation_team_list = IF_ROTATION_TEAMS
        elif tag == 'vtn':
            rotation_team_list = VTN_ROTATION_TEAMS

        for side in ('1', '2'):
            for team in sorted(rotation_team_list[side]):
                if team in attendance[mission_url_hash]['teams'].keys():
                    rotation_attendance[side][team] = attendance[mission_url_hash]['teams'][team]['players']
                else:
                    rotation_attendance[side][team] = 0

        non_rotation_attendance = {}
        for team in sorted(attendance[mission_url_hash]['teams'].keys()):
            if team not in rotation_team_list['1'] and team not in rotation_team_list['2']:
                non_rotation_attendance[team] = attendance[mission_url_hash]['teams'][team]['players']

        attendance[mission_url_hash]['rotation'] = rotation_attendance
        attendance[mission_url_hash]['non_rotation'] = non_rotation_attendance

    return_report = {
        'attendance': attendance,
        'error_message': error_message,
    }

    return return_report
