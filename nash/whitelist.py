from boa.interop.Neo.Runtime import Serialize, Deserialize, CheckWitness
from boa.interop.Neo.Action import RegisterAction
from boa.interop.Neo.Storage import Get, Put, Delete, GetContext
from boa.builtins import concat

from nash.owner import check_owners

# Whitelist events
onAddedToWhitelist = RegisterAction('OnAddedToWhitelist', 'address')
onRemovedFromWhitelist = RegisterAction('OnRemovedFromWhitelist', 'address')
onAddedWhitelistAdmin = RegisterAction('OnAddedWhitelistAdmin', 'address')
onRemovedWhitelistAdmin = RegisterAction('OnRemovedWhitelistAdmin', 'address')

# Whitelist prefixes
Prefix_KYCAccount = b'accountKycOk'

KYC_Admin_Key = b'kycAdminList'

ctx = GetContext()


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

def getWhitelistAdmins():
    """
    Gets a list of current KYC admins

    :return: (list): a list of kyc admins
    """
    admins_serialized = Get(ctx, KYC_Admin_Key)
    if len(admins_serialized):
        return Deserialize(admins_serialized)
    return []

def addWhitelistAdmin(address):
    """
    Adds a whitelist ( kyc ) admin

    :param address (bytearray): The address to make a whitelist admin
    :return: (bool): success
    """
    address = sanitizeAddress(address)
    if check_owners(ctx, 1):
        admins = getWhitelistAdmins()
        admins.append(address)
        serialized_admins = Serialize(admins)
        Put(ctx, KYC_Admin_Key, serialized_admins)
        onAddedWhitelistAdmin(address)
        return True
    return False

def removeWhitelistAdmin(address):
    """
    Removes a whitelist ( kyc ) admin

    :param address (bytearray): The address to un-make a whitelist admin
    :return: (bool): success
    """

    address = sanitizeAddress(address)
    if check_owners(ctx, 1):
        admins = getWhitelistAdmins()
        new_admins = []
        for admin in admins:
            if admin != address:
                new_admins.append(admin)
        serialized_admins = Serialize(new_admins)
        Put(ctx, KYC_Admin_Key, serialized_admins)
        onRemovedWhitelistAdmin(address)
        return True
    return False


def hasWhitelistAdminPermission():
    """
    Checks whether the current invoker is an admin
    :return: (bool): success
    """

    serialized_admins = Get(ctx, KYC_Admin_Key)
    admin_list = Deserialize(serialized_admins)

    for admin in admin_list:
        if CheckWitness(admin):
            return True
    return False

def addToWhitelist(addr):
    """
    Adds an address to the whitelist

    :param address (bytearray): The address to make a whitelist
    :return: (bool): success
    """

    addr = sanitizeAddress(addr)

    if not hasWhitelistAdminPermission():
        raise Exception("Insufficient priviledges")

    kyc_key = concat(Prefix_KYCAccount, addr)
    Put(ctx, kyc_key, True)
    onAddedToWhitelist(addr)
    return True


def removeFromWhitelist(addr):
    """
    Removes an address from the whitelist

    :param address (bytearray): The address to make a whitelist
    :return: (bool): success
    """

    addr = sanitizeAddress(addr)

    if not hasWhitelistAdminPermission():
        raise Exception("Insufficient priviledges")

    kyc_key = concat(Prefix_KYCAccount, addr)
    Delete(ctx, kyc_key)
    onRemovedFromWhitelist(addr)
    return True


def isWhitelisted(addr):
    """
    Checks the whitelist status of an address

    :param address (bytearray): The address to check
    :return: (bool): success
    """

    kyc_key = concat(Prefix_KYCAccount, addr)
    return Get(ctx, kyc_key)
