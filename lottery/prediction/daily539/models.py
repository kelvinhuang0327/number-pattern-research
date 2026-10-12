"""Domain models for Daily 539 prediction generate vertical."""
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

@dataclass(frozen=True)
class Daily539GenerateBetRequest:
    """Request contract for Daily 539 single bet generation."""
    strategy_id: str
    lottery_type: str = "DAILY_539"
    history: List[dict] = field(default_factory=list)

@dataclass(frozen=True)
class Daily539GenerateBetResult:
    """Result contract for Daily 539 single bet generation."""
    strategy_id: str
    lottery_type: str
    numbers: List[int]
    special: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
