#!/usr/bin/python3
from utils import OverWriter as Ow
from replay_parser import ReplayParser as Rp
from api import API
from cache import PlayerCache as Pc
from replay_analyser import cache_players
from statistics import mean
import matplotlib.pyplot as plt

import sys
import argparse

"""global variables"""
args = None
tank_db = None


def parse_input_args():
    global args
    parser = argparse.ArgumentParser(description='A tool to analyse replays.')
    parser.add_argument('dirs', metavar='dir', type=str, nargs='+',
                        help='path to directory(s) containing replays')
    parser.add_argument('-w', '--weighted', dest="weighted", action='store_true',
                        help='Weight player ratings by position on team')
    """parser.add_argument('--output', metavar='OUTPUT', type=str,
                        help="specify a particular output. Default is to output all\n"
                             "options are: 'all', 'rating_scatter', 'rating_histogram', 'result_histogram'")"""
    parser.add_argument('-k', '--key', type=str,
                        default='48cef51dca87be6a244bd55566907d56',
                        help="application id (key) from https://developers.wargaming.net/applications/ (optional)")
    args = parser.parse_args()


def percent_diff(a, b):
    return 100*(float(a)-float(b))/float(a)


def result(replay):
    extended = replay.get('ext')
    if extended:
        for key, val in extended[0].get('personal').items():
            if not key == 'avatar':
                player_team = val.get('team')
                winner = extended[0].get('common').get('winnerTeam')
                if winner == 0:
                    return 'draw'
                return 'win' if player_team == winner else 'loss'
    return 'unknown'


def team_average_ratings(replays, cache):
    team_ratings = []
    for battle in replays:
        teams = [[], []]
        std = battle.get('std')
        for player in std.get('vehicles').values():
            name = player.get('name')
            cached_player = cache.cached_record(name)
            if cached_player and cached_player.get('global_rating'):
                rating = float(cached_player.get('global_rating'))
                team_num = player.get('team') - 1  # 1-indexed -> 0-indexed
                if name == std.get('playerName'):
                    # note player's team but do not eliminate them from the calculation
                    replay_team = team_num
                teams[team_num].append(rating)
        outcome = result(battle)
        green_rating = mean(teams[replay_team])
        red_rating = mean(teams[1 - replay_team])
        if green_rating > red_rating:
            expected_outcome = 'win'
        elif red_rating > green_rating:
            expected_outcome = 'loss'
        else:
            expected_outcome = 'draw'

        team_ratings.append({'green team': green_rating,
                             'red team': red_rating,
                             'outcome': outcome,
                             'expectedOutcome': expected_outcome,
                             'ratingDiff': abs(percent_diff(green_rating, red_rating))})
    return team_ratings


def team_averages(team_ratings):
    g = mean(t.get('green team') for t in team_ratings)
    r = mean(t.get('red team') for t in team_ratings)
    print(f'Total replays:\n\t\t\t{len(team_ratings)}\n'
          f'Green team average rating:\n\t\t\t{g:.6}\n'
          f'Red team average rating:\n\t\t\t{r:.6}\n'
          f'Percentage difference:\n\t\t\t{percent_diff(g, r):+.3}%')


def output_expected_cumulative(team_ratings, diff):
    count_correct = 0
    count_with_outcome = 0
    for t in team_ratings:
        if t.get('outcome') == 'unknown':
            continue
        if t.get('ratingDiff') <= diff:
            continue
        count_with_outcome = count_with_outcome + 1

        if t.get('outcome') == t.get('expectedOutcome'):
            count_correct = count_correct + 1
    if count_with_outcome == 0:
        return {'diff': diff, 'countWithOutcome': 0, 'countCorrect': 0, 'percentageCorrect': 100}
    return {'diff': diff, 'countWithOutcome': count_with_outcome, 'countCorrect': count_correct,
            'percentageCorrect': 100 * count_correct/count_with_outcome}


def output_expected_step(team_ratings, diff_min, diff_max):
    count_correct = 0
    count_with_outcome = 0
    for t in team_ratings:
        if t.get('outcome') == 'unknown':
            continue
        if t.get('ratingDiff') < diff_min or t.get('ratingDiff') >= diff_max:
            continue
        count_with_outcome = count_with_outcome + 1

        if t.get('outcome') == t.get('expectedOutcome'):
            count_correct = count_correct + 1
    if count_with_outcome == 0:
        return {'diff': diff_min, 'countWithOutcome': 0, 'countCorrect': 0, 'percentageCorrect': 100}
    return {'diff': diff_min, 'countWithOutcome': count_with_outcome, 'countCorrect': count_correct,
            'percentageCorrect': 100*count_correct/count_with_outcome}


def plot_diagram(ratings, description):
    plt.subplot(2, 1, 1)
    plt.plot([x.get('diff') for x in ratings], [y.get('percentageCorrect') for y in ratings])
    plt.title(description)
    plt.ylabel("Predicted correct (%)")

    plt.subplot(2, 1, 2)
    plt.plot([x.get('diff') for x in ratings], [y.get('countWithOutcome') for y in ratings])
    plt.xlabel("Team personal rating difference (%)")
    plt.ylabel("count")

    plt.show()


def outputs(replays, team_ratings):
    if not replays:
        return
    team_averages(team_ratings)
    ratings_cumulative = []
    ratings_step = []
    for i in range(1000):
        rating = output_expected_cumulative(team_ratings, i/10)
        ratings_cumulative.append(rating)
        rating_step = output_expected_step(team_ratings, i/10, i+1/10)
        ratings_step.append(rating_step)
        if rating.get('countWithOutcome') < 100:
            break
    plot_diagram(ratings_cumulative, "Outcome prediction cumulative")
    plot_diagram(ratings_step, "Outcome prediction step")


def main():
    global args
    parse_input_args()
    if len(sys.argv) < 2:
        print('Usage = win-and-team.py replay_path [application_id]')
        exit()
    api_key = sys.argv[2] if len(sys.argv) >= 3 else '48cef51dca87be6a244bd55566907d56'
    with Ow(sys.stderr) as ow, Pc('cache.csv', ['nickname', 'id', 'global_rating']) as cache:
        rp = Rp(args.dirs, ow)
        a = API(api_key, ow)
        replays = rp.read_replays()
        cache_players(replays, cache, a)
        team_ratings = team_average_ratings(replays, cache)
    outputs(replays, team_ratings)


if __name__ == "__main__":
    main()
