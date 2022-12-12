import datetime
import itertools
import random
import requests
import time

from opensearchpy import OpenSearch

from oss_know.libs.util.log import logger
from oss_know.libs.util.github_api import GithubAPI
from oss_know.libs.util.opensearch_api import OpensearchAPI
from oss_know.libs.base_dict.options import GITHUB_SLEEP_TIME_MIN, GITHUB_SLEEP_TIME_MAX


def init_github_commits(opensearch_conn_info, owner, repo,
                        token_proxy_accommodator, since=None, until=None):
    opensearch_client = OpenSearch(
        hosts=[{'host': opensearch_conn_info["HOST"], 'port': opensearch_conn_info["PORT"]}],
        http_compress=True,
        http_auth=(opensearch_conn_info["USER"], opensearch_conn_info["PASSWD"]),
        use_ssl=True,
        verify_certs=False,
        ssl_assert_hostname=False,
        ssl_show_warn=False
    )
    session = requests.Session()
    github_api = GithubAPI()
    opensearch_api = OpensearchAPI()

    if not until:
        until = datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ')
    if not since:
        since = "1980-01-01T00:00:00Z"

    for page in range(1, 99999):
        time.sleep(random.uniform(GITHUB_SLEEP_TIME_MIN, GITHUB_SLEEP_TIME_MAX))
        # 获取一页 github commits
        req = github_api.get_github_commits(http_session=session, token_proxy_accommodator=token_proxy_accommodator,
                                            owner=owner,
                                            repo=repo, page=page, since=since, until=until)
        one_page_github_commits = req.json()

        # 没有更多的 github commits 则跳出循环
        if (one_page_github_commits is not None) and len(one_page_github_commits) == 0:
            logger.info(f'get github commits end to break:: {owner}/{repo} page_index:{page}')
            break

        # 向opensearch插入一页 github commits
        opensearch_api.bulk_github_commits(opensearch_client=opensearch_client,
                                           github_commits=one_page_github_commits,
                                           owner=owner, repo=repo, if_sync=0)

        logger.info(f"success get github commits :: {owner}/{repo} page_index:{page}")

    opensearch_api.set_sync_github_commits_check(opensearch_client, owner, repo, since, until)

    return "END::init_github_commits"
