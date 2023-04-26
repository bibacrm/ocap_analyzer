from flask import Flask, render_template, request
import json
import requests
import datetime

REPLAY_LIST_URL = 'https://ocap.red-bear.ru/api/v1/operations?tag=&name=&newer=2023-01-01&older=2026-01-01'

# with open('ocap_example.json', encoding="utf-8") as f:
#     data = json.load(f)

# URL = "https://ocap.red-bear.ru/data/2023_04_22__19_36_RBC199Spasenieostrova2jexp.json"
# URL = "https://ocap.red-bear.ru/data/2023_04_22__23_18_RBC195ObeliskReborn1eexp.json"

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
        'mission_name': 'Please expand the replay list above and select a mission replay',
        'mission_author': ""
    }
    if data_url is None:
        return statistic_result

    response = requests.get(data_url)

    with open("temp_ocap.json", "wb") as temp_file:
        temp_file.write(response.content)
    with open('temp_ocap.json', encoding="utf-8") as f:
        data = json.load(f)

    mission_name = data.get('missionName')
    mission_author = data.get('missionAuthor')

    frag_stats = {}
    team_stats = {}
    players = {}
    kills = []

    for entity in data['entities']:
        player_data = {
            'id': entity['id'],
            'name': entity.get('name', 'no_name'),
            'side': entity.get('side', 'no_side'),
            'group': entity.get("group", 'no_group')
        }
        players.update({entity['id']: player_data})
    players.update({999: {'id': 999, 'name': 'unknown(null)', 'side': 'no_side', 'group': 'no_group'}})

    for event in data['events']:
        if event[1] == 'killed':
            kill_data = {
                "victim_id": event[2] if event[2] != 'null' else 999,
                "killer_id": event[3][0] if event[3][0] != 'null' else 999,
                "distance": event[4] if event[4] != 'null' else 0,
                "weapon": event[3][1] if len(event[3]) > 1 else '',
                "time": event[0] if event[0] != 'null' else 0,
            }
            kills.append(kill_data)

    for kill in kills:
        killer_id = kill['killer_id']
        victim_id = kill['victim_id']
        killer_name = players[killer_id].get('name', 'no_name')
        victim_name = players[victim_id].get('name', 'no_name')
        killer_side = players[killer_id].get('side', 'no side')
        victim_side = players[victim_id].get('side', 'no side')
        victim_group = players[victim_id].get("group", 'no_group')
        killer_group = players[killer_id].get("group", 'no_group')

        teamkilla = "TK" if killer_side == victim_side else ""

        if killer_name not in frag_stats:
            frag_stats[killer_name] = {'frags': 0, 'side': killer_side, 'group': killer_group, 'teamkills': 0,
                                       'victims': []}
        frag_stats[killer_name]['frags'] += 1
        victim_data = {
            'teamkilla': teamkilla,
            'time': seconds_to_human(kill['time']),
            'victim_name': victim_name,
            'distance': kill['distance'],
            'weapon': kill['weapon'],
            'killer': killer_name
        }
        frag_stats[killer_name]['victims'].append(victim_data)

        if victim_name not in frag_stats:
            frag_stats[victim_name] = {'frags': 0, 'side': victim_side, 'group': victim_group, 'teamkills': 0,
                                       'victims': []}
        frag_stats[victim_name]['death_data'] = victim_data

        if "[" in killer_name and "]" in killer_name:
            killer_team = killer_name.split("[")[1].split("]")[0]
        elif 'Dw.' in killer_name:
            killer_team = 'Dw'
        elif '=]B[=' in killer_name:
            killer_team = 'B'
        else:
            killer_team = 'Odino4ki'

        if killer_team not in team_stats:
            team_stats[killer_team] = {'frags': 0, 'side': killer_side, 'teamkills': 0, 'victims': []}
        team_stats[killer_team]['frags'] += 1
        team_stats[killer_team]['victims'].append(victim_data)

        if killer_side == victim_side:
            frag_stats[killer_name]['teamkills'] += 1
            team_stats[killer_team]['teamkills'] += 1

    ko_stats = {}

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

    connected_stats = {}

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
        'mission_author': mission_author
    }
    return statistic_result


@app.route('/', methods=['GET', 'POST'])
def index():
    data_url = None
    if request.method == 'POST':
        data_url = request.form['ocap_url']
    stats_report = process_ocap_file(data_url)

    response = requests.get(REPLAY_LIST_URL)
    replay_list_data = response.json()

    for replay in replay_list_data:
        replay['mission_duration'] = seconds_to_human(replay['mission_duration'])

    return render_template(
        'index2.html',
        stat_data=stats_report['frag_stats'],
        team_stat_data=stats_report['team_stats'],
        ko_stats_data=stats_report['ko_stats'],
        connected_stats_data=stats_report['connected_stats'],
        mission_name=stats_report['mission_name'],
        mission_author=stats_report['mission_author'],
        replay_list=replay_list_data
    )


if __name__ == '__main__':
    app.run(host="0.0.0.0", debug=True, port=80)
