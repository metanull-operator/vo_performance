import csv
import requests
from datetime import datetime
import argparse

COL_INDEX_NAME = 1
COL_INDEX_VALIDATOR_COUNT = 2
COL_HEADER_NAME = 'Name'
COL_HEADER_VALIDATOR_COUNT = 'Validator Count'

def fetch_and_filter_data(url, ids, time_period):
    response = requests.get(url)
    response.raise_for_status()
    data = response.json()

    performance_data = {op["id"]: "{:.2%}".format(op["performance"][time_period]/100) for op in data["operators"] if op["id"] in ids}
    name_data = {op["id"]: op.get("name", '') for op in data["operators"] if op["id"] in ids}
    validator_count_data = {op["id"]: op.get("validators_count", '') for op in data["operators"] if op["id"] in ids}

    return performance_data, name_data, validator_count_data

def update_or_add_column(header, rows, col_name, col_index, data_dict):
    # Check if column exists and find its index
    if col_name in header:
        col_index = header.index(col_name)
    else:
        header.insert(col_index, col_name)

    for row in rows:
        if len(row) > col_index:
            row[col_index] = data_dict.get(int(row[0]), '')
        else:
            row.insert(col_index, data_dict.get(int(row[0]), ''))

def fill_missing_data(rows, num_columns):
    for row in rows:
        while len(row) < num_columns:
            row.append('')

def add_data_column(header, rows, new_column_name, col_index, data_dict):
    header.insert(col_index, new_column_name)
    for row in rows:
        row_data = data_dict.get(int(row[0]), '')
        row.insert(col_index, row_data)

def read_csv_data(file_name):
    with open(file_name, "r", newline="") as csvfile:
        csvreader = csv.reader(csvfile)
        return [row for row in csvreader]

def write_csv_data(file_name, data):
    with open(file_name, "w", newline="") as csvfile:
        csvwriter = csv.writer(csvfile)
        csvwriter.writerows(data)

def main():
    parser = argparse.ArgumentParser(description='Fetch and update operator performance data.')
    parser.add_argument('-t', '--time_period', type=str, choices=['24h', '30d'], default='24h',
                        help='The reporting time period for performance data (24h or 30d).')
    parser.add_argument('-n', '--network', type=str, choices=['mainnet', 'goerli', 'holesky'], default='mainnet',
                        help='The SSV network to fetch data from (mainnet, goerli, or holesky).')
    parser.add_argument('-f', '--file', type=str, default='operators.csv',
                        help='The CSV data file to use (default: operators.csv).')
    args = parser.parse_args()

    existing_data = read_csv_data(args.file)
    header, rows = existing_data[0], existing_data[1:]
    rows.sort(key=lambda x: int(x[0]))

    performance_data, name_data, validator_count_data = fetch_and_filter_data(
        f"https://api.ssv.network/api/v4/{args.network}/operators/?page=1&perPage=1000&validatorsCount=true",
        set(int(row[0]) for row in rows), args.time_period
    )

    fill_missing_data(rows, len(header))

    update_or_add_column(header, rows, COL_HEADER_NAME, COL_INDEX_NAME, name_data)
    update_or_add_column(header, rows, COL_HEADER_VALIDATOR_COUNT, COL_INDEX_VALIDATOR_COUNT, validator_count_data)

    # Insert new performance data column
    new_data_column_name = datetime.now().strftime("%Y-%m-%d") # + " " + args.time_period # Create header name
    new_data_column_index = len(header) # Set to 3 to add new columns on left, set to len(header) to add on right
    add_data_column(header, rows, new_data_column_name, new_data_column_index, performance_data)

    write_csv_data(args.file, [header] + rows)
    print("Data updated in operators.csv")

if __name__ == "__main__":
    main()
