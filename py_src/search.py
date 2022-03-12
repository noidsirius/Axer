import json
import logging
import subprocess
from collections import namedtuple, defaultdict
from functools import lru_cache
from pathlib import Path
from typing import Union, List
from results_utils import AddressBook
from post_analysis import get_post_analysis, SUCCESS, A11Y_WARNING, OTHER, INEFFECTIVE, \
    CRASHED, API_SMELL, EXTERNAL_SERVICE, LOADING, TB_WEBVIEW_LOADING, API_A11Y_ISSUE, TB_A11Y_ISSUE
from utils import convert_bounds


SearchActionResult = namedtuple('SearchActionResult', ['action', 'post_analysis'])
SearchSnapshotResult = namedtuple('SearchSnapshotResult', ['address_book', 'action_results'])


class SearchQuery:
    def __init__(self):
        self.filters = []
        self.valid_app = None

    def is_valid_app(self, app_name):
        if self.valid_app is None:
            return True
        return app_name == self.valid_app

    def set_valid_app(self, app_name):
        if app_name != 'All':
            self.valid_app = app_name
        return self

    def satisfies(self, action, action_post_analysis, address_book: AddressBook, is_sighted: bool) -> bool:
        for i_filter in self.filters:
            if not i_filter(action, action_post_analysis, address_book, is_sighted):
                return False
        logging.getLogger("F").error(f"!!!!!!!!!!!! -> {address_book.snapshot_result_path}")
        return True

    def contains_action_attr(self, attr_name: str, value: str):
        def action_attr_satisfies(action, post_analysis_results, address_book: AddressBook, is_sighted) -> bool:
            if attr_name not in action['element']:
                return False
            if value.lower() not in action['element'][attr_name].lower():
                return False
            return True
        if value and attr_name:
            self.filters.append(action_attr_satisfies)
        return self

    def contains_action_xml_attr(self, attr_name: str, value: str):
        def action_xml_attr_satisfies(action, post_analysis_results, address_book: AddressBook, is_sighted) -> bool:
            # TODO:
            action_attr_values = [action['element'][attr] for attr in ['bounds', 'resourceId', 'class']]
            prefix = "s_" if is_sighted else ""
            if 'node' in action and action['node']:
                if attr_name not in action['node']:
                    return False
                return value in action['node'][attr_name]
            layout_path = address_book.get_layout_path(f'{prefix}exp', action['index'], should_exists=True)
            if layout_path is None:
                return False
            with open(layout_path) as f:
                for line in f.readlines():
                    if all(v in line for v in action_attr_values) and attr_name in line:
                        attr_value = line.split(f'{attr_name}')[1].split('"')[1]
                        return value in attr_value
            return False

        if value and attr_name and value != 'Any':
            self.filters.append(action_xml_attr_satisfies)
        return self

    def contains_tags(self, include_tags: List[str], exclude_tags: List[str]):
        include_tags = [x for x in include_tags if x]
        exclude_tags = [x for x in exclude_tags if x]

        def tag_satisfies(action, post_analysis_results, address_book: AddressBook, is_sighted) -> bool:
            if not address_book.tags_path.exists():
                return len(exclude_tags) >= 0 and len(include_tags) == 0
            action_tags = []
            with open(address_book.tags_path, encoding="utf-8") as f:
                for line in f.readlines():
                    tag_info = json.loads(line)
                    if tag_info['index'] == action['index'] and tag_info['is_sighted'] == is_sighted:
                        action_tags.append(tag_info['tag'])

            for tag in include_tags:
                if tag not in action_tags:
                    return False

            for tag in action_tags:
                if tag in exclude_tags:
                    return False

            return True

        self.filters.append(tag_satisfies)
        return self

    def xml_search(self, select_mode: str, attrs: List[str], queries: List[str]):
        logging.getLogger("F").error(f"---> {select_mode}, {attrs}, {queries}")
        def xml_search_satisfies(action, post_analysis_results, address_book: AddressBook, is_sighted) -> bool:
            modes = ['exp', 'tb', 'reg', 'areg']
            if select_mode in modes:
                modes = [select_mode]
            prefix = "s_" if is_sighted else ''
            for mode in modes:
                if mode == 'exp' and is_sighted:
                    layout_path = address_book.get_layout_path(mode=f"{prefix}{mode}",  index="INITIAL", should_exists=True)
                else:
                    layout_path = address_book.get_layout_path(mode=f"{prefix}{mode}",  index=action['index'], should_exists=True)
                if layout_path:
                    with open(layout_path, encoding="utf-8") as f:
                        for line in f.readlines():
                            line = line.lower()
                            flag = True
                            for (attr, query) in zip(attrs, queries):
                                if not query or len(query) == 0:
                                    continue
                                if attr == 'ALL':
                                    if query.lower() not in line:
                                        flag = False
                                        break
                                else:
                                    new_attr = attr.lower()
                                    if attr in ['width', 'height', 'area']:
                                        new_attr = 'bounds'
                                    # TODO: Should be removed eventually
                                    if attr == 'actionList' and 'z-a11y-actions' in line:
                                        new_attr = 'z-a11y-actions'
                                    if f'{new_attr}="' not in line \
                                            or line[line.index(f'{new_attr}="')-1] not in [' ', '<']:
                                        flag = False
                                        break
                                    value = line[line.index(f'{new_attr}="'):].split('"')[1]
                                    if new_attr == "bounds":
                                        bounds = convert_bounds(value)
                                        target = 0
                                        if attr == 'area':
                                            target = (bounds[2]-bounds[0]) * (bounds[3]-bounds[1])
                                        elif attr == 'width':
                                            target = (bounds[2]-bounds[0])
                                        elif attr == 'height':
                                            target = (bounds[3]-bounds[1])
                                        if query.startswith('<'):
                                            if target >= int(query[1:]):
                                                flag = False
                                                break
                                        elif query.startswith('>'):
                                            if target <= int(query[1:]):
                                                flag = False
                                                break
                                        else:
                                            if target != int(query):
                                                flag = False
                                                break
                                    elif attr == 'actionList':
                                        actions = set(value.split('-'))
                                        is_include = True
                                        if query.startswith("!"):
                                            is_include = False
                                            query = query[1:]
                                        query_set = set(query.split('-'))
                                        if is_include != query_set.issubset(actions):
                                            flag = False
                                            break
                                    else:
                                        if query == "~":  # The value should be empty
                                            if len(value) > 0:
                                                flag = False
                                                break
                                        else:
                                            is_include = True
                                            if query.startswith("!"):
                                                is_include = False
                                                query = query[1:]
                                            if is_include != (query.lower() in value):
                                                flag = False
                                                break
                            if flag:
                                return True
            return False
        if len(attrs) == len(queries) and any(queries):
            self.filters.append(xml_search_satisfies)
        return self

    def talkback_mode(self, tb_type: str):
        def talkback_mode_satisfies(action, post_analysis_results, address_book: AddressBook, is_sighted) -> bool:
            if tb_type == 'exp':
                return is_sighted is False
            elif tb_type == 'sighted':
                return is_sighted is True
            return True
        self.filters.append(talkback_mode_satisfies)
        return self

    def post_analysis(self, post_analysis_result: str):
        def post_analysis_satisfies(action, post_analysis_results, address_book: AddressBook, is_sighted) -> bool:
            if post_analysis_result == 'PROCESSED':
                return len(post_analysis_results) > 0
            issue_status = [result['issue_status'] for result in post_analysis_results.values()]
            if post_analysis_result == 'ACCESSIBLE':
                return SUCCESS in issue_status
            elif post_analysis_result == 'TB_A11Y_ISSUE':
                return TB_A11Y_ISSUE in issue_status
            elif post_analysis_result == 'API_A11Y_ISSUE':
                return API_A11Y_ISSUE in issue_status
            elif post_analysis_result == 'A11Y_WARNING':
                return A11Y_WARNING in issue_status
            elif post_analysis_result == 'API_SMELL':
                return API_SMELL in issue_status
            elif post_analysis_result == 'EXTERNAL_SERVICE':
                return EXTERNAL_SERVICE in issue_status
            elif post_analysis_result == 'LOADING':
                return LOADING in issue_status
            elif post_analysis_result == 'INEFFECTIVE':
                return INEFFECTIVE in issue_status
            elif post_analysis_result == 'TB_WEBVIEW_LOADING':
                return TB_WEBVIEW_LOADING in issue_status
            elif post_analysis_result == 'CRASHED':
                return CRASHED in issue_status
            elif post_analysis_result == 'OTHER':
                return OTHER in issue_status # or not any(x in [SUCCESS, UNREACHABLE, DIFFERENT_BEHAVIOR, EXEC_FAILURE] for x in issue_status)
            return False
        if post_analysis_result != 'ANY':
            self.filters.append(post_analysis_satisfies)
        return self

    def executor_result(self, mode: str, result: str):
        def executor_result_satisfies(action, post_analysis_results, address_book: AddressBook, is_sighted) -> bool:
            executor_result = action.get(f'{mode}_action_result', ('FAILED',))[0]
            if executor_result not in ['FAILED', 'COMPLETED', 'TIMEOUT']:
                executor_result = 'FAILED'
            if executor_result != result:
                return False
            return True

        if result != 'ALL':
            self.filters.append(executor_result_satisfies)
        return self

    def compare_xml(self, first_mode: str, second_mode: str, should_be_same: bool):
        def has_same_xml_satisfies(action, post_analysis_results, address_book: AddressBook, is_sighted) -> bool:
            modes = ['exp', 'tb', 'reg', 'areg']
            if first_mode not in modes or second_mode not in modes:
                return True
            if len(post_analysis_results) == 0:
                return True
            key = f'{first_mode}_{second_mode}'
            for post_analysis_result in post_analysis_results.values():
                xml_similar_map = post_analysis_result.get('xml_similar_map', {})
                if key not in xml_similar_map:
                    continue
                if xml_similar_map[key] != should_be_same:
                    return False
            return True

        self.filters.append(has_same_xml_satisfies)
        return self

    def compare_screen(self, first_mode: str, second_mode: str, should_be_same: bool):
        def has_same_screen_satisfies(action, post_analysis_results, address_book: AddressBook, is_sighted) -> bool:
            modes = ['exp', 'tb', 'reg', 'areg']
            if first_mode not in modes or second_mode not in modes:
                return True
            prefix = 's_' if is_sighted else ''
            left_screen_path = address_book.get_screenshot_path(f"{prefix}{first_mode}", action['index'], should_exists=True)
            right_screen_path = address_book.get_screenshot_path(f"{prefix}{second_mode}", action['index'], should_exists=True)
            if left_screen_path is None or right_screen_path is None:
                return False
            cmd = f"diff --unified {left_screen_path} {right_screen_path}"
            diff_string = subprocess.run(cmd.split(), stdout=subprocess.PIPE).stdout.decode('utf-8')
            return (len(diff_string) == 0) == should_be_same

        self.filters.append(has_same_screen_satisfies)
        return self


class SearchManager:
    def __init__(self, result_path: Path):
        self.result_path = result_path

    def search(self,
               search_query: SearchQuery,
               snapshot_limit: int = 10000,
               action_limit: int = 10000,
               action_per_snapshot_limit: int = 1000,
               ) -> List[SearchSnapshotResult]:
        search_snapshot_result = []
        action_count = 0
        for app_path in self.result_path.iterdir():
            if action_count >= action_limit:
                break
            if not app_path.is_dir():
                continue
            if not search_query.is_valid_app(app_path.name):
                continue
            for snapshot_path in app_path.iterdir():
                if len(search_snapshot_result) >= snapshot_limit:
                    break
                if action_count >= action_limit:
                    break
                if not snapshot_path.is_dir():
                    continue
                search_action_result_list = []
                action_in_snapshot_count = 0
                address_book = AddressBook(snapshot_path)
                post_analysis_results = get_post_analysis(snapshot_path=snapshot_path)
                action_paths = [address_book.action_path, address_book.s_action_path]
                for action_path in action_paths:
                    if action_count >= action_limit or action_in_snapshot_count >= action_per_snapshot_limit:
                        break
                    is_sighted = "s_action" in action_path.name
                    if not action_path.exists():
                        continue
                    with open(action_path, encoding="utf-8") as f:
                        for line in f.readlines():
                            action = json.loads(line)
                            action_post_analysis = post_analysis_results['sighted' if is_sighted else 'unsighted'].get(action['index'], {})
                            if not search_query.satisfies(action, action_post_analysis, address_book, is_sighted):
                                continue
                            search_action_result = SearchActionResult(action=action,
                                                               post_analysis=action_post_analysis)
                            search_action_result_list.append(search_action_result)
                            action_in_snapshot_count += 1
                            action_count += 1
                            if action_count >= action_limit or action_in_snapshot_count >= action_per_snapshot_limit:
                                break
                search_snapshot_result.append(SearchSnapshotResult(address_book, search_action_result_list))
        return search_snapshot_result


@lru_cache(maxsize=None)
def get_search_manager(result_path: Union[str, Path]):
    """
    Given the result_path, creates and returns a SearchManager. The return value is cached
    """
    if isinstance(result_path, str):
        result_path = Path(result_path)
    return SearchManager(result_path)