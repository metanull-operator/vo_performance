import logging
from datetime import datetime, timedelta
from discord.ext import tasks
from storage.storage_factory import StorageFactory
from vo_performance_bot.vopb_messages import send_daily_direct_messages, send_vo_threshold_messages
import asyncio


class LoopTasks:

    def __init__(self, bot, channel, notification_time_str, extra_message, allowed_user_ids=[]):
        self.bot = bot
        self.extra_message = extra_message
        self.channel = channel
        self.notification_time_str = notification_time_str
        self.notification_time = datetime.strptime(notification_time_str, "%H:%M").time()
        self.allowed_user_ids = allowed_user_ids


    async def start_tasks(self):
        now = datetime.now()
        target = datetime.combine(now.date(), self.notification_time).replace(second=0, microsecond=0)

        # Determine whether we are sending alerts now, today, or tomorrow
        # Set alert_time flag to current time for sending alerts now. Typically for testing.
        delay = 0
        if now >= target:
            if now >= target + timedelta(minutes=1):
                target += timedelta(days=1)
                delay = (target - now).total_seconds()
        else:
            delay = (target - now).total_seconds()

        # Wait until the next run should occur...
        await asyncio.sleep(delay)

        # ...then kick off loops.
        self.daily_notification_task.start()
        self.performance_status_all_loop.start()


    @tasks.loop(hours=24)
    async def daily_notification_task(self):

        logging.info(f"Sending daily direct messages: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        try:
            sub_storage = StorageFactory.get_storage('subscription')
            subscriptions = sub_storage.get_subscriptions_by_type('daily')

            if not subscriptions:
                logging.warning("Subscription data empty in daily_notification_task()")
                return

            op_ids = list(subscriptions.keys())

            perf_storage = StorageFactory.get_storage('performance')
            perf_data = perf_storage.get_performance_by_opids(op_ids)

            if not perf_data:
                logging.warning(f"Performance data empty for {op_ids} in daily_notification_task()")
                return

            await send_daily_direct_messages(self.bot, perf_data, subscriptions, self.allowed_user_ids)

        except Exception as e:
            logging.error(f"{type(e).__name__} exception in daily_notification_task(): {e}", exc_info=True)


    @tasks.loop(hours=24)
    async def performance_status_all_loop(self):
        logging.info(f"Sending alert message to channel: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        try:
            perf_storage = StorageFactory.get_storage('performance')
            perf_data = perf_storage.get_performance_all()

            if not perf_data:
                logging.warning("Performance data unavailable.")
                return

            sub_storage = StorageFactory.get_storage('subscription')
            subscriptions = sub_storage.get_subscriptions_by_type('alerts')

            if not subscriptions:
                logging.warning("Subscription data unavailable.")

            await send_vo_threshold_messages(self.channel, perf_data, extra_message=self.extra_message,
                                             subscriptions=subscriptions)
        except Exception as e:
            logging.error(f"{type(e).__name__} exception in performance_status_all_loop(): {e}", exc_info=True)

            try:
                # Attempt to notify the Discord channel about the error
                channel = self.bot.get_channel(self.channel_id)
                if channel:
                    await channel.send(f"An error has occurred attempting to send daily alert messages.")
            except Exception as send_e:
                logging.error(f"{type(send_e).__name__} exception attempting to notify channel of exception in performance_status_all_loop(): {send_e}", exc_info=True)
