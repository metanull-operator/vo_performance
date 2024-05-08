import boto3
from decimal import Decimal

# Initialize DynamoDB resource
dynamodb = boto3.resource('dynamodb')

# Source and target table names
source_table_name = 'SourceTableName'  
target_table_name = 'TargetTableName' 

# Reference to the tables
source_table = dynamodb.Table(source_table_name)
target_table = dynamodb.Table(target_table_name)

def migrate_data():
    # Perform a scan on the source table to retrieve all items
    response = source_table.scan()
    items = response.get('Items', [])
    
    for item in items:
        operator_id = item.get('OperatorID')
        performance_map = item.get('Performance24h', {})
        
        # Prepare the item for insertion into the new table
        new_item = {'OperatorID': operator_id}
        for date, performance_str in performance_map.items():
            # Remove the '%' sign, convert to a decimal number, then divide by 100
            performance_value = Decimal(performance_str.rstrip('%')) / Decimal('100')
            new_item[date] = performance_value
        
        # Insert the new item into the target table
        target_table.put_item(Item=new_item)
        print(f'Migrated OperatorID {operator_id} with performance data to new table')

# Execute the migration function
migrate_data()
