# Facebook ads to google bigQuery ETL

ETL based on cloud function (google cloud) that retrieves data from the Facebook Insight API:

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

And Currency exchange rate from currencylayer.com.

ETL uploads this data to Google Bigquery every day.



## Getting Started

These instructions will get you a copy of the project up and running on your google cloud project for development and testing purposes.


### Installing

[Tutorial](https://medium.com/@snegir/writing-your-data-connector-from-facebook-ads-to-google-bigquery-670caeff8262?sk=ddd9d903a488864428b51f3e00423a40)

A step by step series of examples that tell you how to get a development env running

Create new pubsub topic:

```bash
gcloud pubsub topics create facebook_run
```

Publish cloud function:

```bash
gcloud functions deploy get_facebook_data --runtime python37 --trigger-topic facebook_run --timeout=540 --memory=1024MB
```

Create scheduler for facebook ads ETL:

PROJECT_ID = your google cloud PROJECT_ID
DATASET_ID = for example "facebook"
TABLE_ID = for example "fb_stat"
ACCOUNT_ID = your facebook account id without act_

APP_ID, APP_SECRET, APP_TOKEN = from apps developers.facebook.com

```bash
gcloud beta scheduler jobs create pubsub facebook --time-zone "Europe/Kiev" --schedule "0 5 * * *" --topic facebook_run --message-body "get_facebook" --attributes project_id=PROJECT_ID,dataset_id=DATASET_ID,table_id=TABLE_ID,account_id=ACCOUNT_ID,app_id=APP_ID,app_secret=APP_SECRET,access_token=ACCESS_TOKEN
```


Create scheduler for currency converter:

```bash
gcloud beta scheduler jobs create pubsub converter --time-zone "Europe/Kiev" --schedule "0 5 * * *" --topic facebook_run --message-body "get_currency" --attributes project_id=PROJECT_ID,dataset_id=DATASET_ID,table_id=TABLE_ID,api_key=API_KEY,from_currency=USD,to_currency=UAH
```


## Authors

* **Andrey Osipov**

* [web](https://web-analytics.me/)
* [facebook](https://www.facebook.com/andrey.osipov)
* [telegram group](https://t.me/firebase_app_web_bigquery)


## License

This project is licensed under the MIT License - see the [LICENSE.md](LICENSE.md) file for details
