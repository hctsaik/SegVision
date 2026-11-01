"""Optional PySide6 desktop shell.

The workflow controller remains the product boundary and is usable without a
GUI toolkit.  Qt is imported only from :func:`build_window`/ :func:`main`, so
headless imports never initialise a display or create a global application.
The default window is intentionally small but functional: it shows the
selected overlay, real candidate cards, frozen controls, and routes keyboard
and mouse input through :class:`~segvision.gui.canvas.AnnotationCanvasModel`.
"""

from __future__ import annotations

import sys
from typing import Any


def build_window(controller: Any = None) -> Any:
    """Build a Qt window for an optional existing controller.

    A caller normally creates a session through ``SegVisionEngine.start`` and
    passes an ``AnnotationController`` here.  Keeping construction separate
    lets applications provide their own image picker while preserving the
    frozen core boundary.
    """

    try:
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QImage, QPainter
        from PySide6.QtWidgets import (
            QHBoxLayout,
            QLabel,
            QListWidget,
            QListWidgetItem,
            QMainWindow,
            QPushButton,
            QVBoxLayout,
            QWidget,
        )
    except ImportError as exc:  # pragma: no cover - depends on optional GUI extra
        raise RuntimeError("SegVision GUI requires the optional PySide6 dependency") from exc

    from segvision.core.errors import SegVisionError

    from .canvas import AnnotationCanvasModel
    from .panels import AnnotationPanels

    class CanvasWidget(QWidget):
        def __init__(self, model: AnnotationCanvasModel | None, parent: QWidget | None = None) -> None:
            super().__init__(parent)
            self.model = model
            self.setMinimumSize(640, 480)
            self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
            self.setAccessibleName("SegVision annotation canvas")

        def resizeEvent(self, event: Any) -> None:
            if self.model is not None:
                self.model.resize(self.width(), self.height())
            super().resizeEvent(event)

        def mousePressEvent(self, event: Any) -> None:
            if self.model is None:
                return
            button = "left" if event.button() == Qt.MouseButton.LeftButton else "right"
            try:
                self.model.mouse_press(float(event.position().x()), float(event.position().y()), button)
            except (SegVisionError, TypeError, ValueError):
                # The controller remains the source of typed diagnostics; a
                # canvas input must never crash the event loop.
                pass
            self.update()

        def keyPressEvent(self, event: Any) -> None:
            if self.model is not None:
                try:
                    self.model.key_press(event.text() or event.keyCombination().toString())
                except (SegVisionError, TypeError, ValueError):
                    self.model.controller.last_error = "invalid keyboard input"
                self.update()
            super().keyPressEvent(event)

        def paintEvent(self, _event: Any) -> None:
            painter = QPainter(self)
            painter.fillRect(self.rect(), Qt.GlobalColor.black)
            if self.model is None:
                painter.end()
                return
            session = self.model.controller.session
            image = session._image  # presentation-only read-only copy owned by the session
            rgb = QImage(
                image.data,
                image.shape[1],
                image.shape[0],
                image.strides[0],
                QImage.Format.Format_RGB888,
            )
            painter.drawImage(self.rect(), rgb)
            layers = self.model.layers()
            # Keep overlays visually distinct: selected mask is filled; risk
            # and disagreement are outlines/tints rather than candidate merges.
            if layers.selected_mask_roi.any():
                painter.setPen(Qt.GlobalColor.green)
                x0, y0, x1, y1 = layers.crop_rect_full
                painter.drawRect(
                    self.model.transform.image_to_view(x0, y0)[0],
                    self.model.transform.image_to_view(x0, y0)[1],
                    max(1, int((x1 - x0) * self.model.transform.scale)),
                    max(1, int((y1 - y0) * self.model.transform.scale)),
                )
            painter.end()

    class Window(QMainWindow):
        def __init__(self, active_controller: Any = None) -> None:
            super().__init__()
            self.setWindowTitle("SegVision")
            self.resize(1200, 760)
            self.controller = active_controller
            self.model = AnnotationCanvasModel(active_controller) if active_controller else None
            self.panels = AnnotationPanels(active_controller) if active_controller else None
            self.status = QLabel("Open an image and lock an ROI to begin annotation.")
            self.status.setAccessibleName("SegVision workflow status")
            self.cards = QListWidget()
            self.cards.setAccessibleName("Candidate cards")
            self.canvas = CanvasWidget(self.model)
            self._build_ui()
            self.refresh()

        def _build_ui(self) -> None:
            root = QWidget(self)
            layout = QHBoxLayout(root)
            left = QVBoxLayout()
            left.addWidget(self.canvas, stretch=1)
            left.addWidget(self.status)
            right = QVBoxLayout()
            right.addWidget(QLabel("Candidates"))
            right.addWidget(self.cards, stretch=1)
            for label, callback in (
                ("Expand ROI (X)", self._expand),
                ("Undo (Z)", self._undo),
                ("Erase", self._erase),
                ("Accept (Space)", self._accept),
                ("Needs Review", self._review),
            ):
                button = QPushButton(label)
                button.setAccessibleName(label)
                button.clicked.connect(callback)
                right.addWidget(button)
            layout.addLayout(left, stretch=3)
            layout.addLayout(right, stretch=1)
            self.setCentralWidget(root)

        def refresh(self) -> None:
            self.cards.clear()
            if self.panels is None:
                return
            for card in self.panels.cards:
                item = QListWidgetItem(
                    f"{card.rank}: {card.source}  q={card.quality:.3f}"
                    + ("  [selected]" if card.selected else "")
                )
                item.setData(Qt.ItemDataRole.UserRole, card.rank)
                item.setToolTip(card.accessible_name)
                self.cards.addItem(item)
            state = self.panels.state
            self.status.setText(f"{state.state}  {state.elapsed_ms:.0f} ms")

        def _selected_rank(self) -> int | None:
            item = self.cards.currentItem()
            return int(item.data(Qt.ItemDataRole.UserRole)) if item is not None else None

        def _expand(self) -> None:
            if self.controller:
                self.controller.expand_roi()
                self.refresh()

        def _undo(self) -> None:
            if self.controller:
                self.controller.key("Z")
                self.refresh()

        def _erase(self) -> None:
            if self.controller:
                self.controller.edit("erase", points=[])
                self.refresh()

        def _accept(self) -> None:
            if self.controller:
                self.controller.accept()
                self.refresh()

        def _review(self) -> None:
            if self.controller:
                self.controller.needs_review("user requested review")
                self.refresh()

    return Window(controller)


def main(argv: list[str] | None = None) -> int:
    try:
        from PySide6.QtWidgets import QApplication
    except ImportError:
        print(
            "SegVision GUI requires the optional PySide6 dependency; "
            "the headless core remains available.",
            file=sys.stderr,
        )
        return 2
    app = QApplication(argv or sys.argv)
    window = build_window()
    window.show()
    return app.exec()


__all__ = ["build_window", "main"]
