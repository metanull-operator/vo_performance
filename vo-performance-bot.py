import sys
import argparse
import asyncio
import logging
import discord
import vo_performance_bot.vopb_commands as vopb_commands
from discord.ext import commands
from storage.storage_factory import StorageFactory
from vo_performance_bot.vopb_loops import LoopTasks

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def parse_arguments():
    parser = argparse.ArgumentParser(description="SSV Verified Operator Committee Discord bot")

    parser.add_argument("-d", "--discord_token_file", required=True, help="File containing Discord Bot token")
    parser.add_argument("-t", "--alert_time", type=str, required=True, help="Time of day to send scheduled alert messages (format: HH:MM, 24-hour format)")
    parser.add_argument("-c", "--channel_id", required=True, help="Discord Channel ID on which to listen for commands")
    parser.add_argument("-e", "--extra_message", type=str, help="An additional message sent after alert messages")
    parser.add_argument("-p", "--performance_table", required=True, type=str, help="AWS DynamoDB table from which to pull operator performance data")
    parser.add_argument("-s", "--subscription_table", required=True, type=str, help="AWS DynamoDB table in which to store subscription data")
    parser.add_argument("-l", "--limit_user_ids", nargs="*", required=False, help="Limit direct messages and @mentions to the listed user IDs, for QA")

    args = parser.parse_args()

    allowed_user_ids = list(map(int, args.limit_user_ids)) if args.limit_user_ids else []

    return args.discord_token_file, args.channel_id, args.alert_time, args.extra_message, args.performance_table, args.subscription_table, allowed_user_ids

def read_discord_token_from_file(token_file_path):
    try:
        with open(token_file_path, 'r') as file:
            return file.read().strip()
    except Exception as e:
        logging.error(f"Unable to retrieve Discord token: {e}", exc_info=True)
        sys.exit(1)

async def main():
    try:
        discord_token_file, channel_id, alert_time, extra_message, performance_data_table, subscription_data_table, allowed_user_ids = parse_arguments()
    except SystemExit as e:
        if e.code != 0:
            logging.error("Argument parsing failed", exc_info=True)
        sys.exit(e.code)

    try:
        StorageFactory.initialize('performance', 'DynamoDB', table=performance_data_table)
        StorageFactory.initialize('subscription', 'DynamoDB', table=subscription_data_table)
        logging.info("Storage initialized successfully.")
    except Exception as e:
        logging.error(f"Error initializing storage: {e}", exc_info=True)
        sys.exit(1)

    intents = discord.Intents.default()
    intents.members = True
    intents.message_content = True

    bot = commands.Bot(command_prefix='!', intents=intents, help_command=None)

    @bot.event
    async def on_ready():
        logging.info(f'Logged in as {bot.user.name}')
        logging.info(f"Getting channel {channel_id}")

        try:
            channel = bot.get_channel(int(channel_id))
            if not channel:
                logging.error(f"Cannot get channel {channel_id}")
                sys.exit(1)

            loop_tasks = LoopTasks(bot, channel, alert_time, extra_message, allowed_user_ids)
            bot.loop.create_task(loop_tasks.start_tasks())
            logging.info("Loop tasks started successfully.")
        except Exception as e:
            logging.error(f"Error in on_ready event: {e}", exc_info=True)
            sys.exit(1)

    try:
        await vopb_commands.setup(bot, channel_id, extra_message)
        logging.info("Commands setup successfully.")
    except Exception as e:
        logging.error(f"Error setting up commands: {e}", exc_info=True)
        sys.exit(1)

    try:
        discord_token = read_discord_token_from_file(discord_token_file)
        await bot.start(discord_token)
    except Exception as e:
        logging.error(f"Error starting bot: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())