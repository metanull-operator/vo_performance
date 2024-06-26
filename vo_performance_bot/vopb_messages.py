from vo_performance_bot.vopb_mentions import create_subscriber_mentions
from vo_performance_bot.vopb_subscriptions import get_user_subscriptions_by_type
from vo_performance_bot.vopb_operator_threshold_alerts import *
from datetime import datetime, timedelta
from common.config import OPERATOR_24H_HISTORY_COUNT, ALERTS_THRESHOLDS_30D, ALERTS_THRESHOLDS_24H


# Break messages into < MAX_DISCORD_MESSAGE_LENGTH characters chunks, called bundles
# Returns list of separate bundles, each < MAX_DISCORD_MESSAGE_LENGTH
# Inputs already over MAX_DISCORD_MESSAGE_LENGTH are not truncated or split
def bundle_messages(messages, max_length=MAX_DISCORD_MESSAGE_LENGTH):

    bundles = []
    cur_bundle = ''

    for message in messages:
        # Check if adding the next cur_message exceeds the limit
        if len(cur_bundle) + len(message) + 1 > max_length:  # +1 for the newline character
            bundles.append(cur_bundle)  # cur_bundle is full
            cur_bundle = message  # message we are processing becomes first in new cur_bundle
        else:
            # Room for more message. Add it to the end of cur_bundle
            cur_bundle += "\n" + message if cur_bundle else message

    # Add the cur_bundle if there's anything there
    if cur_bundle:
        bundles.append(cur_bundle)

    return bundles


# Creates a message listing subscriptions for a particular user.
def create_subscriptions_message(user_data, subscriber):

    sub_daily = get_user_subscriptions_by_type(user_data, subscriber.id, 'daily')
    sub_alerts = get_user_subscriptions_by_type(user_data, subscriber.id, 'alerts')

    message = f"**__Operator ID Subscriptions:__**\n"

    # List daily direct message subscriptions
    if sub_daily and len(sub_daily) > 0:
        message += f"- Daily performance direct messages: {', '.join(map(str, sub_daily))}\n"
    else:
        message += f"- Daily performance direct messages: None\n"

    # List VO performance threshold subscriptions
    if sub_alerts and len(sub_alerts) > 0:
        message += f"- VOC performance threshold @mentions: {', '.join(map(str, sub_alerts))}\n"
    else:
        message += f"- VOC performance threshold @mentions: None\n"

    return message


# Create message reporting a single operator's recent performance. Overall assumption in this
# code is that the performance data for any single operator is not longer than the
# maximum Discord message length. Otherwise, each operator's message would have to be broken up.
def create_operator_performance_message(operator_data):
    message = ''

    # Display 24h performance second
    if FIELD_PERF_DATA_24H in operator_data and operator_data[FIELD_PERF_DATA_24H]:
        message += f"Recent 24h Performance:\n"

        # Get a list of dates in the last OPERATOR_24H_HISTORY_COUNT calendar days of performance data
        # Filter the performance data to data points in the last OPERATOR_24H_HISTORY_COUNT days
        # Sort the performance data by date descending
        last_x_days = [(datetime.today() - timedelta(days=x)).strftime('%Y-%m-%d') for x in range(OPERATOR_24H_HISTORY_COUNT)]
        filtered_data_points = {date: performance for date, performance in operator_data[FIELD_PERF_DATA_24H].items() if date in last_x_days}
        sorted_filtered_data_points = dict(sorted(filtered_data_points.items(), key=lambda item: item[0], reverse=True))

        if sorted_filtered_data_points:
            for data_date in sorted_filtered_data_points.keys():
                data_value = sorted_filtered_data_points[data_date]
                if data_value is not None:
                    message += f"- {data_date}: {data_value * 100:.2f}%\n"
                else:
                    message += f"- {data_date}: N/A\n"
        else:
            message += "- 24h performance data is unavailable\n"

    if FIELD_PERF_DATA_30D in operator_data and operator_data[FIELD_PERF_DATA_30D]:
        most_recent_30d_date = max(operator_data[FIELD_PERF_DATA_30D].keys())
        perf_30d = operator_data[FIELD_PERF_DATA_30D][most_recent_30d_date]

        if perf_30d:
            message += f"30d Performance: {perf_30d * 100:.2f}%\n"
        else:
            message += "30d Performance: 30d performance data is unavailable\n"
    else:
        message += "30d Performance: 30d performance data is unavailable\n"

    header = ''
    if message:
        header = f"**__{operator_data[FIELD_OPERATOR_NAME]} (ID: {operator_data[FIELD_OPERATOR_ID]}, Validators: {operator_data[FIELD_VALIDATOR_COUNT]})__**\n"

    return header + message


# Return multiple messages containing performance data for multiple
# operator IDs.
def compile_operator_performance_messages(perf_data, operator_ids):
    messages = []

    # Get the intersection of the IDs we want and the IDs in the perf_data
    reporting_ids = list(set(operator_ids) & set(perf_data.keys()))
    missing_ids = list(set(operator_ids) - set(reporting_ids))

    for operator_id in reporting_ids:
        messages.append(create_operator_performance_message(perf_data[operator_id]))

    if missing_ids and len(missing_ids) > 0:
        missing_ids_str = ', '.join(map(str, missing_ids))
        messages.append(f"Data not found for operator IDs: {missing_ids_str}")

    return messages


# Sends one or more messages detailing performance of one or more
# operator IDs, bundles messages into groups to reduce number of messages
# and ensure that messages don't exceed Discord limits.
async def send_operator_performance_messages(perf_data, ctx, operator_ids):

    op_perf_msgs = compile_operator_performance_messages(perf_data, operator_ids)

    message_bundles = bundle_messages(op_perf_msgs)
    
    responded = False
    for bundle in message_bundles:
        if not responded:
            await ctx.respond(bundle.strip(), ephemeral=False)
            responded = True
        else:
            await ctx.send_followup(bundle.strip(), ephemeral=False)


def create_alerts_24h(perf_data):
    alert_msgs_24h = {threshold: [] for threshold in ALERTS_THRESHOLDS_24H}
    operator_ids = []

    for op_id in perf_data.keys():
        operator = perf_data[op_id]

        if not operator[FIELD_IS_VO]:
            continue

        validator_count = operator[FIELD_VALIDATOR_COUNT]
        if validator_count is None or int(validator_count) <= 0:
            continue

        for threshold, alert_list in alert_msgs_24h.items():
            result = operator_threshold_alert_24h(operator, threshold)
            if result and validator_count > 0:
                operator_ids.append(result[FIELD_OPERATOR_ID])
                performance_str = "N/A" if result['Performance Data Point'] is None else f"{result['Performance Data Point']}"
                alert = f"- {result[FIELD_OPERATOR_NAME]} - {performance_str}    (ID: {result[FIELD_OPERATOR_ID]}, Validators: {validator_count})"
                alert_list.append(alert)

    return operator_ids, alert_msgs_24h


def create_alerts_30d(perf_data):
    alert_msgs_30d = {threshold: [] for threshold in ALERTS_THRESHOLDS_30D}
    operator_ids = []

    for op_id in perf_data.keys():
        operator = perf_data[op_id]

        if not operator[FIELD_IS_VO]:
            continue

        validator_count = operator[FIELD_VALIDATOR_COUNT]
        if validator_count is None or int(validator_count) <= 0:
            continue

        for threshold, alert_list in alert_msgs_30d.items():
            result = operator_threshold_alert_30d(operator, threshold)
            if result and validator_count > 0:
                operator_ids.append(result[FIELD_OPERATOR_ID])
                performance_str = "N/A" if result['Performance Data Point'] is None else f"{result['Performance Data Point']}"
                alert = f"- {result[FIELD_OPERATOR_NAME]} - {performance_str}    (ID: {result[FIELD_OPERATOR_ID]}, Validators: {validator_count})"
                alert_list.append(alert)

    return operator_ids, alert_msgs_30d


def compile_alert_threshold_groups(alerts, period_label):
    messages = []

    for threshold, alert_list in alerts.items():
        title = f"\n**__{period_label} < {threshold:.0%}:__**\n"
        message_bundles = bundle_messages(alert_list, MAX_DISCORD_MESSAGE_LENGTH - len(title))

        for bundle in message_bundles:
            messages.append(title + bundle)

    return messages


# Compile alerts, mentions and any extra message into a single set of separate messages to be sent to Discord.
# This attempts to push everything into as few messages as possible to not bomb Discord with excessive messages.
def compile_vo_threshold_messages(perf_data, extra_message=None, display_mentions=False, subscriptions=None, guild=None, allowed_user_ids=[]):

    # Get alerts for different time periods
    operator_ids_24h, alerts_24h = create_alerts_24h(perf_data)
    operator_ids_30d, alerts_30d = create_alerts_30d(perf_data)

    messages = []

    # Bundle up messages for same time periods into titled groups
    messages.extend(compile_alert_threshold_groups(alerts_24h, "24h"))
    messages.extend(compile_alert_threshold_groups(alerts_30d, "30d"))

    # Add mentions to our messages
    if display_mentions and subscriptions and guild:
        # Unique list of operator IDs to find subscribed users
        operator_ids = list(set(operator_ids_24h + operator_ids_30d))
        mentions = create_subscriber_mentions(guild, subscriptions, operator_ids, 'alerts', allowed_user_ids)
        messages.extend(mentions)

    # Include an extra message, if configured
    if extra_message and len(extra_message) > 0:
        messages.append(extra_message)

    # Rebundle everything up again to reduce down to the fewest messages to post to Discord
    bundles = bundle_messages(messages)

    return(bundles)


async def send_vo_threshold_messages(channel, perf_data, extra_message=None, subscriptions=None, allowed_user_ids=[]):

    try:
        # Only attempt @mentions if we have a guild to query and subscription info
        if channel and hasattr(channel, 'guild') and subscriptions:
            messages = compile_vo_threshold_messages(perf_data, extra_message=extra_message, display_mentions=True, subscriptions=subscriptions, guild=channel.guild, allowed_user_ids=allowed_user_ids)
        else:
            messages = compile_vo_threshold_messages(perf_data, extra_message=extra_message, allowed_user_ids=allowed_user_ids)

        if messages:
            for message in messages:
                await channel.send(message.strip())
        else:
            current_date = datetime.now().strftime("%Y-%m-%d")
            await channel.send(f'No performance alerts for {current_date}.')
    except Exception as e:
        logging.error(f"Failed to send VO threshold messages: {e}", exc_info=True)


async def respond_vo_threshold_messages(ctx, perf_data, extra_message=None):

    try:
        messages = compile_vo_threshold_messages(perf_data, extra_message=extra_message, display_mentions=False)

        if messages:
            for message in messages:
                # Note assumption that defer() was previously called.
                await ctx.followup.send(message.strip(), ephemeral=False)
        else:
            current_date = datetime.now().strftime("%Y-%m-%d")
            await ctx.followup.send(f'No performance alerts for {current_date}.', ephemeral=False)
    except Exception as e:
        logging.error(f"Failed to respond with alerts message: {e}", exc_info=True)


# Creates a message bullet item for a single period performance data point
def get_latest_performance(period, operator, attribute):

    try:
        if not operator.get(attribute):
            logging.error(f"{period} performance data attribute not present in get_latest_performance()")
            return f"- {period}: {period} performance data is not available\n"

        most_recent_date = max(operator[attribute].keys())
        most_recent_performance = operator[attribute][most_recent_date]

        return f"- {period}: {most_recent_performance * 100:.2f}%\n" if most_recent_performance else f"- {period}: {period} performance data is not available\n"
    except Exception as e:
        logging.error(f"Exception in get_latest_performance(): {e}", exc_info=True)
        return f"- {period}: {period} performance data is not available\n"


# Create a performance message for a single operator
def create_daily_operator_message(operator):
    message = f"\n**__{operator[FIELD_OPERATOR_NAME]} (ID: {operator[FIELD_OPERATOR_ID]}, Validators: {operator[FIELD_VALIDATOR_COUNT]}):__**\n"

    message += get_latest_performance("24h", operator, FIELD_PERF_DATA_24H)
    message += get_latest_performance("30d", operator, FIELD_PERF_DATA_30D)

    return message


# Create a dict of daily performance messages to send to Discord users
# Loops through subscriptions for each operator ID and appends the
# operator performance data to a dict of messages to go to each user
def compile_daily_operator_messages(perf_data, subscriptions):
    user_messages = {}

    # Looping through all subscribed users for each operator
    for op_id, users in subscriptions.items():
        op_id = int(op_id)

        # Create the direct message text if there is performance data
        if op_id in perf_data:
            op_performance_message = create_daily_operator_message(perf_data[op_id])

            # Find all the daily subscriptions to that operator ID and
            # add to the list of messages for that user
            for user, notification_types in users.items():
                if notification_types.get("daily", False):
                    if user not in user_messages:
                        user_messages[user] = []
                    user_messages[user].append(op_performance_message)

    return user_messages


# Gets dict of all messages going out to all users and sends them,
# breaking messages into chunks less than maximum message length for Discord.
async def send_daily_direct_messages(bot, perf_data, subscriptions, allowed_user_ids=[]):
    user_messages = compile_daily_operator_messages(perf_data, subscriptions)

    # Send out the compiled messages to each user
    for user, messages in user_messages.items():
        try:
            member = await bot.fetch_user(user)
        except Exception as e:
            logging.error(f"Unable to fetch user {user} in send_daily_direct_messages(): {e}", exc_info=True)
            continue

        if member:
            if allowed_user_ids and member.id not in allowed_user_ids:
                continue

            bundles = bundle_messages(messages)
            for bundle in bundles:
                message = bundle.strip()
                if message:
                    try:
                        await member.send(bundle.strip())
                    except Exception as e:
                        logging.error(f"Failed sending daily operator performance direct message to {user}: {e}", exc_info=True)


# Attempts to send a direct message to a user.
# Used to notify users of problems sending direct messages to them.
async def send_direct_message_test(bot, user_id, message):
    try:
        member = await bot.fetch_user(user_id)
        await member.send(message.strip())
        return True
    except Exception as e:
        logging.error(f"Failed to send direct message test to {user_id}: {e}", exc_info=True)
        return False