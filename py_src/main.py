from snapshot import Snapshot


def bm_explore():
    snapshot = Snapshot("clock_0")
    tb_commands = snapshot.explore()


if __name__ == "__main__":
    bm_explore()
