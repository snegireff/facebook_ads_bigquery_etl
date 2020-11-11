from google.cloud import bigquery
from google.cloud.exceptions import NotFound
from datetime import datetime, date, timedelta
import requests
import logging
import json
import base64
from facebook_business.api import FacebookAdsApi
from facebook_business.adobjects.adaccount import AdAccount
from facebook_business.adobjects.adaccountuser import AdAccountUser
from facebook_business.adobjects.adsinsights import AdsInsights
from facebook_business.adobjects.campaign import Campaign

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
        logger.info("Created dataset {}.{}".format(client.project, dataset.dataset_id))

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
        logger.info("Created table {}.{}.{}".format(table.project, table.dataset_id, table.table_id))

    return 'ok'


def insert_rows_bq(client, table_id, dataset_id, project_id, data):

    table_ref = "{}.{}.{}".format(project_id, dataset_id, table_id)
    table = client.get_table(table_ref)

    resp = client.insert_rows_json(
        json_rows = data,
        table = table_ref,
    )

    logger.info("Success uploaded to table {}".format(table.table_id))


def get_facebook_data(event, context):

    pubsub_message = base64.b64decode(event['data']).decode('utf-8')
    bigquery_client = bigquery.Client()

    if 'date' in event['attributes']:
        yesterday = event['attributes']['date'].strftime('%Y-%m-%d')
    else:
        yesterday = date.today() - timedelta(1)

    if pubsub_message == 'get_currency':

        table_id = event['attributes']['table_id']
        dataset_id = event['attributes']['dataset_id']
        project_id = event['attributes']['project_id']

        api_key = event['attributes']['api_key']
        from_currency = event['attributes']['from_currency']
        to_currency = event['attributes']['to_currency']
        source = from_currency+to_currency

        cur_source = []

        params = {'access_key': api_key,
                   'currencies': to_currency,
                   'source': from_currency,
                   'date': yesterday.strftime("%Y-%m-%d")
                  }

        url = 'http://api.currencylayer.com/historical'


        try:
            r = requests.get(url, params=params)
        except requests.exceptions.RequestException as e:
            logger.error('request to currencylayer error: {}').format(e)
            return e

        if r.json()["success"] is True:

            exist_dataset_table(bigquery_client, table_id, dataset_id, project_id, schema_exchange_rate)

            cur_source.append({'date': yesterday.strftime("%Y-%m-%d"),
                               'currencies' : source,
                               'rate' : r.json()['quotes'][source]
            })

            insert_rows_bq(bigquery_client, table_id, dataset_id, project_id, cur_source)
        else:
            logger.error('request to currencylayer error: {}').format(r.json()['error']['info'])

        return 'ok'

    elif pubsub_message == 'get_facebook':

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
            insights = account.get_insights(fields=[
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
            ], params={
                'level': 'ad',
                'time_range': {
                    'since':  yesterday.strftime("%Y-%m-%d"),
                    'until': yesterday.strftime("%Y-%m-%d")
                },'time_increment': 1
            })

        except Exception as e:
                logger.info(e)
                print(e)
                raise

        fb_source = []

        for index, item in enumerate(insights):

            actions = []
            conversions = []

            if 'actions' in item:
                for i, value in enumerate(item['actions']):
                    actions.append({'action_type' : value['action_type'], 'value': value['value']})

            if 'conversions' in item:
                for i, value in enumerate(item['conversions']):
                    conversions.append({'action_type' : value['action_type'], 'value': value['value']})


            fb_source.append({'date': item['date_start'],
                               'ad_id' : item['ad_id'],
                               'ad_name' : item['ad_name'],
                               'adset_id' : item['adset_id'],
                               'adset_name' : item['adset_name'],
                               'campaign_id' : item['campaign_id'],
                               'campaign_name' : item['campaign_name'],
                               'clicks' : item['clicks'],
                               'impressions' : item['impressions'],
                               'spend' : item['spend'] ,
                               'conversions' : conversions,
                               'actions' : actions
                            })


        if exist_dataset_table(bigquery_client, table_id, dataset_id, project_id, schema_facebook_stat, clustering_fields_facebook) == 'ok':

            insert_rows_bq(bigquery_client, table_id, dataset_id, project_id, fb_source)

            return 'ok'
