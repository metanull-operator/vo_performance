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

    # Adjust here: Divide the performance data by 100 to convert it into a decimal format
    performance_data = {op["id"]: Decimal(str(op["performance"][time_period] / 100)) for op in filtered_operators}
    name_data = {op["id"]: op.get("name", '') for op in filtered_operators}
    validator_count_data = {op["id"]: op.get("validators_count", '') for op in filtered_operators}

    return performance_data, name_data, validator_count_data

def update_performance_data(operator_id, performance, table_name):
    performance_table = dynamodb.Table(table_name)
    date_key = datetime.now().strftime("%Y-%m-%d")

    response = performance_table.update_item(
        Key={'OperatorID': operator_id},
        UpdateExpression="SET #dk = :performance",
        ExpressionAttributeNames={"#dk": date_key},
        ExpressionAttributeValues={":performance": performance},  # Performance already adjusted
        ReturnValues="UPDATED_NEW"
    )
    return response

def update_operator_data(operator_id, name, validator_count, table_name):
    operator_table = dynamodb.Table(table_name)

    response = operator_table.update_item(
        Key={'OperatorID': operator_id},
        UpdateExpression="SET #n = :name, #vc = :vc, #isvo = :isvo",
        ExpressionAttributeNames={"#n": "Name", "#vc": "ValidatorCount", "#isvo": "isVO"},
        ExpressionAttributeValues={":name": name, ":vc": Decimal(str(validator_count)), ":isvo": Decimal('0')},
        ReturnValues="UPDATED_NEW"
    )
    return response

def lambda_handler(event, context):
    api_url = "https://api.ssv.network/api/v4/mainnet/operators/?page=1&perPage=1000&validatorsCount=true"
    time_period = '24h'

    performance_data, name_data, validator_count_data = fetch_and_filter_data(api_url, time_period)
    
    performance_table_name = 'ssvScanData'  # Table for performance data
    operator_table_name = 'testSSVPerformanceData'  # Table for remaining data
    
    for operator_id in performance_data:
        # Update performance data, divide by 100 for decimal format
        update_performance_response = update_performance_data(
            operator_id,
            performance_data[operator_id],
            performance_table_name
        )
        
        # Update operator data, including "isVO" attribute
        update_operator_response = update_operator_data(
            operator_id,
            name_data[operator_id],
            int(validator_count_data[operator_id]),
            operator_table_name
        )

        print(json.dumps(update_performance_response, indent=2, cls=DecimalEncoder))
        print(json.dumps(update_operator_response, indent=2, cls=DecimalEncoder))

    return {
        'statusCode': 200,
        'body': json.dumps('Successfully updated DynamoDB with the latest data.')
    }
