"""
Nash Staking
===================================

Author: Thomas Saunders
Email: tom@nash.io

Date: Sep 30 2019

"""
from boa.builtins import concat
from boa.interop.Neo.Action import RegisterAction
from boa.interop.Neo.App import RegisterAppCall
from boa.interop.Neo.Runtime import CheckWitness, Deserialize, GetTime, GetTrigger, Serialize
from boa.interop.Neo.Storage import *
from boa.interop.Neo.Transaction import *
from boa.interop.Neo.TriggerType import Application, Verification
from boa.interop.System.ExecutionEngine import GetExecutingScriptHash, GetScriptContainer
from boa.interop.Neo.Iterator import IterNext, IterKey, IterValue

from nash.owner import *

ctx = GetContext()

OnStake = RegisterAction("onStake", "stakeID", "addr", "amount", "rate", "start", "expiration")
OnLegacyStakeMigrated = RegisterAction("onLegacyStakeMigrated", "stakeID", "addr", "amount", "rate", "start", "expiration")
OnStakeComplete = RegisterAction("onStakeComplete", "stakeID", "addr", "amount")


SECONDS_PER_MONTH = 2629743
STAKE_MODULUS = 100000000
ADMIN_ADDR_PREFIX = 'adminAddress'

NEX_TOKEN_APPCALL_STAKE = RegisterAppCall("3A4ACD3647086E7C44398AAC0349802E6A171129", 'transferFrom', 'args')
NEX_TOKEN_APPCALL_UNSTAKE = RegisterAppCall("3A4ACD3647086E7C44398AAC0349802E6A171129", 'transfer', 'args')
NEX_TOKEN_APPCALL_BALANCE = RegisterAppCall("3A4ACD3647086E7C44398AAC0349802E6A171129", "balanceOf", 'args')
LEGACY_STAKE_QUERY = RegisterAppCall('3A41E7CE5F4002BE52FD3BFA962C1B4802E5D259', 'getStake', 'args')

def Main(operation, args):
    """

    :param operation: str The name of the operation to perform
    :param args: list A list of arguments along with the operation
    :return:
        bytearray: The result of the operation
    """

    trigger = GetTrigger()

    # This is used in the Verification portion of the contract
    # To determine whether a transfer of system assets ( NEO/Gas) involving
    # This contract's address can proceed
    if trigger == Verification():
        # This is used in case a contract migration is needed ( for example NEO3 transition)
        if check_owners(ctx, 4):
            return True
        return False

    elif trigger == Application():

        if operation == 'stake':
            if len(args) == 3:
                return stakeTokens(args)
            raise Exception("Invalid argument length")

        elif operation == 'completeStake':
            if len(args) == 1:
                return completeStake(args[0])
            raise Exception("Invalid argument length")

        elif operation == 'getStake':
            if len(args) == 1:
                return getStakeById(args[0])
            raise Exception("Invalid argument length")

        elif operation == 'getStakesByAddress':
            if len(args) == 1:
                return getStakesByAddress(args[0])
            raise Exception("Invalid argument length")

        elif operation == 'totalStaked':
            return getTotalStaked()

        elif operation == 'calculateRate':
            if len(args) == 1:
                return calculateRate(args[0])
            raise Exception("Invalid argument length")

        # owner / admin methods

        elif operation == 'initializeOwners':
            return initialize_owners(ctx)

        elif operation == 'getOwners':
            return get_owners(ctx)

        elif operation == 'switchOwner':
            return switch_owner(ctx, args)

        elif operation == 'setAdmin':
            if len(args) == 1:
                return setAdminAddress(args[0])
            raise Exception("Invalid argument length")

        elif operation == 'getAdmin':
            if len(args) == 0:
                return getAdminAddress()
            raise Exception("Invalid argument length")

        elif operation == 'migrateStake':
            if len(args) == 2:
                return migrateStake(args[0], args[1])
            raise Exception("Invalid argument length")

        raise Exception("Unknown operation")

    return False


def calculateRate(duration):
    """
    Calculates the rate of return for a given duration in months.

    :param duration (int): A number of months between 1 and 24
    :return: rate (int): The determined rate for staking
    """

    if duration < 1 or duration > 24:
        raise Exception("Invalid duration")
    return (((((duration-1) * 100) / 23) * 50) + 2500) / 100


def sanitizeAddress(addr):
    """
    Checks whether a bytearray is of length 20
    Args:
        addr (bytearray): an address to be sanitized

    Returns:
        addr (bytearray): sanitized address

    """
    if addr and len(addr) == 20:
        return addr
    raise Exception("Invalid Address")

def sanitizeAmount(amount):
    """
    Determines if the amount to be staked is sane

    :param amount (int): The amount to be staked
    :return: (int): sanitized amount
    """

    if amount <= 0:
        raise Exception("Must be greater than zero")

    # We cannot allow stakes that are not divisible by 100000000
    # because this makes for some interesting issues when calculating
    # dividends
    if amount % STAKE_MODULUS != 0:
        raise Exception("Must be divisible by 100000000")

    return amount

def stakeTokens(args):
    """
    Stakes the given amount of tokens for a user with the given duration

    This must be called by the owner of the tokens to be staked.

    :param args (list): a list with the items [address, amountToStake, durationToStake]
    :return: (bool): success
    """

    addr = sanitizeAddress(args[0])
    amount = sanitizeAmount(args[1])
    duration = args[2]

    tx = GetScriptContainer()
    txHash = tx.Hash

    if not CheckWitness(addr):
        raise Exception("Must be signed by staker addr")

    if duration < 1 or duration > 24:
        raise Exception("Invalid duration")

    rate = calculateRate(duration)

    stake_id = concat(txHash, addr)

    if Get(ctx, stake_id) > 0:
        raise Exception("Already stake for this transaction and address")

    # We save the reverse of the stake id so it can be queried
    # with Storage.Find(addr).
    # We would reverse this to make queryable_stake_id the real stake_id
    # But this would break backwards compatibility with other systems.
    queryable_stake_id = concat(addr, txHash)

    contract_address = GetExecutingScriptHash()
    args = [addr, contract_address, amount]
    transferOfTokens = NEX_TOKEN_APPCALL_STAKE('transferFrom', args)

    if transferOfTokens:

        now = GetTime()
        end = now + (duration * SECONDS_PER_MONTH)
        stake = {
            'addr': addr,
            'stakeId': stake_id,
            'rate': rate,
            'amount': amount,
            'duration': duration,
            'startTime': now,
            'endTime': end,
            'complete': False
        }

        serialized_stake = Serialize(stake)

        Put(ctx, stake_id, serialized_stake)

        # In addition to saving the stake, we also save the stake id
        # In a queryable but cost effective manner
        Put(ctx, queryable_stake_id, stake_id)

        OnStake(stake_id, addr, amount, rate, now, end)

        return True

    raise Exception("Could not transfer tokens to staking contract")


def completeStake(stake_id):
    """
    Complete the stake specified by `stake_id`
    If the staking period is complete, this returns the staked tokens to the user, and dispatches a `complete` event

    Note that since this method can return tokens ONLY back to the address that originally staked the tokens, it can be called by anyone.

    :param args (list): a list with the first item being the address in question and the second being the stakeID
    :return: (bool): success
    """

    stake = getStakeById(stake_id)

    if not stake:
        raise Exception("Could not find stake")

    addr = stake['addr']
    amount = stake['amount']
    now = GetTime()
    end = stake['endTime']

    if end > now:
        raise Exception("Not eligible to unstake yet")

    if stake['complete']:
        raise Exception("Stake already completed")

    # transfer back to user
    contract_address = GetExecutingScriptHash()
    args = [contract_address, addr, amount]
    transferOfTokens = NEX_TOKEN_APPCALL_UNSTAKE('transfer', args)

    if transferOfTokens:

        stake['complete'] = True

        serialized_stake = Serialize(stake)
        Put(ctx, stake_id, serialized_stake)

        OnStakeComplete(stake_id, addr, amount)

        return True

    raise Exception("Could not complete stake")


def getStakeById(stake_id):
    """
    Returns a stake by id

    :param addr (bytearray): The stake id in question
    :return: dict: A stake object

    """

    stakeMapSerialized = Get(ctx, stake_id)

    if len(stakeMapSerialized):
        return Deserialize(stakeMapSerialized)
    return {}


def getStakesByAddress(addr):

    address = sanitizeAddress(addr)

    result_iter = Find(ctx, address)

    items = []
    while result_iter.IterNext():
        stake_id = result_iter.IterValue()
        stake = getStakeById(stake_id)
        items.append(stake)

    return items

def getTotalStaked():
    """
    Gets the total amount of tokens that are currently staked in the contract.
    :return: (int) Current amount of staked tokens
    """

    contractAddress = GetExecutingScriptHash()

    contract_balance = NEX_TOKEN_APPCALL_BALANCE('balanceOf', [contractAddress])

    return contract_balance

def migrateStake(addr, stake_id):

    if not isAdmin():
        raise Exception('Insufficient Priveleges')

    if Get(ctx, stake_id) > 0:
        raise Exception("Already stake for this transaction and address")

    legacy_stake = LEGACY_STAKE_QUERY('getStake', [addr, stake_id])

    if legacy_stake['complete']:
        raise Exception("Cannot migrate stake that has been completed")

    if legacy_stake:
        serialized_legacy_stake = Serialize(legacy_stake)

        queryable_stake_id = concat(addr, stake_id)

        Put(ctx, stake_id, serialized_legacy_stake)

        Put(ctx, queryable_stake_id, stake_id)

        OnLegacyStakeMigrated(stake_id, addr, legacy_stake['amount'], legacy_stake['rate'], legacy_stake['startTime'], legacy_stake['endTime'])

        return legacy_stake

    raise Exception("Could not find stake")

def setAdminAddress(addr):

    if check_owners(ctx, 3):

        address = sanitizeAddress(addr)

        Put(ctx, ADMIN_ADDR_PREFIX, address)

        return True

    raise Exception('Insufficient Permissions')

def getAdminAddress():
    return Get(ctx, ADMIN_ADDR_PREFIX)

def isAdmin():
    admin_address = getAdminAddress()

    return CheckWitness(admin_address)
