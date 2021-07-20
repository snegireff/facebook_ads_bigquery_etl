from google.cloud import bigquery
from google.cloud.exceptions import NotFound
from datetime import datetime, date, timedelta
import requests
import logging
import json
import base64
import time
from facebook_business.api import FacebookAdsApi
from facebook_business.adobjects.adaccount import AdAccount
from facebook_business.adobjects.adaccountuser import AdAccountUser
from facebook_business.adobjects.adsinsights import AdsInsights
from facebook_business.adobjects.campaign import Campaign
from facebook_business.adobjects.adreportrun import AdReportRun

logger = logging.getLogger()

schema_exchange_rate = [
    bigquery.SchemaField("date", "DATE", mode="REQUIRED"),
    bigquery.SchemaField("currencies", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("rate", "FLOAT", mode="REQUIRED")
]

schema_facebook_stat = [
    bigquery.SchemaField("date", "DATE", mode="REQUIRED"),
    bigquery.SchemaField("ad_id", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("ad_name", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("adset_id", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("adset_name", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("campaign_id", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("campaign_name", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("clicks", "INTEGER", mode="REQUIRED"),
    bigquery.SchemaField("impressions", "INTEGER", mode="REQUIRED"),
    bigquery.SchemaField("spend", "FLOAT", mode="REQUIRED"),
    bigquery.SchemaField('conversions', 'RECORD', mode='REPEATED',
                         fields=(bigquery.SchemaField('action_type', 'STRING'),
                                 bigquery.SchemaField('value', 'STRING'))),
    bigquery.SchemaField('actions', 'RECORD', mode='REPEATED',
                         fields=(bigquery.SchemaField('action_type', 'STRING'),
                                 bigquery.SchemaField('value', 'STRING')))

]

clustering_fields_facebook = ['campaign_id', 'campaign_name']


def exist_dataset_table(client, table_id, dataset_id, project_id, schema, clustering_fields=None):

    try:
        dataset_ref = "{}.{}".format(project_id, dataset_id)
        client.get_dataset(dataset_ref)  # Make an API request.

    except NotFound:
        dataset_ref = "{}.{}".format(project_id, dataset_id)
        dataset = bigquery.Dataset(dataset_ref)
        dataset.location = "US"
        dataset = client.create_dataset(dataset)  # Make an API request.
        logger.info("Created dataset {}.{}".format(
            client.project, dataset.dataset_id))

    try:
        table_ref = "{}.{}.{}".format(project_id, dataset_id, table_id)
        client.get_table(table_ref)  # Make an API request.

    except NotFound:

        table_ref = "{}.{}.{}".format(project_id, dataset_id, table_id)

        table = bigquery.Table(table_ref, schema=schema)

        table.time_partitioning = bigquery.TimePartitioning(
            type_=bigquery.TimePartitioningType.DAY,
            field="date"
        )

        if clustering_fields is not None:
            table.clustering_fields = clustering_fields

        table = client.create_table(table)  # Make an API request.
        logger.info("Created table {}.{}.{}".format(
            table.project, table.dataset_id, table.table_id))

    return 'ok'


def insert_rows_bq(client, table_id, dataset_id, project_id, data):

    table_ref = "{}.{}.{}".format(project_id, dataset_id, table_id)
    table = client.get_table(table_ref)

    resp = client.insert_rows_json(
        json_rows=data,
        table=table_ref,
    )

    logger.info("Success uploaded to table {}".format(table.table_id))


def get_facebook_data(event, context):

    pubsub_message = base64.b64decode(event['data']).decode('utf-8')
    bigquery_client = bigquery.Client()

    if 'date' in event['attributes']:
        yesterday = event['attributes']['date'].strftime('%Y-%m-%d')
    else:
        yesterday = date.today() - timedelta(1)

        table_id = event['attributes']['table_id']
        dataset_id = event['attributes']['dataset_id']
        project_id = event['attributes']['project_id']

        app_id = event['attributes']['app_id']
        app_secret = event['attributes']['app_secret']
        access_token = event['attributes']['access_token']
        account_id = event['attributes']['account_id']

    try:
        FacebookAdsApi.init(app_id, app_secret, access_token)

        account = AdAccount('act_'+str(account_id))
        args = dict(
            fields=[
                AdsInsights.Field.account_id,
                AdsInsights.Field.campaign_id,
                AdsInsights.Field.campaign_name,
                AdsInsights.Field.adset_name,
                AdsInsights.Field.adset_id,
                AdsInsights.Field.ad_name,
                AdsInsights.Field.ad_id,
                AdsInsights.Field.spend,
                AdsInsights.Field.impressions,
                AdsInsights.Field.clicks,
                AdsInsights.Field.actions,
                AdsInsights.Field.conversions
            ],
            params={
                'time_range': {
                    'since': yesterday.strftime("%Y-%m-%d"),
                    'until': yesterday.strftime("%Y-%m-%d"),
                },
                'level': 'ad',
                'time_increment': 1
            },
            is_async=True,
        )

        async_job = account.get_insights(**args)
        async_job.api_get()
        while async_job[AdReportRun.Field.async_status] != "Job Completed":
            time.sleep(5)
            async_job.api_get()

        time.sleep(5)
        resp_data = async_job.get_result()

    except Exception as e:
        logger.info(e)
        print(e)
        raise
    results = []

    for item in resp_data:
        data = dict(item)
        results.append(data)
    fb_source = []
    for item in results:

        actions = []
        conversions = []

        if 'actions' in item:
            for i, value in enumerate(item['actions']):
                actions.append(
                    {'action_type': value['action_type'], 'value': value['value']})

        if 'conversions' in item:
            for i, value in enumerate(item['conversions']):
                conversions.append(
                    {'action_type': value['action_type'], 'value': value['value']})

        fb_source.append({'date': item['date_start'],
                          'ad_id': item['ad_id'],
                          'ad_name': item['ad_name'],
                          'adset_id': item['adset_id'],
                          'adset_name': item['adset_name'],
                          'campaign_id': item['campaign_id'],
                          'campaign_name': item['campaign_name'],
                          'clicks': item['clicks'],
                          'impressions': item['impressions'],
                          'spend': item['spend'],
                          'conversions': conversions,
                          'actions': actions
                          })

        if exist_dataset_table(bigquery_client, table_id, dataset_id, project_id, schema_facebook_stat, clustering_fields_facebook) == 'ok':

            insert_rows_bq(bigquery_client, table_id,
                           dataset_id, project_id, fb_source)

            return 'ok'
