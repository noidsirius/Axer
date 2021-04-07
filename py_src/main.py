from latte_utils import get_missing_actions
from snapshot import Snapshot


def bm_explore():
    snapshot_name = "Yelp_0"
    snapshot = Snapshot(snapshot_name)
    tb_commands = snapshot.explore()
    important_actions = snapshot.get_important_actions()
    tb_done_actions = snapshot.get_tb_done_actions()
    tb_undone_actions = get_missing_actions(important_actions, tb_done_actions)
    snapshot.validate_by_stb()
    different_behaviors, directional_unreachable, unlocatable, different_behaviors_directional_unreachable = snapshot.report_issues()


def alaki():
    from snapshot import Snapshot
    from latte_utils import *
    import json
    snapshot_name = "Budget_0"
    snapshot = Snapshot(snapshot_name)
    important_actions = snapshot.get_important_actions()
    tb_done_actions = snapshot.get_tb_done_actions()
    tb_undone_actions = get_missing_actions(important_actions, tb_done_actions)
    l, r = asyncio.run(reg_execute_command(json.dumps(tb_undone_actions[0])))


if __name__ == "__main__":
    # pass
    bm_explore()
