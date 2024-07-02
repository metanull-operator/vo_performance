import requests
from datetime import datetime, timezone
import argparse
import boto3
from botocore.exceptions import ClientError
from decimal import Decimal

def fetch_and_filter_data(base_url, time_period, page_size):
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
                    op["performance"][time_period] = Decimal(str(op["performance"][time_period] / 100))
                    operators[op["id"]] = op
            except Exception as e:
                print(f"Error processing operator {op['id']}: {e}")
                continue

        page += 1

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
        performance = operator["performance"][time_period]

        is_vo = 1 if operator.get("type", "") == "verified_operator" else 0

        update_expression = [
            'SET #name = :name',
            'ValidatorCount = :validator_count',
            'isVO = :is_vo',
            'Address = :address'
        ]
        expression_attribute_values = {
            ':name': operator.get("name", ""),
            ':validator_count': operator.get("validators_count", 0),
            ':is_vo': is_vo,
            ':address': operator.get("owner_address", "")
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
                    attribute_name: {
                        target_date: performance
                    }
                }
            )


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


if __name__ == "__main__":
    main()
