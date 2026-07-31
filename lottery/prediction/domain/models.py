"""Domain models for lottery prediction generate vertical."""
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

MAX_BATCH_SIZE = 20

@dataclass(frozen=True)
class GenerateBetRequest:
    """Request contract for single bet generation."""
    strategy_id: str
    lottery_type: str = "BIG_LOTTO"
    history: List[dict] = field(default_factory=list)

@dataclass(frozen=True)
class GenerateBetResult:
    """Result contract for single bet generation."""
    strategy_id: str
    lottery_type: str
    numbers: List[int]
    special: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class GenerateBatchRequest:
    """Request contract for batch bet generation."""
    strategy_id: str
    count: int
    lottery_type: str = "BIG_LOTTO"
    history: List[dict] = field(default_factory=list)
