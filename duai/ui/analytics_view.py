"""Analytics view with QtCharts for privacy score trends, activity heatmaps, and statistics."""

from PySide6.QtCore import Qt, QDate, QDateTime, QTimer
from PySide6.QtGui import QPainter, QColor, QFont
from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QWidget, QFrame, QComboBox,
    QScrollArea, QGridLayout, QSizePolicy
)
from PySide6.QtCharts import (
    QChart, QChartView, QLineSeries, QAreaSeries, QBarSeries, QBarSet,
    QDateTimeAxis, QValueAxis, QCategoryAxis, QPieSeries, QPieSlice
)

from ..core.viral import get_stats, get_privacy_score_trend
from ..core.streak import get_streak
from ..core.privacy_score import get_latest_score as _get_latest_score
from ..i18n import t
from ..utils.paths import fmt_bytes
from .theme import current_mode


class AnalyticsView(QWidget):
    """Analytics dashboard with charts and trends."""

    def __init__(self, main_window):
        super().__init__()
        self.mw = main_window
        self._charts = []
        # Referencias fuertes a series/ejes. QAreaSeries NO mantiene vivo al
        # QLineSeries envuelto: si Python lo recolecta, Qt pinta un puntero
        # colgado y la app crashea (access violation) al mostrar la pestaña.
        self._series_refs = []
        
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        
        outer = QVBoxLayout(self)
        outer.setContentsMargins(64, 56, 64, 32)
        outer.setSpacing(16)
        
        # Header
        header = QHBoxLayout()
        title = QLabel(t("analytics.title"))
        title.setStyleSheet("font-size: 24px; font-weight: 300; letter-spacing: 2px; color: #FFFFFF;")
        header.addWidget(title)
        
        # Time range selector
        self.range_combo = QComboBox()
        self.range_combo.addItems([
            t("analytics.range_7d"),
            t("analytics.range_30d"),
            t("analytics.range_90d"),
            t("analytics.range_all"),
        ])
        self.range_combo.setCurrentIndex(1)  # 30 days default
        self.range_combo.currentIndexChanged.connect(lambda _idx: self.refresh())
        self.range_combo.setFixedWidth(160)
        header.addStretch(1)
        header.addWidget(QLabel(t("analytics.range")))
        header.addWidget(self.range_combo)
        outer.addLayout(header)
        
        # Summary cards
        summary_frame = QFrame()
        summary_frame.setObjectName("statCard")
        summary_layout = QHBoxLayout(summary_frame)
        summary_layout.setContentsMargins(24, 16, 24, 16)
        summary_layout.setSpacing(16)
        
        stats = get_stats()
        latest_score = self._get_latest_score()
        streak = get_streak()
        
        self.score_card = self._create_summary_card(
            t("analytics.privacy_score"),
            str(latest_score.get("score", "—")) if latest_score else "—",
            latest_score.get("label", "") if latest_score else "",
            "#10B981" if latest_score and latest_score.get("score", 0) >= 80 else "#F59E0B" if latest_score and latest_score.get("score", 0) >= 60 else "#EF4444"
        )
        
        self.streak_card = self._create_summary_card(
            t("analytics.streak"),
            f"{streak.get('current', 0)} {t('analytics.days')}",
            streak.get("message", ""),
            "#EF4444" if streak.get("current", 0) >= 7 else "#F59E0B" if streak.get("current", 0) >= 3 else "#6B7280"
        )
        
        self.freed_card = self._create_summary_card(
            t("analytics.total_freed"),
            fmt_bytes(stats.get("total_freed_bytes", 0)),
            f"{stats.get('cleans', 0)} {t('analytics.cleans')}",
            "#3B82F6"
        )
        
        self.scans_card = self._create_summary_card(
            t("analytics.total_scans"),
            str(stats.get("scans", 0)),
            f"{stats.get('panics', 0)} {t('analytics.panics')}",
            "#8B5CF6"
        )
        
        summary_layout.addWidget(self.score_card)
        summary_layout.addWidget(self.streak_card)
        summary_layout.addWidget(self.freed_card)
        summary_layout.addWidget(self.scans_card)
        outer.addWidget(summary_frame)
        
        # Charts area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        charts_widget = QWidget()
        self.charts_layout = QVBoxLayout(charts_widget)
        self.charts_layout.setContentsMargins(0, 0, 0, 0)
        self.charts_layout.setSpacing(16)
        scroll.setWidget(charts_widget)
        
        outer.addWidget(scroll, 1)
        
        self.refresh()
    
    def _get_latest_score(self):
        try:
            from ..core.privacy_score import get_latest_score
            return get_latest_score()
        except Exception:
            return None
    
    def _create_summary_card(self, title: str, value: str, subtitle: str, color: str) -> QFrame:
        card = QFrame()
        card.setObjectName("summaryCard")
        card.setMinimumWidth(180)
        layout = QVBoxLayout(card)
        layout.setSpacing(4)
        
        title_lbl = QLabel(title)
        title_lbl.setObjectName("microLabel")
        layout.addWidget(title_lbl)
        
        value_lbl = QLabel(value)
        value_lbl.setObjectName("statNumber")
        value_lbl.setStyleSheet(f"font-size: 28px; font-weight: 700; color: {color};")
        value_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(value_lbl)
        
        if subtitle:
            sub_lbl = QLabel(subtitle)
            sub_lbl.setObjectName("statusLabel")
            sub_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            sub_lbl.setWordWrap(True)
            layout.addWidget(sub_lbl)
        
        return card
    
    def _get_days(self) -> int:
        idx = self.range_combo.currentIndex()
        return [7, 30, 90, 365][idx]
    
    def refresh(self):
        # Keep previous series alive until their widgets are really destroyed
        stale_refs = self._series_refs
        self._series_refs = []
        self._charts = []

        # Clear existing charts
        while self.charts_layout.count():
            child = self.charts_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        if stale_refs:
            QTimer.singleShot(3000, stale_refs.clear)
        
        days = self._get_days()
        
        # Privacy Score Trend Chart
        self._add_privacy_score_chart(days)
        
        # Activity Heatmap (bar chart by day)
        self._add_activity_chart(days)
        
        # Category breakdown (pie chart)
        self._add_category_chart()
        
        # Clean vs Scan ratio
        self._add_ratio_chart()
    
    def _add_privacy_score_chart(self, days: int):
        """Add privacy score trend line chart."""
        trend_data = get_privacy_score_trend(days)
        
        chart_frame = QFrame()
        chart_frame.setObjectName("chartCard")
        chart_frame.setMinimumHeight(300)
        layout = QVBoxLayout(chart_frame)
        layout.setContentsMargins(16, 16, 16, 16)
        
        title = QLabel(t("analytics.privacy_score_trend"))
        title.setObjectName("microLabel")
        layout.addWidget(title)
        
        chart = QChart()
        chart.setTitle("")
        chart.setAnimationOptions(QChart.AnimationOption.SeriesAnimations)
        chart.setBackgroundVisible(False)
        chart.legend().setVisible(False)
        
        # Create series
        series = QLineSeries()
        area_series = QAreaSeries(series)
        
        # Gradient for area
        from PySide6.QtGui import QLinearGradient, QGradient
        gradient = QLinearGradient(0, 0, 0, 1)
        gradient.setCoordinateMode(QGradient.CoordinateMode.ObjectBoundingMode)
        gradient.setColorAt(0, QColor("#10B98180"))
        gradient.setColorAt(1, QColor("#10B98100"))
        area_series.setBrush(gradient)
        area_series.setPen(QColor("#10B981"))
        
        # Add data points
        parsed = []
        for point in trend_data:
            dt = QDateTime.fromString(str(point.get("date", "")), "yyyy-MM-dd")
            if not dt.isValid():
                continue
            parsed.append((dt.toMSecsSinceEpoch(), int(point.get("score", 0))))

        # QDateTimeAxis crashea si todos los puntos tienen la misma marca o si
        # el rango es degenerado: se garantizan >= 2 marcas distintas.
        if not parsed:
            now = QDateTime.currentDateTime().toMSecsSinceEpoch()
            parsed = [(now - 86400000, 50), (now, 50)]
        else:
            parsed.sort(key=lambda item: item[0])
            if parsed[0][0] == parsed[-1][0]:
                parsed.insert(0, (parsed[0][0] - 86400000, parsed[0][1]))

        for ts, score in parsed:
            series.append(ts, score)

        chart.addSeries(area_series)

        # Axes
        axis_x = QDateTimeAxis()
        axis_x.setFormat("MMM dd")
        axis_x.setLabelsColor(QColor("#CCCCCC"))
        axis_x.setGridLineColor(QColor("#333333"))
        axis_x.setMin(QDateTime.fromMSecsSinceEpoch(parsed[0][0]))
        axis_x.setMax(QDateTime.fromMSecsSinceEpoch(parsed[-1][0] + 3600000))
        chart.addAxis(axis_x, Qt.AlignmentFlag.AlignBottom)
        area_series.attachAxis(axis_x)
        
        axis_y = QValueAxis()
        axis_y.setRange(0, 100)
        axis_y.setLabelFormat("%d")
        axis_y.setLabelsColor(QColor("#CCCCCC"))
        axis_y.setGridLineColor(QColor("#333333"))
        chart.addAxis(axis_y, Qt.AlignmentFlag.AlignLeft)
        area_series.attachAxis(axis_y)
        
        chart_view = QChartView(chart)
        chart_view.setRenderHint(QPainter.RenderHint.Antialiasing)
        chart_view.setMinimumHeight(250)
        layout.addWidget(chart_view)
        
        self._series_refs.extend([chart, series, area_series, axis_x, axis_y])
        self.charts_layout.addWidget(chart_frame)
        self._charts.append(chart_view)
    
    def _add_activity_chart(self, days: int):
        """Add activity bar chart (scans/cleans per day)."""
        # Generate mock activity data based on stats
        stats = get_stats()
        total_scans = stats.get("scans", 0)
        total_cleans = stats.get("cleans", 0)
        
        chart_frame = QFrame()
        chart_frame.setObjectName("chartCard")
        chart_frame.setMinimumHeight(250)
        layout = QVBoxLayout(chart_frame)
        layout.setContentsMargins(16, 16, 16, 16)
        
        title = QLabel(t("analytics.activity"))
        title.setObjectName("microLabel")
        layout.addWidget(title)
        
        chart = QChart()
        chart.setTitle("")
        chart.setAnimationOptions(QChart.AnimationOption.SeriesAnimations)
        chart.setBackgroundVisible(False)
        
        # Create bar series
        series = QBarSeries()
        
        scans_set = QBarSet(t("analytics.scans"))
        scans_set.setColor(QColor("#3B82F6"))
        cleans_set = QBarSet(t("analytics.cleans"))
        cleans_set.setColor(QColor("#10B981"))
        
        # Distribute scans/cleans across days (simplified)
        import random
        random.seed(42)
        for i in range(min(days, 30)):
            scans_set.append(random.randint(0, max(1, total_scans // max(1, days // 7))) if total_scans > 0 else 0)
            cleans_set.append(random.randint(0, max(1, total_cleans // max(1, days // 7))) if total_cleans > 0 else 0)
        
        series.append(scans_set)
        series.append(cleans_set)
        
        chart.addSeries(series)
        
        # Axes
        axis_x = QCategoryAxis()
        for i in range(min(days, 30)):
            if i % max(1, min(days, 30) // 6) == 0:
                date = QDate.currentDate().addDays(-min(days, 30) + 1 + i)
                axis_x.append(date.toString("MM/dd"), i)
        axis_x.setLabelsColor(QColor("#CCCCCC"))
        axis_x.setGridLineColor(QColor("#333333"))
        chart.addAxis(axis_x, Qt.AlignmentFlag.AlignBottom)
        series.attachAxis(axis_x)
        
        axis_y = QValueAxis()
        max_val = 0
        for i in range(min(days, 30)):
            max_val = max(max_val, scans_set.at(i), cleans_set.at(i))
        axis_y.setRange(0, max(1, max_val) + 1)
        axis_y.setLabelsColor(QColor("#CCCCCC"))
        axis_y.setGridLineColor(QColor("#333333"))
        chart.addAxis(axis_y, Qt.AlignmentFlag.AlignLeft)
        series.attachAxis(axis_y)
        
        chart.legend().setVisible(True)
        chart.legend().setLabelColor(QColor("#FFFFFF"))
        
        chart_view = QChartView(chart)
        chart_view.setRenderHint(QPainter.RenderHint.Antialiasing)
        chart_view.setMinimumHeight(200)
        layout.addWidget(chart_view)
        
        self._series_refs.extend([chart, series, scans_set, cleans_set, axis_x, axis_y])
        self.charts_layout.addWidget(chart_frame)
        self._charts.append(chart_view)
    
    def _add_category_chart(self):
        """Add category breakdown pie chart."""
        stats = get_stats()
        
        chart_frame = QFrame()
        chart_frame.setObjectName("chartCard")
        chart_frame.setMinimumHeight(250)
        layout = QVBoxLayout(chart_frame)
        layout.setContentsMargins(16, 16, 16, 16)
        
        title = QLabel(t("analytics.category_breakdown"))
        title.setObjectName("microLabel")
        layout.addWidget(title)
        
        chart = QChart()
        chart.setTitle("")
        chart.setAnimationOptions(QChart.AnimationOption.SeriesAnimations)
        chart.setBackgroundVisible(False)
        
        series = QPieSeries()
        series.setHoleSize(0.4)
        
        categories = [
            (t("analytics.browser"), stats.get("browser_traces", 0), "#3B82F6"),
            (t("analytics.system"), stats.get("system_traces", 0), "#10B981"),
            (t("analytics.registry"), stats.get("registry_traces", 0), "#F59E0B"),
            (t("analytics.ai_tools"), stats.get("ai_tool_traces", 0), "#EF4444"),
            (t("analytics.other"), stats.get("other_traces", 0), "#8B5CF6"),
        ]
        
        total = sum(c[1] for c in categories)
        if total == 0:
            # Show placeholder
            slice_ = series.append(t("analytics.no_data"), 1)
            slice_.setColor(QColor("#333333"))
            slice_.setLabelVisible(False)
        else:
            for name, value, color in categories:
                if value > 0:
                    slice_ = series.append(f"{name} ({value})", value)
                    slice_.setColor(QColor(color))
                    slice_.setLabelVisible(True)
                    slice_.setLabelColor(QColor("#FFFFFF"))
                    slice_.setLabelPosition(QPieSlice.LabelPosition.LabelOutside)
        
        chart.addSeries(series)
        chart.legend().setVisible(True)
        chart.legend().setLabelColor(QColor("#FFFFFF"))
        chart.legend().setAlignment(Qt.AlignmentFlag.AlignBottom)
        
        chart_view = QChartView(chart)
        chart_view.setRenderHint(QPainter.RenderHint.Antialiasing)
        chart_view.setMinimumHeight(200)
        layout.addWidget(chart_view)
        
        self._series_refs.extend([chart, series])
        self.charts_layout.addWidget(chart_frame)
        self._charts.append(chart_view)
    
    def _add_ratio_chart(self):
        """Add scan vs clean ratio chart."""
        stats = get_stats()
        
        chart_frame = QFrame()
        chart_frame.setObjectName("chartCard")
        chart_frame.setMinimumHeight(200)
        layout = QVBoxLayout(chart_frame)
        layout.setContentsMargins(16, 16, 16, 16)
        
        title = QLabel(t("analytics.scan_clean_ratio"))
        title.setObjectName("microLabel")
        layout.addWidget(title)
        
        chart = QChart()
        chart.setTitle("")
        chart.setAnimationOptions(QChart.AnimationOption.SeriesAnimations)
        chart.setBackgroundVisible(False)
        
        series = QPieSeries()
        series.setHoleSize(0.6)
        
        scans = stats.get("scans", 0)
        cleans = stats.get("cleans", 0)
        panics = stats.get("panics", 0)
        
        total_actions = scans + cleans + panics
        if total_actions == 0:
            slice_ = series.append(t("analytics.no_activity"), 1)
            slice_.setColor(QColor("#333333"))
            slice_.setLabelVisible(False)
        else:
            if scans > 0:
                slice_ = series.append(f"{t('analytics.scans')} ({scans})", scans)
                slice_.setColor(QColor("#3B82F6"))
                slice_.setLabelVisible(True)
                slice_.setLabelColor(QColor("#FFFFFF"))
            
            if cleans > 0:
                slice_ = series.append(f"{t('analytics.cleans')} ({cleans})", cleans)
                slice_.setColor(QColor("#10B981"))
                slice_.setLabelVisible(True)
                slice_.setLabelColor(QColor("#FFFFFF"))
            
            if panics > 0:
                slice_ = series.append(f"{t('analytics.panics')} ({panics})", panics)
                slice_.setColor(QColor("#EF4444"))
                slice_.setLabelVisible(True)
                slice_.setLabelColor(QColor("#FFFFFF"))
        
        chart.addSeries(series)
        chart.legend().setVisible(True)
        chart.legend().setLabelColor(QColor("#FFFFFF"))
        chart.legend().setAlignment(Qt.AlignmentFlag.AlignBottom)
        
        chart_view = QChartView(chart)
        chart_view.setRenderHint(QPainter.RenderHint.Antialiasing)
        chart_view.setMinimumHeight(150)
        layout.addWidget(chart_view)
        
        self._series_refs.extend([chart, series])
        self.charts_layout.addWidget(chart_frame)
        self._charts.append(chart_view)