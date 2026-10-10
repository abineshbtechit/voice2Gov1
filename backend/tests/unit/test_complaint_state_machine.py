"""Phase 1.3.5 — Complaint state machine unit tests.

Tests the central ComplaintStateMachine rules:
- All valid transitions
- All invalid transitions (skips, backwards, disallowed)
- Terminal state immutability
- Role authorization matrix
- Reason requirements
- Duplicate reference requirements
- Assignment requirements
- Department match requirements
"""

import pytest

from app.schemas.complaint import ComplaintStatus
from app.schemas.user import UserRole
from app.services.complaint_state_machine import TERMINAL_STATES, ComplaintStateMachine


class TestTerminalStates:
    def test_terminal_states_defined(self) -> None:
        expected = {
            ComplaintStatus.COMPLETED,
            ComplaintStatus.REJECTED,
            ComplaintStatus.DUPLICATE,
            ComplaintStatus.CLOSED,
        }
        assert TERMINAL_STATES == expected

    @pytest.mark.parametrize("status", list(TERMINAL_STATES))
    def test_is_terminal_true(self, status: ComplaintStatus) -> None:
        assert ComplaintStateMachine.is_terminal(status) is True

    @pytest.mark.parametrize(
        "status",
        [ComplaintStatus.SUBMITTED, ComplaintStatus.ONGOING, ComplaintStatus.PROCESSING],
    )
    def test_is_terminal_false(self, status: ComplaintStatus) -> None:
        assert ComplaintStateMachine.is_terminal(status) is False


class TestValidTransitions:
    @pytest.mark.parametrize(
        ("from_s", "to_s", "role"),
        [
            # SUBMITTED
            (ComplaintStatus.SUBMITTED, ComplaintStatus.ONGOING, UserRole.ORGANIZATION_STAFF),
            (ComplaintStatus.SUBMITTED, ComplaintStatus.ONGOING, UserRole.ORGANIZATION_ADMIN),
            (ComplaintStatus.SUBMITTED, ComplaintStatus.ONGOING, UserRole.ADMIN),
            (ComplaintStatus.SUBMITTED, ComplaintStatus.REJECTED, UserRole.ORGANIZATION_STAFF),
            (ComplaintStatus.SUBMITTED, ComplaintStatus.REJECTED, UserRole.ORGANIZATION_ADMIN),
            (ComplaintStatus.SUBMITTED, ComplaintStatus.REJECTED, UserRole.ADMIN),
            (ComplaintStatus.SUBMITTED, ComplaintStatus.DUPLICATE, UserRole.ORGANIZATION_STAFF),
            (ComplaintStatus.SUBMITTED, ComplaintStatus.DUPLICATE, UserRole.ORGANIZATION_ADMIN),
            (ComplaintStatus.SUBMITTED, ComplaintStatus.DUPLICATE, UserRole.ADMIN),
            (ComplaintStatus.SUBMITTED, ComplaintStatus.CLOSED, UserRole.ADMIN),
            # ONGOING
            (ComplaintStatus.ONGOING, ComplaintStatus.PROCESSING, UserRole.ORGANIZATION_STAFF),
            (ComplaintStatus.ONGOING, ComplaintStatus.PROCESSING, UserRole.ORGANIZATION_ADMIN),
            (ComplaintStatus.ONGOING, ComplaintStatus.PROCESSING, UserRole.ADMIN),
            (ComplaintStatus.ONGOING, ComplaintStatus.REJECTED, UserRole.ORGANIZATION_STAFF),
            (ComplaintStatus.ONGOING, ComplaintStatus.REJECTED, UserRole.ORGANIZATION_ADMIN),
            (ComplaintStatus.ONGOING, ComplaintStatus.REJECTED, UserRole.ADMIN),
            (ComplaintStatus.ONGOING, ComplaintStatus.DUPLICATE, UserRole.ORGANIZATION_STAFF),
            (ComplaintStatus.ONGOING, ComplaintStatus.DUPLICATE, UserRole.ORGANIZATION_ADMIN),
            (ComplaintStatus.ONGOING, ComplaintStatus.DUPLICATE, UserRole.ADMIN),
            (ComplaintStatus.ONGOING, ComplaintStatus.CLOSED, UserRole.ADMIN),
            # PROCESSING
            (ComplaintStatus.PROCESSING, ComplaintStatus.ONGOING, UserRole.ORGANIZATION_STAFF),
            (ComplaintStatus.PROCESSING, ComplaintStatus.ONGOING, UserRole.ORGANIZATION_ADMIN),
            (ComplaintStatus.PROCESSING, ComplaintStatus.ONGOING, UserRole.ADMIN),
            (ComplaintStatus.PROCESSING, ComplaintStatus.COMPLETED, UserRole.ORGANIZATION_STAFF),
            (ComplaintStatus.PROCESSING, ComplaintStatus.COMPLETED, UserRole.ORGANIZATION_ADMIN),
            (ComplaintStatus.PROCESSING, ComplaintStatus.COMPLETED, UserRole.ADMIN),
            (ComplaintStatus.PROCESSING, ComplaintStatus.REJECTED, UserRole.ORGANIZATION_STAFF),
            (ComplaintStatus.PROCESSING, ComplaintStatus.REJECTED, UserRole.ORGANIZATION_ADMIN),
            (ComplaintStatus.PROCESSING, ComplaintStatus.REJECTED, UserRole.ADMIN),
            (ComplaintStatus.PROCESSING, ComplaintStatus.DUPLICATE, UserRole.ORGANIZATION_STAFF),
            (ComplaintStatus.PROCESSING, ComplaintStatus.DUPLICATE, UserRole.ORGANIZATION_ADMIN),
            (ComplaintStatus.PROCESSING, ComplaintStatus.DUPLICATE, UserRole.ADMIN),
            (ComplaintStatus.PROCESSING, ComplaintStatus.CLOSED, UserRole.ADMIN),
        ],
    )
    def test_can_transition_allowed(
        self, from_s: ComplaintStatus, to_s: ComplaintStatus, role: UserRole
    ) -> None:
        assert ComplaintStateMachine.can_transition(from_s, to_s, role) is True


class TestForbiddenTransitions:
    @pytest.mark.parametrize(
        ("from_s", "to_s"),
        [
            # Skip transitions
            (ComplaintStatus.SUBMITTED, ComplaintStatus.PROCESSING),
            (ComplaintStatus.SUBMITTED, ComplaintStatus.COMPLETED),
            (ComplaintStatus.ONGOING, ComplaintStatus.COMPLETED),
            # Backward transitions to SUBMITTED
            (ComplaintStatus.ONGOING, ComplaintStatus.SUBMITTED),
            (ComplaintStatus.PROCESSING, ComplaintStatus.SUBMITTED),
            # Terminal states to anything
            (ComplaintStatus.COMPLETED, ComplaintStatus.SUBMITTED),
            (ComplaintStatus.COMPLETED, ComplaintStatus.ONGOING),
            (ComplaintStatus.COMPLETED, ComplaintStatus.PROCESSING),
            (ComplaintStatus.COMPLETED, ComplaintStatus.CLOSED),
            (ComplaintStatus.REJECTED, ComplaintStatus.SUBMITTED),
            (ComplaintStatus.REJECTED, ComplaintStatus.ONGOING),
            (ComplaintStatus.REJECTED, ComplaintStatus.PROCESSING),
            (ComplaintStatus.DUPLICATE, ComplaintStatus.SUBMITTED),
            (ComplaintStatus.DUPLICATE, ComplaintStatus.ONGOING),
            (ComplaintStatus.CLOSED, ComplaintStatus.SUBMITTED),
            (ComplaintStatus.CLOSED, ComplaintStatus.ONGOING),
            (ComplaintStatus.CLOSED, ComplaintStatus.PROCESSING),
        ],
    )
    @pytest.mark.parametrize("role", list(UserRole))
    def test_forbidden_transitions_blocked_for_all_roles(
        self, from_s: ComplaintStatus, to_s: ComplaintStatus, role: UserRole
    ) -> None:
        assert ComplaintStateMachine.can_transition(from_s, to_s, role) is False


class TestRoleRestrictions:
    @pytest.mark.parametrize(
        ("from_s", "to_s"),
        [
            (ComplaintStatus.SUBMITTED, ComplaintStatus.ONGOING),
            (ComplaintStatus.SUBMITTED, ComplaintStatus.REJECTED),
            (ComplaintStatus.SUBMITTED, ComplaintStatus.DUPLICATE),
            (ComplaintStatus.ONGOING, ComplaintStatus.PROCESSING),
            (ComplaintStatus.PROCESSING, ComplaintStatus.COMPLETED),
        ],
    )
    def test_citizens_cannot_transition_any_status(
        self, from_s: ComplaintStatus, to_s: ComplaintStatus
    ) -> None:
        assert ComplaintStateMachine.can_transition(from_s, to_s, UserRole.CITIZEN) is False

    @pytest.mark.parametrize(
        "from_s",
        [ComplaintStatus.SUBMITTED, ComplaintStatus.ONGOING, ComplaintStatus.PROCESSING],
    )
    def test_closed_is_admin_only(self, from_s: ComplaintStatus) -> None:
        assert ComplaintStateMachine.can_transition(from_s, ComplaintStatus.CLOSED, UserRole.ADMIN) is True
        assert ComplaintStateMachine.can_transition(from_s, ComplaintStatus.CLOSED, UserRole.ORGANIZATION_ADMIN) is False
        assert ComplaintStateMachine.can_transition(from_s, ComplaintStatus.CLOSED, UserRole.ORGANIZATION_STAFF) is False
        assert ComplaintStateMachine.can_transition(from_s, ComplaintStatus.CLOSED, UserRole.CITIZEN) is False


class TestRuleAttributes:
    def test_rejection_requires_reason(self) -> None:
        for from_s in (ComplaintStatus.SUBMITTED, ComplaintStatus.ONGOING, ComplaintStatus.PROCESSING):
            rule = ComplaintStateMachine.get_rule(from_s, ComplaintStatus.REJECTED)
            assert rule is not None
            assert rule.requires_reason is True

    def test_duplicate_requires_reason_and_reference(self) -> None:
        for from_s in (ComplaintStatus.SUBMITTED, ComplaintStatus.ONGOING, ComplaintStatus.PROCESSING):
            rule = ComplaintStateMachine.get_rule(from_s, ComplaintStatus.DUPLICATE)
            assert rule is not None
            assert rule.requires_reason is True
            assert rule.requires_duplicate_of is True

    def test_completion_requires_reason_and_completion_summary(self) -> None:
        rule = ComplaintStateMachine.get_rule(ComplaintStatus.PROCESSING, ComplaintStatus.COMPLETED)
        assert rule is not None
        assert rule.requires_reason is True
        assert rule.requires_completion_summary is True

    def test_submitted_requires_department_match_for_staff(self) -> None:
        rule = ComplaintStateMachine.get_rule(ComplaintStatus.SUBMITTED, ComplaintStatus.ONGOING)
        assert rule is not None
        assert rule.requires_department_match is True

    def test_ongoing_and_processing_require_assignment_for_staff(self) -> None:
        for to_s in (ComplaintStatus.PROCESSING, ComplaintStatus.REJECTED, ComplaintStatus.DUPLICATE):
            rule = ComplaintStateMachine.get_rule(ComplaintStatus.ONGOING, to_s)
            assert rule is not None
            assert rule.requires_assigned_staff is True
