import json
from collections import namedtuple
from functools import lru_cache
from pathlib import Path
from typing import Union, List
from results_utils import AddressBook
from post_analysis import get_post_analysis

SearchResult = namedtuple('SearchResult', ['action', 'post_analysis', 'address_book', 'is_sighted'])


class SearchManager:
    def __init__(self, result_path: Path):
        self.result_path = result_path

    def search(self,
               text: str,
               content_description: str,
               class_name: str,
               tb_type: str,
               has_post_analysis: bool = False,
               limit: int = 10
               ) -> List[SearchResult]:
        search_results = []
        for app_path in self.result_path.iterdir():
            if len(search_results) >= limit:
                break
            if not app_path.is_dir():
                continue
            for snapshot_path in app_path.iterdir():
                if len(search_results) >= limit:
                    break
                if not snapshot_path.is_dir():
                    continue
                address_book = AddressBook(snapshot_path)
                post_analysis_results = get_post_analysis(snapshot_path=snapshot_path)
                action_paths = [address_book.action_path, address_book.s_action_path]
                if tb_type == 'exp':
                    action_paths = [address_book.action_path]
                elif tb_type == 'sighted':
                    action_paths = [address_book.s_action_path]
                for action_path in action_paths:
                    is_sighted = "s_action" in action_path.name
                    post_analysis_result = post_analysis_results['sighted' if is_sighted else 'unsighted']
                    if has_post_analysis and len(post_analysis_result) == 0:
                        continue
                    with open(action_path) as f:
                        for line in f.readlines():
                            action = json.loads(line)
                            if text:
                                if text.lower() not in action['element']['text'].lower():
                                    continue
                            if content_description:
                                if content_description.lower() not in action['element']['contentDescription'].lower():
                                    continue
                            if class_name:
                                if class_name.lower() not in action['element']['class'].lower():
                                    continue
                            post_analysis = post_analysis_results['sighted' if is_sighted else 'unsighted'].get(action['index'], {})
                            search_result = SearchResult(action=action,
                                                         post_analysis=post_analysis,
                                                         address_book=address_book,
                                                         is_sighted=is_sighted)
                            search_results.append(search_result)
                            if len(search_results) >= limit:
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