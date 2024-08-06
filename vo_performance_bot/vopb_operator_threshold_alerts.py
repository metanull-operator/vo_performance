import logging
from common.config import *


# Looks for the most recent 24h data point and returns operator details if that data point violates the threshold
def operator_threshold_alert_24h(operator, threshold):

    try:
        # If we have no data points, then there are no alerts
        if FIELD_PERF_DATA_24H not in operator or not operator[FIELD_PERF_DATA_24H]:
            return None

        # Get the most recent data point for which we have data points for this operator
        most_recent_date = max(operator[FIELD_PERF_DATA_24H])
        data_point = operator[FIELD_PERF_DATA_24H][most_recent_date]

        try:
            if data_point is not None:
                data_point = float(data_point)
            else:
                return None
        except (ValueError, TypeError) as e:
            logging.warning(f"Error converting 24h data point to float for operator {operator[FIELD_OPERATOR_ID]} and date {most_recent_date}: {e}", exc_info=True)
            return None

        if data_point < threshold:
            return {
                FIELD_OPERATOR_ID: operator[FIELD_OPERATOR_ID],
                FIELD_OPERATOR_NAME: operator[FIELD_OPERATOR_NAME],
                FIELD_VALIDATOR_COUNT: operator[FIELD_VALIDATOR_COUNT],
                'Performance Period': most_recent_date,
                'Performance Data Point': f"{data_point * 100:.2f}%"  # Convert back to percentage string for display
            }
    except Exception as e:
        logging.error(f"Unexpected error in vo_24h_threshold_alerts(): {e}", exc_info=True)

    return None


# Looks for the most recent 30d data point and returns operator details if that data point violates the threshold
def operator_threshold_alert_30d(operator, threshold):

    try:
        # If we have no data points, then there are no alerts
        if FIELD_PERF_DATA_30D not in operator or not operator[FIELD_PERF_DATA_30D]:
            return None

        # Get the most recent data point for which we have data points for this operator
        most_recent_date = max(operator[FIELD_PERF_DATA_30D])
        data_point = operator[FIELD_PERF_DATA_30D][most_recent_date]

        try:
            if data_point is not None:
                data_point = float(data_point)
            else:
                return None
        except (ValueError, TypeError) as e:
            logging.warning(f"Error converting 30d data point to float for operator {operator[FIELD_OPERATOR_ID]} and date {most_recent_date}: {e}", exc_info=True)
            return None

        if data_point < threshold:
            return {
                FIELD_OPERATOR_ID: operator[FIELD_OPERATOR_ID],
                FIELD_OPERATOR_NAME: operator[FIELD_OPERATOR_NAME],
                FIELD_VALIDATOR_COUNT: operator[FIELD_VALIDATOR_COUNT],
                'Performance Period': f"30d",
                'Performance Data Point': f"{data_point * 100:.2f}%"
            }
    except Exception as e:
        logging.error(f"Unexpected error in vo_30d_threshold_alerts(): {e}", exc_info=True)

    return None
