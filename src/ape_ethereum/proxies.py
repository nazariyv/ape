from enum import IntEnum, auto

from ethpm_types import ContractType
from lazyasd import LazyObject  # type: ignore

from ape.api.networks import ProxyInfoAPI
from ape.contracts import ContractContainer

MINIMAL_PROXY_BYTES = (
    "0x3d602d80600a3d3981f3363d3d373d3d3d363d73"
    "bebebebebebebebebebebebebebebebebebebebe5af43d82803e903d91602b57fd5bf3"
)


class ProxyType(IntEnum):
    # https://eips.ethereum.org/EIPS/eip-1167
    Minimal = auto()  # eip-1167 minimal proxy contract

    # https://eips.ethereum.org/EIPS/eip-1967
    Standard = auto()  # eip-1967 standard proxy storage slots
    Beacon = auto()  # eip-1967 beacon proxy

    # https://eips.ethereum.org/EIPS/eip-1822
    UUPS = auto()  # # eip-1822 universal upgradeable proxy standard

    # https://github.com/vyperlang/vyper/blob/v0.2.8/vyper/functions/functions.py#L1428
    Vyper = auto()  # vyper <0.2.9 create_forwarder_to
    # https://github.com/vyperlang/vyper/blob/v0.1.0-beta.4/vyper/functions/functions.py#L633
    VyperBeta = auto()  # vyper 0.1-beta

    # https://github.com/0xSplits/splits-contracts/blob/main/contracts/libraries/Clones.sol
    Clones = auto()  # 0xsplits clones

    # https://github.com/safe-global/safe-contracts/blob/main/contracts/proxies/SafeProxy.sol
    GnosisSafe = auto()

    # https://github.com/OpenZeppelin/openzeppelin-labs/blob/master/initializer_contracts/contracts/UpgradeabilityProxy.sol
    OpenZeppelin = auto()  # openzeppelin upgradeability proxy

    # https://eips.ethereum.org/EIPS/eip-897
    Delegate = auto()  # eip-897 delegate proxy

    # https://medium.com/coinmonks/the-more-minimal-proxy-5756ae08ee48
    ZeroAge = auto()  # a more-minimal proxy

    # https://github.com/wighawag/clones-with-immutable-args/blob/master/src/ClonesWithImmutableArgs.sol
    # https://github.com/emo-eth/create2-clones-with-immutable-args/blob/main/src/Create2ClonesWithImmutableArgs.sol
    CWIA = auto()  # clones with immutable args

    # https://github.com/Vectorized/solady/blob/main/src/utils/LibClone.sol
    SoladyPush0 = auto()  # solady push0 minimal proxy
    SoladyCWIA = auto()  # clones with immutable args with a receive method

    # https://github.com/sudoswap/lssvm2/blob/main/src/lib/LSSVMPairCloner.sol
    SudoswapCWIA = auto()  # a variant used in sudoswap


class ProxyInfo(ProxyInfoAPI):
    type: ProxyType


def _make_minimal_proxy() -> ContractContainer:
    bytecode = {"bytecode": MINIMAL_PROXY_BYTES}
    contract_type = ContractType(abi=[], deploymentBytecode=bytecode)
    return ContractContainer(contract_type=contract_type)


minimal_proxy = LazyObject(_make_minimal_proxy, globals(), "minimal_proxy")
