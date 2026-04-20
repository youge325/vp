"""桌面端暗色主题样式表。"""

DARK_STYLESHEET = """
QMainWindow, QWidget#rootPanel, QScrollArea {
    background-color: #08111F;
    color: #D6E2F0;
}

QLabel {
    color: #D6E2F0;
    font-size: 12px;
}

QFrame#heroCard {
    border: 1px solid #1C3557;
    border-radius: 22px;
    background: qlineargradient(
        x1: 0, y1: 0, x2: 1, y2: 1,
        stop: 0 #12243B,
        stop: 0.55 #102033,
        stop: 1 #0B1727
    );
}

QLabel#heroEyebrow {
    color: #5EEAD4;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 1px;
}

QLabel#heroTitle {
    color: #F8FAFC;
    font-size: 28px;
    font-weight: 700;
}

QLabel#heroSubtitle {
    color: #C6D4E4;
    font-size: 13px;
    line-height: 1.5;
}

QLabel#heroSteps {
    color: #8CA2BF;
    font-size: 12px;
}

QLabel#heroTag {
    color: #D8F7F1;
    background-color: rgba(8, 17, 31, 0.46);
    border: 1px solid rgba(130, 171, 210, 0.22);
    border-radius: 999px;
    padding: 6px 10px;
    font-size: 11px;
    font-weight: 600;
}

QLabel#heroStateBadge {
    border-radius: 999px;
    padding: 8px 14px;
    font-size: 12px;
    font-weight: 700;
}

QLabel#heroStateBadge[state="pending"] {
    color: #DCEAFE;
    background-color: rgba(56, 189, 248, 0.18);
    border: 1px solid #38BDF8;
}

QLabel#heroStateBadge[state="ready"] {
    color: #D1FAE5;
    background-color: rgba(20, 184, 166, 0.18);
    border: 1px solid #14B8A6;
}

QLabel#heroStateBadge[state="attention"] {
    color: #FEF3C7;
    background-color: rgba(245, 158, 11, 0.18);
    border: 1px solid #F59E0B;
}

QFrame#navRail,
QFrame#pageIntroCard {
    border: 1px solid #22324B;
    border-radius: 20px;
    background-color: #0F1A2C;
}

QFrame#pageIntroCard {
    background: qlineargradient(
        x1: 0, y1: 0, x2: 1, y2: 1,
        stop: 0 #102033,
        stop: 1 #0B1727
    );
}

QLabel#navBadge,
QLabel#pageIntroEyebrow {
    color: #5EEAD4;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 1px;
}

QLabel#navTitle,
QLabel#pageIntroTitle {
    color: #F8FAFC;
    font-size: 22px;
    font-weight: 700;
}

QLabel#navNote,
QLabel#navFooter,
QLabel#pageIntroText {
    color: #9FB0C6;
    font-size: 12px;
    line-height: 1.5;
}

QPushButton#navButton {
    text-align: left;
    padding: 14px 16px;
    background-color: #0A1424;
    color: #D6E2F0;
    border: 1px solid #22324B;
    border-radius: 16px;
    font-size: 13px;
    font-weight: 700;
}

QPushButton#navButton:hover {
    background-color: #132338;
    border-color: #2B4D74;
    color: #F8FAFC;
}

QPushButton#navButton:checked {
    background: qlineargradient(
        x1: 0, y1: 0, x2: 1, y2: 0,
        stop: 0 #14B8A6,
        stop: 1 #38BDF8
    );
    color: #08111F;
    border-color: #38BDF8;
}

QGroupBox {
    color: #F8FAFC;
    font-size: 14px;
    font-weight: 700;
    border: 1px solid #22324B;
    border-radius: 18px;
    margin-top: 12px;
    padding: 18px 18px 18px 18px;
    background-color: #0F1A2C;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 2px 10px;
    color: #F8FAFC;
}

QLabel#cardNote {
    color: #8BA1BF;
    font-size: 12px;
    line-height: 1.5;
}

QFrame#envBadge,
QFrame#metricCard,
QFrame#summaryRow,
QFrame#hintBanner {
    background-color: #0A1424;
    border: 1px solid #22324B;
    border-radius: 14px;
}

QFrame#envBadge[state="pending"] {
    border-color: #31577A;
    background-color: #0C1828;
}

QFrame#envBadge[state="ok"] {
    border-color: #148A76;
    background-color: #0C1C20;
}

QFrame#envBadge[state="warning"] {
    border-color: #8B5E18;
    background-color: #1A1720;
}

QFrame#envBadge[state="bad"] {
    border-color: #7F1D1D;
    background-color: #1A1218;
}

QLabel#envBadgeTitle,
QLabel#summaryKey,
QLabel#metricCaption {
    color: #8BA1BF;
    font-size: 11px;
    font-weight: 600;
}

QLabel#envBadgeValue {
    color: #F8FAFC;
    font-size: 14px;
    font-weight: 700;
}

QLabel#metricValue {
    color: #F8FAFC;
    font-size: 21px;
    font-weight: 700;
}

QLabel#summaryValue,
QLabel#hintText,
QLabel#processSummary {
    color: #E2E8F0;
    font-size: 12px;
    line-height: 1.5;
}

QLabel#processSummary {
    font-size: 13px;
    font-weight: 600;
}

QPushButton {
    background-color: #14B8A6;
    color: #08111F;
    border: none;
    border-radius: 12px;
    padding: 10px 16px;
    font-size: 13px;
    font-weight: 700;
}

QPushButton:hover {
    background-color: #2DD4BF;
}

QPushButton:pressed {
    background-color: #0F9A8E;
}

QPushButton:disabled {
    background-color: #2A3546;
    color: #718198;
}

QPushButton#secondaryButton {
    background-color: #142236;
    color: #D6E2F0;
    border: 1px solid #2B3F5D;
}

QPushButton#secondaryButton:hover {
    background-color: #1A2D45;
    border-color: #4B658B;
}

QPushButton#startPrimaryButton {
    background: qlineargradient(
        x1: 0, y1: 0, x2: 1, y2: 0,
        stop: 0 #14B8A6,
        stop: 1 #38BDF8
    );
    color: #07111F;
    font-size: 14px;
    font-weight: 700;
    padding: 12px 18px;
}

QPushButton#startPrimaryButton:hover {
    background: qlineargradient(
        x1: 0, y1: 0, x2: 1, y2: 0,
        stop: 0 #2DD4BF,
        stop: 1 #60A5FA
    );
}

QLineEdit,
QComboBox,
QSpinBox,
QDoubleSpinBox {
    background-color: #08111F;
    color: #F8FAFC;
    border: 1px solid #243852;
    border-radius: 12px;
    padding: 9px 12px;
    font-size: 12px;
    min-height: 22px;
}

QLineEdit:focus,
QComboBox:focus,
QSpinBox:focus,
QDoubleSpinBox:focus {
    border-color: #38BDF8;
}

QLineEdit:read-only {
    color: #C6D4E4;
    background-color: #0A1424;
}

QComboBox::drop-down {
    border: none;
    width: 24px;
}

QComboBox::down-arrow {
    image: none;
    border: none;
}

QComboBox QAbstractItemView {
    background-color: #0F1A2C;
    color: #E2E8F0;
    border: 1px solid #243852;
    selection-background-color: #38BDF8;
    selection-color: #08111F;
    outline: none;
}

QSpinBox::up-button,
QSpinBox::down-button,
QDoubleSpinBox::up-button,
QDoubleSpinBox::down-button {
    background-color: #1A2A40;
    border: none;
    width: 20px;
}

QSpinBox::up-button:hover,
QSpinBox::down-button:hover,
QDoubleSpinBox::up-button:hover,
QDoubleSpinBox::down-button:hover {
    background-color: #27425F;
}

QCheckBox {
    color: #D6E2F0;
    font-size: 12px;
    spacing: 8px;
}

QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border-radius: 5px;
    border: 2px solid #2B3F5D;
    background-color: #08111F;
}

QCheckBox::indicator:checked {
    background-color: #14B8A6;
    border-color: #14B8A6;
}

QProgressBar {
    background-color: #0A1424;
    border: 1px solid #243852;
    border-radius: 999px;
    min-height: 18px;
}

QProgressBar::chunk {
    border-radius: 999px;
    background: qlineargradient(
        x1: 0, y1: 0, x2: 1, y2: 0,
        stop: 0 #14B8A6,
        stop: 1 #38BDF8
    );
}

QLabel#progressValue {
    color: #5EEAD4;
    font-size: 13px;
    font-weight: 700;
}

QLabel#statusPill {
    color: #D1FAE5;
    background-color: #0C1C20;
    border: 1px solid #148A76;
    border-radius: 999px;
    padding: 4px 10px;
    font-size: 11px;
    font-weight: 700;
}

QStatusBar {
    background-color: #08111F;
    color: #8BA1BF;
    border-top: 1px solid #132338;
}
"""
