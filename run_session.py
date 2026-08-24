from dotenv import load_dotenv

load_dotenv()

from engine.runner import run_multi_coin_session

if __name__ == "__main__":
    run_multi_coin_session()
