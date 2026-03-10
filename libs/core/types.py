from decimal import Decimal
from typing import TypeAlias

ProfileId: TypeAlias = str
SymbolPair: TypeAlias = str
ExchangeName: TypeAlias = str
Timestamp: TypeAlias = int  # microsecond UTC timestamp
Price: TypeAlias = Decimal
Quantity: TypeAlias = Decimal
Percentage: TypeAlias = Decimal
