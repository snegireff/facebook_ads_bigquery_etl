# Facebook ads to google bigQuery ETL

One Paragraph of project description goes here

## Getting Started

These instructions will get you a copy of the project up and running on your local machine for development and testing purposes. See deployment for notes on how to deploy the project on a live system.

### Prerequisites

What things you need to install the software and how to install them

```bash
Give examples
```

### Installing

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
gcloud beta scheduler jobs create pubsub facebook --time-zone "Europe/Kiev" --schedule "0 5 * * *" --topic facebook_run --message-body "get_facebook_data" --attributes project_id=PROJECT_ID,dataset_id=DATASET_ID,table_id=TABLE_ID,account_id=ACCOUNT_ID,app_id=APP_ID,app_secret=APP_SECRET,access_token=ACCESS_TOKEN
```


Create scheduler for currency converter:

```bash
gcloud beta scheduler jobs create pubsub converter --time-zone "Europe/Kiev" --schedule "0 5 * * *" --topic facebook_run --message-body "get_currency" --attributes project_id=PROJECT_ID,dataset_id=DATASET_ID,table_id=TABLE_ID,api_key=API_KEY,from_currency=USD,to_currency=UAH
```



End with an example of getting some data out of the system or using it for a little demo



## Authors

* **Andrey Osipov**  

[web](https://web-analytics.me/)

[facebook](https://www.facebook.com/andrey.osipov)

[telegram group](https://t.me/firebase_app_web_bigquery)


## License

This project is licensed under the MIT License - see the [LICENSE.md](LICENSE.md) file for details
