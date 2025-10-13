from data_fetcher import fetch_kabuplus_csv
from data_processor import calculate_momentum
from sheet_writer import update_google_sheet

def main():
    print("▶ 株+データ取得中...")
    df_raw = fetch_kabuplus_csv()

    print("▶ モメンタム計算中...")
    df_log, df_top = calculate_momentum(df_raw)

    print("▶ Googleスプレッドシート更新中...")
    update_google_sheet(df_log, df_top)

    print("✅ 更新完了！")

if __name__ == "__main__":
    main()