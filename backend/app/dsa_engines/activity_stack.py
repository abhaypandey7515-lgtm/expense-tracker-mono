"""
LIFO stack behind Undo.

Every expense or payment pushes a frame (persisted in the `actions` table). Undo rebuilds the
stack from the group's not-yet-undone actions in time order and pops the top frame.
"""

from dataclasses import dataclass
from enum import Enum
from typing import List, Optional


class ActionKind(str, Enum):
    EXPENSE = "expense"
    SETTLEMENT = "settlement"


@dataclass
class StackFrame:
    id: str
    group_id: str
    kind: ActionKind
    ref_id: str


class ActivityStack:
    def __init__(self) -> None:
        self._stack: List[StackFrame] = []

    def push(self, frame: StackFrame) -> None:          # O(1)
        self._stack.append(frame)

    def pop(self) -> Optional[StackFrame]:              # O(1)
        return self._stack.pop() if self._stack else None

    def peek(self) -> Optional[StackFrame]:
        return self._stack[-1] if self._stack else None

    def is_empty(self) -> bool:
        return not self._stack

    def size(self) -> int:
        return len(self._stack)

    def to_list(self) -> List[StackFrame]:
        """Most recent first."""
        return list(reversed(self._stack))
