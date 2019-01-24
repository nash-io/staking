"""
NEX Staking
===================================

Author: Thomas Saunders
Email: tom@neonexchange.org

Date: Oct 12 2018

"""
from boa.interop.Neo.Runtime import GetTrigger, CheckWitness, GetTime, Deserialize, Serialize
from boa.interop.System.ExecutionEngine import GetExecutingScriptHash, GetScriptContainer
from boa.interop.Neo.TriggerType import Application, Verification
from boa.interop.Neo.Storage import *
from boa.interop.Neo.Action import RegisterAction
from boa.interop.Neo.App import DynamicAppCall
from boa.interop.Neo.Transaction import *
from boa.builtins import concat
from nash.owner import *
from nash.whitelist import *

ctx = GetContext()

OnStake = RegisterAction("onStake", "stakeID", "addr", "amount", "rate", "start", "expiration")
OnStakeComplete = RegisterAction("onStakeComplete", "stakeID", "addr")

STAKE_CONTRACT_KEY = 'stakingContract'
STAKE_ADDR_KEY = 'addrStakes'

SECONDS_PER_MONTH = 2629743

STAKE_MODULUS = 100000000

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
        # Only owners can transfer NEO or GAS out of the contract
        if check_owners(ctx, 3):
            return True
        return False

    elif trigger == Application():

        if operation == 'stake':
            if len(args) == 3:
                return stakeTokens(args)
            raise Exception("Invalid argument length")

        elif operation == 'completeStake':
            if len(args) == 2:
                return completeStake(args)
            raise Exception("Invalid argument length")

        elif operation == 'getStake':
            if len(args) == 2:
                return getStake(args)
            raise Exception("Invalid argument length")

        elif operation == 'getStakesForAddr':
            if len(args) == 1:
                return getStakesForAddr(args[0])
            raise Exception("Invalid argument length")

        elif operation == 'totalStaked':
            return getTotalStaked()

        elif operation == 'calculateRate':
            if len(args) == 1:
                return calculateRate(args[0])
            raise Exception("Invalid argument length")

        # owner / admin methods
        elif operation == 'setStakeTokenContract':
            return setStakingContract(args)

        elif operation == 'initializeOwners':
            return initialize_owners(ctx)

        elif operation == 'getOwners':
            return get_owners(ctx)

        elif operation == 'switchOwner':
            return switch_owner(ctx, args)

        elif operation == 'addWhitelistAdmin':
            if len(args) == 1:
                return addWhitelistAdmin(args[0])
            raise Exception("Invalid Arguments")

        elif operation == 'removeWhitelistAdmin':
            if len(args) == 1:
                return removeWhitelistAdmin(args[0])
            raise Exception("Invalid Arguments")

        elif operation == 'addToWhitelist':
            if len(args) == 1:
                return addToWhitelist(args[0])
            raise Exception("Invalid Arguments")

        elif operation == 'removeFromWhitelist':
            if len(args) == 1:
                return removeFromWhitelist(args[0])
            raise Exception("Invalid Arguments")

        elif operation == 'getWhitelistAdmins':
            return getWhitelistAdmins()

        elif operation == 'getKYCWhitelistStatus':
            if len(args) == 1:
                return isWhitelisted(args[0])
            raise Exception("Invalid Arguments")

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

    addr = args[0]
    amount = sanitizeAmount(args[1])
    duration = args[2]

    tx = GetScriptContainer()
    txHash = tx.Hash

    if not isWhitelisted(addr):
        raise Exception("Address must be whitelisted")

    if not CheckWitness(addr):
        raise Exception("Must be signed by staker addr")

    if duration < 1 or duration > 24:
        raise Exception("Invalid duration")

    rate = calculateRate(duration)

    stakeId = concat(txHash, addr)

    if Get(ctx, stakeId) > 0:
        raise Exception("Already stake for this transaction and address")

    args = [addr, GetExecutingScriptHash(), amount]

    transferOfTokens = DynamicAppCall(getStakingContract(), 'transferFrom', args)

    if transferOfTokens:

        now = GetTime()
        end = now + (duration * SECONDS_PER_MONTH)
        stake = {
            'addr': addr,
            'stakeId': stakeId,
            'rate': rate,
            'amount': amount,
            'duration': duration,
            'startTime': now,
            'endTime': end,
            'complete': False
        }

        addrStakeKey = concat(STAKE_ADDR_KEY, addr)

        currentStakes = Get(ctx, addrStakeKey)

        if len(currentStakes) < 1:
            currentStakes = {}
        else:
            currentStakes = Deserialize(currentStakes)

        currentStakes[stakeId] = stake

        Put(ctx, stakeId, 1)

        Put(ctx, addrStakeKey, Serialize(currentStakes))

        OnStake(stakeId, addr, amount, rate, now, end)

        return True

    raise Exception("Could not transfer tokens to staking contract")


def completeStake(args):
    """
    Complete the stake specified by `stakeID`
    If the staking period is complete, this returns the staked tokens to the user, and dispatches a `complete` event

    Note that since this method can return tokens ONLY back to the address that originally staked the tokens, it can be called by anyone.

    :param args (list): a list with the first item being the address in question and the second being the stakeID
    :return: (bool): success
    """

    stakes = getStakesForAddr(args[0])
    stakeID = args[1]
    stake = stakes[stakeID]

    if not stake:
        raise Exception("Could not find stake")

    addr = stake['addr']
    amount = stake['amount']
    now = GetTime()

    if stake['endTime'] > now:
        raise Exception("Not eligible to unstake yet")

    if stake['complete']:
        raise Exception("Stake already completed")

    # transfer back to user
    args = [GetExecutingScriptHash(), addr, amount]

    transferOfTokens = DynamicAppCall(getStakingContract(), 'transfer', args)

    if transferOfTokens:

        stake['completed'] = True

        stakes[stakeID] = stake
        addrStakeKey = concat(STAKE_ADDR_KEY, addr)

        Put(ctx, addrStakeKey, Serialize(stakes))

        OnStakeComplete(stakeID, addr)

        return True

    return False


def getStakesForAddr(addr):
    """
    Returns a dictionary of all stakes for an address

    :param addr (bytearray): The address in question
    :return: dict: A dictionary of stake objects with the stakeIDs as the keys

    """

    addrStakeKey = concat(STAKE_ADDR_KEY, addr)
    stakeMapSerialized = Get(ctx, addrStakeKey)

    if len(stakeMapSerialized):
        return Deserialize(stakeMapSerialized)
    return {}


def getStake(args):
    """
    Returns details on a given stake for an address

    :param args (list): a list with the first item being the address in question and the second being the stakeID
    :return: dict: A dictionary with the format:
                   {
                        'addr': addr,
                        'stakeId': stakeId,
                        'rate': rate,
                        'amount': amount,
                        'duration': duration,
                        'startTime': now,
                        'endTime': end,
                        'complete':bool
                    }
    """
    addr = args[0]
    stakeId = args[1]

    stakes = getStakesForAddr(addr)

    return stakes[stakeId]

def getTotalStaked():
    """
    Gets the total amount of tokens that are currently staked in the contract.
    :return: (int) Current amount of staked tokens
    """

    tokenContract = getStakingContract()
    contractAddress = GetExecutingScriptHash()
    args = [contractAddress]
    balance = DynamicAppCall(tokenContract, 'balanceOf', args)

    return balance

def setStakingContract(args):
    """
    Sets the token which will be used for staking

    :param args: (list) a liist containing one item, namely the new staking contract address.
    :return: (bool) success
    """

    # Check if contract is already set.
    # Would be bad if this can be changed when
    # tokens are already staked.
    contract = Get(ctx, STAKE_CONTRACT_KEY)
    if contract:
        raise Exception("Cannot set staking contract, already set.")

    if check_owners(ctx, 3):
        contract = args[0]
        if len(contract) == 20:
            Put(ctx, STAKE_CONTRACT_KEY, contract)
            return True
    return False

def getStakingContract():
    """
    Gets the contract address of the token which is being staked.
    :return: (bytearray) address
    """

    contract = Get(ctx, STAKE_CONTRACT_KEY)
    if len(contract) == 20:
        return contract
    raise Exception("Staking contract not set")
