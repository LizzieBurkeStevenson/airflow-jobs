import datetime

from oss_know.libs.gh_archive import gh_archive

gha = gh_archive.GHArchive()

results = gha.get_hour(current_date=datetime.datetime(2022, 11, 27, 19))


def do_sync_transfer_gha_2ck(year_month_day_list):
    # from airflow.models import Variable
    # from oss_know.libs.gha.transfer_data_to_ck import parse_json_data
    for i in year_month_day_list:
        url = f"https://data.gharchive.org/{i}.json.gz"
        print(url)

    return "end do_transfer_gha_2ck"

with DAG(
        dag_id='sync_gha_transfer',
        schedule_interval=None,
        start_date=datetime(2021, 1, 1),
        catchup=False,
        tags=['gh_archive'],
        concurrency=6
) as dag:
    def init_clickhouse_transfer_data(ds, **kwargs):
        return 'Start init_gha_transfer2ck'



for result in results:
    date_array = result.split('-')
    year = date_array[0]
    month = date_array[1]
    day = date_array[2]
    do_sync_transfer_gha_2ck(results[result])

