import json
import boto3
from datetime import datetime, timezone
import requests
from decimal import Decimal, ROUND_HALF_UP
from botocore.exceptions import ClientError

# Initialize a DynamoDB client
dynamodb = boto3.resource('dynamodb')

class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super(DecimalEncoder, self).default(obj)

def fetch_and_filter_data(base_url, time_periods, page_size):
    page = 1
    operators = {}

    while True:
        url = f"{base_url}&page={page}&perPage={page_size}"
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()

        if not data["operators"]:
            break

        for op in data["operators"]:
            try:
                if int(op["validators_count"]) > 0:
                    for time_period in time_periods:
                        op["performance"][time_period] = Decimal(str(op["performance"].get(time_period, 0))) / Decimal(100)
                    operators[op["id"]] = op
            except Exception as e:
                print(f"Error processing operator {op['id']}: {e}")
                continue

        page += 1

    return operators

# Attempt to create a performance attribute or initialize it with an empty dict/map
# if it isn't already present.
def ensure_performance_attribute(table, operator_id, attribute_name):
    try:
        # ConditionExpression is re-checking existence prior to overwriting
        # with empty map, in case one was recently created.
        table.update_item(
            Key={'OperatorID': operator_id},
            UpdateExpression=f'SET {attribute_name} = :empty_map',
            ExpressionAttributeValues={':empty_map': {}},
            ConditionExpression="attribute_not_exists(attribute_name) OR NOT attribute_type(attribute_name, :type_map)"
        )
    except ClientError as e:
        print(f"Failed to check/initiate {attribute_name} for OperatorID={operator_id}: {e}")
        raise

def update_performance_data(operator_id, performance_data, name, validator_count, address, is_vo, is_private, table_name, overwrite):
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
                'isPrivate': bool(is_private, False),
                'Performance24h': {date_key: format_decimal(performance_data['24h'])},
                'Performance30d': {date_key: format_decimal(performance_data['30d'])}
            }
        )
    else:
        # If we don't see the performance attribute as a dict/map in the
        # record we just retrieved, then make the call to initialize it.
        # This should be a rare case, because this code correctly initializes, but
        # legacy code may not.
        if 'Performance24h' not in item or not isinstance(item['Performance24h'], dict):
            ensure_performance_attribute(table_name, operator_id, 'Performance24h')
        if 'Performance30d' not in item or not isinstance(item['Performance30d'], dict):
            ensure_performance_attribute(table_name, operator_id, 'Performance30d')

        update_expression = [
            'SET #n = :name',
            '#vc = :vc',
            '#addr = :address',
            '#vo = :isvo',
            '#private = :isprivate'
        ]

        expression_attribute_names = {
            "#dk": date_key
            "#n": "Name",
            "#vc": "ValidatorCount",
            "#addr": "Address",
            "#vo": "isVO",
            "#private": "isPrivate"
        }

        expression_attribute_values = {
            ":name": name,
            ":vc": validator_count,
            ":address": address,
            ":isvo": Decimal(is_vo),
            ":private": bool(is_private, False)
        }

        # Update the performance maps and set the values
        if overwrite:
            # If overwriting, set the performance data directly
            update_expression.append('Performance24h.#dk = :p24h')
            update_expression.append('Performance30d.#dk = :p30d')
        else:
            # If not overwriting, initialize the map and set the value if it doesn't exist
            update_expression.append('Performance24h.#dk = if_not_exists(Performance24h.#dk, :p24h)')
            update_expression.append('Performance30d.#dk = if_not_exists(Performance30d.#dk, :p30d)')

        update_expression_str = ', '.join(update_expression)

        try:
            response = table.update_item(
                Key={'OperatorID': operator_id},
                UpdateExpression=update_expression_str,
                ExpressionAttributeNames=expression_attribute_names,
                ExpressionAttributeValues=expression_attribute_values,
                ReturnValues="UPDATED_NEW"
            )
            return response
        except Exception as e:
            print(f"Error updating item: {str(e)}")

def lambda_handler(event, context):
    time_periods = event.get('time_periods', ['24h', '30d'])
    network = event.get('network', 'mainnet')
    table_name = event['table']
    page_size = event.get('page_size', 100)
    utc = event.get('utc', False)
    overwrite = event.get('overwrite', False)

    base_url = f"https://api.ssv.network/api/v4/{network}/operators/?validatorsCount=true"
    operators = fetch_and_filter_data(base_url, time_periods, page_size)

    if utc:
        target_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    else:
        target_date = datetime.now().strftime("%Y-%m-%d")

    for operator_id, operator in operators.items():
        performance_data = {time_period: operator["performance"][time_period] for time_period in time_periods}
        update_response = update_performance_data(
            operator_id,
            performance_data,
            operator.get("name", 'Unknown Name'),
            operator.get("validators_count", 0),
            operator.get("owner_address", ''),
            1 if operator.get("type", '') == "verified_operator" else 0,
            bool(operator.get("is_private", False)),
            table_name,
            overwrite
        )
        print("Updated operator:", operator_id, "Response:", json.dumps(update_response, indent=2, cls=DecimalEncoder))

    return {
        'statusCode': 200,
        'body': json.dumps('Successfully updated DynamoDB with the latest performance data.', cls=DecimalEncoder)
    }