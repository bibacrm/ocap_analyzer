import gzip
import hashlib
import json
import logging

import requests

from config import *
from utils.utils import open_replay_stat_file, seconds_to_human, get_player_squad_name

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s: %(message)s')


def process_ocap_file(data_url, only_results=False, tag=None, replay_list_data=None):
    error_message = ''
    statistic_result = {
        'error_message': error_message,
        'frag_stats': {},
        'team_stats': {},
        'ko_stats': {},
        'connected_stats': {},
        'mission_name': "",
        'mission_author': "",
        'mission_duration': "",
        'sides': {},
        'tag': tag,
        'winner': ''
    }

    # in case tag is not defined - no need to store calculated statistic
    if tag is None:
        only_results = True

    if data_url is None:
        # Start page case
        statistic_result['error_message'] = 'Select a mission replay to get statistic data'
        return statistic_result

    # Cache settings and preparation
    os.makedirs(CACHE_FOLDER, exist_ok=True)
    os.makedirs(RESULTS_FOLDER, exist_ok=True)
    os.makedirs(MISSION_STATS_FOLDER, exist_ok=True)

    mission_url_hash = hashlib.md5(data_url.encode()).hexdigest()
    replay_file_name = data_url.split('/')[-1]
    cache_file = os.path.join(CACHE_FOLDER, mission_url_hash)

    cached_statistic_result, cache_results_file = open_replay_stat_file(mission_url_hash)
    if cached_statistic_result:
        return cached_statistic_result

    # Getting cached ocap replay data or downloading new one
    if os.path.exists(cache_file):
        with gzip.open(cache_file, "rb") as f:
            content = f.read()
        data = json.loads(content.decode('utf-8'))
    else:
        headers = {"Accept-Encoding": "gzip"}
        try:
            response = requests.get(data_url, headers=headers)
        except Exception as e:
            print(data_url)
            statistic_result['error_message'] = f'OCAP file was fail to load: {data_url}'
            return statistic_result
        with gzip.open(cache_file, "wb") as temp_file:
            temp_file.write(response.content)
        data = json.loads(response.content.decode('utf-8'))

    # No need to get mission results data cache in case only mission statistic is required
    if not only_results:
        if os.path.exists(MISSION_STATS_FILE):
            with open(MISSION_STATS_FILE, encoding="utf-8") as f:
                missions_stats_data = json.load(f)
        else:
            missions_stats_data = {}

    # Basic data for Mission statistic header
    mission_name = data.get('missionName')
    mission_author = data.get('missionAuthor')
    mission_duration = seconds_to_human(data.get('endFrame')) if data.get('endFrame') is not None else 0

    # Mission date getting from OCAP replay list response json
    mission_date = ''
    for replay in replay_list_data:
        if replay['filename'] in data_url:
            mission_date = replay['date']
            break

    # Main statistic containers preparation
    frag_stats = {}
    team_stats = {}
    players = {}
    kills = []
    sides = []
    ko_stats = {}
    connected_stats = {}
    winner = ''
    winner_side = ''

    # Basic data collecting for kill events and mission win data
    for event in data['events']:
        if event[1] == 'killed':
            kill_data = {
                "victim_id": event[2] if event[2] != 'null' else 999,  # 999 - dummy player entity
                "killer_id": event[3][0] if event[3][0] != 'null' else 999,
                "distance": event[4] if event[4] != 'null' else 0,
                "weapon": event[3][1] if len(event[3]) > 1 else 'no weapon',
                "time": event[0] if event[0] != 'null' else 0,  # frame number as a fact
            }
            kills.append(kill_data)
        elif event[1] == 'endMission':
            winner = f'{event[2][0]} - {event[2][1]}'
            winner_side = event[2][0]

    # List of player objects creation as dicts
    for entity in data['entities']:
        player_data = {
            'id': entity['id'],
            'name': entity.get('name', 'no_name'),
            'side': entity.get('side', 'no_side'),
            'group': entity.get("group", 'no_group'),
            'type': entity.get("type", 'unit'),  # unit/vehicle
            # vehicle class: tank, apc, car, truck, static-mortar, static-weapon, heli, parachute, plane, sea
            'class': entity.get("class", ''),
            'is_player': entity.get('isPlayer', 0),  # 1/0
            'role': entity.get('role', 'no_role')
        }

        # As a player can connect and replace a bot after a while, trying to get and store updated value
        updated_isplayer = 0
        for update_frame in PLAYER_UPDATE_FRAMES:
            try:
                updated_name = entity['positions'][update_frame][4]
                player_data['name'] = updated_name if updated_name != '' else player_data['name']
                updated_isplayer = entity['positions'][update_frame][5]
                if updated_isplayer == 1:
                    player_data['is_player'] = 1
                    break
            except IndexError:
                pass
        players.update({entity['id']: player_data})

        # Identification of side commanders, players count
        if entity.get('isPlayer', 0) == 1 or updated_isplayer == 1:
            if len(sides) == 0:
                win = 1 if winner_side == player_data['side'] else 0
                sides.append({'name': player_data['side'], 'ks': player_data['name'].replace(" ", ""), 'players': 0,
                              'tk': 0, 'win': win, 'frags': 0, 'vehicle_frags': 0, 'tag': tag,
                              'mission_name': mission_name, 'date': mission_date})
            if len(sides) == 1 and player_data['side'] != sides[0]['name']:
                win = 1 if winner_side == player_data['side'] else 0
                sides.append({'name': player_data['side'], 'ks': player_data['name'].replace(" ", ""), 'players': 0,
                              'tk': 0, 'win': win, 'frags': 0, 'vehicle_frags': 0, 'tag': tag})

            if player_data['side'] == sides[0]['name']:
                sides[0]['players'] += 1
            else:
                sides[1]['players'] += 1
    # Adding a dummy player for handling null or empty statistic records
    players.update(
        {999: {'id': 999, 'name': '*ARMA*', 'side': 'no_side', 'group': 'no_group', 'type': 'unit', 'is_player': 0}}
    )

    # Adding a dummy side in case of there were no active players on 2nd side
    if len(sides) == 1:
        sides.append({'name': players[999]['side'], 'ks': players[999]['name'], 'players': 0, 'tk': 0,
                      'win': 0, 'frags': 0, 'vehicle_frags': 0, 'tag': tag})

    # Main kills statistic calculation
    for kill in kills:
        killer_id = kill['killer_id']
        victim_id = kill['victim_id']
        killer_name = players[killer_id].get('name', 'no_name')
        victim_name = players[victim_id].get('name', 'no_name')
        killer_side = players[killer_id].get('side', 'no side')
        victim_side = players[victim_id].get('side', 'no side')
        victim_group = players[victim_id].get("group", 'no_group')
        killer_group = players[killer_id].get("group", 'no_group')
        victim_type = players[victim_id].get("type", 'no_type')
        victim_class = players[victim_id].get("class", '')
        victim_isplayer = players[victim_id].get("is_player", 'non_player')
        killer_isplayer = players[killer_id].get("is_player", 'non_player')
        killer_role = players[killer_id].get('role', 'no_role')
        victim_role = players[victim_id].get('role', 'no_role')

        # Identification if killer was in vehicle in the moment of kill event
        if killer_isplayer:
            killer_position_no = kill['time'] - data['entities'][killer_id]['startFrameNum'] - 1
            try:
                killer_in_vehicle = data['entities'][killer_id]['positions'][killer_position_no][3]
            except IndexError as e:
                logging.info(f'Handled error appeared while processing file {data_url}\nError: {e} ')
                killer_in_vehicle = 0
        else:
            killer_in_vehicle = 0

        # Identification if victim was in vehicle in the moment of kill event
        if victim_isplayer:
            victim_position_no = kill['time'] - data['entities'][victim_id]['startFrameNum'] - 1
            try:
                victim_in_vehicle = data['entities'][victim_id]['positions'][victim_position_no][3]
            except IndexError as e:
                logging.info(f'Handled error appeared while processing file {data_url}\nError: {e} ')
                victim_in_vehicle = 0
        else:
            victim_in_vehicle = 0

        # Teamkillers identification, incl. incorrect 'suicide' records handling
        teamkilla = "TK" if (killer_side == victim_side and killer_id != victim_id) else ""

        # Adding new record
        if killer_name not in frag_stats:
            frag_stats[killer_name] = {'frags': 0, 'side': killer_side, 'group': killer_group, 'teamkills': 0,
                                       'victims': [], 'bot_frags': 0, 'vehicle_frags': 0, 'role': killer_role,
                                       'killed_from_vehicle': 0, 'victims_in_vehicle': 0}
        # Victim data structure filling
        victim_data = {
            'teamkilla': teamkilla,
            'time': seconds_to_human(kill['time']),
            'victim_name': victim_name,
            'distance': kill['distance'],
            'weapon': kill['weapon'],
            'killer': killer_name,
            'type': victim_type,
            'class': victim_class,
            'is_player': victim_isplayer,
            'killer_in_vehicle': killer_in_vehicle,
            'victim_in_vehicle': victim_in_vehicle
        }

        # Frags increment and victim list extension logic
        if killer_id != victim_id:
            if killer_side != victim_side:
                if victim_type == 'unit' and victim_isplayer == 1:
                    frag_stats[killer_name]['frags'] += 1
                    if killer_side == sides[0]['name']:
                        sides[0]['frags'] += 1
                    else:
                        sides[1]['frags'] += 1
                    if killer_in_vehicle:
                        frag_stats[killer_name]['killed_from_vehicle'] += 1
                    if victim_in_vehicle:
                        frag_stats[killer_name]['victims_in_vehicle'] += 1
                elif victim_type == 'vehicle' and victim_class in VEHICLE_CLASS_COUNT_LIST:
                    frag_stats[killer_name]['vehicle_frags'] += 1
                    if killer_side == sides[0]['name']:
                        sides[0]['vehicle_frags'] += 1
                    else:
                        sides[1]['vehicle_frags'] += 1
                else:
                    frag_stats[killer_name]['bot_frags'] += 1
            frag_stats[killer_name]['victims'].append(victim_data)

        # Adding a record of death information for a victim
        if victim_name not in frag_stats:
            frag_stats[victim_name] = {'frags': 0, 'side': victim_side, 'group': victim_group, 'teamkills': 0,
                                       'victims': [], 'bot_frags': 0, 'vehicle_frags': 0, 'role': victim_role,
                                       'killed_from_vehicle': 0, 'victims_in_vehicle': 0}
        frag_stats[victim_name]['death_data'] = victim_data

        # Getting killer squad name
        killer_team = get_player_squad_name(killer_name)
        # specific pseudo squad for players without a squad
        if killer_team is None:
            killer_team = f'{SQUAD_FOR_NON_SQUAD_PLAYERS} {killer_side}'

        # Adding new record
        if killer_team not in team_stats:
            team_stats[killer_team] = {'frags': 0, 'side': killer_side, 'teamkills': 0, 'victims': [],
                                       'bot_frags': 0, 'vehicle_frags': 0}

        # Teamkills statistic increment logic
        if killer_id != victim_id:
            if killer_side == victim_side:
                frag_stats[killer_name]['teamkills'] += 1
                team_stats[killer_team]['teamkills'] += 1
                if killer_side == sides[0]['name']:
                    sides[0]['tk'] += 1
                else:
                    sides[1]['tk'] += 1
            else:
                if victim_type == 'unit' and victim_isplayer == 1:
                    team_stats[killer_team]['frags'] += 1
                elif victim_type == 'vehicle' and victim_class in VEHICLE_CLASS_COUNT_LIST:
                    team_stats[killer_team]['vehicle_frags'] += 1
                else:
                    team_stats[killer_team]['bot_frags'] += 1
            team_stats[killer_team]['victims'].append(victim_data)

    # KO revival calculation logic. Checking player frames for being knocked and then active again cases
    # TODO Calculates KO events itself, not revivals. To fix
    for player in data['entities']:
        down = False
        for position in player['positions']:
            if position[2] == 2 and not down:
                down = True
                if player['name'] not in ko_stats:
                    ko_stats[player['name']] = 0
                ko_stats[player['name']] += 1
            elif position[2] == 1 and down:
                down = False
            elif position[2] == 0:
                break

    # Connected attempts calculation logic
    for event in data['events']:
        if event[1] == 'connected':
            if event[2] not in connected_stats:
                connected_stats[event[2]] = 0
            connected_stats[event[2]] += 1

    statistic_result = {
        'error_message': error_message,
        'players': players,
        'frag_stats': frag_stats,
        'team_stats': team_stats,
        'ko_stats': ko_stats,
        'connected_stats': connected_stats,
        'mission_name': mission_name,
        'mission_author': mission_author,
        'mission_duration': mission_duration,
        'sides': sides,
        'tag': tag,
        'winner': winner
    }

    # Calculated statistic storing in cache
    with open(cache_results_file, "w") as f:
        json.dump(statistic_result, f)

    # Updating mission results data cache
    if not only_results:
        missions_stats_data[replay_file_name] = sides
        with open(MISSION_STATS_FILE, "w") as f:
            json.dump(missions_stats_data, f)

    return statistic_result
