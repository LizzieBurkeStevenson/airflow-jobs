import time
from datetime import datetime
from airflow import DAG
from airflow.operators.python import PythonOperator
from oss_know.libs.base_dict.variable_key import GITHUB_TOKENS, OPENSEARCH_CONN_DATA, NEED_SYNC_GITHUB_COMMITS_REPOS, \
    PROXY_CONFS
from oss_know.libs.util.proxy import KuaiProxyService, ProxyManager, GithubTokenProxyAccommodator
from oss_know.libs.util.token import TokenManager

# v0.0.1 初始化实现
# v0.0.2 增加set_github_init_commits_check_data 用于设置初始化后更新的point data

with DAG(
        dag_id='github_sync_commits_v1',
        schedule_interval=None,
        start_date=datetime(2000, 1, 1),
        catchup=False,
        tags=['github'],
) as dag:
    def scheduler_sync_github_commit(ds, **kwargs):
        return 'End::scheduler_init_sync_github_commit'


    op_scheduler_sync_github_commit = PythonOperator(
        task_id='op_scheduler_sync_github_commit',
        python_callable=scheduler_sync_github_commit
    )


    def do_sync_github_commit(params):
        from airflow.models import Variable
        from oss_know.libs.github import sync_commits

        github_tokens = Variable.get(GITHUB_TOKENS, deserialize_json=True)
        proxy_confs = Variable.get(PROXY_CONFS, deserialize_json=True)
        opensearch_conn_info = Variable.get(OPENSEARCH_CONN_DATA, deserialize_json=True)
        proxy_api_url = proxy_confs["api_url"]
        proxy_order_id = proxy_confs["orderid"]
        proxy_reserved_proxies = proxy_confs["reserved_proxies"]
        proxies = []
        for proxy in proxy_reserved_proxies:
            proxies.append(f"http://{proxy}")
        proxy_service = KuaiProxyService(api_url=proxy_api_url,
                                         orderid=proxy_order_id)
        token_manager = TokenManager(tokens=github_tokens)
        proxy_manager = ProxyManager(proxies=proxies,
                                     proxy_service=proxy_service)
        proxy_accommodator = GithubTokenProxyAccommodator(token_manager=token_manager,
                                                          proxy_manager=proxy_manager,
                                                          shuffle=True,
                                                          policy=GithubTokenProxyAccommodator.POLICY_FIXED_MAP)
        owner = params["owner"]
        repo = params["repo"]

        do_init_sync_info = sync_commits.sync_github_commits(opensearch_conn_info=opensearch_conn_info,
                                                             owner=owner,
                                                             repo=repo,
                                                             token_proxy_accommodator=proxy_accommodator)
        return params


    need_do_inti_sync_ops = []

    from airflow.models import Variable

    need_sync_github_commits_list = Variable.get(NEED_SYNC_GITHUB_COMMITS_REPOS, deserialize_json=True)

    for now_need_sync_github_commits in need_sync_github_commits_list:
        op_do_sync_github_commit = PythonOperator(
            task_id='op_do_sync_github_commit_{owner}_{repo}'.format(
                owner=now_need_sync_github_commits["owner"],
                repo=now_need_sync_github_commits["repo"]),
            python_callable=do_sync_github_commit,
            op_kwargs={'params': now_need_sync_github_commits},
        )
        op_scheduler_sync_github_commit >> op_do_sync_github_commit
