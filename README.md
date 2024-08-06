# VO Performance

A collection of Python scripts to aid in monitoring and reporting of SSV Network operators, with a focus on Verified Operators.

- vo-performance-bot.py
  - A Discord bot that provides scheduled and on-demand updates of SSV operator performance
- vo-performance-sheets.py
  - A Python script that pulls SSV operator performance data from an AWS DynamoDB database and pushes the data to
    a Google Sheet
- ssv_performance_lamba.py
  - A Python script that retrieves SSV operator performance from the SSV API and stores the data in an AWS DynamoDB 
    database
- ssv_performance_log.py
  - A deprecated script that retrieves SSV operator performance from the SSV API and stores the data in a CSV file

# vo-performance-bot.py

`vo-performance-bot.py` is a Discord bot that provides scheduled and on-demand updates of SSV operator performance. 

- Sends a scheduled daily message to a Discord channel providing details of SSV Verified Operators
  whose performance falls below configurable 24h and 30d thresholds
- Allows Discord users to subscribe to be tagged in scheduled daily messages regarding Verified Operators
  whose performance falls below 24h and 30d thresholds
- Responds to on-demand requests for details of SSV Verified Operators whose performance falls below configurable
  24h and 30d thresholds
- Responds to on-demand requests for recent operator performance history data for any SSV operator, by operator ID
- Allows Discord users to subscribe to daily direct messages containing recent performance history for any 
  SSV operator
- The bot will send a test message to users subscribing to direct messages and will provide immediate feedback
  if the direct message fails
- Bot commands can be triggered in a single allowed channel or in direct messages to the bot

## Prerequisites

The following Python libraries must be installed for `vo-performance-bot.py` to work correctly:

- boto3
- py-cord

## DynamoDB Storage

The bot reads SSV operator performance data from an AWS DynamoDB database populated by another script. 
Subscription data is also stored and read from the AWS DynamoDB database.

### AWS Credentials

AWS credentials must be stored in a configuration file in the following format:

```
[default]
region = eu-central-2
aws_access_key_id = your-access-key-id
aws_secret_access_key = your-secret-access-key
```

By default the AWS credentials are stored in `~/aws/credentials`, but you may specify a different location for
file using the `AWS_CONFIG_FILE` environment variable.

### Performance Data Table

Performance data is read from the performance data table but must be inserted by a separate script or process.
The bot only reads the data and does not insert/modify the data. See `ssv_performance_lambda.py` for the script
presently used to retrieve and store performance data.

The performance data table should contain the following attributes:
- `Operator ID` (Number)
  - Contains the integer Operator ID of the SSV operator
- `Address` (String)
  - Contains the string Ethereum address of the SSV operator
- `isVO` (Number)
  - Value is `1` if the operator is a Verified Operator and `0` if not
- `Name` (String)
  - Contains the name of the operator
- `Performance24h` (Map)
  - A JSON data structure containing the 24h performance data for all tracked operators
- `Performance30d` (Map)
  - A JSON data structure containing the 30d performance data for all tracked operators
- `ValidatorCount` (Number)
  - The number of validators presently associated with the operator
  
#### Performance Data JSON 

The `PerformanceData24h` and `PerformanceData30d` attributes contain JSON object in the format of the following example:

```commandline
{
  "2024-03-21": { "N": "0" },
  "2024-03-22": { "N": "0" },
  "2024-03-23": { "N": "0" },
  "2024-03-24": { "N": "0" },
  "2024-03-25": { "N": "0" },
  "2024-03-26": { "N": "0.998409" },
  "2024-03-27": { "N": "0.997655" },
  "2024-03-28": { "N": "0.997483" },
  "2024-03-29": { "N": "0.999748" },
  "2024-06-17": { "N": "0.998484" },
  "2024-06-18": { "N": "0.998295" }
}
```

The JSON object follows a specific structure where:

- Each key is a date in the format YYYY-MM-DD.
- Each value is an object containing a single key "N", which represents a numeric value.
- The numeric value is stored as a string to preserve precision and can be an integer or a decimal.

### Subscription Data Table

Subscriptions in the subscription data table are managed by the bot.

The subscription data table should contain the following attributes:

- `UserID` (String)
  - The Discord ID of the user subscribed to one or more operator IDs
- `SubscriptionInfo` (String)
  - A global secondary index on the table
- `OperatorID` (Number)
  - The ID of the operator to which the user is subscribed
- `SubscriptionType` (String)
  - The type of subscription to which the user is subscribed for the operator ID ('daily' or 'alerts')

A single records in the database is used for each UserID, OperatorID, and SubscriptionType combination.

## Running vo-performance-bot.py

`vo-performance-bot.py` command line flags:

```
usage: vo-performance-bot.py [-h] -d DISCORD_TOKEN_FILE -t ALERT_TIME -c CHANNEL_ID [-e EXTRA_MESSAGE] -p PERFORMANCE_TABLE -s SUBSCRIPTION_TABLE [-l [LIMIT_USER_IDS ...]]

SSV Verified Operator Committee Discord bot

options:
  -h, --help            show this help message and exit
  -d DISCORD_TOKEN_FILE, --discord_token_file DISCORD_TOKEN_FILE
                        File containing Discord Bot token
  -t ALERT_TIME, --alert_time ALERT_TIME
                        Time of day to send scheduled alert messages (format: HH:MM, 24-hour format)
  -c CHANNEL_ID, --channel_id CHANNEL_ID
                        Discord Channel ID on which to listen for commands
  -e EXTRA_MESSAGE, --extra_message EXTRA_MESSAGE
                        An additional message sent after alert messages
  -p PERFORMANCE_TABLE, --performance_table PERFORMANCE_TABLE
                        AWS DynamoDB table from which to pull operator performance data
  -s SUBSCRIPTION_TABLE, --subscription_table SUBSCRIPTION_TABLE
                        AWS DynamoDB table in which to store subscription data
  -l [LIMIT_USER_IDS ...], --limit_user_ids [LIMIT_USER_IDS ...]
                        Limit direct messages and @mentions to the listed user IDs, for QA
```

### Example:

```
python3 vo-performance-bot.py -d discord_token.txt -c 12345678901234567890 -p SSVPerformanceData -s SSVPerformanceSubscriptions -t 6:30
```

- `-d discord_token.txt` specifies a file that contains the Discord authentication token that gives the bot access to the Discord server and channels
- `-c 12345678901234567890` specifies the Discord channel to which daily alert messages are sent, and the channel on which the bot will respond to commands
- `-p SSVPerformanceData` specifies the name of the AWS DynamoDB table from which to pull performance data
- `-s SSVPerformanceSubscriptions` specifies the name of the AWS DynamoDB table in which subscription data will be stored
- `-t 6:30` specifies that the daily alert messages regarding Verified Operator performance will be sent at 6:00

To run the bot using a custom location for AWS credentials, set the `AWS_CONFIG_FILE` environment variable to
the path of the AWS credentials file. For example:

```
AWS_CONFIG_FILE=aws_config.ini python3 vo-performance-bot.py -d discord_token.txt -c 12345678901234567890 -p SSVPerformanceData -s SSVPerformanceSubscriptions -t 6:30
```

### Discord Configuration

To configure Discord for bot access:

- Create New Discord Application
  - Go to Discord Developer Portal at https://discord.com/developers/applications
  - Click New Application
  - Enter a name for the new application, accept the terms, and click Create
- Configure Bot
  - Click on Bot in the left-hand menu
  - Edit Username if necessary
  - Click Reset Token and follow instructions to view new token
    - Back up token somewhere safe
  - Turn on the Server Members Intent
  - Turn on the Message Content Intent
  - Click Save
- Configure Authentication
  - Click on OAuth2 in the left-hand menu
  - Select the "bot" checkbox under SCOPES
  - Under Bot Permissions, select the following permissions:
    - Read Messages/View Channels
    - Send Messages
    - Use Slash Commands
  - Copy the generated URL at the bottom of the screen
- Authorize Bot for Server
  - Paste the URL into a browser where you are logged in as the Discord server owner
  - Select the correct server under Add to Server
  - Click Continue
  - Review permissions and click Authorize
- Configure Allowed Channels
  - In the Discord server settings, go to the Integrations screen
  - Click on Manage for the bot
  - Remove access to All Channels
  - Add access to the allowed channel
  - Save Changes

For access to Discord channel IDs:

- Turn on Developer Mode
  - In Discord, click on the settings icon (gear) next to your username
  - Click on Advanced in the left-hand menu
  - Turn on Developer Mode for access to channel IDs

# update_google_sheet.py

The `update_google_sheet.py` script opens a Google Sheet worksheet, clears the data from the worksheet, and uploads fresh performance data from an attribute in an AWS DynamoDB table.

- All data is cleared from the worksheet prior to updating the worksheet with data from the DynamoDB table.
- Credentials for accessing the Google Sheet are stored in an external file
- Credentials for accessing the AWS DynamoDB table are stored in an external file

The script must be run separately for each Google Sheets worksheet that must be updated. For example,
if one worksheet contains 24h performance data and another contains 30d performance data, the script
must be run twice with different arguments to specify the source and destination of the data. Similarly, 
the script must be run separately for each Ethereum network. A Google sheet containing worksheets with Mainnet 24h, 
Mainnet 30d, Holesky 24h, and Holesky 30d data will require the script to be run four times to populate all worksheets.

## Prerequisites

The following Python libraries must be installed for `vo-performance-bot.py` to work correctly:

- boto3
- gspread
- oauth2client

## Running update_google_sheet.py

`update_google_sheet.py` command line flags:

```console
usage: update_google_sheet.py [-h] -c DISCORD_CREDENTIALS -d DOCUMENT -w WORKSHEET -p PERFORMANCE_TABLE -a ATTRIBUTE

Retrieve SSV operator performance data from AWS Dynamo DB and update in Google Sheets

options:
  -h, --help            show this help message and exit
  -c DISCORD_CREDENTIALS, --discord_credentials DISCORD_CREDENTIALS
                        The credentials JSON file used to access the Google Sheet
  -d DOCUMENT, --document DOCUMENT
                        The name of the Google Sheet to update
  -w WORKSHEET, --worksheet WORKSHEET
                        The name of the worksheet to update with data from the CSV
  -p PERFORMANCE_TABLE, --performance_table PERFORMANCE_TABLE
                        The DynamoDB table from which performance data should be queried
  -a ATTRIBUTE, --attribute ATTRIBUTE
                        The DynamoDB table attribute from which JSON performance data should be pulled
```

### Example

Example that updates the worksheet "Mainnet 24h" with data from the DynamoDB table `SSVPerformanceData`:

```console
python3 update_google_sheet.py -d 'VOC Performance Data' -c google-credentials.json -w 'Mainnet 24h' -p 'SSVPerformanceData' -a 'Performance24h'
```

- `-d 'VOC Performance Data'` specifies the name of the Google Sheets document containing the worksheet to be updated
- `-c google-credentials.json` specifies the credentials for accessing Google Sheets via the API
- `-w 'Mainnet 24h'` specifies the name of the Google Sheets worksheet in which to populate performance data
- `-p SSVPerformanceData` specifies the name of the AWS DynamoDB table in which performance data is stored
- `-a 'Performance24h` specifies the database table attribute from which to pull performance data

To run the bot using a custom location for AWS credentials, set the `AWS_CONFIG_FILE` environment variable to
the path of the AWS credentials file. For example:

```
AWS_CONFIG_FILE=aws_config.ini python3 update_google_sheet.py -d 'VOC Performance Data' -c google-credentials.json -w 'Mainnet 24h' -p 'SSVPerformanceData' -a 'Performance24h'
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
28 00 * * * AWS_CONFIG_FILE=aws_config.ini /usr/bin/python3 /usr/local/bin/update_google_sheet.py -d 'VOC Performance Data' -c google-credentials.json -w 'Mainnet 24h' -p 'SSVPerformanceData' -a 'Performance24h'
```

Save your crontab and exit the editor. Your worksheet should be updated daily.

# ssv_performance_log.py [Deprecated]
The ssv_performance_loq.py Python script queries for current SSV operator
performance data and adds that data to an existing CSV file. 

**This script is deprecated and no longer supported.**

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
New operator IDs may be added at any time. The script will fill in missing columns from prior reporting periods with
blanks.

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
27 00 * * * /usr/bin/python3 /usr/local/bin/ssv_performance_log.py -t 24h -n mainnet -f /var/lib/vo_performance/ssv_operator_performance-mainnet-24h.csv
```

Save your crontab and exit the editor. Your data collection should automatically run daily.
