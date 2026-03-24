from tools.internal.get_customer_profile import get_customer_profile
from tools.internal.get_account_summary import get_account_summary
from tools.internal.get_transaction_history import get_transaction_history
from tools.internal.get_prior_alert_history import get_prior_alert_history
from tools.internal.screen_watchlist import screen_watchlist

tools = [
    get_customer_profile,
    get_account_summary,
    get_transaction_history,
    get_prior_alert_history,
    screen_watchlist,
]
