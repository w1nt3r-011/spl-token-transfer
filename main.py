import json
import time
from datetime import datetime
from solders.pubkey import Pubkey  # type: ignore
from solders.keypair import Keypair  # type: ignore
from solders.message import MessageV0  # type: ignore
from solders.instruction import Instruction, AccountMeta  # type: ignore
from solders.transaction import VersionedTransaction  # type: ignore
from solders.compute_budget import set_compute_unit_limit, set_compute_unit_price  # type: ignore
from solana.rpc.api import Client
from solana.rpc.types import TxOpts
from spl.token.instructions import get_associated_token_address, create_associated_token_account

TOKEN_PROGRAM_ID = Pubkey.from_string("TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA")
LAMPORTS_PER_SOL = 1_000_000_000
MICROLAMPORTS_PER_SOL = LAMPORTS_PER_SOL * 1_000_000

def log(message):
    print(f"[{datetime.now().strftime('%H:%M:%S.%f')[:-3]}] {message}")

try:
    with open("config.json", "r") as config_file:
        config_data = json.load(config_file)
        client = Client(config_data["rpc_http"]) #signup to helius free trial or use your own if u have
        sender_keypair = Keypair.from_base58_string(config_data["sender_pk"]) #base58 (format you get when exporting pk from phantom)
        token_pubkey = Pubkey.from_string(config_data["token_addr"]) #normal pub key
        receiver_pubkey = Pubkey.from_string(config_data["receiver_addr"]) #normal pub key
        token_transfer_amount = float(config_data["transfer_amount"]) #int/float can be a string but only if its in a valid format to convert
        compute_units = int(config_data["compute_units"]) #leave as is, or raise if txs failing bc its hitting limit
        tx_fee_sol = float(config_data["tx_fee"]) #change to whatever you want but not that deep
except Exception as e:
    log(f"load config.json error {str(e)}")
    time.sleep(3) 
    raise SystemExit


def transfer_tokens():
    try:
        instructions = []

        desired_fee_micro_lamports = tx_fee_sol * MICROLAMPORTS_PER_SOL
        unit_price = int(desired_fee_micro_lamports / compute_units)

        instructions.append(set_compute_unit_limit(compute_units))
        instructions.append(set_compute_unit_price(unit_price))


        token_info = client.get_token_supply(token_pubkey)
        log(f"got token info {token_pubkey}")
        decimals = token_info.value.decimals

        sender_ata = get_associated_token_address(sender_keypair.pubkey(), token_pubkey)

        recipient_ata = get_associated_token_address(receiver_pubkey, token_pubkey)
        recipient_info = client.get_account_info(recipient_ata)
        if recipient_info.value is None:
            instructions.append(
                create_associated_token_account(
                    payer=sender_keypair.pubkey(),
                    owner=receiver_pubkey,
                    mint=token_pubkey
                )
            )

        balance_resp = client.get_token_account_balance(sender_ata)
        if balance_resp.value.ui_amount is None:
            log("no sender token balance")
            return

        sender_balance = balance_resp.value.ui_amount
        log(f"senders token balance {sender_balance}")

        transfer_amount = int(token_transfer_amount * (10 ** decimals))
        if transfer_amount <= 0:
            log(f"transfer amount invalid {transfer_amount}")
            return

        instructions.append(
            Instruction(
                program_id=TOKEN_PROGRAM_ID,
                accounts=[
                    AccountMeta(pubkey=sender_ata, is_signer=False, is_writable=True),
                    AccountMeta(pubkey=token_pubkey, is_signer=False, is_writable=False),
                    AccountMeta(pubkey=recipient_ata, is_signer=False, is_writable=True),
                    AccountMeta(pubkey=sender_keypair.pubkey(), is_signer=True, is_writable=True),
                ],
                data=bytes([12])
                + transfer_amount.to_bytes(8, byteorder="little")
                + decimals.to_bytes(1, byteorder="little"),
            )
        )

        MEMO_PROGRAM_ID = Pubkey.from_string("MemoSq4gqABAXKb96qnH8TysNcWxMyWCqXgDLGmfcHr")
        instructions.append(
            Instruction(
                program_id=MEMO_PROGRAM_ID,
                accounts=[],
                data=f"Kev is gay".encode("utf-8")
            )
        )
        log("letting kev know his place")


        latest_blockhash = client.get_latest_blockhash().value.blockhash
        compiled_message = MessageV0.try_compile(
            sender_keypair.pubkey(),
            instructions,
            [],
            latest_blockhash
        )

        log("sending tx")
        txn_sig = client.send_transaction(
            txn=VersionedTransaction(compiled_message, [sender_keypair]),
            opts=TxOpts(skip_preflight=True)
        ).value
        log(f"tx sent: https://solscan.io/tx/{txn_sig}")
    except Exception as e:
        log(f"transfer tokens error {str(e)}")
        time.sleep(3)
        raise SystemExit


try:
    log(f"transfer {token_transfer_amount} tokens of {token_pubkey} to {receiver_pubkey} from {sender_keypair.pubkey()}")
    input(f"[{datetime.now().strftime('%H:%M:%S.%f')[:-3]}] hit ENTER to send")
    log("starting transfer")
    transfer_tokens()
except Exception as e:
    log(f"main error {str(e)}")
    time.sleep(3)
    raise SystemExit
