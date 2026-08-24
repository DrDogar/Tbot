from dotenv import load_dotenv

load_dotenv()

from ui.menu import show_menu

from controllers.market_controller import (
    dashboard,
    download_market_data,
    last_24h_scalping_smoke_test,
    live_price,
    market_model_analysis,
    rsi_analysis,
    show_chart,
    trade_preview,
)
from controllers.arena_controller import show_arena_report, start_bot_arena
from controllers.session_controller import (
    show_session_report,
    start_multi_coin_session,
    start_web_monitor,
)


def main():

    while True:

        choice = show_menu()

        if choice == "1":

            live_price()

        elif choice == "2":

            download_market_data()

        elif choice == "3":

            show_chart()

        elif choice == "4":

            rsi_analysis()

        elif choice == "5":

            dashboard()

        elif choice == "6":

            trade_preview()

        elif choice == "7":

            market_model_analysis()

        elif choice == "8":

            last_24h_scalping_smoke_test()

        elif choice == "9":

            start_multi_coin_session()

        elif choice == "10":

            show_session_report()

        elif choice == "11":

            start_web_monitor()

        elif choice == "12":

            start_bot_arena()

        elif choice == "13":

            show_arena_report()

        elif choice == "14":

            print("\n====================================")
            print("Thank you for using TBOT!")
            print("See you again.")
            print("====================================\n")
            break

        else:

            print("\nInvalid option. Please try again.")

        input("\nPress Enter to return to the menu...")


if __name__ == "__main__":
    main()
