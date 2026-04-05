"""
Centralized Qt Style Sheets: dark glass, rounded shell, list and buttons.
Translucency uses alpha in backgrounds; true OS blur is optional (see widget notes).
"""


def application_stylesheet() -> str:
    return """
    QWidget#TodoGlassRoot {
        background-color: rgba(18, 28, 48, 232);
        border-radius: 14px;
        border: 1px solid rgba(140, 180, 255, 45);
    }
    QLabel#HeaderTitle {
        color: rgba(255, 255, 255, 245);
        font-size: 16px;
        font-weight: 600;
    }
    QLabel#HeaderDate {
        color: rgba(200, 200, 210, 220);
        font-size: 11px;
    }
    QScrollArea {
        background: transparent;
        border: none;
    }
    QScrollBar:vertical {
        background: rgba(0, 0, 0, 40);
        width: 8px;
        margin: 4px 2px 4px 0;
        border-radius: 4px;
    }
    QScrollBar::handle:vertical {
        background: rgba(255, 255, 255, 55);
        min-height: 28px;
        border-radius: 4px;
    }
    QScrollBar::handle:vertical:hover {
        background: rgba(255, 255, 255, 85);
    }
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
        height: 0;
    }
    QPushButton#ToolbarButton {
        background-color: rgba(70, 120, 200, 55);
        color: rgba(255, 255, 255, 245);
        border: 1px solid rgba(160, 200, 255, 55);
        border-radius: 8px;
        padding: 6px 10px;
        font-size: 11px;
    }
    QPushButton#ToolbarButton:hover {
        background-color: rgba(90, 140, 220, 85);
    }
    QPushButton#ToolbarButton:pressed {
        background-color: rgba(50, 90, 160, 70);
    }
    QPushButton#IconButton {
        background-color: transparent;
        color: rgba(255, 255, 255, 180);
        border: none;
        border-radius: 4px;
        padding: 2px 6px;
        font-size: 12px;
        min-width: 22px;
    }
    QPushButton#IconButton:hover {
        background-color: rgba(255, 255, 255, 20);
        color: rgba(255, 255, 255, 240);
    }
    QFrame#TaskRowFrame {
        background-color: rgba(40, 70, 120, 45);
        border-radius: 8px;
        border: 1px solid rgba(130, 170, 230, 35);
    }
    QFrame#TaskRowFrameOverdue {
        background-color: rgba(180, 40, 50, 55);
        border-radius: 8px;
        border: 1px solid rgba(255, 100, 110, 90);
    }
    QLabel#TaskTitle {
        color: rgba(255, 255, 255, 245);
        font-size: 12px;
    }
    QLabel#TaskTitleDone {
        color: rgba(120, 220, 140, 255);
        font-size: 12px;
        text-decoration: line-through;
    }
    QLabel#TaskTitleOverdue {
        color: rgba(255, 130, 130, 255);
        font-size: 12px;
        font-weight: 500;
    }
    QLabel#TaskMeta {
        color: rgba(180, 180, 190, 220);
        font-size: 10px;
    }
    QLabel#OverdueBadge {
        color: rgba(255, 160, 160, 255);
        font-size: 9px;
        font-weight: 600;
    }
    QCheckBox#TaskCheck {
        spacing: 6px;
    }
    QCheckBox#TaskCheck::indicator {
        width: 16px;
        height: 16px;
        border-radius: 4px;
        border: 1px solid rgba(180, 210, 255, 90);
        background: rgba(10, 20, 40, 55);
    }
    QCheckBox#TaskCheck::indicator:checked {
        background: rgba(70, 180, 100, 200);
        border: 1px solid rgba(120, 220, 140, 255);
    }
    QLineEdit, QTextEdit {
        background-color: rgba(0, 0, 0, 45);
        border: 1px solid rgba(255, 255, 255, 35);
        border-radius: 6px;
        padding: 6px;
        color: rgba(255, 255, 255, 240);
        selection-background-color: rgba(80, 120, 200, 180);
    }
    QDialog {
        background-color: rgba(22, 32, 52, 248);
    }
    QLabel {
        color: rgba(230, 230, 235, 240);
    }
    QCalendarWidget QWidget {
        alternate-background-color: rgba(0, 0, 0, 30);
    }
    QCalendarWidget QAbstractItemView:enabled {
        color: rgba(255, 255, 255, 230);
        background-color: rgba(16, 26, 44, 220);
        selection-background-color: rgba(70, 120, 210, 200);
        selection-color: white;
    }
    """
