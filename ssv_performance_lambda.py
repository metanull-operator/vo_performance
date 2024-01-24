import json
import boto3
from datetime import datetime
import requests
from decimal import Decimal

# Initialize a DynamoDB client
dynamodb = boto3.resource('dynamodb')

class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super(DecimalEncoder, self).default(obj)

def fetch_and_filter_data(url, time_period):
    response = requests.get(url)
    response.raise_for_status()
    data = response.json()

    # Filter operators for IDs 1 through 300 and validator_count >= 1
    filtered_operators = [op for op in data["operators"] if 1 <= op["id"] <= 300 and op.get("validators_count", 0) >= 1]

    performance_data = {op["id"]: "{:.2%}".format(op["performance"][time_period] / 100) for op in filtered_operators}
    name_data = {op["id"]: op.get("name", '') for op in filtered_operators}
    validator_count_data = {op["id"]: op.get("validators_count", '') for op in filtered_operators}

    return performance_data, name_data, validator_count_data


def update_dynamodb(operator_id, name, validator_count, performance, table_name):
    table = dynamodb.Table(table_name)
    date_key = datetime.now().strftime("%Y-%m-%d")

    # Ensure that the Performance24h map exists.
    table.update_item(
        Key={'OperatorID': operator_id},
        UpdateExpression="SET #p24 = if_not_exists(#p24, :empty_map)",
        ExpressionAttributeNames={"#p24": "Performance24h"},
        ExpressionAttributeValues={":empty_map": {}}
    )

    # Now update the specific performance data for the date.
    response = table.update_item(
        Key={'OperatorID': operator_id},
        UpdateExpression="SET #n = :name, #vc = :vc, #p24.#dk = :performance",
        ExpressionAttributeNames={
            "#n": "Name",
            "#vc": "ValidatorCount",
            "#p24": "Performance24h",  # Change the attribute name here
            "#dk": date_key
        },
        ExpressionAttributeValues={
            ":name": name,
            ":vc": validator_count,
            ":performance": performance
        },
        ReturnValues="UPDATED_NEW"
    )
    return response


def lambda_handler(event, context):
    api_url = "https://api.ssv.network/api/v4/mainnet/operators/?page=1&perPage=1000&validatorsCount=true"
    time_period = '24h'  # Fixed time period for demonstration

    performance_data, name_data, validator_count_data = fetch_and_filter_data(api_url, time_period)
    table_name = 'SSVPerformanceData'
    
    for operator_id in performance_data:
        update_response = update_dynamodb(
            operator_id,
            name_data[operator_id],
            int(validator_count_data[operator_id]),
            performance_data[operator_id],
            table_name
        )
        print(json.dumps(update_response, indent=2, cls=DecimalEncoder))

    return {
        'statusCode': 200,
        'body': json.dumps('Successfully updated DynamoDB with the latest performance data.')
    }
