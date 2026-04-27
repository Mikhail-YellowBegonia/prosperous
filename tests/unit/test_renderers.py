"""
Unit tests for renderer classes in renderers.py.
Tests do not depend on PIL image loading — matrices are constructed directly.
"""

import os
import sys
import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC_DIR = os.path.join(PROJECT_ROOT, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from prosperous.renderers import BrailleRenderer, BrailleColorRenderer, BinmapColorRenderer


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_matrix(rows, cols, fill=1):
    """Return a rows×cols matrix filled with `fill`."""
    return [[fill] * cols for _ in range(rows)]


def make_zero_matrix(rows, cols):
    return make_matrix(rows, cols, fill=0)


class _PushCapture:
    """Captures every call to a push_braille / push_binmap stub."""

    def __init__(self):
        self.calls = []

    def push_braille(self, y, x, bits, fg):
        self.calls.append({"y": y, "x": x, "bits": bits, "fg": fg})

    def push_binmap(self, y, x, char, fg, bg=None):
        self.calls.append({"y": y, "x": x, "char": char, "fg": fg, "bg": bg})


# ---------------------------------------------------------------------------
# TestBrailleRenderer (6-dot)
# ---------------------------------------------------------------------------


class TestBrailleRenderer:
    # -- empty matrix --------------------------------------------------------

    def test_empty_matrix_does_not_crash(self):
        """BrailleRenderer with a 0-row matrix must not raise during draw."""
        renderer = BrailleRenderer([], dots=6)
        cap = _PushCapture()
        renderer.draw(0, 0, cap.push_braille)
        assert cap.calls == []

    def test_empty_row_matrix_does_not_crash(self):
        """BrailleRenderer with rows but 0 columns must not raise during draw."""
        renderer = BrailleRenderer([[]], dots=6)
        cap = _PushCapture()
        renderer.draw(0, 0, cap.push_braille)
        assert cap.calls == []

    # -- all-ones 4×6 matrix, dots=6 ----------------------------------------

    def test_all_ones_4x6_matrix_bits_6dot(self):
        """A fully lit 4×6 matrix with dots=6 must produce bits=0b00111111 per cell.

        4 rows / 3 rows_per_cell = ceil result but only floor cells are emitted:
        cy=0 covers rows 0-2; cy=3 would be out of the 4-row range so only cy=0
        completes a full 6-dot cell for columns 0-2 (cx=0) and columns 2-4 (cx=2).
        However the loop steps cy by rpc=3, so cy values are 0 and 3.
        cy=3: dr offsets 0/1/2 → rows 3, 4, 5 — rows 4 & 5 are out of bounds,
        so only row 3 contributes bits 1 and 8 (dot_map entries (0,0,1) and (0,1,8)).
        We therefore only assert the full-cell case for cy=0.
        """
        matrix = make_matrix(4, 6)  # 4 rows, 6 cols
        renderer = BrailleRenderer(matrix, dots=6, fg=(255, 0, 0), skip_empty=False)
        cap = _PushCapture()
        renderer.draw(0, 0, cap.push_braille)

        # cy=0, cx=0 → cell (0,0): all 6 dot positions within rows 0-2
        cell_0_0 = next(c for c in cap.calls if c["y"] == 0 and c["x"] == 0)
        assert cell_0_0["bits"] == 0b00111111, (
            f"Expected 0b00111111, got {bin(cell_0_0['bits'])}"
        )

    def test_all_ones_6x6_matrix_all_cells_full_6dot(self):
        """A fully lit 6×6 matrix with dots=6 produces bits=0b00111111 for all 6 cells."""
        matrix = make_matrix(6, 6)  # 6 rows, 6 cols → 2 cell-rows × 3 cell-cols
        renderer = BrailleRenderer(matrix, dots=6, fg=(255, 255, 255), skip_empty=False)
        cap = _PushCapture()
        renderer.draw(0, 0, cap.push_braille)

        assert len(cap.calls) == 6, f"Expected 6 cells, got {len(cap.calls)}"
        for call in cap.calls:
            assert call["bits"] == 0b00111111, (
                f"Cell ({call['y']},{call['x']}) bits={bin(call['bits'])}"
            )

    # -- skip_empty ----------------------------------------------------------

    def test_skip_empty_true_omits_zero_bit_cells(self):
        """When skip_empty=True, cells where bits==0 must not be passed to push."""
        matrix = make_zero_matrix(6, 4)
        renderer = BrailleRenderer(matrix, dots=6, skip_empty=True)
        cap = _PushCapture()
        renderer.draw(0, 0, cap.push_braille)
        assert cap.calls == [], "No push calls expected for all-zero matrix with skip_empty=True"

    def test_skip_empty_false_emits_zero_bit_cells(self):
        """When skip_empty=False, even cells with bits==0 are pushed."""
        matrix = make_zero_matrix(6, 4)
        renderer = BrailleRenderer(matrix, dots=6, skip_empty=False)
        cap = _PushCapture()
        renderer.draw(0, 0, cap.push_braille)
        assert len(cap.calls) > 0, "Expected push calls even for all-zero matrix"
        for call in cap.calls:
            assert call["bits"] == 0

    # -- dot_map 6 vs 8 -------------------------------------------------------

    def test_6dot_uses_6dot_map(self):
        """dots=6: a 3-row, 2-col all-ones matrix should produce bits=0b00111111."""
        matrix = make_matrix(3, 2)
        renderer = BrailleRenderer(matrix, dots=6, skip_empty=False)
        cap = _PushCapture()
        renderer.draw(0, 0, cap.push_braille)
        assert len(cap.calls) == 1
        assert cap.calls[0]["bits"] == 0b00111111

    def test_8dot_uses_8dot_map(self):
        """dots=8: a 4-row, 2-col all-ones matrix should produce bits=0b11111111."""
        matrix = make_matrix(4, 2)
        renderer = BrailleRenderer(matrix, dots=8, skip_empty=False)
        cap = _PushCapture()
        renderer.draw(0, 0, cap.push_braille)
        assert len(cap.calls) == 1
        assert cap.calls[0]["bits"] == 0b11111111

    def test_8dot_partial_matrix_correct_bits(self):
        """dots=8: only rows 0-1 filled → bits should only have the top-two-row dots set.

        _BRAILLE_DOT_MAP_8 top-two-rows for left col: (0,0,1),(1,0,2); right: (0,1,8),(1,1,16)
        Expected bits = 1 | 2 | 8 | 16 = 0b00011011
        """
        matrix = [
            [1, 1],
            [1, 1],
            [0, 0],
            [0, 0],
        ]
        renderer = BrailleRenderer(matrix, dots=8, skip_empty=False)
        cap = _PushCapture()
        renderer.draw(0, 0, cap.push_braille)
        assert len(cap.calls) == 1
        assert cap.calls[0]["bits"] == (1 | 2 | 8 | 16)

    # -- start offset ---------------------------------------------------------

    def test_start_offset_applied_to_cell_coordinates(self):
        """draw() should offset all cell coordinates by (start_y, start_x)."""
        matrix = make_matrix(3, 2)
        renderer = BrailleRenderer(matrix, dots=6, skip_empty=False)
        cap = _PushCapture()
        renderer.draw(5, 10, cap.push_braille)
        assert len(cap.calls) == 1
        assert cap.calls[0]["y"] == 5
        assert cap.calls[0]["x"] == 10

    # -- fg passthrough -------------------------------------------------------

    def test_fg_colour_passed_to_push(self):
        """BrailleRenderer must pass its fg colour to every push call."""
        fg = (123, 45, 67)
        matrix = make_matrix(3, 2)
        renderer = BrailleRenderer(matrix, dots=6, fg=fg, skip_empty=False)
        cap = _PushCapture()
        renderer.draw(0, 0, cap.push_braille)
        for call in cap.calls:
            assert call["fg"] == fg


# ---------------------------------------------------------------------------
# TestBrailleColorRenderer
# ---------------------------------------------------------------------------


class TestBrailleColorRenderer:
    def test_block_fg_colour_passed_to_push(self):
        """BrailleColorRenderer should look up block_fg and pass it to push."""
        matrix = make_matrix(3, 2)  # 1 cell: (0, 0)
        block_fg = {(0, 0): (10, 20, 30)}
        renderer = BrailleColorRenderer(matrix, block_fg, dots=6, skip_empty=False)
        cap = _PushCapture()
        renderer.draw(0, 0, cap.push_braille)
        assert len(cap.calls) == 1
        assert cap.calls[0]["fg"] == (10, 20, 30)

    def test_missing_block_fg_passes_none(self):
        """If a cell key is absent from block_fg, push should receive fg=None."""
        matrix = make_matrix(3, 2)  # cell (0, 0)
        block_fg = {}  # no entry for (0, 0)
        renderer = BrailleColorRenderer(matrix, block_fg, dots=6, skip_empty=False)
        cap = _PushCapture()
        renderer.draw(0, 0, cap.push_braille)
        assert len(cap.calls) == 1
        assert cap.calls[0]["fg"] is None

    def test_multiple_cells_correct_fg_mapping(self):
        """Each cell receives its own fg from block_fg."""
        matrix = make_matrix(6, 4)  # 2 cell-rows × 2 cell-cols = 4 cells
        block_fg = {
            (0, 0): (255, 0, 0),
            (0, 1): (0, 255, 0),
            (1, 0): (0, 0, 255),
            (1, 1): (255, 255, 0),
        }
        renderer = BrailleColorRenderer(matrix, block_fg, dots=6, skip_empty=False)
        cap = _PushCapture()
        renderer.draw(0, 0, cap.push_braille)
        result = {(c["y"], c["x"]): c["fg"] for c in cap.calls}
        assert result[(0, 0)] == (255, 0, 0)
        assert result[(0, 1)] == (0, 255, 0)
        assert result[(1, 0)] == (0, 0, 255)
        assert result[(1, 1)] == (255, 255, 0)

    def test_skip_empty_true_omits_zero_bit_cells(self):
        """skip_empty=True must not push cells with bits==0."""
        matrix = make_zero_matrix(6, 4)
        renderer = BrailleColorRenderer(matrix, {}, dots=6, skip_empty=True)
        cap = _PushCapture()
        renderer.draw(0, 0, cap.push_braille)
        assert cap.calls == []

    def test_skip_empty_false_emits_zero_bit_cells(self):
        """skip_empty=False must push cells with bits==0."""
        matrix = make_zero_matrix(6, 4)
        renderer = BrailleColorRenderer(matrix, {}, dots=6, skip_empty=False)
        cap = _PushCapture()
        renderer.draw(0, 0, cap.push_braille)
        assert len(cap.calls) > 0
        for call in cap.calls:
            assert call["bits"] == 0

    def test_8dot_colour_renderer(self):
        """BrailleColorRenderer with dots=8 should map 4-row cells."""
        matrix = make_matrix(4, 2)  # 1 cell (0,0) in 8-dot mode
        block_fg = {(0, 0): (99, 88, 77)}
        renderer = BrailleColorRenderer(matrix, block_fg, dots=8, skip_empty=False)
        cap = _PushCapture()
        renderer.draw(0, 0, cap.push_braille)
        assert len(cap.calls) == 1
        assert cap.calls[0]["bits"] == 0b11111111
        assert cap.calls[0]["fg"] == (99, 88, 77)

    def test_start_offset(self):
        """draw() offsets cell coordinates by (start_y, start_x)."""
        matrix = make_matrix(3, 2)
        renderer = BrailleColorRenderer(matrix, {(0, 0): (1, 2, 3)}, dots=6, skip_empty=False)
        cap = _PushCapture()
        renderer.draw(7, 3, cap.push_braille)
        assert cap.calls[0]["y"] == 7
        assert cap.calls[0]["x"] == 3


# ---------------------------------------------------------------------------
# TestBinmapColorRenderer
# ---------------------------------------------------------------------------


class TestBinmapColorRenderer:
    # Helper constants
    CHAR_MAP = " ▘▝▀▖▌▞▛▗▚▐▜▄▙▟█"

    def test_empty_matrix_does_not_crash(self):
        """BinmapColorRenderer with empty matrix must not raise."""
        renderer = BinmapColorRenderer([], {}, skip_empty=True)
        cap = _PushCapture()
        renderer.draw(0, 0, cap.push_binmap)
        assert cap.calls == []

    def test_all_ones_2x2_produces_full_block(self):
        """A 2×2 all-ones matrix → index=15 → char '█'."""
        matrix = make_matrix(2, 2)
        fg, bg = (255, 0, 0), (0, 0, 255)
        block_colors = {(0, 0): (fg, bg)}
        renderer = BinmapColorRenderer(matrix, block_colors, skip_empty=False)
        cap = _PushCapture()
        renderer.draw(0, 0, cap.push_binmap)
        assert len(cap.calls) == 1
        assert cap.calls[0]["char"] == "█"  # CHAR_MAP[15]

    def test_fg_bg_passed_correctly(self):
        """BinmapColorRenderer passes fg and bg from block_colors to push."""
        matrix = make_matrix(2, 2)
        fg = (111, 222, 33)
        bg = (44, 55, 66)
        renderer = BinmapColorRenderer(matrix, {(0, 0): (fg, bg)}, skip_empty=False)
        cap = _PushCapture()
        renderer.draw(0, 0, cap.push_binmap)
        assert cap.calls[0]["fg"] == fg
        assert cap.calls[0]["bg"] == bg

    def test_missing_block_colors_passes_none_none(self):
        """If a cell key is absent from block_colors, fg and bg should both be None."""
        matrix = make_matrix(2, 2)
        renderer = BinmapColorRenderer(matrix, {}, skip_empty=False)
        cap = _PushCapture()
        renderer.draw(0, 0, cap.push_binmap)
        assert cap.calls[0]["fg"] is None
        assert cap.calls[0]["bg"] is None

    def test_skip_empty_true_omits_zero_index_cells(self):
        """skip_empty=True must not push cells where all four pixels are 0."""
        matrix = make_zero_matrix(4, 4)
        renderer = BinmapColorRenderer(matrix, {}, skip_empty=True)
        cap = _PushCapture()
        renderer.draw(0, 0, cap.push_binmap)
        assert cap.calls == []

    def test_skip_empty_false_emits_zero_index_cells(self):
        """skip_empty=False must push even cells with index==0."""
        matrix = make_zero_matrix(2, 2)
        renderer = BinmapColorRenderer(matrix, {(0, 0): (None, None)}, skip_empty=False)
        cap = _PushCapture()
        renderer.draw(0, 0, cap.push_binmap)
        assert len(cap.calls) == 1
        assert cap.calls[0]["char"] == " "  # CHAR_MAP[0]

    def test_partial_pixel_pattern_correct_char(self):
        """tl=1, tr=0, bl=0, br=0 → index=1 → char '▘'."""
        matrix = [
            [1, 0],
            [0, 0],
        ]
        renderer = BinmapColorRenderer(matrix, {(0, 0): (None, None)}, skip_empty=False)
        cap = _PushCapture()
        renderer.draw(0, 0, cap.push_binmap)
        assert cap.calls[0]["char"] == "▘"  # CHAR_MAP[1]

    def test_multiple_cells_correct_coordinates(self):
        """A 2×4 matrix should produce 2 cell calls at the correct coords."""
        matrix = make_matrix(2, 4)  # 1 cell-row × 2 cell-cols
        block_colors = {(0, 0): ((1, 2, 3), None), (0, 1): ((4, 5, 6), None)}
        renderer = BinmapColorRenderer(matrix, block_colors, skip_empty=False)
        cap = _PushCapture()
        renderer.draw(0, 0, cap.push_binmap)
        coords = {(c["y"], c["x"]) for c in cap.calls}
        assert (0, 0) in coords
        assert (0, 1) in coords

    def test_start_offset_applied(self):
        """draw() offsets cell coordinates by (start_y, start_x)."""
        matrix = make_matrix(2, 2)
        renderer = BinmapColorRenderer(matrix, {(0, 0): (None, None)}, skip_empty=False)
        cap = _PushCapture()
        renderer.draw(4, 7, cap.push_binmap)
        assert cap.calls[0]["y"] == 4
        assert cap.calls[0]["x"] == 7

    def test_index_calculation_all_combinations(self):
        """Verify bitmask index for each of the four individual lit pixels."""
        # tl only → index 1, tr only → index 2, bl only → index 4, br only → index 8
        cases = [
            ([[1, 0], [0, 0]], 1),
            ([[0, 1], [0, 0]], 2),
            ([[0, 0], [1, 0]], 4),
            ([[0, 0], [0, 1]], 8),
        ]
        for matrix, expected_index in cases:
            renderer = BinmapColorRenderer(matrix, {(0, 0): (None, None)}, skip_empty=False)
            cap = _PushCapture()
            renderer.draw(0, 0, cap.push_binmap)
            expected_char = BinmapColorRenderer.CHAR_MAP[expected_index]
            assert cap.calls[0]["char"] == expected_char, (
                f"matrix={matrix} expected CHAR_MAP[{expected_index}]={expected_char!r}, "
                f"got {cap.calls[0]['char']!r}"
            )
