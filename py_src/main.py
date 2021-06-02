from latte_utils import get_missing_actions
from snapshot import Snapshot


def bm_explore(snapshot_name):
    snapshot = Snapshot(snapshot_name)
    tb_commands = snapshot.explore()
    important_actions = snapshot.get_important_actions()
    tb_done_actions = snapshot.get_tb_done_actions()
    tb_undone_actions = get_missing_actions(important_actions, tb_done_actions)
    snapshot.validate_by_stb()
    different_behaviors, directional_unreachable, unlocatable, different_behaviors_directional_unreachable = snapshot.report_issues()
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
    # pass
    import sys
    snapshot_name = "Checkout_N2"
    if len(sys.argv) > 1:
        snapshot_name = sys.argv[1]
    bm_explore(snapshot_name)
