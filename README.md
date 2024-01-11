# ssv_performance_log.py
The ssv_performance_loq.py Python script queries for current SSV operator
performance data and adds that data to an existing CSV file.

- Data is provided by the SSV explorer
- The CSV file must have the SSV operator ID in the first column. Data will be collected only for the operator IDs listed in CSV file.
- The script will add/update a Name column and a Validator Count column

```console
usage: ssv_performance_log.py [-h] [-t {24h,30d}] [-n {mainnet,goerli,holesky}] [-f FILE]

Fetch and update operator performance data.

optional arguments:
  -h, --help            show this help message and exit
  -t {24h,30d}, --time_period {24h,30d}
                        The reporting time period for performance data (24h or 30d).
  -n {mainnet,goerli,holesky}, --network {mainnet,goerli,holesky}
                        The SSV network to fetch data from (mainnet, goerli, or holesky).
  -f FILE, --file FILE  The CSV data file to use (default: operators.csv).
```

## Example

Example that updates the CSV file with 24-hour mainnet operator performance data:

```console
python3 ssv_performance_log.py -t 24h -n mainnet -f data/ssv_operator_performance-mainnet-24h.csv
```

## CSV File Format

Performance data will only be added for operator IDs listed in the first column of the CSV file.
New operator IDs may be added at any time. The script will fill in missing columns from prior reporting periods.

```
Operator ID
1
2
3
4
10
25
```

If they do not already exist, the script will add two columns for operator Name and Validator Count.
The values in these columns will be updated each time the script is run.

## Example Cron Job

Add a cron job to run data collection automatically on a daily basis.

Edit your crontab:

```console
crontab -e
```

Add a `ssv_performance_log.py` job for each network and time period combination for which you would like to collect data.
This example runs the script each morning at 12:27am.

```
27 00 * * * /usr/bin/python3 /home/metanull/vo_performance/ssv_performance_log.py -t 24h -n mainnet -f /home/metanull/vo_performance/data/ssv_operator_performance-mainnet-24h.csv
```

Save your crontab and exit the editor. Your data collection should automatically run daily.

# update_google_sheet.py

The `update_google_sheet.py` script opens a Google Sheet worksheet, clears the data from the worksheet, and uploads fresh data from a specified CSV file. The worksheet is then formatted under the assumption that the data came from the `ssv_performance_log.py` script.

- All data is cleared from the worksheet prior to updating the worksheet with data from the CSV file.
- Credentials for editing the Google Sheet are stored in a separate JSON file

```console
usage: update_google_sheet.py [-h] [-w WORKSHEET] [-f FILE] [-c CREDENTIALS] [-s SHEET]

Update operator performance data CSV on Google Sheet

options:
  -h, --help            show this help message and exit
  -w WORKSHEET, --worksheet WORKSHEET
                        The name of the worksheet to update with data from the CSV
  -f FILE, --file FILE  The CSV data file to use (default: operators.csv)
  -c CREDENTIALS, --credentials CREDENTIALS
                        The credentials JSON file used to access the Google Sheet
  -s SHEET, --sheet SHEET
                        The name of the Google Sheet to update
```

## Example

Example that updates the worksheet "Mainnet 24h" with data from a CSV file:

```console
python3 update_google_sheet.py -f data/ssv_operator_performance-mainnet-24h.csv -w "Mainnet 24h" -c credentials.json -s "ssv_performance_data"
```

## Example Cron Job

Add a cron job to automatically update the worksheet with a CSV file on a daily basis.

Edit your crontab:

```console
crontab -e
```

Add a `update_google_sheet.py` job for each CSV you would like uploaded to a Google Sheet worksheet.
This example runs the script each morning at 12:28am.

```
28 00 * * * /usr/bin/python3 /home/metanull/vo_performance/update_google_sheet.py -c /home/metanull/vo_performance/credentials.json -f /home/metanull/vo_performance/data/ssv_operator_performance-mainnet-24h.csv -w "Mainnet 24h" -s "ssv_performance_data"
```

Save your crontab and exit the editor. Your worksheet should be updated daily.