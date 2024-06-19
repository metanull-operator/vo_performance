import json
import boto3
from datetime import datetime
import requests
from decimal import Decimal, ROUND_HALF_UP

# Initialize a DynamoDB client
dynamodb = boto3.resource('dynamodb')

class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super(DecimalEncoder, self).default(obj)

def fetch_and_filter_data(url, time_periods):
    response = requests.get(url)
    response.raise_for_status()
    data = response.json()

    filtered_operators = [
        op for op in data["operators"]
        if 1 <= op["id"] <= 1000 and op.get("validators_count", 0) >= 1
    ]

    performance_data = {
        time_period: {
            op["id"]: Decimal(str(op["performance"].get(time_period, 0))) / Decimal(100)
            for op in filtered_operators
        } for time_period in time_periods
    }
    name_data = {op["id"]: op.get("name", 'Unknown Name') for op in filtered_operators}
    validator_count_data = {op["id"]: op.get("validators_count", 0) for op in filtered_operators}
    address_data = {op["id"]: op.get("owner_address", '') for op in filtered_operators}
    type_data = {op["id"]: 1 if op.get("type", '') == "verified_operator" else 0 for op in filtered_operators}

    return performance_data, name_data, validator_count_data, address_data, type_data

def update_performance_data(operator_id, performance_data, name, validator_count, address, is_vo, table_name):
    table = dynamodb.Table(table_name)
    date_key = datetime.now().strftime("%Y-%m-%d")

    def format_decimal(value):
        return Decimal(value).quantize(Decimal('.000001'), rounding=ROUND_HALF_UP)

    existing_item_response = table.get_item(Key={'OperatorID': operator_id})
    item_exists = 'Item' in existing_item_response

    if not item_exists:
        # Initialize the performance maps if not existing
        table.put_item(
            Item={
                'OperatorID': operator_id,
                'Name': name,
                'ValidatorCount': validator_count,
                'Address': address,
                'isVO': Decimal(is_vo),
                'Performance24h': {date_key: format_decimal(performance_data['24h'])},
                'Performance30d': {date_key: format_decimal(performance_data['30d'])}
            }
        )
    else:
        # Update the performance maps if they already exist
        response = table.update_item(
            Key={'OperatorID': operator_id},
            UpdateExpression="SET Performance24h.#dk = :p24h, Performance30d.#dk = :p30d, #n = :name, #vc = :vc, #addr = :address, #vo = :isvo",
            ExpressionAttributeNames={
                "#dk": date_key,
                "#n": "Name",
                "#vc": "ValidatorCount",
                "#addr": "Address",
                "#vo": "isVO"
            },
            ExpressionAttributeValues={
                ":p24h": format_decimal(performance_data['24h']),
                ":p30d": format_decimal(performance_data['30d']),
                ":name": name,
                ":vc": validator_count,
                ":address": address,
                ":isvo": is_vo
            },
            ReturnValues="UPDATED_NEW"
        )
        return response

def lambda_handler(event, context):
    api_url = "https://api.ssv.network/api/v4/mainnet/operators/?page=1&perPage=1000&validatorsCount=true"
    time_periods = ['24h', '30d']

    performance_data, name_data, validator_count_data, address_data, type_data = fetch_and_filter_data(api_url, time_periods)
    table_name = 'SSVPerformanceData'

    for operator_id in performance_data['24h'].keys():
        response = update_performance_data(
            operator_id,
            {'24h': performance_data['24h'][operator_id], '30d': performance_data['30d'][operator_id]},
            name_data[operator_id],
            validator_count_data[operator_id],
            address_data[operator_id],
            type_data[operator_id],
            table_name
        )
        print("Updated operator:", operator_id, "Response:", json.dumps(response, indent=2, cls=DecimalEncoder))

    return {
        'statusCode': 200,
        'body': json.dumps('Successfully updated DynamoDB with the latest performance data.', cls=DecimalEncoder)
    }
