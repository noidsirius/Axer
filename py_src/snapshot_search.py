import asyncio
from pathlib import Path
from typing import List
import logging

from results_utils import AddressBook
from snapshot import Snapshot

logger = logging.getLogger(__name__)


def compare_string(value: str, query: str):
    value = value.strip().lower()
    query = query.strip().lower()
    if query == '~':
        return len(value) == 0
    elif query[0] == '!':
        return query[1:].strip() not in value
    elif query[0] == '"' and query[-1] == '"':
        return query[1:-1] == value
    else:
        return query in value


def compare_bool(value: bool, query: str):
    query = query.strip().lower()
    if query == 'any':
        return True
    return value == (query == 'true')


def compare_int(value: int, query: str):
    query = query.strip().lower()
    if query.startswith('<'):
        return value < int(query[1:])
    elif query.startswith('>'):
        return value > int(query[1:])
    elif query.startswith('<='):
        return value <= int(query[2:])
    elif query.startswith('>='):
        return value >= int(query[2:])
    return value == int(query)


def compare_list(value: List, query: str):
    query = query.strip().lower()
    if query[0] == '!':
        parts = query[1:].split(",")
        for part in parts:
            if part.strip() in value:
                return False
        return True
    parts = query.split(",")
    for part in parts:
        if part.strip() not in value:
            return False
    return True


class SnapshotSearchQuery:
    def __init__(self):
        self.filters = []
        self.valid_app = None

    def satisfies(self, snapshot: Snapshot) -> bool:
        for i_filter in self.filters:
            if not i_filter(snapshot):
                return False
        return True

    def is_valid_app(self, app_name):
        if self.valid_app is None:
            return True
        return app_name == self.valid_app

    def set_valid_app(self, app_name):
        if app_name != 'All':
            self.valid_app = app_name
        return self

    def contains_node(self, attrs: List[str], queries: List[str]):
        def contains_node_satisfies(snapshot: Snapshot) -> bool:
            if snapshot is None or not snapshot.initial_layout or len(snapshot.nodes) == 0:
                return False
            for node in snapshot.nodes:
                is_satisfied = True
                for (attr, query) in zip(attrs, queries):
                    if not query:
                        continue  # TODO
                    if attr == 'text':
                        is_satisfied = is_satisfied and compare_string(node.text, query)
                    elif attr == 'content_desc':
                        is_satisfied = is_satisfied and compare_string(node.content_desc, query)
                    elif attr == 'class_name':
                        is_satisfied = is_satisfied and compare_string(node.class_name, query)
                    elif attr == 'resource_id':
                        is_satisfied = is_satisfied and compare_string(node.resource_id, query)
                    elif attr == 'clickable':
                        is_satisfied = is_satisfied and compare_bool(node.clickable, query)
                    elif attr == 'checkable':
                        is_satisfied = is_satisfied and compare_bool(node.checkable, query)
                    elif attr == 'visible':
                        is_satisfied = is_satisfied and compare_bool(node.visible, query)
                    elif attr == 'enabled':
                        is_satisfied = is_satisfied and compare_bool(node.enabled, query)
                    elif attr == 'clickable_span':
                        is_satisfied = is_satisfied and compare_bool(node.clickable_span, query)
                    elif attr == 'invalid':
                        is_satisfied = is_satisfied and compare_bool(node.invalid, query)
                    elif attr == 'context_clickable':
                        is_satisfied = is_satisfied and compare_bool(node.context_clickable, query)
                    elif attr == 'long_clickable':
                        is_satisfied = is_satisfied and compare_bool(node.long_clickable, query)
                    elif attr == 'important_for_accessibility':
                        is_satisfied = is_satisfied and compare_bool(node.important_for_accessibility, query)
                    elif attr == 'a11y_actions':
                        is_satisfied = is_satisfied and compare_list(node.a11y_actions, query)
                    elif attr == 'area':
                        is_satisfied = is_satisfied and compare_int(node.area(), query)
                    elif attr == 'width':
                        is_satisfied = is_satisfied and compare_int(node.bounds[2]-node.bounds[0], query)
                    elif attr == 'height':
                        is_satisfied = is_satisfied and compare_int(node.bounds[3]-node.bounds[1], query)

                    if not is_satisfied:
                        break
                if is_satisfied:
                    return True
            return False

        if len(attrs) == len(queries):
            self.filters.append(contains_node_satisfies)
        return self


class SnapshotSearchManager:
    def __init__(self, result_path: Path):
        self.result_path = result_path

    def search(self,
               search_query: SnapshotSearchQuery,
               snapshot_limit: int = 10000,
               ) -> List[Snapshot]:
        results = []
        for app_path in self.result_path.iterdir():
            if len(results) >= snapshot_limit:
                break
            if not app_path.is_dir():
                continue
            if not search_query.is_valid_app(app_path.name):
                continue
            for snapshot_path in app_path.iterdir():
                if len(results) >= snapshot_limit:
                    break
                if not snapshot_path.is_dir():
                    continue
                address_book = AddressBook(snapshot_path)
                try:
                    snapshot = Snapshot(address_book)
                    asyncio.run(snapshot.setup())
                    if search_query.satisfies(snapshot):
                        results.append(snapshot)
                except Exception as e:
                    logger.error(f"Error in SnapshotSearch for snapshot {address_book.snapshot_result_path}: {e}")
        return results
