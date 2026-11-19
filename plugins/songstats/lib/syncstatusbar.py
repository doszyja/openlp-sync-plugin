# -*- coding: utf-8 -*-
"""KWCH sync strip in the main menu bar (OpenLP has no visible toolbars)."""
import qtawesome as qta
from PyQt5 import QtCore, QtGui, QtWidgets

from openlp.core.common.i18n import translate
from openlp.core.ui.icons import UiIcons

_STATUS_ICON_SIZE = 24
_SYNC_ICON_SIZE = 20
_ACCOUNT_TOOLBAR_ICON_SIZE = 22
_ACCOUNT_MENU_HEADER_AVATAR = 56
_ACCOUNT_MENU_HEADER_WIDTH = 252
_AVATAR_MIN_LOADED_WIDTH = 256
_CHIP_FONT_PT_DELTA = 0
_CHIP_LAYOUT_MARGIN = (6, 2, 6, 2)
_HEADER_ITEM_SPACING = 6
_TOOLBAR_RIGHT_MARGIN = 8
_TOOL_BUTTON_MAX_HEIGHT = 28
_PROGRESS_BAR_WIDTH = 120
_PROGRESS_BAR_CHECK_WIDTH = 56
_PROGRESS_BAR_HEIGHT = 18
_CHIP_TEXT_MAX_WIDTH = 168
_FIT_SLACK = 20
# Below this window width the header may collapse to icons only.
_ICON_ONLY_WINDOW_WIDTH = 960
# Gap between OpenLP's File/View/… menus and this corner widget.
_MENUBAR_CLEARANCE = 32
_MIN_HEADER_WIDTH = 48
# Collapse chips/label so the menubar never wraps (wrapping shrinks the
# central widget and OpenLP's live controller then resize-loops).
_DENSITY_FULL = 0
_DENSITY_COMPACT = 1
_DENSITY_HIDE_DATABASE = 2
_DENSITY_HIDE_SYNC = 3
_DENSITY_HIDE_CHIPS = 4
_DENSITY_MINIMAL = 5
_QWIDGETSIZE_MAX = 16777215


class StatusChip(QtWidgets.QWidget):
    """Icon + one-line label (title and value side by side)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('songstats_status_chip')
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(*_CHIP_LAYOUT_MARGIN)
        layout.setSpacing(_HEADER_ITEM_SPACING)
        layout.setAlignment(QtCore.Qt.AlignVCenter)

        self.icon_label = QtWidgets.QLabel(self)
        self.icon_label.setFixedSize(_STATUS_ICON_SIZE, _STATUS_ICON_SIZE)
        self.icon_label.setAlignment(QtCore.Qt.AlignCenter)
        self.icon_label.setScaledContents(True)

        self.text_label = QtWidgets.QLabel(self)
        chip_font = self.text_label.font()
        chip_font.setPointSize(max(chip_font.pointSize() + _CHIP_FONT_PT_DELTA, 8))
        chip_font.setWeight(QtGui.QFont.Normal)
        chip_font.setBold(False)
        self.text_label.setFont(chip_font)
        self.text_label.setWordWrap(False)
        self.text_label.setTextFormat(QtCore.Qt.RichText)
        self.text_label.setSizePolicy(
            QtWidgets.QSizePolicy.Maximum,
            QtWidgets.QSizePolicy.Preferred,
        )
        self.text_label.setMinimumWidth(0)

        layout.addWidget(self.icon_label)
        layout.addWidget(self.text_label)
        self.setSizePolicy(QtWidgets.QSizePolicy.Maximum, QtWidgets.QSizePolicy.Fixed)

    def _set_icon_pixmap(self, pixmap):
        if pixmap is None or pixmap.isNull():
            return
        self.icon_label.setPixmap(
            pixmap.scaled(
                _STATUS_ICON_SIZE,
                _STATUS_ICON_SIZE,
                QtCore.Qt.KeepAspectRatioByExpanding,
                QtCore.Qt.SmoothTransformation,
            )
        )

    def set_state(self, icon, title, value, tip='', compact=False, max_text_width=0, icon_only=False, pixmap=None):
        if pixmap is not None and not pixmap.isNull():
            self._set_icon_pixmap(pixmap)
        elif icon is not None:
            self.icon_label.setPixmap(icon.pixmap(_STATUS_ICON_SIZE, _STATUS_ICON_SIZE))
        self.setToolTip(tip or '')
        if icon_only:
            self.text_label.hide()
            return
        display_value = value if value else title
        self.text_label.show()
        budget = max_text_width or (
            _CHIP_TEXT_MAX_WIDTH if not compact else 96
        )
        fm = self.text_label.fontMetrics()
        if compact:
            self.text_label.setTextFormat(QtCore.Qt.PlainText)
            self.text_label.setText(
                fm.elidedText(display_value, QtCore.Qt.ElideRight, max(32, budget))
            )
        else:
            self.text_label.setTextFormat(QtCore.Qt.RichText)
            if value:
                self.text_label.setText(
                    '<span style="color:#888;">{title}</span> {value}'.format(
                        title=title,
                        value=value,
                    )
                )
            else:
                self.text_label.setText(title)


def _short_sync_time(time_str):
    """Display sync time without long ISO date in the menubar chip."""
    if not time_str:
        return ''
    parts = time_str.split()
    if len(parts) >= 2 and len(parts[0]) >= 10 and '-' in parts[0]:
        y, m, d = parts[0].split('-')[:3]
        return '{day}.{month} {clock}'.format(day=d, month=m, clock=parts[1])
    return time_str[:14]


def _circle_pixmap(source, logical_size, device_pixel_ratio=1.0):
    """
    Round avatar at exactly logical_size×logical_size device pixels (DPR = 1 on
    the result). Using setDevicePixelRatio on a pixmap inside fixed QLabels /
    QToolButtons often shows only the top-left quadrant on Windows.
    """
    if source is None or source.isNull():
        return QtGui.QPixmap()
    logical_size = max(1, int(logical_size))
    supersample = max(3.0, float(device_pixel_ratio))
    work = max(1, int(round(logical_size * supersample)))
    scaled = source.scaled(
        work,
        work,
        QtCore.Qt.KeepAspectRatio,
        QtCore.Qt.SmoothTransformation,
    )
    canvas = QtGui.QPixmap(work, work)
    canvas.fill(QtCore.Qt.transparent)
    painter = QtGui.QPainter(canvas)
    painter.setRenderHint(QtGui.QPainter.Antialiasing)
    painter.setRenderHint(QtGui.QPainter.SmoothPixmapTransform)
    path = QtGui.QPainterPath()
    path.addEllipse(0, 0, work, work)
    painter.setClipPath(path)
    x = (work - scaled.width()) // 2
    y = (work - scaled.height()) // 2
    painter.drawPixmap(x, y, scaled)
    painter.end()
    if work == logical_size:
        canvas.setDevicePixelRatio(1.0)
        return canvas
    result = canvas.scaled(
        logical_size,
        logical_size,
        QtCore.Qt.IgnoreAspectRatio,
        QtCore.Qt.SmoothTransformation,
    )
    result.setDevicePixelRatio(1.0)
    return result


def _themed_icon(name, **kwargs):
    try:
        return UiIcons().get_icon_variant(name, **kwargs)
    except KeyError:
        # Community plugins must not crash OpenLP if UiIcons has no such key.
        return qta.icon('mdi.{0}'.format(name.replace('_', '-')), **kwargs)


class SyncHeaderWidget(QtCore.QObject):
    """
    Menu bar top-right: compact sync, KWCH menu, status chips (vertically centered).
    """

    sync_clicked = QtCore.pyqtSignal()
    check_updates_clicked = QtCore.pyqtSignal()
    cancel_sync_clicked = QtCore.pyqtSignal()
    configure_requested = QtCore.pyqtSignal()
    login_requested = QtCore.pyqtSignal()
    logout_requested = QtCore.pyqtSignal()
    open_web_requested = QtCore.pyqtSignal()
    about_requested = QtCore.pyqtSignal()

    def __init__(self, main_window):
        super().__init__(main_window)
        self._main_window = main_window
        self._fitting = False
        self._activity_mode = False
        self._activity_message = ''
        self._density = _DENSITY_FULL
        self._last_fitted_width = None
        self._last_icons_only = None
        self._show_sync_primary = False
        self._status_panel_args = None
        self._version_checking = False
        self._avatar_url = ''
        self._avatar_pixmap = QtGui.QPixmap()
        self._avatar_load_busy = False

        self.header_panel = QtWidgets.QWidget(main_window)
        self.header_panel.setObjectName('songstats_sync_header_panel')
        panel_layout = QtWidgets.QHBoxLayout(self.header_panel)
        panel_layout.setContentsMargins(0, 0, _TOOLBAR_RIGHT_MARGIN, 0)
        panel_layout.setSpacing(0)
        panel_layout.setAlignment(QtCore.Qt.AlignVCenter)
        self.header_panel.setSizePolicy(
            QtWidgets.QSizePolicy.Maximum,
            QtWidgets.QSizePolicy.Preferred,
        )

        self.status_frame = QtWidgets.QFrame(self.header_panel)
        self.status_frame.setSizePolicy(
            QtWidgets.QSizePolicy.Maximum,
            QtWidgets.QSizePolicy.Preferred,
        )
        self.status_frame.setObjectName('songstats_status_frame')
        self.status_frame.setFrameShape(QtWidgets.QFrame.NoFrame)
        status_layout = QtWidgets.QHBoxLayout(self.status_frame)
        status_layout.setContentsMargins(0, 0, 0, 0)
        status_layout.setSpacing(_HEADER_ITEM_SPACING)
        status_layout.setAlignment(QtCore.Qt.AlignVCenter)

        self.sync_button = QtWidgets.QToolButton(self.status_frame)
        self.sync_button.setObjectName('songstats_sync_button')
        self.sync_button.setAutoRaise(True)
        self.sync_button.setIcon(UiIcons().download)
        self.sync_button.setIconSize(QtCore.QSize(_SYNC_ICON_SIZE, _SYNC_ICON_SIZE))
        self.sync_button.setToolButtonStyle(QtCore.Qt.ToolButtonTextBesideIcon)
        sync_font = self.sync_button.font()
        sync_font.setPointSize(max(sync_font.pointSize() + _CHIP_FONT_PT_DELTA, 8))
        sync_font.setWeight(QtGui.QFont.Normal)
        self.sync_button.setFont(sync_font)
        self.sync_button.setMaximumHeight(_TOOL_BUTTON_MAX_HEIGHT)
        self.sync_button.clicked.connect(self.sync_clicked.emit)

        self.check_updates_button = QtWidgets.QToolButton(self.status_frame)
        self.check_updates_button.setObjectName('songstats_check_updates_button')
        self.check_updates_button.setAutoRaise(True)
        self.check_updates_button.setIcon(
            qta.icon('mdi.cloud-sync-outline', color='#666')
        )
        self.check_updates_button.setIconSize(QtCore.QSize(_SYNC_ICON_SIZE, _SYNC_ICON_SIZE))
        self.check_updates_button.setToolButtonStyle(QtCore.Qt.ToolButtonTextBesideIcon)
        check_font = self.check_updates_button.font()
        check_font.setPointSize(max(check_font.pointSize() + _CHIP_FONT_PT_DELTA, 8))
        check_font.setWeight(QtGui.QFont.Normal)
        self.check_updates_button.setFont(check_font)
        self.check_updates_button.setMaximumHeight(_TOOL_BUTTON_MAX_HEIGHT)
        self.check_updates_button.clicked.connect(self.check_updates_clicked.emit)

        self.stop_button = QtWidgets.QToolButton(self.status_frame)
        self.stop_button.setObjectName('songstats_stop_sync_button')
        self.stop_button.setAutoRaise(True)
        self.stop_button.setIcon(qta.icon('mdi.stop-circle-outline', color='orange'))
        self.stop_button.setIconSize(QtCore.QSize(_SYNC_ICON_SIZE, _SYNC_ICON_SIZE))
        self.stop_button.setToolButtonStyle(QtCore.Qt.ToolButtonTextBesideIcon)
        stop_font = self.stop_button.font()
        stop_font.setPointSize(max(stop_font.pointSize() + _CHIP_FONT_PT_DELTA, 8))
        self.stop_button.setFont(stop_font)
        self.stop_button.setMaximumHeight(_TOOL_BUTTON_MAX_HEIGHT)
        self.stop_button.clicked.connect(self.cancel_sync_clicked.emit)
        self.stop_button.hide()

        self.account_button = QtWidgets.QToolButton(self.status_frame)
        self.account_button.setObjectName('songstats_account_menu')
        self.account_button.setPopupMode(QtWidgets.QToolButton.InstantPopup)
        self.account_button.setAutoRaise(True)
        self.account_button.setIcon(_themed_icon('authentication'))
        self.account_button.setIconSize(QtCore.QSize(_SYNC_ICON_SIZE, _SYNC_ICON_SIZE))
        self.account_button.setToolButtonStyle(QtCore.Qt.ToolButtonTextBesideIcon)
        self.account_button.setMaximumHeight(_TOOL_BUTTON_MAX_HEIGHT)
        account_font = self.account_button.font()
        account_font.setPointSize(max(account_font.pointSize() + _CHIP_FONT_PT_DELTA, 8))
        account_font.setWeight(QtGui.QFont.DemiBold)
        self.account_button.setFont(account_font)
        self._account_menu = QtWidgets.QMenu(self.account_button)
        self.account_button.setMenu(self._account_menu)
        self._build_account_menu()
        self._account_menu.aboutToShow.connect(self._refresh_account_menu_header)

        self.chip_database = StatusChip(self.status_frame)
        self.chip_sync = StatusChip(self.status_frame)

        self.progress_bar = QtWidgets.QProgressBar(self.status_frame)
        self.progress_bar.setFixedWidth(_PROGRESS_BAR_WIDTH)
        self.progress_bar.setMaximumHeight(_PROGRESS_BAR_HEIGHT)
        self.progress_bar.hide()

        self.activity_label = QtWidgets.QLabel(self.status_frame)
        self.activity_label.hide()
        activity_font = self.activity_label.font()
        activity_font.setPointSize(max(activity_font.pointSize() + _CHIP_FONT_PT_DELTA, 8))
        activity_font.setItalic(True)
        self.activity_label.setFont(activity_font)

        status_layout.addWidget(self.progress_bar)
        status_layout.addWidget(self.sync_button)
        status_layout.addWidget(self.check_updates_button)
        status_layout.addWidget(self.stop_button)
        status_layout.addWidget(self.account_button)
        status_layout.addWidget(self.chip_database)
        status_layout.addWidget(self.chip_sync)
        status_layout.addWidget(self.activity_label)

        panel_layout.addWidget(self.status_frame, alignment=QtCore.Qt.AlignVCenter)

        menubar = main_window.menuBar()
        menubar.setCornerWidget(self.header_panel, QtCore.Qt.TopRightCorner)
        menubar.installEventFilter(self)
        main_window.installEventFilter(self)

        self._fit_timer = QtCore.QTimer(self)
        self._fit_timer.setSingleShot(True)
        self._fit_timer.setInterval(0)
        self._fit_timer.timeout.connect(self._fit_to_menubar)

        self._retranslate()
        self._apply_chip_placeholders()
        self.set_primary_catalog_action(False)
        self._schedule_fit()

    def _build_account_menu(self):
        self._account_menu.clear()

        header_row_h = _ACCOUNT_MENU_HEADER_AVATAR + 16
        self._menu_header_widget = QtWidgets.QWidget(self._account_menu)
        self._menu_header_widget.setMinimumSize(
            _ACCOUNT_MENU_HEADER_WIDTH,
            header_row_h,
        )
        self._menu_header_widget.setMaximumHeight(header_row_h)
        self._menu_header_widget.setAttribute(
            QtCore.Qt.WA_TransparentForMouseEvents,
            True,
        )
        self._menu_header_widget.setFocusPolicy(QtCore.Qt.NoFocus)
        header_layout = QtWidgets.QHBoxLayout(self._menu_header_widget)
        header_layout.setContentsMargins(12, 4, 12, 4)
        header_layout.setSpacing(10)
        header_layout.setAlignment(QtCore.Qt.AlignVCenter)

        self._menu_header_avatar = QtWidgets.QLabel(self._menu_header_widget)
        self._menu_header_avatar.setFixedSize(
            _ACCOUNT_MENU_HEADER_AVATAR,
            _ACCOUNT_MENU_HEADER_AVATAR,
        )
        self._menu_header_avatar.setAlignment(QtCore.Qt.AlignCenter)
        self._menu_header_avatar.setScaledContents(False)
        self._menu_header_avatar.setAttribute(
            QtCore.Qt.WA_TransparentForMouseEvents,
            True,
        )

        self._menu_header_name = QtWidgets.QLabel(self._menu_header_widget)
        header_name_font = self._menu_header_name.font()
        header_name_font.setWeight(QtGui.QFont.DemiBold)
        self._menu_header_name.setFont(header_name_font)
        self._menu_header_name.setAttribute(
            QtCore.Qt.WA_TransparentForMouseEvents,
            True,
        )
        palette = self._menu_header_name.palette()
        palette.setColor(
            QtGui.QPalette.WindowText,
            palette.color(QtGui.QPalette.Text),
        )
        palette.setColor(
            QtGui.QPalette.Text,
            palette.color(QtGui.QPalette.Text),
        )
        self._menu_header_name.setPalette(palette)
        self._menu_header_name.setWordWrap(False)
        self._menu_header_name.setSizePolicy(
            QtWidgets.QSizePolicy.Ignored,
            QtWidgets.QSizePolicy.Preferred,
        )

        header_layout.addWidget(self._menu_header_avatar)
        header_layout.addWidget(self._menu_header_name, 1)

        self._header_action = QtWidgets.QWidgetAction(self._account_menu)
        self._header_action.setDefaultWidget(self._menu_header_widget)
        self._header_action.setEnabled(True)
        self._header_action.setVisible(True)
        self._account_menu.addAction(self._header_action)
        self._header_separator = self._account_menu.addSeparator()
        self._menu_header_widget.hide()

        self._act_configure = self._account_menu.addAction('')
        self._act_configure.triggered.connect(self.configure_requested.emit)
        self._act_login = self._account_menu.addAction('')
        self._act_login.triggered.connect(self.login_requested.emit)
        self._act_logout = self._account_menu.addAction('')
        self._act_logout.triggered.connect(self.logout_requested.emit)
        self._act_web = self._account_menu.addAction('')
        self._act_web.triggered.connect(self.open_web_requested.emit)
        self._account_menu.addSeparator()
        self._act_about = self._account_menu.addAction('')
        self._act_about.triggered.connect(self.about_requested.emit)

    def detach(self):
        if self._fit_timer.isActive():
            self._fit_timer.stop()
        menubar = self._main_window.menuBar()
        menubar.removeEventFilter(self)
        self._main_window.removeEventFilter(self)
        menubar.setCornerWidget(None, QtCore.Qt.TopRightCorner)
        self.header_panel.deleteLater()
        self.header_panel = None

    def eventFilter(self, watched, event):
        if self._fitting:
            return super().eventFilter(watched, event)
        if event.type() in (QtCore.QEvent.Resize, QtCore.QEvent.Show):
            self._schedule_fit()
        return super().eventFilter(watched, event)

    def _schedule_fit(self):
        if self._fitting or self.header_panel is None:
            return
        if not self._fit_timer.isActive():
            self._fit_timer.start()

    def _native_menus_width(self):
        """Width needed by OpenLP's own menu titles on a single menubar row."""
        menubar = self._main_window.menuBar()
        style = menubar.style()
        fm = menubar.fontMetrics()
        hmargin = style.pixelMetric(QtWidgets.QStyle.PM_MenuBarHMargin, None, menubar)
        spacing = style.pixelMetric(QtWidgets.QStyle.PM_MenuBarItemSpacing, None, menubar)
        width = max(hmargin, 0) * 2
        first = True
        for action in menubar.actions():
            if not action.isVisible() or action.isSeparator():
                continue
            opt = QtWidgets.QStyleOptionMenuItem()
            opt.initFrom(menubar)
            opt.text = action.text()
            opt.font = menubar.font()
            content = fm.size(QtCore.Qt.TextShowMnemonic, action.text())
            size = style.sizeFromContents(QtWidgets.QStyle.CT_MenuBarItem, opt, content, menubar)
            if not first:
                width += max(spacing, 0)
            first = False
            width += max(size.width(), content.width() + 16)
        return width

    def _available_header_width(self):
        menubar = self._main_window.menuBar()
        leftover = menubar.width() - self._native_menus_width() - _MENUBAR_CLEARANCE
        if self._wide_layout():
            leftover += 64
        return max(leftover, 0)

    def _wide_layout(self):
        return self._main_window.width() >= _ICON_ONLY_WINDOW_WIDTH

    def _icons_only(self):
        return not self._wide_layout()

    def _set_action_button_style(self, icon_only, account_icon_only):
        style = (
            QtCore.Qt.ToolButtonIconOnly
            if icon_only
            else QtCore.Qt.ToolButtonTextBesideIcon
        )
        self.sync_button.setToolButtonStyle(style)
        self.check_updates_button.setToolButtonStyle(style)
        self.stop_button.setToolButtonStyle(style)
        self.account_button.setToolButtonStyle(
            QtCore.Qt.ToolButtonIconOnly
            if account_icon_only
            else QtCore.Qt.ToolButtonTextBesideIcon
        )

    def _elide_activity(self, max_width):
        text = self._activity_message or ''
        if not text:
            self.activity_label.setText('')
            return
        fm = self.activity_label.fontMetrics()
        self.activity_label.setText(
            fm.elidedText(text, QtCore.Qt.ElideMiddle, max(24, max_width))
        )

    def _apply_density(self, density, available):
        self._density = density
        wide = self._wide_layout()
        icons_only = not wide
        if wide:
            button_icons_only = density >= _DENSITY_HIDE_CHIPS
            account_icons_only = density >= _DENSITY_HIDE_CHIPS
        else:
            button_icons_only = icons_only or density >= _DENSITY_COMPACT
            account_icons_only = icons_only or density >= _DENSITY_MINIMAL
        self._set_action_button_style(
            icon_only=button_icons_only,
            account_icon_only=account_icons_only,
        )
        if self._activity_mode:
            for chip in (self.chip_database, self.chip_sync):
                chip.hide()
            self.account_button.hide()
            compact_progress = icons_only or density >= _DENSITY_COMPACT
            bar_width = 72 if compact_progress else _PROGRESS_BAR_WIDTH
            self.progress_bar.setFixedWidth(bar_width)
            self.progress_bar.show()
            if icons_only:
                self.activity_label.hide()
            else:
                reserved = 80 if density >= _DENSITY_MINIMAL else 110
                reserved += self.progress_bar.width()
                self.activity_label.show()
                self._elide_activity(available - reserved)
        else:
            self._render_status_panel()
            self.chip_database.setVisible(density < _DENSITY_HIDE_DATABASE)
            self.chip_sync.setVisible(density < _DENSITY_HIDE_SYNC)
            self.account_button.setVisible(density < _DENSITY_HIDE_CHIPS)
            if self._version_checking:
                compact_progress = density >= _DENSITY_COMPACT
                self.progress_bar.setFixedWidth(
                    40 if compact_progress else _PROGRESS_BAR_CHECK_WIDTH
                )
                self.progress_bar.setRange(0, 0)
                self.progress_bar.show()
            elif not self.stop_button.isVisible():
                self.progress_bar.hide()
    def _fit_to_menubar(self):
        """Shrink header contents until they fit beside the native menus."""
        if self._fitting or self.header_panel is None:
            return
        menubar = self._main_window.menuBar()
        if menubar is None or menubar.width() < 10:
            return
        self._fitting = True
        try:
            available = self._available_header_width()
            self.header_panel.setMinimumWidth(0)
            self.header_panel.setMaximumWidth(_QWIDGETSIZE_MAX)
            if available < _MIN_HEADER_WIDTH:
                if menubar.cornerWidget() is self.header_panel:
                    menubar.setCornerWidget(None, QtCore.Qt.TopRightCorner)
                self.header_panel.hide()
                self._last_fitted_width = 0
                return
            self.header_panel.show()
            wide = self._wide_layout()
            start_density = _DENSITY_FULL
            max_density = _DENSITY_HIDE_CHIPS if wide else _DENSITY_MINIMAL
            for density in range(start_density, max_density + 1):
                self._apply_density(density, available)
                QtWidgets.QApplication.processEvents(
                    QtCore.QEventLoop.ExcludeUserInputEvents
                )
                self.header_panel.adjustSize()
                need = self.header_panel.sizeHint().width()
                if need + _FIT_SLACK <= available:
                    break
            need = self.header_panel.sizeHint().width()
            # Prefer the content width so labels are not clipped to zero.
            fitted = max(need, 1)
            if available and fitted > available:
                fitted = max(available, 1)
            already_placed = menubar.cornerWidget() is self.header_panel
            icons_only = self._icons_only()
            if (
                already_placed
                and self._last_fitted_width == fitted
                and self.header_panel.width() == fitted
                and self._last_icons_only == icons_only
            ):
                self._render_status_panel()
                return
            self.header_panel.setMinimumWidth(0)
            self.header_panel.setMaximumWidth(fitted)
            self.header_panel.resize(fitted, self.header_panel.sizeHint().height())
            # Re-set even when already placed so QMenuBar re-reads width() and
            # does not wrap File/View/… onto a second line.
            menubar.setCornerWidget(self.header_panel, QtCore.Qt.TopRightCorner)
            self._last_fitted_width = fitted
            self._last_icons_only = self._icons_only()
            self._render_status_panel()
        finally:
            self._fitting = False

    def _apply_chip_placeholders(self):
        self.update_status_panel(
            remote_version='',
            local_version='',
            has_token=False,
            last_sync_status='',
            last_sync_time='',
            version_checking=False,
        )

    def _retranslate(self):
        self.sync_button.setText(translate('SongStatsPlugin', 'Synchronizuj'))
        self.check_updates_button.setText(
            translate('SongStatsPlugin', 'Sprawdź aktualizacje')
        )
        self.stop_button.setText(translate('SongStatsPlugin', 'Zatrzymaj'))
        self.sync_button.setToolTip('')
        self.stop_button.setToolTip('')
        self.check_updates_button.setToolTip('')
        self.account_button.setToolTip('')
        self._update_account_button()
        self._act_configure.setText(
            translate('SongStatsPlugin', 'Konfiguruj wtyczkę…')
        )
        self._act_login.setText(
            translate('SongStatsPlugin', 'Zaloguj przez przeglądarkę (Discord)…')
        )
        self._act_logout.setText(
            translate('SongStatsPlugin', 'Wyloguj z Discord…')
        )
        self._act_web.setText(
            translate('SongStatsPlugin', 'Otwórz stronę pieśni…')
        )
        self._act_about.setText(
            translate('SongStatsPlugin', 'O programie…')
        )

    def set_sync_enabled(self, enabled):
        self.sync_button.setEnabled(enabled)

    def set_primary_catalog_action(self, show_sync):
        """Show Synchronizuj when an update is available; otherwise Sprawdź aktualizacje."""
        self._show_sync_primary = bool(show_sync)
        if self.stop_button.isVisible():
            return
        want_sync = bool(show_sync)
        if (
            self.sync_button.isVisible() == want_sync
            and self.check_updates_button.isVisible() == (not want_sync)
        ):
            return
        self.sync_button.setVisible(want_sync)
        self.check_updates_button.setVisible(not want_sync)
        self._last_fitted_width = None
        self._schedule_fit()

    def set_sync_busy(self, busy):
        """While sync runs, show stop control instead of sync / check buttons."""
        busy = bool(busy)
        if self.stop_button.isVisible() == busy:
            if busy:
                self.sync_button.setVisible(False)
                self.check_updates_button.setVisible(False)
            return
        self.stop_button.setVisible(busy)
        if busy:
            self.sync_button.setVisible(False)
            self.check_updates_button.setVisible(False)
        else:
            self.set_primary_catalog_action(self._show_sync_primary)

    def _nudge_corner_width(self):
        """Grow/shrink the menubar corner widget without collapsing chips."""
        if self._fitting or self.header_panel is None:
            return
        menubar = self._main_window.menuBar()
        if menubar is None:
            return
        self.header_panel.adjustSize()
        need = max(self.header_panel.sizeHint().width(), 1)
        available = self._available_header_width()
        fitted = need
        if available and fitted > available:
            fitted = max(available, 1)
        self.header_panel.setMinimumWidth(0)
        self.header_panel.setMaximumWidth(fitted)
        self.header_panel.resize(fitted, self.header_panel.sizeHint().height())
        menubar.setCornerWidget(self.header_panel, QtCore.Qt.TopRightCorner)
        self._last_fitted_width = fitted

    def set_version_checking(self, checking):
        """Show a compact progress bar left of the action button; keep chip text still."""
        checking = bool(checking)
        if self._version_checking == checking:
            if checking:
                self.progress_bar.setRange(0, 0)
                self.progress_bar.show()
            return
        self._version_checking = checking
        self.check_updates_button.setEnabled(not checking)
        self.sync_button.setEnabled(not checking)
        if checking:
            self.progress_bar.setFixedWidth(_PROGRESS_BAR_CHECK_WIDTH)
            self.progress_bar.setRange(0, 0)
            self.progress_bar.show()
        elif not self._activity_mode:
            self.progress_bar.hide()
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(0)
        self._nudge_corner_width()

    def _set_activity_visible(self, visible, message=''):
        visible = bool(visible)
        if self._activity_mode == visible and (
            not visible or self._activity_message == message
        ):
            return
        self._activity_mode = visible
        self._activity_message = message if visible else ''
        self.activity_label.setVisible(visible)
        if visible:
            self.activity_label.setText(message)
        show_chips = not visible
        for chip in (self.chip_database, self.chip_sync):
            chip.setVisible(show_chips)
        self.account_button.setVisible(show_chips)
        self._last_fitted_width = None
        self._schedule_fit()

    @staticmethod
    def _versions_differ(remote_version, local_version):
        if not remote_version or not local_version:
            return False
        try:
            return int(remote_version) != int(local_version)
        except (TypeError, ValueError):
            return remote_version != local_version

    def _request_account_avatar(self, url):
        url = (url or '').strip()
        from contrib.plugins.songstats.lib.apiutil import discord_avatar_ui_fetch_url

        fetch_url = discord_avatar_ui_fetch_url(url, size=512) if url else ''
        pixmap_ok = (
            not self._avatar_pixmap.isNull()
            and self._avatar_pixmap.width() >= _AVATAR_MIN_LOADED_WIDTH
        )
        if url == self._avatar_url and pixmap_ok:
            return
        if self._avatar_load_busy and url == self._avatar_url:
            return
        self._avatar_url = url
        if not pixmap_ok:
            self._avatar_pixmap = QtGui.QPixmap()
        if not url:
            self._update_account_button()
            return
        from contrib.plugins.songstats.lib.apiutil import alternate_discord_avatar_url
        from openlp.core.common.httputils import get_proxy_settings
        from openlp.core.threading import ThreadWorker, run_thread

        primary_url = fetch_url
        alt_url = alternate_discord_avatar_url(primary_url)

        class AvatarWorker(ThreadWorker):
            loaded = QtCore.pyqtSignal(bytes)

            def __init__(self, urls):
                super().__init__()
                self._urls = [u for u in urls if u]

            def start(self):
                import requests
                for fetch_url in self._urls:
                    try:
                        response = requests.get(
                            fetch_url,
                            timeout=20,
                            proxies=get_proxy_settings(),
                            headers={
                                'User-Agent': 'OpenLP-SongStats/1.2',
                                'Accept': 'image/*,*/*;q=0.8',
                            },
                        )
                        if response.status_code == 200 and response.content:
                            self.loaded.emit(response.content)
                            break
                    except Exception:
                        pass
                self.quit.emit()

        worker = AvatarWorker([primary_url, alt_url])
        worker.loaded.connect(self._on_avatar_bytes)
        self._avatar_load_busy = True
        worker.quit.connect(self._on_avatar_worker_finished)
        run_thread(
            worker,
            'songstats-avatar-{0}'.format(abs(hash(url)) % (10 ** 8)),
            can_start=True,
        )

    def _on_avatar_worker_finished(self):
        self._avatar_load_busy = False

    def _on_avatar_bytes(self, raw):
        if not raw:
            return
        pixmap = QtGui.QPixmap()
        data = bytes(raw)
        if not pixmap.loadFromData(data):
            image = QtGui.QImage.fromData(data)
            if image.isNull():
                return
            pixmap = QtGui.QPixmap.fromImage(image)
        self._avatar_pixmap = pixmap
        self._update_account_button()
        self._render_status_panel()

    def _refresh_account_menu_header(self):
        if not self._status_panel_args:
            return
        has_token = self._status_panel_args.get('has_token')
        account_name = (self._status_panel_args.get('account_name') or '').strip()
        self._update_account_menu_header(has_token, account_name)

    def _update_account_menu_header(self, has_token, account_name):
        if not hasattr(self, '_menu_header_widget'):
            return
        self._header_action.setVisible(bool(has_token))
        self._header_separator.setVisible(bool(has_token))
        self._menu_header_widget.setVisible(bool(has_token))
        if not has_token:
            self._menu_header_avatar.clear()
            self._menu_header_name.clear()
            return
        label = (account_name or '').strip()
        if label:
            fm = self._menu_header_name.fontMetrics()
            max_w = max(
                60,
                _ACCOUNT_MENU_HEADER_WIDTH
                - _ACCOUNT_MENU_HEADER_AVATAR
                - 24,
            )
            self._menu_header_name.setText(
                fm.elidedText(label, QtCore.Qt.ElideRight, max_w)
            )
        else:
            self._menu_header_name.clear()
        self._menu_header_widget.setEnabled(True)
        self._menu_header_avatar.setEnabled(True)
        self._menu_header_name.setEnabled(True)
        active_text = self._menu_header_name.palette().color(
            QtGui.QPalette.Active,
            QtGui.QPalette.Text,
        )
        name_palette = self._menu_header_name.palette()
        for group in (
            QtGui.QPalette.Active,
            QtGui.QPalette.Inactive,
            QtGui.QPalette.Disabled,
        ):
            name_palette.setColor(group, QtGui.QPalette.WindowText, active_text)
            name_palette.setColor(group, QtGui.QPalette.Text, active_text)
        self._menu_header_name.setPalette(name_palette)
        if self._avatar_pixmap.isNull():
            self._menu_header_avatar.clear()
            return
        dpr = max(1.0, self._menu_header_avatar.devicePixelRatioF())
        rounded = _circle_pixmap(
            self._avatar_pixmap,
            _ACCOUNT_MENU_HEADER_AVATAR,
            dpr,
        )
        self._menu_header_avatar.setPixmap(rounded)
        self._menu_header_avatar.setMinimumSize(
            _ACCOUNT_MENU_HEADER_AVATAR,
            _ACCOUNT_MENU_HEADER_AVATAR,
        )

    def _account_avatar_icon(self, logical_size, dpr_widget):
        if self._avatar_pixmap.isNull():
            return QtGui.QIcon()
        dpr = max(1.0, dpr_widget.devicePixelRatioF())
        rounded = _circle_pixmap(self._avatar_pixmap, logical_size, dpr)
        return QtGui.QIcon(rounded)

    def _update_account_button(self):
        if not self._status_panel_args:
            return
        has_token = self._status_panel_args.get('has_token')
        account_name = (self._status_panel_args.get('account_name') or '').strip()
        wide = self._wide_layout()
        compact = (not wide) and self._density >= _DENSITY_COMPACT

        self._act_login.setVisible(not has_token)
        self._act_logout.setVisible(bool(has_token))

        if has_token and account_name and (wide or not compact):
            fm = self.account_button.fontMetrics()
            self.account_button.setText(
                fm.elidedText(account_name, QtCore.Qt.ElideRight, 160)
            )
        else:
            self.account_button.setText('')

        if has_token and not self._avatar_pixmap.isNull():
            self.account_button.setIcon(
                self._account_avatar_icon(
                    _ACCOUNT_TOOLBAR_ICON_SIZE,
                    self.account_button,
                )
            )
            self.account_button.setIconSize(
                QtCore.QSize(_ACCOUNT_TOOLBAR_ICON_SIZE, _ACCOUNT_TOOLBAR_ICON_SIZE)
            )
            self.account_button.setMaximumHeight(
                max(_TOOL_BUTTON_MAX_HEIGHT, _ACCOUNT_TOOLBAR_ICON_SIZE + 4)
            )
        else:
            self.account_button.setIconSize(
                QtCore.QSize(_SYNC_ICON_SIZE, _SYNC_ICON_SIZE)
            )
            self.account_button.setMaximumHeight(_TOOL_BUTTON_MAX_HEIGHT)
            if has_token:
                self.account_button.setIcon(
                    qta.icon('mdi.account-circle-outline', color='#2e7d32')
                )
            else:
                self.account_button.setIcon(_themed_icon('authentication'))
        self._update_account_menu_header(has_token, account_name)

    def update_status_panel(
        self,
        remote_version='',
        local_version='',
        has_token=False,
        last_sync_status='',
        last_sync_time='',
        version_checking=False,
        account_name='',
        account_avatar_url='',
    ):
        if version_checking:
            self.set_version_checking(True)
            return
        if self._version_checking:
            self.set_version_checking(False)
        self._set_activity_visible(False)
        self._status_panel_args = dict(
            remote_version=remote_version,
            local_version=local_version,
            has_token=has_token,
            last_sync_status=last_sync_status,
            last_sync_time=last_sync_time,
            version_checking=False,
            account_name=account_name or '',
            account_avatar_url=account_avatar_url or '',
        )
        if not has_token:
            self._avatar_url = ''
            self._avatar_pixmap = QtGui.QPixmap()
        self._request_account_avatar(account_avatar_url if has_token else '')
        self._update_account_button()
        self._render_status_panel()

    def _render_status_panel(self):
        if not self._status_panel_args:
            return
        args = self._status_panel_args
        remote_version = args['remote_version']
        local_version = args['local_version']
        has_token = args['has_token']
        last_sync_status = args['last_sync_status']
        last_sync_time = args['last_sync_time']
        wide = self._wide_layout()
        icons_only = not wide
        compact = (not wide) and self._density >= _DENSITY_COMPACT

        db_tip = ''
        if remote_version:
            remote_line = translate('SongStatsPlugin', 'Serwer v{version}').format(
                version=remote_version
            )
        else:
            remote_line = translate('SongStatsPlugin', 'Serwer: nieznana')

        if local_version:
            local_line = translate('SongStatsPlugin', 'Lokalnie v{version}').format(
                version=local_version
            )
        else:
            local_line = translate('SongStatsPlugin', 'Lokalnie: brak')

        db_tip = '{remote} · {local}'.format(remote=remote_line, local=local_line)
        if compact:
            if remote_version and local_version:
                db_value = 'S{0}·L{1}'.format(remote_version, local_version)
            elif remote_version:
                db_value = 'S{0}'.format(remote_version)
            elif local_version:
                db_value = 'L{0}'.format(local_version)
            else:
                db_value = '—'
        else:
            if remote_version and local_version:
                db_value = translate(
                    'SongStatsPlugin',
                    'Serwer v{remote} · lokalnie v{local}',
                ).format(remote=remote_version, local=local_version)
            elif remote_version:
                db_value = translate(
                    'SongStatsPlugin',
                    'Serwer v{version}',
                ).format(version=remote_version)
            elif local_version:
                db_value = translate(
                    'SongStatsPlugin',
                    'Lokalnie v{version}',
                ).format(version=local_version)
            else:
                db_value = '—'

        if self._versions_differ(remote_version, local_version):
            db_icon = _themed_icon('database', color='orange')
        elif remote_version and local_version:
            db_icon = _themed_icon('database', color='green')
        else:
            db_icon = _themed_icon('database', color='#888')

        self.chip_database.set_state(
            db_icon,
            translate('SongStatsPlugin', 'Baza'),
            db_value,
            '',
            compact=compact,
            icon_only=icons_only,
        )

        if last_sync_status == 'ok' and last_sync_time:
            sync_icon = qta.icon('mdi.check-circle', color='green')
            short_time = _short_sync_time(last_sync_time)
            if compact:
                sync_value = 'OK'
            else:
                sync_value = translate(
                    'SongStatsPlugin',
                    'OK {time}',
                ).format(time=short_time)
        elif last_sync_status == 'error':
            sync_icon = UiIcons().error
            sync_value = translate('SongStatsPlugin', 'Błąd')
        else:
            sync_icon = _themed_icon('time', color='#888')
            sync_value = '—'

        self.chip_sync.set_state(
            sync_icon,
            translate('SongStatsPlugin', 'Synchronizacja'),
            sync_value,
            '',
            compact=compact,
            icon_only=icons_only,
        )

    def set_status_text(self, text, tip=None):
        self._activity_message = text
        self.activity_label.setText(text)
        if tip:
            self.activity_label.setToolTip(tip)
        if not self._activity_mode:
            self._last_fitted_width = None
            self._schedule_fit()

    def _update_progress_bar(self, value, maximum):
        self.progress_bar.setFixedWidth(_PROGRESS_BAR_WIDTH)
        self.progress_bar.show()
        if maximum <= 0:
            self.progress_bar.setRange(0, 0)
        else:
            self.progress_bar.setRange(0, maximum)
            self.progress_bar.setValue(min(max(value, 0), maximum))

    def show_indeterminate_progress(self, message):
        entering = not self._activity_mode
        self.set_sync_busy(True)
        if entering:
            self._set_activity_visible(True, message)
        else:
            self._activity_message = message
            self.activity_label.setText(message)
            self.activity_label.show()
        self._update_progress_bar(0, 0)

    def show_progress(self, value, maximum, message):
        entering = not self._activity_mode
        self.set_sync_busy(True)
        if entering:
            self._set_activity_visible(True, message)
        else:
            self._activity_message = message
            self.activity_label.setText(message)
            self.activity_label.show()
        self._update_progress_bar(value, maximum)

    def hide_progress(self):
        if (
            not self.progress_bar.isVisible()
            and not self._activity_mode
            and not self.stop_button.isVisible()
            and not self._version_checking
        ):
            return
        if not self._version_checking:
            self.progress_bar.hide()
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(0)
        self._set_activity_visible(False)
        self.set_sync_busy(False)


SyncStatusBarWidget = SyncHeaderWidget
