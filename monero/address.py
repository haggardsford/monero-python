from binascii import hexlify, unhexlify
import re
import struct
from sha3 import keccak_256

from . import base58
from . import numbers

_ADDR_REGEX = re.compile(r'^[123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz]{95}$')
_IADDR_REGEX = re.compile(r'^[123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz]{106}$')


class Address(object):
    """Monero address.

    Address of this class is the master address for a :class:`Wallet <monero.wallet.Wallet>`.

    :param address: a Monero address as string-like object
    :param label: a label for the address (defaults to `None`)
    """
    label = None
    _valid_netbytes = (18, 53)
    # NOTE: _valid_netbytes order is (real, testnet)

    def __init__(self, addr, label=None):
        addr = str(addr)
        if not _ADDR_REGEX.match(addr):
            raise ValueError("Address must be 95 characters long base58-encoded string, "
                "is {addr} ({len} chars length)".format(addr=addr, len=len(addr)))
        self._decode(addr)
        self.label = label or self.label

    def _decode(self, address):
        self._decoded = bytearray(unhexlify(base58.decode(address)))
        checksum = self._decoded[-4:]
        if checksum != keccak_256(self._decoded[:-4]).digest()[:4]:
            raise ValueError("Invalid checksum in address {}".format(address))
        if self._decoded[0] not in self._valid_netbytes:
            raise ValueError("Invalid address netbyte {nb}. Allowed values are: {allowed}".format(
                nb=self._decoded[0],
                allowed=", ".join(map(lambda b: '%02x' % b, self._valid_netbytes))))

    def is_testnet(self):
        """Returns `True` if the address belongs to testnet.

        :rtype: bool
        """
        return self._decoded[0] == self._valid_netbytes[1]

    def view_key(self):
        """Returns public view key.

        :rtype: str
        """
        return hexlify(self._decoded[33:65]).decode()

    def spend_key(self):
        """Returns public spend key.

        :rtype: str
        """
        return hexlify(self._decoded[1:33]).decode()

    def with_payment_id(self, payment_id=0):
        """Integrates payment id into the address.

        :param payment_id: int, hexadecimal string or :class:`PaymentID <monero.numbers.PaymentID>`
                    (max 64-bit long)

        :rtype: `IntegratedAddress`
        :raises: `TypeError` if the payment id is too long
        """
        payment_id = numbers.PaymentID(payment_id)
        if not payment_id.is_short():
            raise TypeError("Payment ID {0} has more than 64 bits and cannot be integrated".format(payment_id))
        prefix = 54 if self.is_testnet() else 19
        data = bytearray([prefix]) + self._decoded[1:65] + struct.pack('>Q', int(payment_id))
        checksum = bytearray(keccak_256(data).digest()[:4])
        return IntegratedAddress(base58.encode(hexlify(data + checksum)))

    def __repr__(self):
        return base58.encode(hexlify(self._decoded))

    def __eq__(self, other):
        if isinstance(other, Address):
            return str(self) == str(other)
        if isinstance(other, str):
            return str(self) == other
        return super(Address, self).__eq__(other)


class SubAddress(Address):
    """Monero subaddress.

    Any type of address which is not the master one for a wallet.
    """

    _valid_netbytes = (42, 63)

    def with_payment_id(self, _):
        raise TypeError("SubAddress cannot be integrated with payment ID")


class IntegratedAddress(Address):
    """Monero integrated address.

    A master address integrated with payment id (short one, max 64 bit).
    """

    _valid_netbytes = (19, 54)

    def __init__(self, address):
        address = str(address)
        if not _IADDR_REGEX.match(address):
            raise ValueError("Integrated address must be 106 characters long base58-encoded string, "
                "is {addr} ({len} chars length)".format(addr=address, len=len(address)))
        self._decode(address)

    def payment_id(self):
        """Returns the integrated payment id.

        :rtype: :class:`PaymentID <monero.numbers.PaymentID>`
        """
        return numbers.PaymentID(hexlify(self._decoded[65:-4]).decode())

    def base_address(self):
        """Returns the base address without payment id.
        :rtype: :class:`Address`
        """
        prefix = 53 if self.is_testnet() else 18
        data = bytearray([prefix]) + self._decoded[1:65]
        checksum = keccak_256(data).digest()[:4]
        return Address(base58.encode(hexlify(data + checksum)))


def address(addr, label=None):
    """Discover the proper class and return instance for a given Monero address.

    :param addr: the address as a string-like object
    :param label: a label for the address (defaults to `None`)

    :rtype: :class:`Address`, :class:`SubAddress` or :class:`IntegratedAddress`
    """
    addr = str(addr)
    if _ADDR_REGEX.match(addr):
        netbyte = bytearray(unhexlify(base58.decode(addr)))[0]
        if netbyte in Address._valid_netbytes:
            return Address(addr, label=label)
        elif netbyte in SubAddress._valid_netbytes:
            return SubAddress(addr, label=label)
        raise ValueError("Invalid address netbyte {nb:x}. Allowed values are: {allowed}".format(
            nb=netbyte,
            allowed=", ".join(map(
                lambda b: '%02x' % b,
                sorted(Address._valid_netbytes + SubAddress._valid_netbytes)))))
    elif _IADDR_REGEX.match(addr):
        return IntegratedAddress(addr)
    raise ValueError("Address must be either 95 or 106 characters long base58-encoded string, "
        "is {addr} ({len} chars length)".format(addr=addr, len=len(addr)))
