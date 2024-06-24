import argparse
import logging
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from storage.storage_factory import StorageFactory
from common.config import *


# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


# Creates a two-dimensional representation of the data to be populated into the Google Sheet
def create_spreadsheet_data(data, performance_data_attribute):
    dates = sorted({date for details in data.values() for date in details[performance_data_attribute]}, reverse=True)
    sorted_entries = sorted(data.items(), key=lambda item: item[1].get(FIELD_OPERATOR_ID, 'Unknown'))

    spreadsheet_data = [['OperatorID', 'Name', 'isVO', 'ValidatorCount', 'Address'] + dates]

    for id, details in sorted_entries:
        row = [id, details.get(FIELD_OPERATOR_NAME, None), 1 if details.get(FIELD_IS_VO, 0) else 0,
               details.get(FIELD_VALIDATOR_COUNT, None), details.get(FIELD_ADDRESS, None)]
        for date in dates:
            row.append(details[performance_data_attribute].get(date, None))
        spreadsheet_data.append(row)

    return spreadsheet_data


def main():
    parser = argparse.ArgumentParser(
        description='Retrieve SSV operator performance data from AWS Dynamo DB and update in Google Sheets')
    parser.add_argument('-c', '--discord_credentials', type=str, required=True,
                        help='The credentials JSON file used to access the Google Sheet')
    parser.add_argument('-d', '--document', type=str, required=True, help='The name of the Google Sheet to update')
    parser.add_argument('-w', '--worksheet', type=str, required=True,
                        help='The name of the worksheet to update with data from the CSV')
    parser.add_argument('-p', '--performance_table', type=str, required=True,
                        help='The DynamoDB table from which performance data should be queried')
    parser.add_argument('-a', '--attribute', type=str, required=True,
                        help='The DynamoDB table attribute from which JSON performance data should be pulled')

    args = parser.parse_args()

    credentials_file = args.discord_credentials
    document_name = args.document
    worksheet_name = args.worksheet
    performance_data_table = args.performance_table
    performance_data_attribute = args.attribute

    try:
        # Authenticate with Google Sheets API using provided credentials
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        credentials = ServiceAccountCredentials.from_json_keyfile_name(credentials_file, scope)
        gc = gspread.authorize(credentials)
        logging.info("Authenticated with Google Sheets API.")

        # Open the Google Sheet document
        worksheet = gc.open(document_name).worksheet(worksheet_name)
        logging.info(f"Opened Google Sheet document: {document_name}, worksheet: {worksheet_name}.")

    except Exception as e:
        logging.error(f"Error during Google Sheets authentication or opening document: {e}")
        return

    try:
        # Initialize storage and retrieve performance data
        StorageFactory.initialize('performance', 'DynamoDB', table=performance_data_table)
        storage = StorageFactory.get_storage('performance')
        perf_data = storage.get_performance_all()
        logging.info("Retrieved performance data from DynamoDB.")

    except Exception as e:
        logging.error(f"Error during DynamoDB operations: {e}")
        return

    try:
        # Create spreadsheet data
        spreadsheet = create_spreadsheet_data(perf_data, performance_data_attribute)

        # Clear spreadsheet and update with new data
        worksheet.clear()
        worksheet.update(values=spreadsheet, range_name='A1', value_input_option='USER_ENTERED')
        logging.info("Updated Google Sheet with new performance data.")

    except Exception as e:
        logging.error(f"Error during spreadsheet update: {e}")


if __name__ == "__main__":
    main()