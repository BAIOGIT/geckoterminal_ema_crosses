from app.db_manager import init_database, save_alert, get_alerts, get_recent_alert
from app.fetch_data import fetch_trending_pools_data, fetch_ohlcv_data

import pandas as pd
import numpy as np
import ta
import time

from tqdm import tqdm
from datetime import datetime, timedelta


def calculate_ema_price(
    df: pd.DataFrame, 
    period_short: int = 9, 
    period_long: int = 26
) -> pd.DataFrame:
    """
    Calculate the EMA prices for the specified short and long periods (e.g., 9 and 26).

    Args:
        df (pd.DataFrame): DataFrame with OHLCV data, including at least a 'Close' column.
        period_short (int): Short period for EMA (default is 9).
        period_long (int): Long period for EMA (default is 26).

    Returns:
        pd.DataFrame: DataFrame with additional columns for the calculated EMA prices.
    """
    if 'Close' not in df.columns:
        raise ValueError("The input df must contain a 'Close' column for EMA calculations.")
    
    # Reverse the DataFrame to calculate EMAs from the most recent data
    df_reversed = df.iloc[::-1].copy()

    # Calculate the short-period (9) EMA price using the 'ta' library
    df_reversed['EMA_9_Price'] = ta.trend.ema_indicator(df_reversed['Close'], window=period_short)

    # Calculate the long-period (26) EMA price using the 'ta' library
    df_reversed['EMA_26_Price'] = ta.trend.ema_indicator(df_reversed['Close'], window=period_long)

    # Reverse the DataFrame back to get the data in the original order
    df['EMA_9_Price'] = df_reversed['EMA_9_Price'].iloc[::-1].values
    df['EMA_26_Price'] = df_reversed['EMA_26_Price'].iloc[::-1].values

    # Calculate EMA diff and add the price column
    df['EMA_Diff'] = df['EMA_9_Price'] - df['EMA_26_Price']

    # Calculate the distance between the two EMAs in percentage
    df['EMA_Diff_Percentage'] = (df['EMA_Diff'] / df['Close']) * 100

    # Calculate the distanche between price and EMA_9 in percentage
    df['EMA_9_Price_Diff_Percentage'] = (df['Close'] - df['EMA_9_Price']) / df['Close'] * 100

    # Calculate if price action is Bullish, Bearish, or Neutral
    # Element-wise comparison between the two EMAs
    df['Signal'] = [
        np.nan if pd.isna(x) or pd.isna(y) else
        'Bullish' if x > y else 
        'Bearish' if x < y else 
        'Neutral' for x, y in zip(df['EMA_9_Price'], df['EMA_26_Price'])
    ]
        
    return df

def scan_pool(pool_address: str) -> pd.DataFrame:
    """
    Fetch OHLCV data for a given pool address, calculate EMAs, and determine market signals.

    Args:
        pool_address (str): The pool address for fetching OHLCV data.

    Returns:
        pd.DataFrame: Processed data with EMA calculations and signals, or None if data is invalid.
    """
    # Fetch OHLCV data for the specified pool address
    data = fetch_ohlcv_data(pool_address)
    ohlcv_data = data['data']['attributes']['ohlcv_list']

    # Create a DataFrame with appropriate column names
    ohlcv_df = pd.DataFrame(ohlcv_data, columns=["Timestamp", "Open", "High", "Low", "Close", "Volume"])

    # Convert the timestamp column to a readable datetime format (optional but recommended)
    ohlcv_df['Timestamp'] = pd.to_datetime(ohlcv_df['Timestamp'], unit='s')

    if isinstance(ohlcv_df, pd.DataFrame) and not ohlcv_df.empty:
        try:
            # Perform EMA calculations and get market signals
            processed_data = calculate_ema_price(ohlcv_df)
            # processed_data = append_pool_data()

            # current_10_rows = processed_data.head(10)
            # print(current_10_rows)

            return processed_data
        except Exception as e:
            print(f"Error processing data: {e}")
            return None
    else:
        print("Failed to fetch valid OHLCV data or the data is empty.")
        return None

def save_alert_if_needed(pool_address, base_mint):
    """
    Save the alert only if there isn't another alert for the same pool within the last hour.
    """
    recent_alert_time = get_recent_alert(pool_address)
    
    if recent_alert_time:
        # Parse the timestamp from the database
        recent_alert_time = datetime.strptime(recent_alert_time, "%Y-%m-%d %H:%M:%S")
        # Check if the recent alert is within the last hour
        if datetime.now() - recent_alert_time < timedelta(hours=2):
            print(f"Skipping alert for {pool_address}: Recent alert exists within the past hour.")
            return False
    
    # Save the alert as it's either new or beyond the 1-hour threshold
    save_alert(pool_address, base_mint)
    return True

def main():
    pools_pages = []
    pages = 10

    print(f"Fetching trending pools from Geckoterminal API, looking for {pages} pages...")
    for page in tqdm(range(1, pages + 1)):
        pools = fetch_trending_pools_data(page)
        pools_pages.append(pools)
        time.sleep(.075)

    print(f"Processing pools data...")
    for pool_page in pools_pages:
        for pool in tqdm(pool_page['data']):
            pool_address = pool['attributes']['address']
            base_mint = pool['relationships']['base_token']['data']['id'].replace('solana_', '')
            quote_mint = pool['relationships']['quote_token']['data']['id'].replace('solana_', '')

            if quote_mint != 'So11111111111111111111111111111111111111112':
                continue
            
            mcap = 0
            try:
                mcap = float(pool['attributes']['market_cap_usd'])
            except:
                mcap = float(pool['attributes']['fdv_usd'])
            # volume = int(pool['attributes']['volume_usd'])
            
            mcap_min = 8_000_000
            mcap_max = 15_000_000
            volume_min = 100_000
            ema_diff_percentage_min = -5
            ema_diff_percentage_max = 0
            ema9_price_diff_percentage_min = -2
            ema9_price_diff_percentage_max = 1

            pool_data = scan_pool(pool_address)

            if pool_data is None:
                continue

            if mcap >= mcap_min and mcap <= mcap_max:
                # if volume >= volume_min:
                if pool_data['Signal'].iloc[0] == 'Bullish':
                    continue
                    print("Currently Bullish")
                elif pool_data['Signal'].iloc[0] == 'Bearish':
                    current_row = pool_data.iloc[0]
                    current_ema_diff_percentage = current_row['EMA_Diff_Percentage']
                    current_price = round(float(current_row['Close']), 6)
                    current_ema9_price_diff_percentage = current_row['EMA_9_Price_Diff_Percentage']

                    if current_ema_diff_percentage >= ema_diff_percentage_min and current_ema_diff_percentage < ema_diff_percentage_max and current_ema9_price_diff_percentage >= ema9_price_diff_percentage_min and current_ema9_price_diff_percentage < ema9_price_diff_percentage_max:
                        if save_alert_if_needed(pool_address, base_mint):
                            print("EMA Crossing")
                            print(f"Processing pool: {pool_address}")
                            print(f"Base Mint: {base_mint}")
                            print(f"Quote Mint: {quote_mint}")
                            print(pool_data.head(5))
                            print(f"Current price: ${current_price}")
                            print(f"Current EMA Difference Percentage: {current_ema_diff_percentage:.2f}%")
                            print(f"Current EMA 9 Price Diff Percentage: {current_ema9_price_diff_percentage:.2f}%")
                            print("\n")
                else:
                    continue
                    print("Actually EMA Crossing")

            time.sleep(2.75)

if __name__ == "__main__":
    init_database()

    while True:
        try:
            main()
            time.sleep(10)
        except Exception as e:
            print(f"An error occurred: {e}")
            time.sleep(30)