import os
import copy
import time
import datetime
from git import Repo, exc
from opensearchpy import helpers
from loguru import logger
from oss_know.libs.github.init_gits import init_sync_git_datas
from oss_know.libs.util.base import get_opensearch_client
from oss_know.libs.base_dict.opensearch_index import OPENSEARCH_INDEX_CHECK_SYNC_DATA, OPENSEARCH_GIT_RAW
from oss_know.libs.util.opensearch_api import OpensearchAPI


def timestamp_to_utc(timestamp):
    # 10位时间戳
    return datetime.datetime.utcfromtimestamp(int(timestamp)).strftime("%Y-%m-%dT%H:%M:%SZ")


def sync_git_datas(git_url, owner, repo, proxy_config, opensearch_conn_datas, git_save_local_path=None):
    repo_path = f'{git_save_local_path["PATH"]}/{owner}/{repo}'
    check_point_timestamp = int(datetime.datetime.now().timestamp() * 1000)
    git_repo = None
    before_pull = []
    after_pull = []
    # 先获取客户端
    opensearch_client = get_opensearch_client(opensearch_conn_infos=opensearch_conn_datas)
    try:
        # 判断opensearch里有没有这个git库
        if_owner_exist = opensearch_client.search(index='gits', body={
            "query": {
                "bool": {
                    "must": [
                        {"term": {
                            "search_key.owner.keyword": {
                                "value": owner
                            }
                        }},
                        {"term": {
                            "search_key.repo.keyword": {
                                "value": repo
                            }
                        }}
                    ]
                }
            }
        })
        if if_owner_exist['hits']['hits']:
            # 先判断本地有没有git库 如果没有就克隆 如果有就pull
            logger.info("opensearch中存在该项目的git 提交信息")
            # 如果本地有这个库
            if os.path.exists(repo_path):
                logger.info("本地存在该项目的源码仓库    ------进行新代码的拉取")
                git_repo = Repo(repo_path)
                pull_response = git_repo.git.pull()
                logger.info(f'git pull 之后的返回结果:{pull_response}')
            # 如果本地没有这个库就重新clone
            else:
                logger.info("本地不存在该项目的源码仓库   ------进行该项目仓的克隆")
                git_repo = Repo.clone_from(url=git_url, to_path=repo_path)
            for commit in git_repo.iter_commits():
                after_pull.append(commit.hexsha)

            # opensearch里拥有这个库
            # 将这个库的hash值抽取出来
            hexshas = helpers.scan(client=opensearch_client, index='gits', query={
                "query": {
                    "bool": {
                        "must": [
                            {"term": {
                                "search_key.owner.keyword": {
                                    "value": owner
                                }
                            }},
                            {"term": {
                                "search_key.repo.keyword": {
                                    "value": repo
                                }
                            }}
                        ]
                    }
                }
                , "_source": "raw_data.hexsha"
            }, timeout='10m')
            for hexsha in hexshas:
                # print(hexsha)
                # return
                before_pull.append(hexsha['_source']['raw_data']['hexsha'])
        else:
            logger.warning("opensearch 中不存在该项目的git提交记录 ------进行init该项目项目的git提交记录获取")
            # 在这个位置调用init
            init_sync_git_datas(git_url=git_url,
                                owner=owner,
                                repo=repo,
                                proxy_config=proxy_config,
                                opensearch_conn_datas=opensearch_conn_datas,
                                git_save_local_path=git_save_local_path)
            return

    #     # 判断有没有这个仓库
    #     if os.path.exists(repo_path):
    #         git_repo = Repo(repo_path)
    #
    #         for commit in git_repo.iter_commits():
    #             before_pull.append(commit.hexsha)
    #         # 如果本地已经有之前克隆的项目，执行pull
    #         logger.info(f'在git pull之前的commit数量:{len(before_pull)}')
    #         pull_response = git_repo.git.pull()
    #         logger.info(f'git pull 之后的返回结果:{pull_response}')
    #         for commit in git_repo.iter_commits():
    #             after_pull.append(commit.hexsha)
    #         logger.info(f'在git pull之后的commit数量:{len(after_pull)}')
    #
    #     else:
    #         logger.warning("This project does not exist in this file directory. Attempting to clone this project")
    #         # 在这个位置调用init
    #         init_sync_git_datas(git_url=git_url,
    #                             owner=owner,
    #                             repo=repo,
    #                             proxy_config=proxy_config,
    #                             opensearch_conn_datas=opensearch_conn_datas,
    #                             git_save_local_path=git_save_local_path)
    #         return
    except exc.InvalidGitRepositoryError as a:
        logger.error("InvalidGitRepositoryError ：This directory may not a GitRepository")
        return

    # 从数据中获取上次的更新位置

    diff_commits = (set(before_pull) ^ set(after_pull))
    before_pull.clear()
    after_pull.clear()
    if not diff_commits:
        logger.info(f"这个仓库pull后没有发现新的commit")
    else:
        all_git_list = []
        now_count = 0
        opensearch_api = OpensearchAPI()
        logger.info(f"新更新的commit的hash值{diff_commits}")
        for diff_commit in diff_commits:
            commit_data = {"_index": OPENSEARCH_GIT_RAW,
                           "_source": {
                               "search_key": {
                                   "owner": owner,
                                   "repo": repo,
                                   "origin": f"https://github.com/{owner}/{repo}.git",
                                   'updated_at': 0,
                                   'if_sync': 1
                               },
                               "raw_data": {
                                   "message": "",
                                   "hexsha": "",
                                   "parents": "",
                                   "author_tz": "",
                                   "committer_tz": "",
                                   "author_name": "",
                                   "author_email": "",
                                   "committer_name": "",
                                   "committer_email": "",
                                   "authored_date": "",
                                   "authored_timestamp": "",
                                   "committed_date": "",
                                   "committed_timestamp": "",
                                   "files": "",
                                   "total": "",
                                   "if_merged": False
                               }
                           }}
            commit = git_repo.commit(diff_commit)
            files = commit.stats.files
            files_list = []
            for file in files:
                file_dict = files[file]
                file_dict["file_name"] = file
                files_list.append(file_dict)
            commit_data["_source"]["search_key"]["updated_at"] = check_point_timestamp
            commit_data["_source"]["raw_data"]["message"] = commit.message
            commit_data["_source"]["raw_data"]["hexsha"] = commit.hexsha
            commit_data["_source"]["raw_data"]["type"] = commit.type
            commit_data["_source"]["raw_data"]["parents"] = [i.hexsha for i in commit.parents]
            commit_data["_source"]["raw_data"]["author_tz"] = -int(commit.author_tz_offset / 3600)
            commit_data["_source"]["raw_data"]["committer_tz"] = -int(commit.committer_tz_offset / 3600)
            commit_data["_source"]["raw_data"]["author_name"] = commit.author.name
            commit_data["_source"]["raw_data"]["author_email"] = commit.author.email
            commit_data["_source"]["raw_data"]["committer_name"] = commit.committer.name
            commit_data["_source"]["raw_data"]["committer_email"] = commit.committer.email
            commit_data["_source"]["raw_data"]["authored_date"] = timestamp_to_utc(commit.authored_datetime.timestamp())
            commit_data["_source"]["raw_data"]["authored_timestamp"] = commit.authored_date
            commit_data["_source"]["raw_data"]["committed_date"] = timestamp_to_utc(
                commit.committed_datetime.timestamp())
            commit_data["_source"]["raw_data"]["committed_timestamp"] = commit.committed_date
            commit_data["_source"]["raw_data"]["files"] = files_list
            commit_data["_source"]["raw_data"]["total"] = commit.stats.total
            if_merged = False
            if len(commit_data["_source"]["raw_data"]["parents"]) == 2:
                if_merged = True
            commit_data["_source"]["raw_data"]["if_merged"] = if_merged
            now_count = now_count + 1
            all_git_list.append(commit_data)
            if now_count % 500 == 0:
                success, failed = opensearch_api.do_opensearch_bulk(opensearch_client=opensearch_client,
                                                                    bulk_all_data=all_git_list,
                                                                    owner=owner,
                                                                    repo=repo)
                logger.info(f"sync_bulk_git_datas::success:{success},failed:{failed}")
                logger.info(f"count:{now_count}::{owner}/{repo}::commit.hexsha:{commit.hexsha}")
                all_git_list.clear()
        success, failed = opensearch_api.do_opensearch_bulk(opensearch_client=opensearch_client,
                                                            bulk_all_data=all_git_list,
                                                            owner=owner,
                                                            repo=repo)
        logger.info(f"sync_bulk_git_datas::success:{success},failed:{failed}")
        logger.info(f"count:{now_count}::{owner}/{repo}::commit.hexsha:{commit.hexsha}")

        # 加入check_point点
        opensearch_api.set_sync_gits_check(opensearch_client=opensearch_client,
                                           owner=owner,
                                           repo=repo,
                                           check_point_timestamp=check_point_timestamp)
