import boto3
from common.config import *
from boto3.dynamodb.conditions import Attr, Key
from .storage_data_interface import DataStorageInterface


class DynamoDBStorage(DataStorageInterface):

    def __init__(self, **kwargs):
        self.dynamodb = boto3.resource('dynamodb')
        self.table = kwargs.get('table')


    # Returns dict of operator IDs to DynamoDB data for all operator IDs
    def get_performance_all(self):
        perf_data = {}

        daily_perf_data = self._load_performance_data()
        for row in daily_perf_data:
            perf_data[row[FIELD_OPERATOR_ID]] = row

        return perf_data


    # Returns dict of operator IDs to DynamoDB data for specified operator IDs
    def get_performance_by_opids(self, op_ids):
        perf_data = {}

        daily_perf_data = self._load_performance_data(op_ids)
        for row in daily_perf_data:
            perf_data[row[FIELD_OPERATOR_ID]] = row

        return perf_data

    def _load_performance_data(self, operator_ids=None):
        table = self.dynamodb.Table(self.table)
        op_ids = set(map(int, operator_ids)) if operator_ids else None
        data = []

        try:
            response = table.scan()
            while 'Items' in response:
                for item in response['Items']:
                    if op_ids and int(item[FIELD_OPERATOR_ID]) not in op_ids:
                        continue
                    data_points_24h = self._parse_performance_data(item, FIELD_PERF_DATA_24H)
                    data_points_30d = self._parse_performance_data(item, FIELD_PERF_DATA_30D)

                    validator_count_str = item.get(FIELD_VALIDATOR_COUNT, '0')
                    try:
                        validator_count = int(validator_count_str) if validator_count_str else 0
                    except ValueError:
                        validator_count = 0

                    data_row = {
                        FIELD_OPERATOR_ID: int(item[FIELD_OPERATOR_ID]),
                        FIELD_OPERATOR_NAME: item[FIELD_OPERATOR_NAME],
                        FIELD_IS_VO: bool(item.get(FIELD_IS_VO, False)),
                        FIELD_VALIDATOR_COUNT: validator_count,
                        FIELD_ADDRESS: item.get(FIELD_ADDRESS),
                        FIELD_PERF_DATA_24H: data_points_24h,
                        FIELD_PERF_DATA_30D: data_points_30d
                    }
                    data.append(data_row)

                if 'LastEvaluatedKey' in response:
                    response = table.scan(ExclusiveStartKey=response['LastEvaluatedKey'])
                else:
                    break

        except ClientError as e:
            logging.error(f"Failed to load performance data: {e}", exc_info=True)

        return data

    def _parse_performance_data(self, item, field):
        data_points = {}
        if field in item and isinstance(item[field], dict):
            for date, data_point in item[field].items():
                try:
                    if isinstance(data_point, str) and '%' in data_point:
                        data_points[date] = float(data_point.strip('%')) / 100
                    else:
                        data_points[date] = float(data_point)
                except ValueError:
                    data_points[date] = None
        return data_points


    # Incredibly inefficient way to get latest performance date,
    # and also not accurate if we are only checking 24h data.
    def get_latest_perf_data_date(self):
        perf_data = self._load_performance_data()
        if not perf_data:
            return None

        most_recent_date = None

        for row in perf_data:
            if FIELD_PERF_DATA_24H not in row:
                return None

            # So inefficient
            for date, data_point in row[FIELD_PERF_DATA_24H].items():
                if most_recent_date is None or date > most_recent_date:
                    most_recent_date = date

        return most_recent_date


    def get_subscriptions_by_type(self, subscription_type):

        table = self.dynamodb.Table(self.table)
        results = {}

        try:
            response = table.scan(
                FilterExpression=Attr('SubscriptionType').eq(subscription_type)
            )
            for subscription in response['Items']:
                if subscription['SubscriptionType'] != subscription_type:
                    continue
                op_id = int(subscription['OperatorID'])
                user_id = int(subscription['UserID'])
                if op_id not in results:
                    results[op_id] = {}
                results[op_id][user_id] = { subscription_type: True }

        except ClientError as e:
            logging.error(f"Failed to get subscriptions by type: {e}", exc_info=True)

        return results


    def get_subscriptions_by_userid(self, user_id):

        table = self.dynamodb.Table(self.table)
        results = {}

        try:
            response = table.query(
                KeyConditionExpression=Key('UserID').eq(str(user_id))
            )
            if response['Items']:
                for item in response['Items']:
                    op_id = int(item['OperatorID'])
                    if op_id not in results:
                        results[op_id] = {}
                    if user_id not in results[op_id]:
                        results[op_id][user_id] = {}
                    results[op_id][user_id][item['SubscriptionType']] = True

        except ClientError as e:
            logging.error(f"Failed to get subscriptions by user ID: {e}", exc_info=True)
        return results

    def add_user_subscription(self, user_id, op_id, subscription_type):

        table = self.dynamodb.Table(self.table)
        sort_key = f"{subscription_type}#{op_id}"

        try:
            response = table.put_item(
                Item={
                    'UserID': str(user_id),
                    'OperatorID': op_id,
                    'SubscriptionType': subscription_type,
                    'SubscriptionInfo': sort_key
                }
            )
            return response

        except ClientError as e:
            logging.error(f"Failed to add user subscription: {e}", exc_info=True)
            return None

    def del_user_subscription(self, user_id, op_id, subscription_type):


        table = self.dynamodb.Table(self.table)
        sort_key = f"{subscription_type}#{op_id}"

        try:
            response = table.delete_item(
                Key={
                    'UserID': str(user_id),
                    'SubscriptionInfo': sort_key
                }
            )
            return response

        except self.dynamodb.meta.client.exceptions.ConditionalCheckFailedException as e:
            logging.error(f"Subscription not found for deletion: {e}")
            return None

        except ClientError as e:
            logging.error(f"Unexpected error deleting subscription: {e}", exc_info=True)
            return None