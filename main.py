import json
from pathlib import Path

from textual import on
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Button, Footer, Header, Label, Static

DATA_FILE = Path("data.json")
"""Path to the file for saving config."""

ROWS: int = 8
"""Rows count."""

COLS: int = 5
"""Columns count."""

SLOT_COUNT: int = 8
"""Slot count."""


def empty_char() -> list[list[int]]:
    """Get an empty characters grid."""
    return [[0] * COLS for _ in range(ROWS)]


def generate_c_code(slot: int, data: list[list[int]]) -> str:
    """Generate C code for a custom character."""
    var = f"customChar{slot}"
    lines: list[str] = [f"uint8_t {var}[8] = {{"]

    for i, row in enumerate(data):
        bits = "".join(str(b) for b in row)
        comma = "," if i < ROWS - 1 else ""

        lines.append(f"  0b{bits}{comma}")

    lines.append("};")
    lines.append("")
    lines.append(f"lcd.createChar({slot}, {var});")

    return "\n".join(lines)


class PixelToggled(Message):
    pass


class PixelCell(Static):
    lit: reactive[bool] = reactive(False)

    def __init__(self, row: int, col: int) -> None:
        super().__init__("", id=f"cell-{row}-{col}")
        self._row = row
        self._col = col

    def on_click(self) -> None:
        self.lit = not self.lit
        self.post_message(PixelToggled())

    def watch_lit(self, value: bool) -> None:
        self.set_class(value, "lit")


class CharacterGrid(Widget):
    def compose(self) -> ComposeResult:
        for row in range(ROWS):
            for col in range(COLS):
                yield PixelCell(row, col)

    def get_data(self) -> list[list[int]]:
        data: list[list[int]] = []

        for row in range(ROWS):
            row_data: list[int] = []

            for col in range(COLS):
                cell = self.query_one(f"#cell-{row}-{col}", PixelCell)
                row_data.append(1 if cell.lit else 0)
            data.append(row_data)

        return data

    def set_data(self, data: list[list[int]]) -> None:
        for row in range(ROWS):
            for col in range(COLS):
                cell = self.query_one(f"#cell-{row}-{col}", PixelCell)
                cell.lit = bool(data[row][col])

    def clear(self) -> None:
        self.set_data(empty_char())


class WokwiCharEditor(App[None]):
    CSS = """
    Screen {
        background: $background;
    }

    #main {
        height: 1fr;
    }

    #left-panel {
        width: auto;
        padding: 1 2;
        border-right: solid $panel;
        align: center top;
    }

    #slot-label {
        margin-bottom: 1;
        text-style: bold;
        width: 100%;
        text-align: center;
    }

    #slot-buttons {
        margin-bottom: 1;
        width: auto;
        height: auto;
    }

    #slot-buttons Button {
        min-width: 4;
        height: 1;
    }

    CharacterGrid {
        layout: grid;
        grid-size: 5;
        width: 35;
        height: 24;
        margin: 1 0;
    }

    PixelCell {
        background: $surface;
        border: solid $panel-lighten-1;
    }

    PixelCell:hover {
        background: $panel-lighten-2;
        border: solid $primary-lighten-1;
    }

    PixelCell.lit {
        background: $warning;
        border: solid $warning-darken-1;
    }

    PixelCell.lit:hover {
        background: $warning-lighten-1;
        border: solid $warning;
    }

    #actions {
        margin-top: 1;
        width: auto;
    }

    #actions Button {
        margin-right: 1;
    }

    #right-panel {
        width: 1fr;
        padding: 1 2;
    }

    #code-label {
        margin-bottom: 1;
        text-style: bold;
    }

    #code-output {
        background: $panel;
        padding: 1 2;
        border: solid $panel-darken-2;
        width: 1fr;
        height: 1fr;
    }
    """

    TITLE = "Wokwi LCD Character Editor"
    BINDINGS = [
        ("ctrl+s", "save", "Save"),
        ("ctrl+l", "load", "Load"),
        ("ctrl+x", "clear", "Clear"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._slots: dict[int, list[list[int]]] = {i: empty_char() for i in range(SLOT_COUNT)}
        self._active_slot: int = 0

    def compose(self) -> ComposeResult:
        yield Header()

        with Horizontal(id="main"):
            with Vertical(id="left-panel"):
                yield Label("Character Slot", id="slot-label")
                with Horizontal(id="slot-buttons"):
                    for i in range(SLOT_COUNT):
                        yield Button(str(i), id=f"slot-{i}", variant="default")
                yield CharacterGrid(id="grid")
                with Horizontal(id="actions"):
                    yield Button("Save", id="save-btn", variant="success")
                    yield Button("Load", id="load-btn", variant="primary")
                    yield Button("Clear", id="clear-btn", variant="warning")
            with Vertical(id="right-panel"):
                yield Label("Generated C Code", id="code-label")
                yield Static("", id="code-output")

        yield Footer()

    def on_mount(self) -> None:
        self._update_slot_buttons()
        self._update_code_output()

    def _update_slot_buttons(self) -> None:
        for i in range(SLOT_COUNT):
            btn = self.query_one(f"#slot-{i}", Button)
            btn.variant = "primary" if i == self._active_slot else "default"

    def _update_code_output(self) -> None:
        grid = self.query_one("#grid", CharacterGrid)
        data = grid.get_data()
        code = generate_c_code(self._active_slot, data)
        self.query_one("#code-output", Static).update(code)

    def _switch_slot(self, new_slot: int) -> None:
        grid = self.query_one("#grid", CharacterGrid)

        self._slots[self._active_slot] = grid.get_data()
        self._active_slot = new_slot

        grid.set_data(self._slots[new_slot])

        self._update_slot_buttons()
        self._update_code_output()

    def _save(self) -> None:
        grid = self.query_one("#grid", CharacterGrid)
        self._slots[self._active_slot] = grid.get_data()

        serialized: dict[str, list[list[int]]] = {str(k): v for k, v in self._slots.items()}

        DATA_FILE.write_text(json.dumps(serialized, indent=2))
        self.notify("Saved to data.json", severity="information")

    def _load(self) -> None:
        if not DATA_FILE.exists():
            self.notify("data.json not found", severity="error")
            return

        raw: dict[str, list[list[int]]] = json.loads(DATA_FILE.read_text())
        for k, v in raw.items():
            slot_index = int(k)
            if 0 <= slot_index < SLOT_COUNT:
                self._slots[slot_index] = v

        grid = self.query_one("#grid", CharacterGrid)
        grid.set_data(self._slots[self._active_slot])

        self._update_code_output()
        self.notify("Loaded from data.json", severity="information")

    def _clear(self) -> None:
        grid = self.query_one("#grid", CharacterGrid)
        grid.clear()

        self._slots[self._active_slot] = empty_char()
        self._update_code_output()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        btn_id: str | None = event.button.id

        if btn_id == "save-btn":
            self._save()
        elif btn_id == "load-btn":
            self._load()
        elif btn_id == "clear-btn":
            self._clear()
        elif btn_id is not None and btn_id.startswith("slot-"):
            slot = int(btn_id.split("-")[1])
            self._switch_slot(slot)

    @on(PixelToggled)
    def on_pixel_toggled(self) -> None:
        self._update_code_output()

    def action_save(self) -> None:
        self._save()

    def action_load(self) -> None:
        self._load()

    def action_clear(self) -> None:
        self._clear()


def main() -> None:
    WokwiCharEditor().run()


if __name__ == "__main__":
    main()
