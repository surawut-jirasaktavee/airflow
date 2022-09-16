from airflow import DAG
from airflow.operators.email import EmailOperator
from airflow.operators.dummy import DummyOperator
from airflow.operators.python import PythonOperator
from airflow.providers.postgres.operators.postgres import PostgresOperator
from airflow.utils import timezone

from datetime import timedelta

from etl import (
    _fetch_ohlcv,
    _download_file,
    _load_data_into_database,
)


default_args = {
    "owner": "prem",
    "email": ["premsurawut2021@gmail.com"],
    "start_date": timezone.datetime(2022, 1, 1, 0, 0, 0),
    "retries": 3,
    "retry_delay": timedelta(minutes=3),
}
with DAG(
    "cryptocurrency_data_pipeline",
    default_args=default_args,
    schedule_interval="@daily",
) as dag:

    fetch_ohlcv = PythonOperator(
        task_id="fetch_ohlcv",
        python_callable=_fetch_ohlcv,
    )

    download_file = PythonOperator(
        task_id="download_file",
        python_callable=_download_file,
    )

    create_import_table = PostgresOperator(
        task_id="create_import_table",
        postgres_conn_id="postgres",
        sql="""
            CREATE TABLE IF NOT EXISTS eth_import (
                timestamp BIGINT,
                open FLOAT,
                highest FLOAT,
                lowest FLOAT,
                closing FLOAT,
                volume FLOAT
            )
        """,
    )

    load_data_into_database = PythonOperator(
        task_id="load_data_into_database",
        python_callable=_load_data_into_database,
    )

    create_final_table = PostgresOperator(
        task_id="create_final_table",
        postgres_conn_id="postgres",
        sql="""
            CREATE TABLE IF NOT EXISTS eth (
                timestamp BIGINT PRIMARY KEY,
                open FLOAT,
                highest FLOAT,
                lowest FLOAT,
                closing FLOAT,
                volume FLOAT
            )
        """,
    )

    merge_import_into_final_table = PostgresOperator(
        task_id="merge_import_into_final_table",
        postgres_conn_id="postgres",
        sql="""
            INSERT INTO eth (
                timestamp,
                open,
                highest,
                lowest,
                closing,
                volume
            )
            SELECT
                timestamp,
                open,
                highest,
                lowest,
                closing,
                volume
            FROM
                eth_import
            ON CONFLICT (timestamp)
            DO UPDATE SET
                open = EXCLUDED.open,
                highest = EXCLUDED.highest,
                lowest = EXCLUDED.lowest,
                closing = EXCLUDED.closing,
                volume = EXCLUDED.volume
        """,
    )

    clear_import_table = PostgresOperator(
        task_id="clear_import_table",
        postgres_conn_id="postgres",
        sql="""
            DELETE FROM eth_import
        """,
    )
    notify = EmailOperator(
        task_id="notify",
        to=["premsurawut@gmail.com"],
        subject="Loaded data into database successfully on {{ ds }}",
        html_content="Your pipeline has loaded data into database successfully",
    )

    fetch_ohlcv >> download_file >> create_import_table >> load_data_into_database >> create_final_table >> merge_import_into_final_table >> clear_import_table >> notify