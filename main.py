import json
import requests
import logging

from flask import Flask, render_template, request, jsonify
from apscheduler.schedulers.background import BackgroundScheduler
from config import *
from processing.process_attendance import get_attendance
from processing.process_ocap_file import process_ocap_file
from processing.process_player_stats import get_player_stats
from processing.process_total_stats import process_total_stats
from utils.utils import seconds_to_human

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s: %(message)s')

app = Flask(__name__)

scheduler = BackgroundScheduler()
scheduler.start()

# Adding scheduled tasks to initiate recalculation of total statistic data
scheduler.add_job(process_total_stats, 'interval', minutes=7, args=[TVT_MODE_ID])
scheduler.add_job(process_total_stats, 'interval', minutes=17, args=[IF_MODE_ID])
scheduler.add_job(process_total_stats, 'interval', minutes=13, args=[VTN_MODE_ID])


# Home page. Mission list and mission statistic data
@app.route('/', methods=['GET', 'POST'])
def index():
    tag = request.args.get('mission_tag')
    filename = request.args.get('filename')
    data_url = f'{REPLAY_FILE_URL}{filename}' if filename is not None else None
    data_only = request.args.get('data_only')
    # Getting submitted form parameter with a direct OCAP replay json file URL
    if request.method == 'POST':
        data_url = request.form['ocap_url']
        tag = request.form['tag']
        filename = data_url.lstrip(REPLAY_FILE_URL)

    # Getting replay list data
    response = requests.get(REPLAY_LIST_URL)
    replay_list_data = response.json()

    stats_report = process_ocap_file(data_url, tag=tag, replay_list_data=replay_list_data)

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

    # Identification of tag value(project ID in scope of RBC community projects)
    if stats_report['tag'] in MISSION_TAGS_FOR_TOTAL_STATS:
        tag = TVT_MODE_ID
    elif stats_report['tag'] in MISSION_TAGS_FOR_TOTAL_STATS_IF:
        tag = IF_MODE_ID
    elif stats_report['tag'] in MISSION_TAGS_FOR_TOTAL_STATS_VTN:
        tag = VTN_MODE_ID

    if data_only is not None:
        if filename is not None:
            response_body = {
                'stat_data': stats_report['frag_stats'],
                'team_stat_data': stats_report['team_stats'],
                'ko_stats_data': stats_report['ko_stats'],
                'connected_stats_data': stats_report['connected_stats'],
                'mission_name': stats_report['mission_name'],
                'mission_author': stats_report['mission_author'],
                'mission_duration': stats_report['mission_duration'],
                'sides': stats_report['sides'],
                'winner': stats_report['winner'],
                'filename': filename
            }
        else:
            response_body = {
                'replay_list': replay_list_data
            }
        return jsonify(response_body), 200

    return render_template(
        'index2.html',
        tag=tag,
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
        replay_list=replay_list_data,
        filename=filename
    )


# Total statistic by project/tag
@app.route('/total_<tag>', methods=['GET'])
def total(tag):
    stats_report = process_total_stats(tag, calculate=False)
    data_only = request.args.get('data_only')

    if data_only is not None:
        response_body = {
            'cache_count': stats_report['cache_count'],
            'tk_stats': stats_report['tk_stats'],
            'tk_stats_steam': stats_report['tk_stats_steam'],
            'team_tk_stats': stats_report['team_tk_stats'],
            'frag_stats': stats_report['frag_stats'],
            'frag_stats_steam': stats_report['frag_stats_steam'],
            'team_frag_stats': stats_report['team_frag_stats'],
            'ks_win_stat': stats_report['ks_win_stat']
        }
        return jsonify(response_body), 200

    return render_template(
        'index_total.html',
        tag=tag,
        error_message=stats_report['error_message'],
        cache_count=stats_report['cache_count'],
        tk_stats=stats_report['tk_stats'],
        tk_stats_steam=stats_report['tk_stats_steam'],
        team_tk_stats=stats_report['team_tk_stats'],
        frag_stats=stats_report['frag_stats'],
        frag_stats_steam=stats_report['frag_stats_steam'],
        team_frag_stats=stats_report['team_frag_stats'],
        ks_win_stat=stats_report['ks_win_stat']
    )


# Personal statistic by player name or steam_id
@app.route('/total_<tag>/personal', methods=['GET'])
def player_total(tag):
    player_name = request.args.get('player_name')
    steam_id = request.args.get('steam_id')
    data_only = request.args.get('data_only')

    stats_report = get_player_stats(player_name, tag, steam_id)

    if data_only is not None:
        response_body = {
            'player_name': player_name,
            'steam_id': steam_id if steam_id is not None else stats_report['steam_id'],
            'tk_stats': stats_report['tk_stats'],
            'frag_stats': stats_report['frag_stats'],
            'ks_win_stat': stats_report['ks_win_stat'],
            'ks_missions': stats_report['ks_missions']
        }
        return jsonify(response_body), 200

    return render_template(
        'index_player.html',
        tag=tag,
        player_name=player_name,
        steam_id=steam_id if steam_id is not None else stats_report['steam_id'],
        error_message=stats_report['error_message'],
        tk_stats=stats_report['tk_stats'],
        frag_stats=stats_report['frag_stats'],
        ks_win_stat=stats_report['ks_win_stat'],
        ks_missions=stats_report['ks_missions']
    )


# Missions attendance statistic
@app.route('/attendance', methods=['GET'])
def attendance():
    tag = request.args.get('tag')
    data_only = request.args.get('data_only')

    stats_report = get_attendance(tag)

    # Getting sorted data to show in resulting tables
    rotation_1_1 = sorted(TVT_1_ROTATION_TEAMS['1'])
    rotation_1_2 = sorted(TVT_1_ROTATION_TEAMS['2'])
    rotation_2_1 = sorted(TVT_2_ROTATION_TEAMS['1'])
    rotation_2_2 = sorted(TVT_2_ROTATION_TEAMS['2'])

    if tag != 'tvt':
        rotation_2_1 = []
        rotation_2_2 = []
        if tag == 'if':
            rotation_1_1 = sorted(IF_ROTATION_TEAMS['1'])
            rotation_1_2 = sorted(IF_ROTATION_TEAMS['2'])
        elif tag == 'vtn':
            rotation_1_1 = sorted(VTN_ROTATION_TEAMS['1'])
            rotation_1_2 = sorted(VTN_ROTATION_TEAMS['2'])

    if data_only is not None:
        response_body = {
            'attendance': stats_report['attendance'],
            'rotation_1_1': rotation_1_1,
            'rotation_1_2': rotation_1_2,
            'rotation_2_1': rotation_2_1,
            'rotation_2_2': rotation_2_2
        }
        return jsonify(response_body), 200

    return render_template(
        'index_attendance2.html',
        error_message=stats_report['error_message'],
        tag=tag,
        attendance=stats_report['attendance'],
        rotation_1_1=rotation_1_1,
        rotation_1_2=rotation_1_2,
        rotation_2_1=rotation_2_1,
        rotation_2_2=rotation_2_2
    )


if __name__ == '__main__':
    app.run(host="0.0.0.0", debug=True, port=80)
