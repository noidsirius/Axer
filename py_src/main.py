import argparse
import asyncio
import logging
from latte_utils import get_missing_actions
from snapshot import Snapshot


def bm_explore(snapshot_name):
    snapshot = Snapshot(snapshot_name)
    success_explore = asyncio.run(snapshot.explore())
    if not success_explore:
        print("Problem with explore!")
        return
    important_actions = snapshot.get_important_actions()
    tb_done_actions = snapshot.get_tb_done_actions()
    tb_undone_actions = get_missing_actions(important_actions, tb_done_actions)
    snapshot.validate_by_stb()
    different_behaviors, directional_unreachable, unlocatable, different_behaviors_directional_unreachable, pending = snapshot.report_issues()
    print("Number of different behavior: ", len(different_behaviors))
    print("Number of directional unreachable: ", len(directional_unreachable))
    print("Number of unlocatable: ", len(unlocatable))
    print("Number of ddifferent behaviors directional unreachable: ", len(different_behaviors_directional_unreachable))


# def alaki():
#     from snapshot import Snapshot
#     from latte_utils import *
#     import json
#     snapshot_name = "Budget_0"
#     snapshot = Snapshot(snapshot_name)
#     important_actions = snapshot.get_important_actions()
#     tb_done_actions = snapshot.get_tb_done_actions()
#     tb_undone_actions = get_missing_actions(important_actions, tb_done_actions)
#     l, r = asyncio.run(reg_execute_command(json.dumps(tb_undone_actions[0])))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--snapshot', type=str, required=True, help='Name of the snapshot on the running AVD')
    parser.add_argument('--debug', action='store_true')
    args = parser.parse_args()

    if args.debug:
        level = logging.DEBUG
    else:
        level = logging.INFO
    logging.basicConfig(level=level)

    bm_explore(args.snapshot)
