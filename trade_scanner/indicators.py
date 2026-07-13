import pandas as pd


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    df["SMA_50"] = df["Close"].rolling(50).mean()
    df["SMA_150"] = df["Close"].rolling(150).mean()
    df["SMA_200"] = df["Close"].rolling(200).mean()

    high_low = df["High"] - df["Low"]
    high_close = (df["High"] - df["Close"].shift(1)).abs()
    low_close = (df["Low"] - df["Close"].shift(1)).abs()
    df["TR"] = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)

    df["ATR_5"] = df["TR"].rolling(5).mean()
    df["ATR_10"] = df["TR"].rolling(10).mean()
    df["ATR_21"] = df["TR"].rolling(21).mean()

    df["VMA_10"] = df["Volume"].rolling(10).mean()
    df["VMA_50"] = df["Volume"].rolling(50).mean()

    df["RANGE_PCT"] = (df["High"] - df["Low"]) / df["Close"] * 100

    return df
