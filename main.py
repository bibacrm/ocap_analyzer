from flask import Flask, render_template, request
import json
import requests
import datetime
import os
import hashlib
import re
import gzip
import heapq

REPLAY_LIST_URL = 'https://ocap.red-bear.ru/api/v1/operations?tag=&name=&newer=2020-01-01&older=2026-01-01'
MISSION_STATS_FOLDER = './cache/mission_stats'
MISSION_STATS_FILE = os.path.join(MISSION_STATS_FOLDER, 'missions_stats.json')
TOTAL_STATS_FOLDER = './cache/total_stats'
TOTAL_STATS_FILE = os.path.join(TOTAL_STATS_FOLDER, 'total_stats.json')

VEHICLE_CLASS_COUNT_LIST = ['tank', 'apc', 'car', 'heli', 'plane', 'sea']


app = Flask(__name__)


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
    for k, v in d.items():
        if value in v:
            if steam_id is None:
                steam_id = k
            name_list.update(set(v))
    if steam_id is not None:
        d[steam_id] = name_list

    return steam_id, name_list


def create_steam_name_list():
    file_path = "hashids.txt"

    name_dict = {}

    with open(file_path, encoding="utf-8") as file:
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


def process_ocap_file(data_url, only_results=False):
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
        'winner': ''
    }

    if data_url is None:
        # Start page case
        statistic_result['error_message'] = 'Please select a mission replay to get statistic data'
        return statistic_result

    # Cache settings and preparation
    cache_folder = './cache'
    results_folder = './cache/results'
    os.makedirs(cache_folder, exist_ok=True)
    os.makedirs(results_folder, exist_ok=True)
    os.makedirs(MISSION_STATS_FOLDER, exist_ok=True)

    mission_url_hash = hashlib.md5(data_url.encode()).hexdigest()
    replay_file_name = data_url.split('/')[-1]
    cache_file = os.path.join(cache_folder, mission_url_hash)
    cache_results = os.path.join(results_folder, mission_url_hash)
    cache_missions = MISSION_STATS_FILE

    # Cache logic
    if os.path.exists(cache_results):
        with open(cache_results, encoding="utf-8") as f:
            statistic_result = json.load(f)
        return statistic_result

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

    if not only_results:
        if os.path.exists(cache_missions):
            with open(cache_missions, encoding="utf-8") as f:
                missions_stats_data = json.load(f)
        else:
            missions_stats_data = {}

    # Basic data for Mission statistic header
    mission_name = data.get('missionName')
    mission_author = data.get('missionAuthor')
    mission_duration = seconds_to_human(data.get('endFrame'))

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

    # Basic data collecting for kill events
    for event in data['events']:
        if event[1] == 'killed':
            kill_data = {
                "victim_id": event[2] if event[2] != 'null' else 999,
                "killer_id": event[3][0] if event[3][0] != 'null' else 999,
                "distance": event[4] if event[4] != 'null' else 0,
                "weapon": event[3][1] if len(event[3]) > 1 else '',
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
            'is_player': entity.get('isPlayer', 0)  # 1/0
        }

        # As a player can connect and replace a bot after a while, trying to get and store updated value
        update_frames = [1200, 900, 600, 300, 180]  # 20min, 15min, 10min, 5min, 3min delay to get updated name and type
        updated_isplayer = 0
        for update_frame in update_frames:
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
                sides.append({'name': player_data['side'], 'ks': player_data['name'], 'players': 0, 'tk': 0,
                              'win': win, 'frags': 0, 'vehicle_frags': 0})
            if len(sides) == 1 and player_data['side'] != sides[0]['name']:
                win = 1 if winner_side == player_data['side'] else 0
                sides.append({'name': player_data['side'], 'ks': player_data['name'], 'players': 0, 'tk': 0,
                              'win': win, 'frags': 0, 'vehicle_frags': 0})

            if player_data['side'] == sides[0]['name']:
                sides[0]['players'] += 1
            else:
                sides[1]['players'] += 1
    # Adding a dummy player for handling null or empty statistic records
    players.update({999: {'id': 999, 'name': 'unknown(null)', 'side': 'no_side', 'group': 'no_group', 'type': 'unit'}})

    # Adding a dummy side in case of there were no players on 2nd side
    if len(sides) == 1:
        sides.append({'name': players[999]['side'], 'ks': players[999]['name'], 'players': 0, 'tk': 0,
                      'win': 0, 'frags': 0, 'vehicle_frags': 0})

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

        # Teamkillers identification, incl. incorrect 'suicide' records handling
        teamkilla = "TK" if (killer_side == victim_side and killer_id != victim_id) else ""

        if killer_name not in frag_stats:
            frag_stats[killer_name] = {'frags': 0, 'side': killer_side, 'group': killer_group, 'teamkills': 0,
                                       'victims': [], 'bot_frags': 0, 'vehicle_frags': 0}
        victim_data = {
            'teamkilla': teamkilla,
            'time': seconds_to_human(kill['time']),
            'victim_name': victim_name,
            'distance': kill['distance'],
            'weapon': kill['weapon'],
            'killer': killer_name,
            'type': victim_type,
            'class': victim_class,
            'is_player': victim_isplayer
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
                                       'victims': [], 'bot_frags': 0, 'vehicle_frags': 0}
        frag_stats[victim_name]['death_data'] = victim_data

        # Squad tag parsing logic for a main pattern "[<Squad>]<Player>", "~" is for recruits specific players on RBC
        if '=]B[=' in killer_name:
            killer_team = 'B'
        elif any(i in killer_name for i in ["=UN=", '-UN-', '|UN|', '[UN]']):
            killer_team = 'UN'
        elif 'Dw.' in killer_name:
            killer_team = 'Dw'
        elif "[" in killer_name and "]" in killer_name:
            killer_team = killer_name.split("[")[1].split("]")[0].strip('~')
        elif 'St.' in killer_name:
            killer_team = 'St'
        else:
            # specific pseudo squad for players without a squad
            killer_team = f'Odino4ki {killer_side}'

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
        'winner': winner
    }

    # Calculated statistic storing in cache
    with open(cache_results, "w") as f:
        json.dump(statistic_result, f)

    if not only_results:
        missions_stats_data[replay_file_name] = sides
        with open(cache_missions, "w") as f:
            json.dump(missions_stats_data, f)

    return statistic_result


def process_total_stats():
    # Getting replay list data
    response = requests.get(REPLAY_LIST_URL)
    replay_list_data = response.json()

    results_folder = './cache/results'
    tk_stats = {}
    tk_stats_steam = {}
    team_tk_stats = {}
    frag_stats = {}
    frag_stats_steam = {}
    team_frag_stats = {}
    error_message = ''

    os.makedirs(TOTAL_STATS_FOLDER, exist_ok=True)

    if os.path.exists(TOTAL_STATS_FILE):
        with open(TOTAL_STATS_FILE, encoding="utf-8") as f:
            statistic_result = json.load(f)
        if statistic_result['cache_count'] == len(replay_list_data):
            return statistic_result

    player_steam_dict = create_steam_name_list()

    for replay in replay_list_data:
        if replay.get('mission_duration', 0) > 1800 and replay.get('tag', '') in ['tvt', 'TvT', 'tvt_ii', 'TvT_II']:
            file_url = 'https://ocap.red-bear.ru/data/' + replay['filename'].strip()
            mission_url_hash = hashlib.md5(file_url.encode()).hexdigest()
            cache_results = os.path.join(results_folder, mission_url_hash)
            if os.path.exists(cache_results):
                with open(cache_results, encoding="utf-8") as f:
                    statistic_result = json.load(f)
            else:
                error_message = 'Some missions OCAP replays are not processed still, please do it on the home page'
                break

            # ST.to Dw. legacy statistic handling
            # to_delete = []
            player_to_add = []
            for player, stats in statistic_result['frag_stats'].items():
                if 'St.' in player or 'Dw.' in player:
                    new_name = player.replace('St.', '[StDw]')
                    new_name = new_name.replace('Dw.', '[StDw]')
                    player_to_add.append({new_name: stats})
                    # to_delete.append(player)
            # for player in to_delete:
            #     del statistic_result['frag_stats'][player]
            for player in player_to_add:
                statistic_result['frag_stats'].update(player)
            team_to_add = []
            for team, stats in statistic_result['team_stats'].items():
                if team == 'St' or team == 'Dw':
                    team_to_add.append(stats)
            if len(team_to_add) > 0:
                new_stats = {'teamkills': 0, 'frags': 0, 'bot_frags': 0, 'vehicle_frags': 0, 'side': 'no_side',
                             'victims': []}

                for team in team_to_add:
                    for k, v in team.items():
                        if k in new_stats:
                            new_stats[k] += v
                statistic_result['team_stats']['StDw'] = new_stats

            # By SteamID. Kiberkotlets and Teamkills statistic aggregation
            for player, stats in statistic_result['frag_stats'].items():
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
                                                      'vehicle_frags': 0, 'name_list': set()}
                    frag_stats_steam[steam_id]['kills'] += stats['frags']
                    frag_stats_steam[steam_id]['bot_frags'] += stats['bot_frags']
                    frag_stats_steam[steam_id]['vehicle_frags'] += stats['vehicle_frags']
                    frag_stats_steam[steam_id]['missions'] += 1
                    frag_stats_steam[steam_id]['name_list'].add(player)
                    frag_stats_steam[steam_id]['name_last'] = player_name
                    if 'death_data' in stats:
                        frag_stats_steam[steam_id]['deaths'] += 1

                # By nickname. Kiberkotlets and Teamkills statistic aggregation
                if player_name not in tk_stats:
                    tk_stats[player_name] = {'kills': 0, 'missions': 0}
                tk_stats[player_name]['kills'] += stats['teamkills']
                tk_stats[player_name]['missions'] += 1

                if player_name not in frag_stats:
                    frag_stats[player_name] = {'kills': 0, 'missions': 0, 'deaths': 0, 'bot_frags': 0,
                                               'vehicle_frags': 0, 'victims': {}}
                frag_stats[player_name]['kills'] += stats['frags']
                frag_stats[player_name]['bot_frags'] += stats['bot_frags']
                frag_stats[player_name]['vehicle_frags'] += stats['vehicle_frags']
                frag_stats[player_name]['missions'] += 1
                for victim in stats['victims']:
                    if victim['victim_name'] not in frag_stats[player_name]['victims']:
                        frag_stats[player_name]['victims'][victim['victim_name']] = 0
                    frag_stats[player_name]['victims'][victim['victim_name']] += 1
                if 'death_data' in stats:
                    frag_stats[player_name]['deaths'] += 1

            # Kiber squads players and Squad teamkills statistic aggregation
            for team, stats in statistic_result['team_stats'].items():
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
            if stat['missions'] > 28:
                stat['k_m'] = round(stat['kills'] / stat['missions'], 3)
                if stat_dict == frag_stats or stat_dict == frag_stats_steam:
                    deaths = stat['deaths'] if stat['deaths'] > 0 else 1
                    stat['k_d'] = round(stat['kills'] / deaths, 3)
            else:
                to_delete.append(item)
        for key in to_delete:
            del stat_dict[key]

    # sorted(stats['victims'].items(), key=lambda item: item[1], reverse=True)
    for stat_dict in [frag_stats, team_frag_stats]:
        for name, stats in stat_dict.items():
            stats['victims'] = heapq.nlargest(20, stats['victims'].items(), key=lambda x: x[1])

    statistic_result = {
        'cache_count': len(replay_list_data),
        'error_message': error_message,
        'frag_stats': frag_stats,
        'team_frag_stats': team_frag_stats,
        'frag_stats_steam': frag_stats_steam,
        'team_tk_stats': team_tk_stats,
        'tk_stats_steam': tk_stats_steam,
        'tk_stats': tk_stats
    }

    # Calculated statistic storing in cache
    with open(TOTAL_STATS_FILE, "w") as f:
        json.dump(statistic_result, f, default=serialize_sets)

    return statistic_result


@app.route('/', methods=['GET', 'POST'])
def index():
    data_url = None
    # Getting submitted form parameter with a direct OCAP replay json file URL
    if request.method == 'POST':
        data_url = request.form['ocap_url']
    stats_report = process_ocap_file(data_url)

    # Getting replay list data
    response = requests.get(REPLAY_LIST_URL)
    replay_list_data = response.json()

    # Getting cached mission stats data
    if os.path.exists(MISSION_STATS_FILE):
        with open(MISSION_STATS_FILE, encoding="utf-8") as f:
            missions_stats_data = json.load(f)
    else:
        missions_stats_data = {}

    # Mission duration converting logic and filling with cached data
    for replay in replay_list_data:
        replay['mission_duration'] = seconds_to_human(replay['mission_duration'])
        if replay['filename'] in missions_stats_data:
            replay['stats'] = missions_stats_data[replay['filename']]

    # loading modal window text definition
    loading_message = "Loading..."
    if data_url is not None:
        loading_message = "Processing OCAP file, please wait..."

    return render_template(
        'index2.html',
        loading_message=loading_message,
        error_message=stats_report['error_message'],
        stat_data=stats_report['frag_stats'],
        team_stat_data=stats_report['team_stats'],
        ko_stats_data=stats_report['ko_stats'],
        connected_stats_data=stats_report['connected_stats'],
        mission_name=stats_report['mission_name'],
        mission_author=stats_report['mission_author'],
        mission_duration=stats_report['mission_duration'],
        sides=stats_report['sides'],
        winner=stats_report['winner'],
        replay_list=replay_list_data
    )


@app.route('/total', methods=['GET'])
def total():
    stats_report = process_total_stats()

    # loading modal window text definition
    loading_message = "Loading..."

    return render_template(
        'index_total.html',
        loading_message=loading_message,
        error_message=stats_report['error_message'],
        tk_stats=stats_report['tk_stats'],
        tk_stats_steam=stats_report['tk_stats_steam'],
        team_tk_stats=stats_report['team_tk_stats'],
        frag_stats=stats_report['frag_stats'],
        frag_stats_steam=stats_report['frag_stats_steam'],
        team_frag_stats=stats_report['team_frag_stats']
    )


if __name__ == '__main__':
    app.run(host="0.0.0.0", debug=True, port=80)
