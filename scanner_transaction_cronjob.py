import os
import json
import time
import psycopg2
from web3 import Web3
from dotenv import load_dotenv
import datetime

load_dotenv(dotenv_path="config.env")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")

RPC_URL = "https://evm-rpc-arctic-1.sei-apis.com"
CONTRACT_ADDRESS = Web3.to_checksum_address("0x6b2b43b3b162c2a7aea56c8422fd34a94847f2c0")
BLOCK_FILE = "last_processed_block.json"
POLL_INTERVAL = 0.5

EVENT_SIGNATURES = {
    "InvestmentMade": "InvestmentMade(uint256,address,uint256,uint256)",
    "VoteCast": "VoteCast(uint256,address)",
    "Refunded": "Refunded(uint256,address,uint256)"
}

CONTRACT_ABI = [
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "internalType": "uint256", "name": "projectId", "type": "uint256"},
            {"indexed": True, "internalType": "address", "name": "investor", "type": "address"},
            {"indexed": False, "internalType": "uint256", "name": "amount", "type": "uint256"},
            {"indexed": False, "internalType": "uint256", "name": "tokensToReceive", "type": "uint256"}
        ],
        "name": "InvestmentMade",
        "type": "event"
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "internalType": "uint256", "name": "projectId", "type": "uint256"},
            {"indexed": True, "internalType": "address", "name": "voter", "type": "address"}
        ],
        "name": "VoteCast",
        "type": "event"
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "internalType": "uint256", "name": "projectId", "type": "uint256"},
            {"indexed": True, "internalType": "address", "name": "investor", "type": "address"},
            {"indexed": False, "internalType": "uint256", "name": "amount", "type": "uint256"}
        ],
        "name": "Refunded",
        "type": "event"
    }
]


def get_db_connection():
    """Establish and return a database connection"""
    try:
        conn = psycopg2.connect(
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST,
            port=DB_PORT
        )
        return conn
    except psycopg2.Error as e:
        print(f"Database connection error: {e}")
        return None


def get_last_processed_block():
    """Get the last processed block from the JSON file"""
    try:
        if os.path.exists(BLOCK_FILE):
            with open(BLOCK_FILE, 'r') as f:
                data = json.load(f)
                return data.get('last_block', 0)
        else:
            return 0
    except Exception as e:
        print(f"Error reading last processed block: {e}")
        return 0


def save_last_processed_block(block_number):
    """Save the last processed block to the JSON file"""
    try:
        with open(BLOCK_FILE, 'w') as f:
            json.dump({'last_block': block_number}, f)
        print(f"Saved last processed block: {block_number}")
    except Exception as e:
        print(f"Error saving last processed block: {e}")

def process_investment_made_event(web3, event):
    """Process InvestmentMade event and insert into database"""
    try:
        project_id = event['args']['projectId']
        investor_address = event['args']['investor']
        amount = event['args']['amount']
        tokens_received = event['args']['tokensToReceive']
        transaction_hash = event['transactionHash'].hex()
        
        tx_receipt = web3.eth.get_transaction_receipt(transaction_hash)
        block = web3.eth.get_block(tx_receipt['blockNumber'])
        transaction_time = datetime.datetime.fromtimestamp(block['timestamp'])
        
        amount_decimal = amount / 10**6
        
        conn = get_db_connection()
        if not conn:
            return False
        
        cur = conn.cursor()
        
        cur.execute("SELECT id FROM investor WHERE wallet_address = %s", (investor_address.lower(),))
        result = cur.fetchone()
        if not result:
            cur.execute("INSERT INTO investor(wallet_address) VALUES (%s)", (investor_address.lower(),))
            conn.commit()
        
        cur.execute(
            """
            INSERT INTO transaction(project_id, investor_address, amount, token_received, transaction_time, transaction_hash, type)
            VALUES (%s, %s, %s, %s, %s, %s, 'investment')
            """,
            (project_id, investor_address.lower(), amount_decimal, tokens_received, transaction_time, transaction_hash)
        )
        
        conn.commit()
        cur.close()
        conn.close()
        
        print(f"Processed InvestmentMade: Project {project_id}, Investor {investor_address}, Amount {amount_decimal}, Tokens {tokens_received}, Hash {transaction_hash[:10]}...")
        return True
    
    except Exception as e:
        print(f"Error processing InvestmentMade event: {e}")
        if 'conn' in locals() and conn:
            conn.close()
        return False


def process_vote_cast_event(web3, event):
    """Process VoteCast event and insert into database"""
    try:
        project_id = event['args']['projectId']
        voter_address = event['args']['voter']
        transaction_hash = event['transactionHash'].hex()
        
        tx_receipt = web3.eth.get_transaction_receipt(transaction_hash)
        block = web3.eth.get_block(tx_receipt['blockNumber'])
        transaction_time = datetime.datetime.fromtimestamp(block['timestamp'])
        
        conn = get_db_connection()
        if not conn:
            return False
        
        cur = conn.cursor()
        
        cur.execute("SELECT id FROM investor WHERE wallet_address = %s", (voter_address.lower(),))
        result = cur.fetchone()
        if not result:
            cur.execute("INSERT INTO investor(wallet_address) VALUES (%s)", (voter_address.lower(),))
            conn.commit()
        
        cur.execute(
            """
            INSERT INTO transaction(project_id, investor_address, transaction_time, transaction_hash, type)
            VALUES (%s, %s, %s, %s, 'vote')
            """,
            (project_id, voter_address.lower(), transaction_time, transaction_hash)
        )
        
        conn.commit()
        cur.close()
        conn.close()
        
        print(f"Processed VoteCast: Project {project_id}, Voter {voter_address}, Hash {transaction_hash[:10]}...")
        return True
    
    except Exception as e:
        print(f"Error processing VoteCast event: {e}")
        if 'conn' in locals() and conn:
            conn.close()
        return False


def process_refund_event(web3, event):
    """Process Refunded event and insert into database"""
    try:
        project_id = event['args']['projectId']
        investor_address = event['args']['investor']
        amount = event['args']['amount']
        transaction_hash = event['transactionHash'].hex()
        
        tx_receipt = web3.eth.get_transaction_receipt(transaction_hash)
        block = web3.eth.get_block(tx_receipt['blockNumber'])
        transaction_time = datetime.datetime.fromtimestamp(block['timestamp'])
        
        amount_decimal = amount / 10**6
        
        conn = get_db_connection()
        if not conn:
            return False
        
        cur = conn.cursor()
        
        cur.execute("SELECT id FROM investor WHERE wallet_address = %s", (investor_address.lower(),))
        result = cur.fetchone()
        if not result:
            cur.execute("INSERT INTO investor(wallet_address) VALUES (%s)", (investor_address.lower(),))
            conn.commit()
        
        cur.execute(
            """
            INSERT INTO transaction(project_id, investor_address, amount, transaction_time, transaction_hash, type)
            VALUES (%s, %s, %s, %s, %s, 'get_refund')
            """,
            (project_id, investor_address.lower(), amount_decimal, transaction_time, transaction_hash)
        )
        
        conn.commit()
        cur.close()
        conn.close()
        
        print(f"Processed Refunded: Project {project_id}, Investor {investor_address}, Amount {amount_decimal}, Hash {transaction_hash[:10]}...")
        return True
    
    except Exception as e:
        print(f"Error processing Refunded event: {e}")
        if 'conn' in locals() and conn:
            conn.close()
        return False

def scan_for_events():
    """Main function to scan for events and process them"""
    try:
        web3 = Web3(Web3.HTTPProvider(RPC_URL))
        if not web3.is_connected():
            print("Web3 connection error")
            return
        
        contract = web3.eth.contract(address=CONTRACT_ADDRESS, abi=CONTRACT_ABI)
        
        latest_block = web3.eth.block_number
        last_processed_block = get_last_processed_block()
        
        if last_processed_block == 0:
            last_processed_block = 0
        
        print(f"Scanning blocks from {last_processed_block + 1} to {latest_block}")
        
        chunk_size = 1999
        start_block = last_processed_block + 1
        
        while start_block <= latest_block:
            end_block = min(start_block + chunk_size - 1, latest_block)
            print(f"Processing chunk from block {start_block} to {end_block}")
            
            investment_filter = contract.events.InvestmentMade.create_filter(
                fromBlock=start_block,
                toBlock=end_block
            )
            
            vote_filter = contract.events.VoteCast.create_filter(
                fromBlock=start_block,
                toBlock=end_block
            )
            
            refund_filter = contract.events.Refunded.create_filter(
                fromBlock=start_block,
                toBlock=end_block
            )
            
            investment_events = investment_filter.get_all_entries()
            vote_events = vote_filter.get_all_entries()
            refund_events = refund_filter.get_all_entries()
            
            for event in investment_events:
                process_investment_made_event(web3, event)
            
            for event in vote_events:
                process_vote_cast_event(web3, event)
            
            for event in refund_events:
                process_refund_event(web3, event)
            
            if investment_events or vote_events or refund_events:
                print(f"Processed {len(investment_events)} investments, {len(vote_events)} votes, {len(refund_events)} refunds in block range {start_block}-{end_block}")
            
            save_last_processed_block(end_block)
            
            start_block = end_block + 1
        
        return latest_block
    
    except Exception as e:
        print(f"Error scanning for events: {e}")
        return None


def main():
    print("Starting blockchain event listener...")
    
    while True:
        try:
            latest_block = scan_for_events()
            if latest_block:
                print(f"Latest processed block: {latest_block}")
            
            print(f"Waiting for {POLL_INTERVAL} seconds before next scan...")
            time.sleep(POLL_INTERVAL)
            
        except KeyboardInterrupt:
            print("Process interrupted by user.")
            break
        except Exception as e:
            print(f"Unexpected error: {e}")
            time.sleep(60)

if __name__ == "__main__":
    main()