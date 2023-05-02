from main import process_ocap_file, MISSION_STATS_FILE, MISSION_STATS_FOLDER
from tqdm import tqdm
import requests
import json
import concurrent.futures
import os
import hashlib


BULK_PROCESSING_URL = 'https://ocap.red-bear.ru/api/v1/operations?tag=&name=&newer=2020-01-01&older=2026-01-01'

response = requests.get(BULK_PROCESSING_URL)
replay_list_data = response.json()
total = len(replay_list_data)


file_list = ['https://ocap.red-bear.ru/data/' + replay['filename'].strip() for replay in replay_list_data]

max_threads = 6

with concurrent.futures.ThreadPoolExecutor(max_workers=max_threads) as executor:
    results = []
    future_to_file = {executor.submit(process_ocap_file, file_url, True): file_url for file_url in file_list}
    with tqdm(total=len(file_list)) as pbar:
        for future in concurrent.futures.as_completed(future_to_file):
            file = future_to_file[future]
            try:
                result = future.result()
                results.append(result)
            except Exception as e:
                print(f"Error processing file {file}: {e}")
            pbar.update(1)

# print(results)

# worked not well via threads don`t know why(boring to investigate), so here is a simple loop
for i, replay in enumerate(replay_list_data):
    data_url = 'https://ocap.red-bear.ru/data/' + replay['filename'].strip()
    replay_file_name = data_url.split('/')[-1]
    mission_url_hash = hashlib.md5(data_url.encode()).hexdigest()
    results_folder = './cache/results'
    cache_results = os.path.join(results_folder, mission_url_hash)

    os.makedirs(MISSION_STATS_FOLDER, exist_ok=True)

    if os.path.exists(MISSION_STATS_FILE):
        with open(MISSION_STATS_FILE, encoding="utf-8") as f:
            missions_stats_data = json.load(f)
    else:
        missions_stats_data = {}

    if replay_file_name in missions_stats_data:
        continue

    if os.path.exists(cache_results):
        with open(cache_results, encoding="utf-8") as f:
            statistic_result = json.load(f)

    missions_stats_data[replay_file_name] = statistic_result['sides']
    with open(MISSION_STATS_FILE, "w") as f:
        json.dump(missions_stats_data, f)

    print(f'Finished processing {i+1} of total {total} OCAP replays')


# KS statistic
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

