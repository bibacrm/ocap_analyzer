import hashlib
import heapq
import json
import logging
import re
from collections import OrderedDict

import requests

from config import *
from utils.utils import create_steam_name_list, open_replay_stat_file, get_steam_data, serialize_sets

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s: %(message)s')


def process_total_stats(tag=TVT_MODE_ID, calculate=True):
    # Getting replay list data
    response = requests.get(REPLAY_LIST_URL)
    replay_list_data = response.json()

    # Identifying main project parameters
    mission_duration_limit = TVT_DURATION_LIMIT
    tag_list = MISSION_TAGS_FOR_TOTAL_STATS
    if tag == IF_MODE_ID:
        mission_duration_limit = IF_DURATION_LIMIT
        tag_list = MISSION_TAGS_FOR_TOTAL_STATS_IF
    elif tag == VTN_MODE_ID:
        mission_duration_limit = VTN_DURATION_LIMIT
        tag_list = MISSION_TAGS_FOR_TOTAL_STATS_VTN

    # Amount of missions by specified parameters
    missions_count = sum(
        1 for v in replay_list_data if (v['tag'] in tag_list and v['mission_duration'] > mission_duration_limit)
    )

    logging.info(f'Start processing total {tag} statistic')

    tk_stats = {}
    tk_stats_steam = {}
    team_tk_stats = {}
    frag_stats = {}
    frag_stats_steam = {}
    team_frag_stats = {}
    error_message = ''

    os.makedirs(TOTAL_STATS_FOLDER, exist_ok=True)

    total_file = TOTAL_STATS_FILE
    if tag == IF_MODE_ID:
        total_file = TOTAL_STATS_FILE_IF
    elif tag == VTN_MODE_ID:
        total_file = TOTAL_STATS_FILE_VTN

    if os.path.exists(total_file):
        with open(total_file, encoding="utf-8") as f:
            total_result = json.load(f)
        if total_result['cache_count'] == missions_count:
            logging.info(f"Cached total {tag} statistic is up to date, no need to refresh it")
            return total_result
        elif not calculate:
            return total_result

    player_steam_dict = create_steam_name_list(STEAM_ID_LIST_PATH)
    ban_steam_dict = create_steam_name_list(STEAM_ID_BAN_PATH)

    for replay in replay_list_data:
        if replay.get('mission_duration', 0) > mission_duration_limit and replay.get('tag', '') in tag_list:
            file_url = REPLAY_FILE_URL + replay['filename'].strip()
            mission_url_hash = hashlib.md5(file_url.encode()).hexdigest()

            total_result, cache_results_file = open_replay_stat_file(mission_url_hash)
            if not total_result:
                error_message = f'Some {tag} missions OCAP replays are not processed, please select it on the home page'
                logging.error(error_message)
                break

            # ST.to Dw. legacy statistic handling start. Specific case for RBC squad changed name. Can be just erased
            player_to_add = []
            for player, stats in total_result['frag_stats'].items():
                if 'St.' in player or 'Dw.' in player:
                    new_name = player.replace('St.', '[StDw]')
                    new_name = new_name.replace('Dw.', '[StDw]')
                    player_to_add.append({new_name: stats})

            for player in player_to_add:
                total_result['frag_stats'].update(player)
            team_to_add = []
            for team, stats in total_result['team_stats'].items():
                if team == 'St' or team == 'Dw':
                    team_to_add.append(stats)
            if len(team_to_add) > 0:
                new_stats = {'teamkills': 0, 'frags': 0, 'bot_frags': 0, 'vehicle_frags': 0, 'side': 'no_side',
                             'victims': []}

                for team in team_to_add:
                    for k, v in team.items():
                        if k in new_stats:
                            new_stats[k] += v
                total_result['team_stats']['StDw'] = new_stats
            # ST.to Dw. legacy statistic handling end.

            # By SteamID. Kiberkotlets and Teamkills statistic aggregation
            for player, stats in total_result['frag_stats'].items():
                player_name = player.replace(" ", "")

                steam_id, names = get_steam_data(player_steam_dict, player)

                if steam_id is not None:
                    if steam_id not in tk_stats_steam:
                        tk_stats_steam[steam_id] = {'kills': 0, 'missions': 0, 'name_list': set()}
                    tk_stats_steam[steam_id]['kills'] += stats['teamkills']
                    tk_stats_steam[steam_id]['missions'] += 1
                    tk_stats_steam[steam_id]['name_list'].add(player)
                    tk_stats_steam[steam_id]['name_last'] = player_name

                    if steam_id not in frag_stats_steam:
                        frag_stats_steam[steam_id] = {'kills': 0, 'missions': 0, 'deaths': 0, 'bot_frags': 0,
                                                      'vehicle_frags': 0, 'name_list': set(), 'teamkilled': 0,
                                                      'tk_by': {}, 'killed_by': {}, 'weapon_list': {}, 'victims': {},
                                                      'vehicle_list': {}, 'killed_from_vehicle': 0,
                                                      'victims_in_vehicle': 0, 'last_missions': OrderedDict()}
                    frag_stats_steam[steam_id]['kills'] += stats['frags']
                    frag_stats_steam[steam_id]['bot_frags'] += stats['bot_frags']
                    frag_stats_steam[steam_id]['vehicle_frags'] += stats['vehicle_frags']
                    frag_stats_steam[steam_id]['missions'] += 1
                    frag_stats_steam[steam_id]['name_list'].add(player)
                    frag_stats_steam[steam_id]['name_last'] = player_name
                    frag_stats_steam[steam_id]['killed_from_vehicle'] += stats['killed_from_vehicle']
                    frag_stats_steam[steam_id]['victims_in_vehicle'] += stats['victims_in_vehicle']

                    missions_len = len(frag_stats_steam[steam_id]['last_missions'])
                    if missions_len == 10:
                        frag_stats_steam[steam_id]['last_missions'].popitem(last=False)
                    frag_stats_steam[steam_id]['last_missions'][replay['mission_name']] = {
                        'filename': replay['filename'],
                        'kills': stats['frags'],
                        'vehicle_frags': stats['vehicle_frags'],
                        'killed_from_vehicle': stats['killed_from_vehicle'],
                        'victims_in_vehicle': stats['victims_in_vehicle'],
                        'date': replay['date']
                    }

                    for victim in stats['victims']:
                        if victim['victim_name'] not in frag_stats_steam[steam_id]['victims']:
                            frag_stats_steam[steam_id]['victims'][victim['victim_name']] = 0
                        frag_stats_steam[steam_id]['victims'][victim['victim_name']] += 1
                        if victim['weapon'] not in frag_stats_steam[steam_id]['weapon_list']:
                            frag_stats_steam[steam_id]['weapon_list'][victim['weapon']] = 0
                        frag_stats_steam[steam_id]['weapon_list'][victim['weapon']] += 1
                        if victim['class'] in VEHICLE_CLASS_COUNT_LIST:
                            if victim['victim_name'] not in frag_stats_steam[steam_id]['vehicle_list']:
                                frag_stats_steam[steam_id]['vehicle_list'][victim['victim_name']] = 0
                            frag_stats_steam[steam_id]['vehicle_list'][victim['victim_name']] += 1

                    if 'death_data' in stats:
                        frag_stats_steam[steam_id]['deaths'] += 1
                        killer_name = stats['death_data']['killer']
                        if killer_name not in frag_stats_steam[steam_id]['killed_by']:
                            frag_stats_steam[steam_id]['killed_by'][killer_name] = 0
                        frag_stats_steam[steam_id]['killed_by'][killer_name] += 1
                        if stats['death_data']['teamkilla'] != '':
                            frag_stats_steam[steam_id]['teamkilled'] += 1
                            tk_name = stats['death_data']['killer']
                            if tk_name not in frag_stats_steam[steam_id]['tk_by']:
                                frag_stats_steam[steam_id]['tk_by'][tk_name] = 0
                            frag_stats_steam[steam_id]['tk_by'][tk_name] += 1

                # By nickname. Kiberkotlets and Teamkills statistic aggregation
                if player_name not in tk_stats:
                    tk_stats[player_name] = {'kills': 0, 'missions': 0, 'steam_id': steam_id}
                tk_stats[player_name]['kills'] += stats['teamkills']
                tk_stats[player_name]['missions'] += 1

                if player_name not in frag_stats:
                    frag_stats[player_name] = {'kills': 0, 'missions': 0, 'deaths': 0, 'bot_frags': 0, 'tk_by': {},
                                               'vehicle_frags': 0, 'victims': {}, 'teamkilled': 0, 'killed_by': {},
                                               'weapon_list': {}, 'role_list': {}, 'vehicle_list': {},
                                               'killed_from_vehicle': 0, 'victims_in_vehicle': 0, 'steam_id': steam_id,
                                               'last_missions': OrderedDict()}
                frag_stats[player_name]['kills'] += stats['frags']
                frag_stats[player_name]['bot_frags'] += stats['bot_frags']
                frag_stats[player_name]['vehicle_frags'] += stats['vehicle_frags']
                frag_stats[player_name]['missions'] += 1
                frag_stats[player_name]['killed_from_vehicle'] += stats['killed_from_vehicle']
                frag_stats[player_name]['victims_in_vehicle'] += stats['victims_in_vehicle']

                missions_len = len(frag_stats[player_name]['last_missions'])
                if missions_len == 10:
                    frag_stats[player_name]['last_missions'].popitem(last=False)
                frag_stats[player_name]['last_missions'][replay['mission_name']] = {
                    'filename': replay['filename'],
                    'kills': stats['frags'],
                    'vehicle_frags': stats['vehicle_frags'],
                    'killed_from_vehicle': stats['killed_from_vehicle'],
                    'victims_in_vehicle': stats['victims_in_vehicle'],
                    'date': replay['date']
                }

                if 'role' in stats:
                    if stats['role'] not in frag_stats[player_name]['role_list']:
                        frag_stats[player_name]['role_list'][stats['role']] = 0
                    frag_stats[player_name]['role_list'][stats['role']] += 1

                for victim in stats['victims']:
                    if victim['victim_name'] not in frag_stats[player_name]['victims']:
                        frag_stats[player_name]['victims'][victim['victim_name']] = 0
                    frag_stats[player_name]['victims'][victim['victim_name']] += 1
                    if victim['weapon'] not in frag_stats[player_name]['weapon_list']:
                        frag_stats[player_name]['weapon_list'][victim['weapon']] = 0
                    frag_stats[player_name]['weapon_list'][victim['weapon']] += 1
                    if victim['class'] in VEHICLE_CLASS_COUNT_LIST:
                        if victim['victim_name'] not in frag_stats[player_name]['vehicle_list']:
                            frag_stats[player_name]['vehicle_list'][victim['victim_name']] = 0
                        frag_stats[player_name]['vehicle_list'][victim['victim_name']] += 1

                if 'death_data' in stats:
                    frag_stats[player_name]['deaths'] += 1
                    killer_name = stats['death_data']['killer']
                    if killer_name not in frag_stats[player_name]['killed_by']:
                        frag_stats[player_name]['killed_by'][killer_name] = 0
                    frag_stats[player_name]['killed_by'][killer_name] += 1
                    if stats['death_data']['teamkilla'] != '':
                        frag_stats[player_name]['teamkilled'] += 1
                        tk_name = stats['death_data']['killer']
                        if tk_name not in frag_stats[player_name]['tk_by']:
                            frag_stats[player_name]['tk_by'][tk_name] = 0
                        frag_stats[player_name]['tk_by'][tk_name] += 1

            # Kiber squads players and Squad teamkills statistic aggregation
            for team, stats in total_result['team_stats'].items():
                # removing all non alphanumeric symbols from squad name, '-' is allowed also
                team_name = re.sub('[^A-Za-z0-9-]+', '', team)
                if team_name not in team_tk_stats:
                    team_tk_stats[team_name] = {'kills': 0, 'missions': 0}
                team_tk_stats[team_name]['kills'] += stats['teamkills']
                team_tk_stats[team_name]['missions'] += 1

                if team_name not in team_frag_stats:
                    team_frag_stats[team_name] = {'kills': 0, 'missions': 0, 'bot_frags': 0, 'vehicle_frags': 0,
                                                  'victims': {}}
                team_frag_stats[team_name]['kills'] += stats['frags']
                team_frag_stats[team_name]['bot_frags'] += stats['bot_frags']
                team_frag_stats[team_name]['vehicle_frags'] += stats['vehicle_frags']
                team_frag_stats[team_name]['missions'] += 1
                for victim in stats['victims']:
                    if victim['victim_name'] not in team_frag_stats[team_name]['victims']:
                        team_frag_stats[team_name]['victims'][victim['victim_name']] = 0
                    team_frag_stats[team_name]['victims'][victim['victim_name']] += 1

    # Kills/missions and Kills/deaths statistic adding
    for stat_dict in [tk_stats, team_tk_stats, frag_stats, team_frag_stats, frag_stats_steam, tk_stats_steam]:
        to_delete = []
        for item, stat in stat_dict.items():
            if stat['missions'] > TOTAL_STATISTIC_MISSION_LIMIT:
                stat['k_m'] = round(stat['kills'] / stat['missions'], 3)
                if stat_dict == frag_stats or stat_dict == frag_stats_steam:
                    deaths = stat['deaths'] if stat['deaths'] > 0 else 1
                    stat['k_d'] = round(stat['kills'] / deaths, 3)
            else:
                to_delete.append(item)

            # Erasing stat data for banned players and squads
            if stat_dict in [team_tk_stats, team_frag_stats]:
                if any(team.upper() == item.upper() for team in BAN_TEAM_LIST):
                    for stat_key in list(stat.keys()):
                        if stat_key in BAN_STAT_ERASE:
                            stat[stat_key] = 0
            elif stat_dict in [frag_stats_steam, tk_stats_steam]:
                if item in ban_steam_dict.keys():
                    for stat_key in list(stat.keys()):
                        if stat_key in BAN_STAT_ERASE:
                            stat[stat_key] = 0
            elif stat_dict in [frag_stats, tk_stats]:
                if stat['steam_id'] in ban_steam_dict.keys():
                    for stat_key in list(stat.keys()):
                        if stat_key in BAN_STAT_ERASE:
                            stat[stat_key] = 0
        for key in to_delete:
            del stat_dict[key]

    # Removing records like 'player was killed by himself'
    for player, stats in frag_stats.items():
        for name in list(stats['killed_by'].keys()):
            if player.replace(" ", "") == name.replace(" ", ""):
                del stats['killed_by'][name]
    for steam_id, stats in frag_stats_steam.items():
        for name in list(stats['killed_by'].keys()):
            if any(steam_name.replace(" ", "") == name.replace(" ", "") for steam_name in stats['name_list']):
                del stats['killed_by'][name]

    # Leaving top # records for player and team statistic data
    for stat_dict in [frag_stats, frag_stats_steam, team_frag_stats]:
        for name, stats in stat_dict.items():
            stats['victims'] = heapq.nlargest(VICTIMS_STAT_LIMIT, stats['victims'].items(), key=lambda x: x[1])
            if stat_dict in (frag_stats, frag_stats_steam):
                stats['killed_by'] = heapq.nlargest(
                    KILLED_BY_STAT_LIMIT, stats['killed_by'].items(), key=lambda x: x[1]
                )
                stats['tk_by'] = heapq.nlargest(
                    TEAMKILLED_BY_STAT_LIMIT, stats['tk_by'].items(), key=lambda x: x[1]
                )
                stats['weapon_list'] = heapq.nlargest(
                    WEAPONS_STAT_LIMIT, stats['weapon_list'].items(), key=lambda x: x[1]
                )
                stats['vehicle_list'] = heapq.nlargest(
                    VEHICLE_STAT_LIMIT, stats['vehicle_list'].items(), key=lambda x: x[1]
                )

    # KS statistic
    with open(MISSION_STATS_FILE, encoding="utf-8") as f:
        missions_stats_data = json.load(f)

    ks_list = set()
    ks_win_stat = {}

    for mission, stat in missions_stats_data.items():
        if len(stat) > 1:
            if stat[0]['tag'] in tag_list:
                for side in stat:
                    steam_id, names = get_steam_data(player_steam_dict, side['ks'])
                    if steam_id not in ban_steam_dict.keys():
                        ks_list.add(side['ks'])

    for ks_name in ks_list:
        for mission, stat in missions_stats_data.items():
            if len(stat) > 1:
                if stat[0]['tag'] in tag_list:
                    for side in stat:
                        if ks_name == side['ks']:
                            if ks_name not in ks_win_stat:
                                ks_win_stat[ks_name] = {'win': 0, 'lost': 0, 'draw': 0}
                            if side['win'] == 1:
                                ks_win_stat[ks_name]['win'] += 1
                            elif stat[0]['win'] == 0 and stat[1]['win'] == 0:
                                ks_win_stat[ks_name]['draw'] += 1
                            else:
                                ks_win_stat[ks_name]['lost'] += 1

    for ks_name, stats in ks_win_stat.items():
        stats['total'] = stats['win'] + stats['lost'] + stats['draw']
        stats['win_rate'] = round(stats['win'] / stats['total'], 3) if stats['total'] > KS_MISSION_LIMIT else 0

    total_result = {
        'cache_count': missions_count,
        'error_message': error_message,
        'frag_stats': frag_stats,
        'team_frag_stats': team_frag_stats,
        'frag_stats_steam': frag_stats_steam,
        'team_tk_stats': team_tk_stats,
        'tk_stats_steam': tk_stats_steam,
        'tk_stats': tk_stats,
        'ks_win_stat': ks_win_stat
    }

    # Calculated statistic storing in cache
    if error_message == '':
        with open(total_file, "w") as f:
            json.dump(total_result, f, default=serialize_sets)
        logging.info(f"Total {tag} statistic cache data has been updated")

    return total_result
