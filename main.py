from ui.menu import show_menu

from controllers.market_controller import (
    live_price,
    download_market_data,
    show_chart,
    rsi_analysis,
    dashboard,
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

            print("\n====================================")
            print("Thank you for using TBOT!")
            print("See you again. 👋")
            print("====================================\n")
            break

        else:

            print("\n❌ Invalid option. Please try again.")

        input("\nPress Enter to return to the menu...")


if __name__ == "__main__":
    main()