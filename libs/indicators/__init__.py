from typing import Any, Dict

from ._adx import ADXCalculator
from ._atr import ATRCalculator
from ._bollinger import BollingerCalculator, BollingerResult
from ._choppiness import ChoppinessCalculator
from ._ema import EMACalculator
from ._hurst import HurstCalculator
from ._keltner import KeltnerCalculator, KeltnerResult
from ._macd import MACDCalculator, MACDResult
from ._obv import OBVCalculator
from ._regime import SimpleRegimeClassifier
from ._rsi import RSICalculator
from ._rvol import RVOLCalculator
from ._vwap import VWAPCalculator
from ._zscore import ZScoreCalculator


class IndicatorSet:
    __slots__ = (
        "rsi",
        "macd",
        "atr",
        "regime",
        "adx",
        "bollinger",
        "obv",
        "choppiness",
        "vwap",
        "keltner",
        "rvol",
        "zscore",
        "hurst",
    )

    def __init__(
        self,
        rsi: RSICalculator,
        macd: MACDCalculator,
        atr: ATRCalculator,
        regime: SimpleRegimeClassifier,
        adx: ADXCalculator = None,
        bollinger: BollingerCalculator = None,
        obv: OBVCalculator = None,
        choppiness: ChoppinessCalculator = None,
        vwap: VWAPCalculator = None,
        keltner: KeltnerCalculator = None,
        rvol: RVOLCalculator = None,
        zscore: ZScoreCalculator = None,
        hurst: HurstCalculator = None,
    ):
        self.rsi = rsi
        self.macd = macd
        self.atr = atr
        self.regime = regime
        self.adx = adx
        self.bollinger = bollinger
        self.obv = obv
        self.choppiness = choppiness
        self.vwap = vwap
        self.keltner = keltner
        self.rvol = rvol
        self.zscore = zscore
        self.hurst = hurst


def create_indicator_set(profile_config: Dict[str, Any] = None) -> IndicatorSet:
    # Later profile_config allows customization of periods
    return IndicatorSet(
        rsi=RSICalculator(),
        macd=MACDCalculator(),
        atr=ATRCalculator(),
        regime=SimpleRegimeClassifier(),
        adx=ADXCalculator(),
        bollinger=BollingerCalculator(),
        obv=OBVCalculator(),
        choppiness=ChoppinessCalculator(),
        vwap=VWAPCalculator(),
        keltner=KeltnerCalculator(),
        rvol=RVOLCalculator(),
        zscore=ZScoreCalculator(),
        hurst=HurstCalculator(),
    )


__all__ = [
    "RSICalculator",
    "EMACalculator",
    "MACDCalculator",
    "MACDResult",
    "ATRCalculator",
    "SimpleRegimeClassifier",
    "ADXCalculator",
    "BollingerCalculator",
    "BollingerResult",
    "OBVCalculator",
    "ChoppinessCalculator",
    "VWAPCalculator",
    "KeltnerCalculator",
    "KeltnerResult",
    "RVOLCalculator",
    "ZScoreCalculator",
    "HurstCalculator",
    "IndicatorSet",
    "create_indicator_set",
]
