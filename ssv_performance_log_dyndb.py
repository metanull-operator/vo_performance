import requests
from datetime import datetime, timezone, timedelta
import argparse
import boto3
from botocore.exceptions import ClientError
from decimal import Decimal
import time

DAYS_LIMIT = 7
REQUESTS_PER_MINUTE = 10

# Set a delay between API requests (in seconds)
REQUEST_DELAY = 60 / REQUESTS_PER_MINUTE  # Delay in seconds between requests to space them out

def fetch_and_filter_data(base_url, time_period, page_size):
    page = 1
    operators = {}

    while True:
        url = f"{base_url}&page={page}&perPage={page_size}"
        print(f"Getting page {page} of results")
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()

        if not data["operators"]:
            break

        for op in data["operators"]:
            try:
                if int(op["validators_count"]) > 0:
                    op["performance"][time_period] = Decimal(str(op["performance"][time_period] / 100))
                operators[op["id"]] = op
            except Exception as e:
                print(f"Error processing operator {op['id']}: {e}")
                continue

        page += 1

        time.sleep(REQUEST_DELAY)

    return operators


def ensure_performance_attribute(table, operator_id, attribute_name):
    try:
        response = table.get_item(Key={'OperatorID': operator_id})
        item = response.get('Item', {})
        if attribute_name not in item:
            table.update_item(
                Key={'OperatorID': operator_id},
                UpdateExpression=f'SET {attribute_name} = :empty_map',
                ExpressionAttributeValues={':empty_map': {}}
            )
    except ClientError as e:
        print(f"Failed to check/initiate {attribute_name} for OperatorID={operator_id}: {e}")
        raise


def update_dynamodb_performance_data(table_name, operators, target_date, attribute_name, time_period, overwrite):
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table(table_name)

    for operator_id, operator in operators.items():
        print(f"Processing operator {operator_id}")

        performance = operator["performance"][time_period]

        is_vo = 1 if operator.get("type", "") == "verified_operator" else 0
        is_private = bool(operator.get("is_private", False))

        update_expression = [
            'SET #name = :name',
            'ValidatorCount = :validator_count',
            'isVO = :is_vo',
            'Address = :address',
            'isPrivate = :is_private',
            'last_updated = :last_updated'
        ]
        expression_attribute_values = {
            ':name': operator.get("name", ""),
            ':validator_count': operator.get("validators_count", 0),
            ':is_vo': is_vo,
            ':address': operator.get("owner_address", ""),
            ':is_private': is_private,
            ':last_updated': target_date
        }
        expression_attribute_names = {
            '#name': 'Name'
        }

        ensure_performance_attribute(table, operator_id, attribute_name)

        if overwrite:
            update_expression.append(f'{attribute_name}.#date = :performance')
            expression_attribute_names['#date'] = target_date
            expression_attribute_values[':performance'] = performance
        else:
            update_expression.append(f'{attribute_name}.#date = if_not_exists({attribute_name}.#date, :performance)')
            expression_attribute_names['#date'] = target_date
            expression_attribute_values[':performance'] = performance

        update_expression_str = ', '.join(update_expression)

        try:
            response = table.update_item(
                Key={'OperatorID': operator_id},
                UpdateExpression=update_expression_str,
                ExpressionAttributeNames=expression_attribute_names,
                ExpressionAttributeValues=expression_attribute_values,
                ConditionExpression='attribute_exists(OperatorID)'
            )
        except Exception as e:
            table.put_item(
                Item={
                    'OperatorID': operator_id,
                    'Name': operator.get("name", ""),
                    'ValidatorCount': operator.get("validators_count", 0),
                    'isVO': is_vo,
                    'Address': operator.get("owner_address", ""),
                    'isPrivate': is_private,
                    'last_updated': target_date,
                    attribute_name: {
                        target_date: performance
                    }
                }
            )


def cleanup_outdated_records(table_name):
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table(table_name)

    # Define the cutoff date
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=DAYS_LIMIT)
    cutoff_date_str = cutoff_date.strftime('%Y-%m-%d')

    print(f"Cutoff date: {cutoff_date_str}")

    try:
        outdated_items = []

        # Scan the table to get all items where last_updated exists and is older than the cutoff date
        response = table.scan(
            FilterExpression='last_updated < :cutoff_date',
            ExpressionAttributeValues={':cutoff_date': cutoff_date_str}
        )

        outdated_items.extend(response.get('Items', []))

        while 'LastEvaluatedKey' in response:
            response = table.scan(
                FilterExpression='last_updated < :cutoff_date',
                ExpressionAttributeValues={':cutoff_date': cutoff_date_str},
                ExclusiveStartKey=response['LastEvaluatedKey']  # Pagination key
            )
            outdated_items.extend(response['Items'])

        print(f"Found {len(outdated_items)} outdated items")  # Debugging: Log the number of items found

        for item in outdated_items:
            operator_id = item['OperatorID']
            print(f"Updating operator {operator_id} - last_updated = {item['last_updated']}")

            # Update ValidatorCount to 0 and set last_updated to the current date
            table.update_item(
                Key={'OperatorID': operator_id},
                UpdateExpression='SET ValidatorCount = :zero, last_updated = :last_updated',
                ExpressionAttributeValues={
                    ':zero': 0,
                    ':last_updated': datetime.now(timezone.utc).strftime('%Y-%m-%d')
                }
            )

    except ClientError as e:
        print(f"Failed to scan table and update outdated records: {e}")




def main():
    parser = argparse.ArgumentParser(description='Fetch and update operator performance data, bro.')
    parser.add_argument('-t', '--time_period', type=str, choices=['24h', '30d'], default='24h',
                        help='The reporting time period for performance data (24h or 30d).')
    parser.add_argument('-n', '--network', type=str, choices=['mainnet', 'goerli', 'holesky'], default='mainnet',
                        help='The SSV network to fetch data from (mainnet, goerli, or holesky).')
    parser.add_argument('--table', type=str, required=True,
                        help='The DynamoDB table to update, dude.')
    parser.add_argument('--attribute', type=str, required=True,
                        help='The attribute name in DynamoDB to update.')
    parser.add_argument('--page_size', type=int, default=100,
                        help='The number of items per page for API queries (default: 100).')
    parser.add_argument('--utc', action='store_true',
                        help='If set, use the current date in UTC for the target date.')
    parser.add_argument('--overwrite', action='store_true',
                        help='If set, overwrite existing performance data.')
    args = parser.parse_args()

    base_url = f"https://api.ssv.network/api/v4/{args.network}/operators/?validatorsCount=true"
    operators = fetch_and_filter_data(
        base_url, args.time_period, args.page_size
    )

    if args.utc:
        target_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    else:
        target_date = datetime.now().strftime("%Y-%m-%d")

    update_dynamodb_performance_data(args.table, operators, target_date, args.attribute, args.time_period, args.overwrite)

    cleanup_outdated_records(args.table)


if __name__ == "__main__":
    main()
