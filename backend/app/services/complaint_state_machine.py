"""Centralized Complaint State Machine (Phase 1.3.5).

Implements the formal state machine specification from docs/complaint-state-machine.md:
- States: SUBMITTED, ONGOING, PROCESSING, COMPLETED, REJECTED, DUPLICATE, CLOSED
- Primary Lifecycle: SUBMITTED -> ONGOING -> PROCESSING -> COMPLETED
- Terminal States: COMPLETED, REJECTED, DUPLICATE, CLOSED
- Strict transition rules, role-based authorization, required reasons, duplicate checking,
  department scoping, assignment enforcement, and fail-closed security.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.schemas.complaint import ComplaintStatus
from app.schemas.user import UserRole


@dataclass(frozen=True)
class StateTransitionRule:
    from_status: ComplaintStatus
    to_status: ComplaintStatus
    allowed_roles: frozenset[UserRole]
    requires_reason: bool = False
    requires_duplicate_of: bool = False
    requires_completion_summary: bool = False
    requires_assigned_staff: bool = False
    requires_department_match: bool = False


TERMINAL_STATES: frozenset[ComplaintStatus] = frozenset(
    {
        ComplaintStatus.COMPLETED,
        ComplaintStatus.REJECTED,
        ComplaintStatus.DUPLICATE,
        ComplaintStatus.CLOSED,
    }
)

# Transition specifications according to docs/complaint-state-machine.md
TRANSITION_RULES: dict[tuple[ComplaintStatus, ComplaintStatus], StateTransitionRule] = {
    # From SUBMITTED
    (ComplaintStatus.SUBMITTED, ComplaintStatus.ONGOING): StateTransitionRule(
        from_status=ComplaintStatus.SUBMITTED,
        to_status=ComplaintStatus.ONGOING,
        allowed_roles=frozenset({UserRole.ORGANIZATION_STAFF, UserRole.ORGANIZATION_ADMIN, UserRole.ADMIN}),
        requires_reason=False,
        requires_department_match=True,  # org_staff must belong to same department
    ),
    (ComplaintStatus.SUBMITTED, ComplaintStatus.REJECTED): StateTransitionRule(
        from_status=ComplaintStatus.SUBMITTED,
        to_status=ComplaintStatus.REJECTED,
        allowed_roles=frozenset({UserRole.ORGANIZATION_STAFF, UserRole.ORGANIZATION_ADMIN, UserRole.ADMIN}),
        requires_reason=True,
        requires_department_match=True,
    ),
    (ComplaintStatus.SUBMITTED, ComplaintStatus.DUPLICATE): StateTransitionRule(
        from_status=ComplaintStatus.SUBMITTED,
        to_status=ComplaintStatus.DUPLICATE,
        allowed_roles=frozenset({UserRole.ORGANIZATION_STAFF, UserRole.ORGANIZATION_ADMIN, UserRole.ADMIN}),
        requires_reason=True,
        requires_duplicate_of=True,
        requires_department_match=True,
    ),
    (ComplaintStatus.SUBMITTED, ComplaintStatus.CLOSED): StateTransitionRule(
        from_status=ComplaintStatus.SUBMITTED,
        to_status=ComplaintStatus.CLOSED,
        allowed_roles=frozenset({UserRole.ADMIN}),
        requires_reason=False,
    ),
    # From ONGOING
    (ComplaintStatus.ONGOING, ComplaintStatus.PROCESSING): StateTransitionRule(
        from_status=ComplaintStatus.ONGOING,
        to_status=ComplaintStatus.PROCESSING,
        allowed_roles=frozenset({UserRole.ORGANIZATION_STAFF, UserRole.ORGANIZATION_ADMIN, UserRole.ADMIN}),
        requires_reason=False,
        requires_assigned_staff=True,  # org_staff must be assigned to complaint
    ),
    (ComplaintStatus.ONGOING, ComplaintStatus.REJECTED): StateTransitionRule(
        from_status=ComplaintStatus.ONGOING,
        to_status=ComplaintStatus.REJECTED,
        allowed_roles=frozenset({UserRole.ORGANIZATION_STAFF, UserRole.ORGANIZATION_ADMIN, UserRole.ADMIN}),
        requires_reason=True,
        requires_assigned_staff=True,
    ),
    (ComplaintStatus.ONGOING, ComplaintStatus.DUPLICATE): StateTransitionRule(
        from_status=ComplaintStatus.ONGOING,
        to_status=ComplaintStatus.DUPLICATE,
        allowed_roles=frozenset({UserRole.ORGANIZATION_STAFF, UserRole.ORGANIZATION_ADMIN, UserRole.ADMIN}),
        requires_reason=True,
        requires_duplicate_of=True,
        requires_assigned_staff=True,
    ),
    (ComplaintStatus.ONGOING, ComplaintStatus.CLOSED): StateTransitionRule(
        from_status=ComplaintStatus.ONGOING,
        to_status=ComplaintStatus.CLOSED,
        allowed_roles=frozenset({UserRole.ADMIN}),
        requires_reason=False,
    ),
    # From PROCESSING
    (ComplaintStatus.PROCESSING, ComplaintStatus.ONGOING): StateTransitionRule(
        from_status=ComplaintStatus.PROCESSING,
        to_status=ComplaintStatus.ONGOING,
        allowed_roles=frozenset({UserRole.ORGANIZATION_STAFF, UserRole.ORGANIZATION_ADMIN, UserRole.ADMIN}),
        requires_reason=False,
        requires_assigned_staff=True,
    ),
    (ComplaintStatus.PROCESSING, ComplaintStatus.COMPLETED): StateTransitionRule(
        from_status=ComplaintStatus.PROCESSING,
        to_status=ComplaintStatus.COMPLETED,
        allowed_roles=frozenset({UserRole.ORGANIZATION_STAFF, UserRole.ORGANIZATION_ADMIN, UserRole.ADMIN}),
        requires_reason=True,  # Completion summary
        requires_completion_summary=True,
        requires_assigned_staff=True,
    ),
    (ComplaintStatus.PROCESSING, ComplaintStatus.REJECTED): StateTransitionRule(
        from_status=ComplaintStatus.PROCESSING,
        to_status=ComplaintStatus.REJECTED,
        allowed_roles=frozenset({UserRole.ORGANIZATION_STAFF, UserRole.ORGANIZATION_ADMIN, UserRole.ADMIN}),
        requires_reason=True,
        requires_assigned_staff=True,
    ),
    (ComplaintStatus.PROCESSING, ComplaintStatus.DUPLICATE): StateTransitionRule(
        from_status=ComplaintStatus.PROCESSING,
        to_status=ComplaintStatus.DUPLICATE,
        allowed_roles=frozenset({UserRole.ORGANIZATION_STAFF, UserRole.ORGANIZATION_ADMIN, UserRole.ADMIN}),
        requires_reason=True,
        requires_duplicate_of=True,
        requires_assigned_staff=True,
    ),
    (ComplaintStatus.PROCESSING, ComplaintStatus.CLOSED): StateTransitionRule(
        from_status=ComplaintStatus.PROCESSING,
        to_status=ComplaintStatus.CLOSED,
        allowed_roles=frozenset({UserRole.ADMIN}),
        requires_reason=False,
    ),
}


class ComplaintStateMachine:
    """Central validator and rule manager for complaint status transitions."""

    @classmethod
    def get_rule(
        cls, from_status: ComplaintStatus, to_status: ComplaintStatus
    ) -> StateTransitionRule | None:
        """Return the transition rule if defined, else None."""
        return TRANSITION_RULES.get((from_status, to_status))

    @classmethod
    def is_terminal(cls, status: ComplaintStatus) -> bool:
        """Check if a state is terminal."""
        return status in TERMINAL_STATES

    @classmethod
    def can_transition(
        cls,
        from_status: ComplaintStatus,
        to_status: ComplaintStatus,
        actor_role: UserRole,
    ) -> bool:
        """Check if transition exists and role is permitted."""
        rule = cls.get_rule(from_status, to_status)
        if rule is None:
            return False
        return actor_role in rule.allowed_roles
