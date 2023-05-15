import os

# 'Rotation' teams/squads - regular active team/squad names, split and scheduled for each mission side
# RBC project has 2 servers for playing TVT games, called "TVT1" and "TVT2"
TVT_1_ROTATION_TEAMS = {
    '1': ['LS', 'URAL', 'STELS', 'KSK', 'BWR', 'DON', 'UN', 'StB', '13th'],
    '2': ['RMC', 'VRG', 'RE', '7th', 'MPU', 'DG', 'TF', 'YKZ', 'B', 'WF']
}
TVT_2_ROTATION_TEAMS = {
    '1': ['NT', 'STELS', 'Dw', 'AGG', 'RE', '7th', 'URAL', 'DON', 'VRG', '5th'],
    '2': ['UN', 'RS', 'RMC', 'CBR', 'Delta', '404', 'CA', 'WF', 'ATT', 'KSK']
}
VTN_ROTATION_TEAMS = {
    '1': ['FoS', 'HA', 'TF'],
    '2': ['Гивай', 'KSK', 'WF']
}
IF_ROTATION_TEAMS = {
    '1': ['MPU', 'DON', 'RATS', 'ANVIL', 'ATW', 'DSG', 'KPblM', 'RS', '7th', 'URAL'],
    '2': ['StB', 'TF', 'RKKA', 'STC', 'TNA', 'VTS', 'WF', 'Гивай', 'HA', 'KSK']
}

# URL to get OCAP replay list
REPLAY_LIST_URL = 'https://ocap.red-bear.ru/api/v1/operations?tag=&name=&newer=2020-01-01&older=2026-01-01'
# URL base to be concatenated with ocap file name for getting OCAP replay json file
REPLAY_FILE_URL = 'https://ocap.red-bear.ru/data/'

# Cache folders and filenames
CACHE_FOLDER = './cache'
RESULTS_FOLDER = './cache/results'
MISSION_STATS_FOLDER = './cache/mission_stats'
MISSION_STATS_FILE = os.path.join(MISSION_STATS_FOLDER, 'missions_stats.json')
TOTAL_STATS_FOLDER = './cache/total_stats'
# Total statistic files per project, TVT(default), IF, VTN for RBC
TOTAL_STATS_FILE = os.path.join(TOTAL_STATS_FOLDER, 'total_stats.json')
TOTAL_STATS_FILE_IF = os.path.join(TOTAL_STATS_FOLDER, 'total_stats_if.json')
TOTAL_STATS_FILE_VTN = os.path.join(TOTAL_STATS_FOLDER, 'total_stats_vtn.json')

# List with steam_id hash and player names
STEAM_ID_LIST_PATH = "hashids.txt"
# List with steam_id hash and player names for banned players
STEAM_ID_BAN_PATH = "hash_bans.txt"
# List of teams/squads banned
BAN_TEAM_LIST = ['OT', 'X', 'CU', 'VTS']
# List of statistic fields to erase data for banned players and teams/squads
BAN_STAT_ERASE = ['kills', 'vehicle_frags', 'k_d', 'k_m', 'killed_from_vehicle', 'victims_in_vehicle']

# Main identifiers of projects inside ARMA3 community
TVT_MODE_ID = 'tvt'
IF_MODE_ID = 'if'
VTN_MODE_ID = 'vtn'
# OCAP replay tag list for each project
MISSION_TAGS_FOR_TOTAL_STATS = [TVT_MODE_ID, 'TvT', 'tvt_ii', 'TvT_II']
MISSION_TAGS_FOR_TOTAL_STATS_IF = [IF_MODE_ID, 'IF']
MISSION_TAGS_FOR_TOTAL_STATS_VTN = [VTN_MODE_ID, 'Brutal']

# List of OCAP vehile classes to count as "Vehicle frags"
VEHICLE_CLASS_COUNT_LIST = ['tank', 'apc', 'car', 'heli', 'plane', 'sea']

# 35, 20, 15, 10, 5min delay to get updated active player data
PLAYER_UPDATE_FRAMES = [2100, 1200, 900, 600, 300]

# Name of Team/squad for players without team/squad
SQUAD_FOR_NON_SQUAD_PLAYERS = '*Odino4ki*'

# Seconds, to calculate only real ocap replays, skipping test/filler missions
TVT_DURATION_LIMIT = 1800
IF_DURATION_LIMIT = 300
VTN_DURATION_LIMIT = 300

# Missions count player must be part of in order to calculate K/D and K/M stats
TOTAL_STATISTIC_MISSION_LIMIT = 20

# Limits to calculate top # statistic records for each player or team/squad
VICTIMS_STAT_LIMIT = 20
KILLED_BY_STAT_LIMIT = 10
VEHICLE_STAT_LIMIT = 10
TEAMKILLED_BY_STAT_LIMIT = 10
WEAPONS_STAT_LIMIT = 10
# Limit to calculated KS win rate
KS_MISSION_LIMIT = 4
