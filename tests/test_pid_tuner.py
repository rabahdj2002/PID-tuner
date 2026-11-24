import numpy as np
import pytest

from pid_tuner import closed_loop_tf, format_poly, parse_coeffs, step_response


class TestParseCoeffs:
    def test_space_separated(self):
        assert parse_coeffs("1 0.5 2") == [1.0, 0.5, 2.0]

    def test_comma_separated(self):
        assert parse_coeffs("1,0.5,2") == [1.0, 0.5, 2.0]
        assert parse_coeffs("1, 0.5, 2") == [1.0, 0.5, 2.0]

    def test_empty(self):
        assert parse_coeffs("") == []
        assert parse_coeffs("   ") == []

    def test_invalid(self):
        assert parse_coeffs("1 abc 2") is None
        assert parse_coeffs("one two") is None

    def test_negative_and_scientific(self):
        assert parse_coeffs("1 -3 1e-2") == [1.0, -3.0, 0.01]


class TestFormatPoly:
    def test_simple(self):
        assert format_poly([1, 0.5, 2]) == "1s^2 + 0.5s + 2"

    def test_constant_only(self):
        assert format_poly([5]) == "5"

    def test_zero_coeffs_skipped(self):
        assert format_poly([1, 0, 2]) == "1s^2 + 2"

    def test_negative(self):
        assert format_poly([1, -2, 1]) == "1s^2 - 2s + 1"

    def test_all_zeros(self):
        assert format_poly([0, 0]) == "0"
        assert format_poly([]) == "0"


class TestClosedLoopTf:
    def test_unity_feedback_first_order(self):
        # Plant 1/(s+1), Kp=1 Ki=Kd=0 -> open = s/(s^2+s),
        # closed = s/(s^2+2s) = 1/(s+2)
        num, den = closed_loop_tf([1], [1, 1], kp=1, ki=0, kd=0)
        np.testing.assert_allclose(num, [1, 0])
        np.testing.assert_allclose(den, [1, 2, 0])

    def test_pid_structure(self):
        # Plant 1/(s^2+s), C = (Kd s^2 + Kp s + Ki)/s
        # T = C G / (1 + C G): den = open_den + open_num
        num, den = closed_loop_tf([1], [1, 1, 0], kp=2, ki=3, kd=1)
        # open_num = conv([1],[1,2,3]) = [1,2,3]; open_den = conv([1,1,0],[1,0]) = [1,1,0,0]
        # den = [1,1,0,0] + [0,1,2,3] = [1,2,2,3]
        np.testing.assert_allclose(den, [1, 2, 2, 3])
        np.testing.assert_allclose(num, [1, 2, 3])

    def test_both_directions_padding(self):
        # Plant with more zeros than poles must not raise broadcast errors
        num, den = closed_loop_tf([1, 2, 3], [1, 1], kp=1, ki=0, kd=0)
        assert len(den) == len(num)


class TestStepResponse:
    def test_first_order_settles(self):
        # 1/(s+2): steady-state 0.5
        t, y = step_response([1], [1, 2], t_max=10)
        assert t[-1] == pytest.approx(10)
        assert y[-1] == pytest.approx(0.5, abs=0.02)

    def test_output_lengths(self):
        t, y = step_response([1], [1, 1], t_max=5, points=200)
        assert len(t) == 200
        assert len(y) == 200
        assert y[0] == pytest.approx(0, abs=0.05)
