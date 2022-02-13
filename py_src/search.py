import json
from collections import namedtuple
from functools import lru_cache
from pathlib import Path
from typing import Union, List
from results_utils import AddressBook
from post_analysis import get_post_analysis

SearchResult = namedtuple('SearchResult', ['action', 'post_analysis', 'address_book', 'is_sighted'])


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
        return True

    def contains_text(self, text):
        def text_satisfies(action, post_analysis_results, address_book: AddressBook, is_sighted) -> bool:
            if text and text.lower() not in action['element']['text'].lower():
                return False
            return True
        self.filters.append(text_satisfies)
        return self

    def contains_content_description(self, content_description):
        def content_description_satisfies(action, post_analysis_results, address_book: AddressBook, is_sighted) -> bool:
            if content_description and content_description.lower() not in action['element']['contentDescription'].lower():
                return False
            return True
        self.filters.append(content_description_satisfies)
        return self

    def contains_class_name(self, class_name):
        def class_name_satisfies(action, post_analysis_results, address_book: AddressBook, is_sighted) -> bool:
            if class_name and class_name.lower() not in action['element']['class'].lower():
                return False
            return True
        self.filters.append(class_name_satisfies)
        return self

    def contains_resource_id(self, resource_id):
        def resource_id_satisfies(action, post_analysis_results, address_book: AddressBook, is_sighted) -> bool:
            if resource_id and resource_id.lower() not in action['element']['resourceId'].lower():
                return False
            return True
        self.filters.append(resource_id_satisfies)
        return self

    def contains_tags(self, include_tags: List[str], exclude_tags: List[str]):
        include_tags = [x for x in include_tags if x]
        exclude_tags = [x for x in exclude_tags if x]

        def tag_satisfies(action, post_analysis_results, address_book: AddressBook, is_sighted) -> bool:
            if not address_book.tags_path.exists():
                return len(exclude_tags) >= 0 and len(include_tags) == 0
            action_tags = []
            with open(address_book.tags_path) as f:
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

    def xml_search(self, select_mode: str, attr: str, query: str):
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
                    with open(layout_path) as f:
                        if attr == 'ALL':
                            if query.lower() in f.read().lower():
                                return True
                        else:
                            for line in f.readlines():
                                if attr in line:
                                    value = line[line.index(attr):].split('"')[1]
                                    if query in value:
                                        return True
            return False

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

    def post_analysis(self, only_post_analyzed: bool):
        def post_analysis_satisfies(action, post_analysis_results, address_book: AddressBook, is_sighted) -> bool:
            if only_post_analyzed:
                return len(post_analysis_results) > 0
            return True
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


class SearchManager:
    def __init__(self, result_path: Path):
        self.result_path = result_path

    def search(self,
               search_query: SearchQuery,
               limit: int = 10,
               limit_per_snapshot: int = 1000,
               ) -> List[SearchResult]:
        search_results = []
        for app_path in self.result_path.iterdir():
            if len(search_results) >= limit:
                break
            if not app_path.is_dir():
                continue
            if not search_query.is_valid_app(app_path.name):
                continue
            for snapshot_path in app_path.iterdir():
                if len(search_results) >= limit:
                    break
                if not snapshot_path.is_dir():
                    continue
                snapshot_result_count = 0
                address_book = AddressBook(snapshot_path)
                post_analysis_results = get_post_analysis(snapshot_path=snapshot_path)
                action_paths = [address_book.action_path, address_book.s_action_path]
                for action_path in action_paths:
                    if len(search_results) >= limit or snapshot_result_count >= limit_per_snapshot:
                        break
                    is_sighted = "s_action" in action_path.name
                    if not action_path.exists():
                        continue
                    with open(action_path) as f:
                        for line in f.readlines():
                            action = json.loads(line)
                            action_post_analysis = post_analysis_results['sighted' if is_sighted else 'unsighted'].get(action['index'], {})
                            if not search_query.satisfies(action, action_post_analysis, address_book, is_sighted):
                                continue
                            search_result = SearchResult(action=action,
                                                         post_analysis=action_post_analysis,
                                                         address_book=address_book,
                                                         is_sighted=is_sighted)
                            search_results.append(search_result)
                            snapshot_result_count += 1
                            if len(search_results) >= limit or snapshot_result_count >= limit_per_snapshot:
                                break
        return search_results


@lru_cache(maxsize=None)
def get_search_manager(result_path: Union[str, Path]):
    """
    Given the result_path, creates and returns a SearchManager. The return value is cached
    """
    if isinstance(result_path, str):
        result_path = Path(result_path)
    return SearchManager(result_path)