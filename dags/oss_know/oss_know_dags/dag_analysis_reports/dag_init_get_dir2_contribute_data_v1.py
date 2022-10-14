# -*-coding:utf-8-*-
from datetime import datetime
from airflow import DAG
from airflow.operators.python import PythonOperator

# git_init_sync_v0.0.3
from oss_know.libs.analysis_report.init_get_dir2_contribute_data_v1 import get_dir2_contribute_data
from oss_know.libs.base_dict.variable_key import CLICKHOUSE_DRIVER_INFO

with DAG(
        dag_id='dag_init_get_dir2_contribute_data_v1',
        schedule_interval=None,
        start_date=datetime(2021, 1, 1),
        catchup=False,
        tags=['analysis'],
) as dag:
    def init_sync_get_dir2_contribute_data(ds, **kwargs):
        return 'Start init_sync_get_dir2_contribute_data'


    op_init_sync_get_dir2_contribute_data = PythonOperator(
        task_id='init_sync_git_info',
        python_callable=init_sync_get_dir2_contribute_data,
    )


    def do_sync_get_dir2_contribute_data(params):
        from airflow.models import Variable
        from oss_know.libs.github import init_gits
        project_line=params["project_line"]
        owner = params["owner"]
        repo = params["repo"]
        ck_conn_info = Variable.get(CLICKHOUSE_DRIVER_INFO, deserialize_json=True)
        get_dir2_contribute_data(project_info=params,ck_conn_info=ck_conn_info)

        return 'do_sync_get_dir2_contribute_data:::end'


    from airflow.models import Variable

    project_lines = Variable.get("project_lines", deserialize_json=True)
    for project_line in project_lines:
        project_line_name = project_line["project_line"]
        owner_repo_list = project_line["project_list"]
        for owner_repo in owner_repo_list:
            project_info = {"project_line": project_line_name,
                            "owner": owner_repo["owner"],
                            "repo": owner_repo["repo"]
                            }
            op_do_init_sync_get_dir2_contribute_data = PythonOperator(
                task_id=f'project_line_{project_line["project_line"]}__owner_{owner_repo["owner"]}__repo_{owner_repo["repo"]}',
                python_callable=do_sync_get_dir2_contribute_data,
                op_kwargs={'params': project_info},
            )
            op_init_sync_get_dir2_contribute_data >> op_do_init_sync_get_dir2_contribute_data
