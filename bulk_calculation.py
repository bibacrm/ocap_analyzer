from main import process_ocap_file, MISSION_STATS_FILE
import requests
import json

BULK_PROCESSING_URL = 'https://ocap.red-bear.ru/api/v1/operations?tag=&name=&newer=2021-01-01&older=2026-01-01'

response = requests.get(BULK_PROCESSING_URL)
replay_list_data = response.json()
total = len(replay_list_data)

# worked not well via threads don`t know why(boring to investigate), so here is a simple loop
for i, replay in enumerate(replay_list_data):
    file_url = 'https://ocap.red-bear.ru/data/' + replay['filename'].strip()
    process_ocap_file(file_url)
    print(f'Finished processing {i+1} of total {total} OCAP replays')

with open(MISSION_STATS_FILE, encoding="utf-8") as f:
    missions_stats_data = json.load(f)

STELS_KS = {'win': 0, 'lost': 0, 'draw': 0}

print(f"\n{'win':3} {'commandor_1':20} - {'win':3} {'commandor_2':20} {'mission_ name':<50}")

for mission, stat in missions_stats_data.items():
    if len(stat) > 1:
        for side in stat:
            if 'STELS' in side['ks']:
                if side['win'] == 1:
                    STELS_KS['win'] += 1
                elif stat[0]['win'] == 0 and stat[1]['win'] == 0:
                    STELS_KS['draw'] += 1
                else:
                    STELS_KS['lost'] += 1
                print(f"{stat[0]['win']:3} {stat[0]['ks']:20} - {stat[1]['win']:3} {stat[1]['ks']:20} {mission:<50}")

print(f"\n Total wins: {STELS_KS['win']} , lost: {STELS_KS['lost']}, draw: {STELS_KS['draw']}")

