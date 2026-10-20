"""Demo view - guided tour for new users to learn duAI features."""

import os

from PySide6.QtCore import (Qt, QTimer, QPropertyAnimation, QEasingCurve, QRect,
                             QPoint, Property)
from PySide6.QtGui import QPainter, QColor, QPen, QFont, QPixmap
from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QWidget, QFrame, QPushButton,
    QStackedWidget, QGraphicsOpacityEffect, QScrollArea, QGridLayout
)

from ..i18n import t
from .theme import current_mode
from .animations import fade_widget


class DemoStep:
    """Represents a single step in the demo tour."""
    def __init__(self, widget_name: str, title: str, description: str, 
                 target_widget: str = "", position: str = "bottom",
                 action: str = "", highlight_rect: QRect = None):
        self.widget_name = widget_name
        self.title = title
        self.description = description
        self.target_widget = target_widget  # objectName of widget to highlight
        self.position = position  # top, bottom, left, right, center
        self.action = action  # optional action to perform (e.g., "click_scan")
        self.highlight_rect = highlight_rect


class HighlightOverlay(QWidget):
    """Overlay widget that highlights a target widget with a spotlight effect."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.target_rect = QRect()
        self.visible = False
        self._opacity = 0.0
        self._animation = QPropertyAnimation(self, b"dimOpacity")
        self._animation.setDuration(300)
        self._animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._animation.finished.connect(self._on_animation_finished)

    # El overlay es hijo de la ventana principal, por lo que windowOpacity no
    # aplica: se anima la opacidad del pintado como propiedad Python.
    def getDimOpacity(self) -> float:
        return self._opacity

    def setDimOpacity(self, value: float):
        self._opacity = max(0.0, min(1.0, float(value)))
        self.update()

    dimOpacity = Property(float, getDimOpacity, setDimOpacity)

    def _on_animation_finished(self):
        if self._opacity <= 0.001:
            self.hide()

    def set_target(self, rect: QRect):
        self.target_rect = rect
        self.update()
    
    def show_highlight(self):
        self.visible = True
        self._animation.stop()
        self._animation.setStartValue(self._opacity)
        self._animation.setEndValue(1.0)
        self._animation.start()
        self.show()
        self.raise_()
    
    def hide_highlight(self):
        self.visible = False
        self._animation.stop()
        self._animation.setStartValue(self._opacity)
        self._animation.setEndValue(0.0)
        self._animation.start()
    
    def paintEvent(self, event):
        if not self.visible or self.target_rect.isNull() or self._opacity <= 0.001:
            return
        
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Draw dark overlay with hole
        overlay_color = QColor(0, 0, 0, int(180 * self._opacity))
        painter.fillRect(self.rect(), overlay_color)
        
        # Cut out the target area
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
        margin = 8
        highlight_rect = self.target_rect.adjusted(-margin, -margin, margin, margin)
        painter.drawRoundedRect(highlight_rect, 8, 8)
        
        # Draw highlight border
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
        pen = QPen(QColor("#FFD700"), 3)
        painter.setPen(pen)
        painter.drawRoundedRect(highlight_rect, 8, 8)


class TooltipWidget(QFrame):
    """Floating tooltip for demo steps."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("demoTooltip")
        # Se crea como widget hijo de la ventana principal (no como ventana
        # ToolTip) para poder situarlo con coordenadas locales y que quede
        # por encima de cualquier pestaña.
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)
        
        self.step_label = QLabel()
        self.step_label.setObjectName("demoStepLabel")
        layout.addWidget(self.step_label)
        
        self.title_label = QLabel()
        self.title_label.setObjectName("demoTitleLabel")
        self.title_label.setWordWrap(True)
        layout.addWidget(self.title_label)
        
        self.desc_label = QLabel()
        self.desc_label.setObjectName("demoDescLabel")
        self.desc_label.setWordWrap(True)
        layout.addWidget(self.desc_label)
        
        # Navigation buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)
        
        self.prev_btn = QPushButton(t("demo.prev"))
        self.prev_btn.setObjectName("demoNavBtn")
        self.prev_btn.clicked.connect(self._prev_clicked)
        btn_layout.addWidget(self.prev_btn)
        
        btn_layout.addStretch(1)
        
        self.skip_btn = QPushButton(t("demo.skip"))
        self.skip_btn.setObjectName("demoSkipBtn")
        self.skip_btn.clicked.connect(self._skip_clicked)
        btn_layout.addWidget(self.skip_btn)
        
        self.next_btn = QPushButton(t("demo.next"))
        self.next_btn.setObjectName("demoNextBtn")
        self.next_btn.clicked.connect(self._next_clicked)
        btn_layout.addWidget(self.next_btn)
        
        layout.addLayout(btn_layout)
        
        self.setFixedWidth(320)
        self.setStyleSheet("""
            QFrame#demoTooltip {
                background: #1A1A1A;
                border: 2px solid #FFD700;
                border-radius: 12px;
            }
            QLabel#demoStepLabel {
                color: #FFD700;
                font-size: 11px;
                font-weight: 600;
                text-transform: uppercase;
                letter-spacing: 1px;
            }
            QLabel#demoTitleLabel {
                color: #FFFFFF;
                font-size: 16px;
                font-weight: 600;
            }
            QLabel#demoDescLabel {
                color: #CCCCCC;
                font-size: 13px;
                line-height: 1.4;
            }
            QPushButton#demoNavBtn, QPushButton#demoNextBtn {
                background: #FFD700;
                color: #000000;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: 600;
            }
            QPushButton#demoNavBtn:hover, QPushButton#demoNextBtn:hover {
                background: #FFED4A;
            }
            QPushButton#demoSkipBtn {
                background: transparent;
                color: #888888;
                border: none;
                padding: 8px 16px;
            }
            QPushButton#demoSkipBtn:hover {
                color: #CCCCCC;
            }
        """)
        
        self.prev_callback = None
        self.next_callback = None
        self.skip_callback = None
    
    def set_step(self, step_num: int, total: int, title: str, description: str):
        self.step_label.setText(f"{t('demo.step')} {step_num} {t('demo.of')} {total}")
        self.title_label.setText(title)
        self.desc_label.setText(description)
    
    def set_navigation_state(self, is_first: bool, is_last: bool):
        self.prev_btn.setEnabled(not is_first)
        self.prev_btn.setVisible(not is_first)
        self.next_btn.setText(t("demo.finish") if is_last else t("demo.next"))
    
    def _prev_clicked(self):
        if self.prev_callback:
            self.prev_callback()
    
    def _next_clicked(self):
        if self.next_callback:
            self.next_callback()
    
    def _skip_clicked(self):
        if self.skip_callback:
            self.skip_callback()


class DemoView(QWidget):
    """Guided tour / demo mode for new users."""
    
    def __init__(self, main_window):
        super().__init__()
        self.mw = main_window
        self.current_step = 0
        self.steps = []
        # Overlay y tooltip viven en la ventana principal para poder
        # resaltar widgets de OTRA pestaña (el tour navega entre pestañas).
        self.overlay = HighlightOverlay(main_window)
        self.tooltip = TooltipWidget(main_window)
        
        # Connect tooltip callbacks
        self.tooltip.prev_callback = self._prev_step
        self.tooltip.next_callback = self._next_step
        self.tooltip.skip_callback = self._skip_demo
        
        self._setup_steps()
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(64, 56, 64, 32)
        layout.setSpacing(16)
        
        # Only show start screen if not in demo mode
        if not hasattr(self.mw, "demo_active") or not self.mw.demo_active:
            self._show_start_screen(layout)
        else:
            self._start_demo()
    
    def _show_start_screen(self, layout):
        # Welcome screen
        title = QLabel(t("demo.welcome_title"))
        title.setStyleSheet("font-size: 32px; font-weight: 300; letter-spacing: 2px; color: #FFFFFF;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        subtitle = QLabel(t("demo.welcome_subtitle"))
        subtitle.setStyleSheet("font-size: 16px; color: #CCCCCC;")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)
        
        layout.addSpacing(32)
        
        # Feature highlights
        features = [
            (t("demo.feature_scan"), t("demo.feature_scan_desc"), "🔍"),
            (t("demo.feature_clean"), t("demo.feature_clean_desc"), "🧹"),
            (t("demo.feature_panic"), t("demo.feature_panic_desc"), "🚨"),
            (t("demo.feature_privacy"), t("demo.feature_privacy_desc"), "🛡️"),
            (t("demo.feature_viral"), t("demo.feature_viral_desc"), "🏆"),
            (t("demo.feature_portable"), t("demo.feature_portable_desc"), "💾"),
        ]
        
        grid = QGridLayout()
        grid.setSpacing(16)
        for i, (feat_title, feat_desc, icon) in enumerate(features):
            row, col = divmod(i, 3)
            card = self._create_feature_card(feat_title, feat_desc, icon)
            grid.addWidget(card, row, col)
        
        layout.addLayout(grid)
        layout.addSpacing(32)
        
        # Start button
        start_btn = QPushButton(t("demo.start_tour"))
        start_btn.setObjectName("demoStartBtn")
        start_btn.setMinimumHeight(48)
        start_btn.setMinimumWidth(200)
        start_btn.clicked.connect(self._start_demo)
        
        btn_layout = QHBoxLayout()
        btn_layout.addStretch(1)
        btn_layout.addWidget(start_btn)
        btn_layout.addStretch(1)
        layout.addLayout(btn_layout)
        
        layout.addStretch(1)
    
    def _create_feature_card(self, title: str, desc: str, icon: str) -> QFrame:
        card = QFrame()
        card.setObjectName("featureCard")
        card.setStyleSheet("""
            QFrame#featureCard {
                background: #1A1A1A;
                border: 1px solid #333333;
                border-radius: 12px;
            }
            QFrame#featureCard:hover {
                border-color: #FFD700;
            }
        """)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(8)
        
        icon_lbl = QLabel(icon)
        icon_lbl.setStyleSheet("font-size: 32px;")
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon_lbl)
        
        title_lbl = QLabel(title)
        title_lbl.setStyleSheet("font-size: 14px; font-weight: 600; color: #FFFFFF;")
        title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_lbl)
        
        desc_lbl = QLabel(desc)
        desc_lbl.setStyleSheet("font-size: 12px; color: #AAAAAA;")
        desc_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc_lbl.setWordWrap(True)
        layout.addWidget(desc_lbl)
        
        return card
    
    def _setup_steps(self):
        """Define the demo tour steps."""
        self.steps = [
            DemoStep(
                "dashboard",
                t("demo.step1_title"),
                t("demo.step1_desc"),
                target_widget="scanBtn",
                position="bottom",
                action="navigate_scan"
            ),
            DemoStep(
                "scan",
                t("demo.step2_title"),
                t("demo.step2_desc"),
                target_widget="scanView",
                position="top",
                action="start_scan"
            ),
            DemoStep(
                "clean",
                t("demo.step3_title"),
                t("demo.step3_desc"),
                target_widget="cleanView",
                position="top",
                action="navigate_clean"
            ),
            DemoStep(
                "panic",
                t("demo.step4_title"),
                t("demo.step4_desc"),
                target_widget="panicWidget",
                position="left",
                action="navigate_panic"
            ),
            DemoStep(
                "privacy_score",
                t("demo.step5_title"),
                t("demo.step5_desc"),
                target_widget="scoreFrame",
                position="right",
                action=""
            ),
            DemoStep(
                "viral",
                t("demo.step6_title"),
                t("demo.step6_desc"),
                target_widget="viralView",
                position="top",
                action="navigate_viral"
            ),
            DemoStep(
                "settings",
                t("demo.step7_title"),
                t("demo.step7_desc"),
                target_widget="settingsView",
                position="left",
                action="navigate_settings"
            ),
        ]
    
    def _start_demo(self):
        """Start the guided tour."""
        self.mw.demo_active = True
        
        # Hide start screen widgets
        for child in self.findChildren(QWidget):
            child.hide()
        
        # Show overlay and tooltip (viven en la ventana principal)
        self.overlay.setGeometry(0, 0, self.mw.width(), self.mw.height())
        self.overlay.show()
        self.overlay.raise_()
        
        self.current_step = 0
        self._show_step(0)
    
    def _show_step(self, index: int):
        if index >= len(self.steps):
            self._finish_demo(completed=True)
            return
        
        step = self.steps[index]
        
        # Handle navigation actions
        if step.action == "navigate_scan":
            self.mw.navigate(1)
        elif step.action == "navigate_clean":
            self.mw.navigate(2)
        elif step.action == "navigate_panic":
            self.mw.navigate(4)
        elif step.action == "navigate_viral":
            self.mw.navigate(7)
        elif step.action == "navigate_settings":
            self.mw.navigate(5)
        elif step.action == "start_scan":
            QTimer.singleShot(500, lambda: self.mw.scan_view.start_scan() if hasattr(self.mw, 'scan_view') else None)
        
        # Find target widget
        target = self._find_target(step.target_widget)
        if target:
            # Map to coordinates relative to the main window (tour navigates
            # between tabs, so the overlay must live on the window).
            global_pos = target.mapToGlobal(QPoint(0, 0))
            local_pos = self.mw.mapFromGlobal(global_pos)
            rect = QRect(local_pos, target.size())
            self.overlay.setGeometry(0, 0, self.mw.width(), self.mw.height())
            self.overlay.set_target(rect)
            
            # Position tooltip
            self._position_tooltip(rect, step.position)
        
        # Update tooltip
        self.tooltip.set_step(
            index + 1, len(self.steps),
            step.title, step.description
        )
        self.tooltip.set_navigation_state(index == 0, index == len(self.steps) - 1)
        self.overlay.show_highlight()
        self.tooltip.adjustSize()
        self.tooltip.show()
        self.tooltip.raise_()
    
    def _find_target(self, object_name: str):
        """Find widget by objectName in the main window."""
        if not object_name:
            return None
        return self.mw.findChild(QWidget, object_name)
    
    def _position_tooltip(self, target_rect: QRect, position: str):
        """Position tooltip relative to target (coords relative to main window)."""
        margin = 16
        tooltip_size = self.tooltip.sizeHint()
        if tooltip_size.width() <= 0:
            tooltip_size = self.tooltip.frameGeometry().size()
        
        if position == "bottom":
            x = target_rect.center().x() - tooltip_size.width() // 2
            y = target_rect.bottom() + margin
        elif position == "top":
            x = target_rect.center().x() - tooltip_size.width() // 2
            y = target_rect.top() - tooltip_size.height() - margin
        elif position == "left":
            x = target_rect.left() - tooltip_size.width() - margin
            y = target_rect.center().y() - tooltip_size.height() // 2
        elif position == "right":
            x = target_rect.right() + margin
            y = target_rect.center().y() - tooltip_size.height() // 2
        else:  # center
            x = self.mw.width() // 2 - tooltip_size.width() // 2
            y = self.mw.height() // 2 - tooltip_size.height() // 2
        
        # Keep on screen
        x = max(margin, min(x, self.mw.width() - tooltip_size.width() - margin))
        y = max(margin, min(y, self.mw.height() - tooltip_size.height() - margin))
        
        self.tooltip.move(x, y)
    
    def _next_step(self):
        self.current_step += 1
        if self.current_step >= len(self.steps):
            self._finish_demo(completed=True)
            return
        self._show_step(self.current_step)
    
    def _prev_step(self):
        self.current_step = max(0, self.current_step - 1)
        self._show_step(self.current_step)
    
    def _skip_demo(self):
        self._finish_demo(completed=False)
    
    def _finish_demo(self, completed: bool = True):
        """End the demo tour.

        Si completed es True se muestra el mensaje de felicitacion; si el
        usuario ha saltado el tour no se muestra nada.
        """
        self.overlay.hide_highlight()
        self.tooltip.hide()
        self.mw.demo_active = False

        # Restaurar la pantalla de bienvenida (se oculto al empezar el tour)
        for child in self.findChildren(QWidget):
            if child is not self.overlay and child is not self.tooltip:
                child.show()

        # Show completion message (solo al completar el tour)
        if completed and not os.environ.get("DUAI_NO_DIALOGS"):
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.information(
                self, t("demo.complete_title"),
                t("demo.complete_message")
            )
        
        # Navigate back to dashboard
        self.mw.navigate(0)
    
    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.overlay.setGeometry(0, 0, self.mw.width(), self.mw.height())
        if self.current_step < len(self.steps):
            step = self.steps[self.current_step]
            target = self._find_target(step.target_widget)
            if target:
                global_pos = target.mapToGlobal(QPoint(0, 0))
                local_pos = self.mw.mapFromGlobal(global_pos)
                rect = QRect(local_pos, target.size())
                self.overlay.set_target(rect)
                self._position_tooltip(rect, step.position)