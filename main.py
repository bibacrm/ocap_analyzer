from flask import Flask, render_template, request
import json
import requests
import datetime
import os
import hashlib

REPLAY_LIST_URL = 'https://ocap.red-bear.ru/api/v1/operations?tag=&name=&newer=2023-01-01&older=2026-01-01'

app = Flask(__name__)


def seconds_to_human(seconds):
    time = str(datetime.timedelta(seconds=seconds))
    if '.' in time:
        time = time[:time.index('.')]
    return time


def process_ocap_file(data_url):
    statistic_result = {
        'frag_stats': {},
        'team_stats': {},
        'ko_stats': {},
        'connected_stats': {},
        'mission_name': 'Please expand the list above and select a mission replay',
        'mission_author': "",
        'mission_duration': "",
        'sides': {},
        'winner': ''
    }

    if data_url is None:
        # Start page case
        return statistic_result

    # Cache settings and preparation
    cache_folder = './cache'
    results_folder = './cache/results'
    os.makedirs(cache_folder, exist_ok=True)
    os.makedirs(results_folder, exist_ok=True)

    cache_file = os.path.join(cache_folder, hashlib.md5(data_url.encode()).hexdigest())
    cache_results = os.path.join(results_folder, hashlib.md5(data_url.encode()).hexdigest())

    # Cache logic
    if os.path.exists(cache_results):
        with open(cache_results, encoding="utf-8") as f:
            statistic_result = json.load(f)
        return statistic_result

    if os.path.exists(cache_file):
        with open(cache_file, encoding="utf-8") as f:
            data = json.load(f)
    else:
        response = requests.get(data_url)
        with open(cache_file, "wb") as temp_file:
            temp_file.write(response.content)
        with open(cache_file, encoding="utf-8") as f:
            data = json.load(f)

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

    # List of player objects creation as dicts
    for entity in data['entities']:
        player_data = {
            'id': entity['id'],
            'name': entity.get('name', 'no_name'),
            'side': entity.get('side', 'no_side'),
            'group': entity.get("group", 'no_group')
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
                    break
            except IndexError:
                pass

        players.update({entity['id']: player_data})

        # Identification of side commanders, players count
        if entity.get('isPlayer', 0) == 1 or updated_isplayer == 1:
            if len(sides) == 0:
                sides.append({'name': player_data['side'], 'ks': player_data['name'], 'players': 0})
            if len(sides) == 1 and player_data['side'] != sides[0]['name']:
                sides.append({'name': player_data['side'], 'ks': player_data['name'], 'players': 0})

            if player_data['side'] == sides[0]['name']:
                sides[0]['players'] += 1
            else:
                sides[1]['players'] += 1
    # Adding a dummy player for handling null or empty statistic records
    players.update({999: {'id': 999, 'name': 'unknown(null)', 'side': 'no_side', 'group': 'no_group'}})

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

        # Teamkillers identification, incl. incorrect 'suicide' records handling
        teamkilla = "TK" if (killer_side == victim_side and killer_id != victim_id) else ""

        if killer_name not in frag_stats:
            frag_stats[killer_name] = {'frags': 0, 'side': killer_side, 'group': killer_group, 'teamkills': 0,
                                       'victims': []}
        victim_data = {
            'teamkilla': teamkilla,
            'time': seconds_to_human(kill['time']),
            'victim_name': victim_name,
            'distance': kill['distance'],
            'weapon': kill['weapon'],
            'killer': killer_name
        }

        # Frags increment and victim list extension logic
        if killer_id != victim_id:
            if killer_side != victim_side:
                frag_stats[killer_name]['frags'] += 1
            frag_stats[killer_name]['victims'].append(victim_data)

        # Adding a record of death information for a victim
        if victim_name not in frag_stats:
            frag_stats[victim_name] = {'frags': 0, 'side': victim_side, 'group': victim_group, 'teamkills': 0,
                                       'victims': []}
        frag_stats[victim_name]['death_data'] = victim_data

        # Squad tag parsing logic for a main pattern "[<Squad>]<Player>", "~" is for recruits specific players on RBC
        if "[" in killer_name and "]" in killer_name:
            killer_team = killer_name.split("[")[1].split("]")[0].strip('~')
        elif 'Dw.' in killer_name:
            killer_team = 'Dw'
        elif '=]B[=' in killer_name:
            killer_team = 'B'
        else:
            # specific pseudo squad for players without a squad
            killer_team = f'Odino4ki {killer_side}'

        if killer_team not in team_stats:
            team_stats[killer_team] = {'frags': 0, 'side': killer_side, 'teamkills': 0, 'victims': []}

        # Teamkills statistic increment logic
        if killer_id != victim_id:
            if killer_side == victim_side:
                frag_stats[killer_name]['teamkills'] += 1
                team_stats[killer_team]['teamkills'] += 1
            else:
                team_stats[killer_team]['frags'] += 1
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

    # Mission duration converting logic
    for replay in replay_list_data:
        replay['mission_duration'] = seconds_to_human(replay['mission_duration'])

    # loading modal window text definition
    loading_message = "Loading..."
    if data_url is not None:
        loading_message = "Processing OCAP file, please wait..."

    return render_template(
        'index2.html',
        loading_message=loading_message,
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


if __name__ == '__main__':
    app.run(host="0.0.0.0", debug=True, port=80)
