import json
import boto3
from datetime import datetime
import requests
from decimal import Decimal
from boto3.dynamodb.conditions import Key

# Initialize a DynamoDB client
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('SSVPerformanceData')

class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            if obj % 1 == 0:
                return int(obj)
            else:
                return float(obj) 
        return super(DecimalEncoder, self).default(obj)

def fetch_and_filter_data(url, time_periods):
    response = requests.get(url)
    response.raise_for_status()
    data = response.json()

    # Filter operators for IDs 1 through 1000 and validator_count >= 1
    filtered_operators = [
        op for op in data["operators"]
        if 1 <= op["id"] <= 1000 and op.get("validators_count", 0) >= 1
    ]

    # Store performance data for different time periods
    performance_data = {
        time_period: {
            op["id"]: (Decimal(op["performance"].get(time_period, 0)) / Decimal(100)).quantize(Decimal('0.000001'))
            for op in filtered_operators
        } for time_period in time_periods
    }
    name_data = {op["id"]: op.get("name", '') for op in filtered_operators}
    validator_count_data = {op["id"]: op.get("validators_count", '') for op in filtered_operators}
    address_data = {op["id"]: op.get("owner_address", '') for op in filtered_operators}
    type_data = {op["id"]: 1 if op.get("type", '') == "verified_operator" else 0 for op in filtered_operators}

    return performance_data, name_data, validator_count_data, address_data, type_data

def fetch_last_90_entries(operator_id, table):
    try:
        response = table.query(
            KeyConditionExpression=Key('OperatorID').eq(operator_id),
            ProjectionExpression="Performance24h",
            Limit=90
        )
        return response['Items']
    except Exception as e:
        print(f"Error fetching performance data for Operator ID {operator_id}: {str(e)}")
        return None

def calculate_90d_average(entries):
    if not entries or len(entries) < 90:
        return None
    total_performance = sum(Decimal(entry['Performance24h']) for entry in entries)
    return (total_performance / Decimal(90)).quantize(Decimal('0.000001'))

def update_dynamodb(operator_id, name, validator_count, performance_data, address, is_vo, performance_90d, table_name):
    table = dynamodb.Table(table_name)
    date_key = datetime.now().strftime("%Y-%m-%d")

    # Base update expression setup
    update_expression = "SET #n = :name, #vc = :vc, #p24.#dk = :performance24h, #p30.#dk = :performance30d, #addr = :address, #vo = :is_vo"
    expression_attribute_names = {
        "#n": "Name",
        "#vc": "ValidatorCount",
        "#p24": "Performance24h",
        "#p30": "Performance30d",
        "#dk": date_key,
        "#addr": "Address",
        "#vo": "isVO",
        "#p90": "Performance90d" 
    }
    expression_attribute_values = {
        ":name": name,
        ":vc": validator_count,
        ":performance24h": performance_data['24h'],
        ":performance30d": performance_data['30d'],
        ":address": address,
        ":is_vo": is_vo
    }

    if performance_90d is not None and performance_90d != 0:
        update_expression += ", #p90.#dk = :performance90d"
        expression_attribute_values[":performance90d"] = performance_90d
    else:
        # Remove the Performance90d attribute if it should not be stored
        update_expression += " REMOVE #p90"

    try:
        response = table.update_item(
            Key={'OperatorID': operator_id},
            UpdateExpression=update_expression,
            ExpressionAttributeNames=expression_attribute_names,
            ExpressionAttributeValues=expression_attribute_values,
            ReturnValues="UPDATED_NEW"
        )
        return response
    except Exception as e:
        print(f"Error updating item: {str(e)}")

def lambda_handler(event, context):
    api_url = "https://api.ssv.network/api/v4/mainnet/operators/?page=1&perPage=1000&validatorsCount=true"
    time_periods = ['24h', '30d']  

    performance_data, name_data, validator_count_data, address_data, type_data = fetch_and_filter_data(api_url, time_periods)
    table_name = 'SSVPerformanceData'

    for operator_id in performance_data['24h']:
        try:
            entries = fetch_last_90_entries(operator_id, table)
            performance_90d = calculate_90d_average(entries)

            update_response = update_dynamodb(
                operator_id,
                name_data[operator_id],
                int(validator_count_data[operator_id]),
                {'24h': performance_data['24h'][operator_id], '30d': performance_data['30d'][operator_id]},
                address_data[operator_id],
                type_data[operator_id],
                performance_90d,
                table_name
            )
            print(json.dumps(update_response, cls=DecimalEncoder, indent=2))
        except Exception as e:
            print(f"Error updating DynamoDB for Operator ID {operator_id}: {str(e)}")

    return {
        'statusCode': 200,
        'body': json.dumps('Successfully updated DynamoDB with the latest performance data.')
    }
