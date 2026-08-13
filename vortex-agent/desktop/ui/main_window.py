"""Main application window for Vortex desktop client."""
from __future__ import annotations

import json
import threading
from typing import Any

import requests
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QSplitter,
    QStatusBar,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from api_client import VortexApiClient
from backend_manager import BackendManager
from config import ConfigManager, DesktopConfig


def pretty(data: Any) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False, default=str)


class MainWindow(QMainWindow):
    def __init__(
        self,
        api_client: VortexApiClient,
        config: DesktopConfig,
        config_manager: ConfigManager,
        backend_manager: BackendManager,
    ):
        super().__init__()
        self.api = api_client
        self.config = config
        self.config_manager = config_manager
        self.backend_manager = backend_manager
        self._quit_to_tray = True

        self.setWindowTitle("Vortex Agent Desktop")
        self.resize(1400, 900)

        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.connection_label = QLabel("Disconnected")
        self.status.addPermanentWidget(self.connection_label)

        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        self._build_chat_tab()
        self._build_dashboard_tab()
        self._build_kg_tab()
        self._build_council_tab()
        self._build_governance_tab()
        self._build_tools_tab()
        self._build_orchestration_tab()
        self._build_benchmark_tab()
        self._build_logs_tab()
        self._build_settings_tab()

        self.timer = QTimer(self)
        self.timer.setInterval(max(1000, int(self.config.poll_interval_ms)))
        self.timer.timeout.connect(self.refresh_realtime)
        self.timer.start()

        self.refresh_realtime()

    def _build_chat_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        self.chat_history = QPlainTextEdit()
        self.chat_history.setReadOnly(True)
        self.chat_input = QLineEdit()
        self.chat_input.setPlaceholderText("Ask Vortex Agent...")
        self.chat_orch = QCheckBox("Use orchestration")
        send = QPushButton("Send")
        send.clicked.connect(self.send_chat)

        top_row = QHBoxLayout()
        top_row.addWidget(self.chat_input)
        top_row.addWidget(self.chat_orch)
        top_row.addWidget(send)

        self.memory_query = QLineEdit()
        self.memory_query.setPlaceholderText("Memory recall query")
        mem_btn = QPushButton("Recall")
        mem_btn.clicked.connect(self.recall_memory)
        self.memory_results = QPlainTextEdit()
        self.memory_results.setReadOnly(True)

        mem_row = QHBoxLayout()
        mem_row.addWidget(self.memory_query)
        mem_row.addWidget(mem_btn)

        splitter = QSplitter()
        splitter.addWidget(self.chat_history)
        splitter.addWidget(self.memory_results)

        layout.addLayout(top_row)
        layout.addLayout(mem_row)
        layout.addWidget(splitter)
        self.tabs.addTab(tab, "Chat & Memory")

    def _build_dashboard_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        self.dashboard_health = QLabel("Health: unknown")
        self.dashboard_stats = QPlainTextEdit()
        self.dashboard_stats.setReadOnly(True)
        self.dashboard_obs = QPlainTextEdit()
        self.dashboard_obs.setReadOnly(True)
        layout.addWidget(self.dashboard_health)
        layout.addWidget(QLabel("Stats / Telemetry"))
        layout.addWidget(self.dashboard_stats)
        layout.addWidget(QLabel("Observability"))
        layout.addWidget(self.dashboard_obs)
        self.tabs.addTab(tab, "Dashboard")

    def _build_kg_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        refresh = QPushButton("Refresh Knowledge Graph")
        refresh.clicked.connect(self.refresh_knowledge_graph)
        self.kg_stats = QLabel("Knowledge graph stats unavailable")
        self.kg_table = QTableWidget(0, 3)
        self.kg_table.setHorizontalHeaderLabels(["Label", "Count", "Last Seen"])
        layout.addWidget(refresh)
        layout.addWidget(self.kg_stats)
        layout.addWidget(self.kg_table)
        self.tabs.addTab(tab, "Knowledge Graph")

    def _build_council_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        load = QPushButton("Refresh Council")
        load.clicked.connect(self.refresh_council)
        self.council_goal = QLineEdit()
        self.council_goal.setPlaceholderText("Goal for deliberation")
        run = QPushButton("Run Deliberation")
        run.clicked.connect(self.run_deliberation)
        self.council_out = QPlainTextEdit()
        self.council_out.setReadOnly(True)
        row = QHBoxLayout()
        row.addWidget(self.council_goal)
        row.addWidget(run)
        layout.addWidget(load)
        layout.addLayout(row)
        layout.addWidget(self.council_out)
        self.tabs.addTab(tab, "Council")

    def _build_governance_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        refresh = QPushButton("Refresh Governance & Policies")
        refresh.clicked.connect(self.refresh_governance)
        self.gov_policies = QPlainTextEdit()
        self.gov_policies.setReadOnly(True)

        form = QFormLayout()
        self.gov_task = QLineEdit()
        self.gov_action = QLineEdit("execute")
        self.gov_agent = QLineEdit("chief")
        form.addRow("Task", self.gov_task)
        form.addRow("Action", self.gov_action)
        form.addRow("Agent", self.gov_agent)
        run = QPushButton("Evaluate")
        run.clicked.connect(self.evaluate_governance)
        self.gov_out = QPlainTextEdit()
        self.gov_out.setReadOnly(True)

        layout.addWidget(refresh)
        layout.addWidget(self.gov_policies)
        layout.addLayout(form)
        layout.addWidget(run)
        layout.addWidget(self.gov_out)
        self.tabs.addTab(tab, "Governance")

    def _build_tools_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        row = QHBoxLayout()
        refresh = QPushButton("Refresh Tools")
        refresh.clicked.connect(self.refresh_tools)
        self.tools_list = QListWidget()
        row.addWidget(refresh)
        layout.addLayout(row)

        self.tool_args = QLineEdit("{}")
        self.tool_agent = QLineEdit("chief")
        run = QPushButton("Execute Selected Tool")
        run.clicked.connect(self.execute_tool)
        form = QFormLayout()
        form.addRow("Arguments (JSON)", self.tool_args)
        form.addRow("Agent", self.tool_agent)
        self.tool_out = QPlainTextEdit()
        self.tool_out.setReadOnly(True)

        layout.addWidget(self.tools_list)
        layout.addLayout(form)
        layout.addWidget(run)
        layout.addWidget(self.tool_out)
        self.tabs.addTab(tab, "Tools")

    def _build_orchestration_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        self.orch_goal = QLineEdit()
        self.orch_goal.setPlaceholderText("Orchestration goal")
        run = QPushButton("Run Orchestration")
        run.clicked.connect(self.run_orchestration)
        refresh = QPushButton("Refresh Recent Runs")
        refresh.clicked.connect(self.refresh_orchestration)
        row = QHBoxLayout()
        row.addWidget(self.orch_goal)
        row.addWidget(run)
        row.addWidget(refresh)
        self.orch_graph = QPlainTextEdit()
        self.orch_graph.setReadOnly(True)
        layout.addLayout(row)
        layout.addWidget(self.orch_graph)
        self.tabs.addTab(tab, "Orchestration")

    def _build_benchmark_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        run = QPushButton("Run Benchmark")
        run.clicked.connect(self.run_benchmark)
        self.benchmark_out = QPlainTextEdit()
        self.benchmark_out.setReadOnly(True)
        layout.addWidget(run)
        layout.addWidget(self.benchmark_out)
        self.tabs.addTab(tab, "Benchmark")

    def _build_logs_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        controls = QHBoxLayout()
        self.log_filter = QLineEdit()
        self.log_filter.setPlaceholderText("Filter logs/audit")
        refresh = QPushButton("Refresh Audit + Logs")
        refresh.clicked.connect(self.refresh_logs)
        controls.addWidget(self.log_filter)
        controls.addWidget(refresh)

        self.audit_view = QPlainTextEdit()
        self.audit_view.setReadOnly(True)
        self.backend_log_view = QPlainTextEdit()
        self.backend_log_view.setReadOnly(True)

        layout.addLayout(controls)
        layout.addWidget(QLabel("Governance Audit Trail"))
        layout.addWidget(self.audit_view)
        layout.addWidget(QLabel("Backend Process Logs"))
        layout.addWidget(self.backend_log_view)
        self.tabs.addTab(tab, "Audit & Logs")

    def _build_settings_tab(self) -> None:
        tab = QWidget()
        layout = QFormLayout(tab)

        self.remote_url = QLineEdit(self.config.backend_url)
        self.local_host = QLineEdit(self.config.backend_host)
        self.local_port = QLineEdit(str(self.config.backend_port))
        self.connect_remote = QCheckBox()
        self.connect_remote.setChecked(self.config.connect_remote)
        self.auto_start = QCheckBox()
        self.auto_start.setChecked(self.config.auto_start_backend)
        self.poll_interval = QLineEdit(str(self.config.poll_interval_ms))

        save = QPushButton("Save Settings")
        save.clicked.connect(self.save_settings)
        reconnect = QPushButton("Reconnect")
        reconnect.clicked.connect(self.reconnect_backend)

        layout.addRow("Remote backend URL", self.remote_url)
        layout.addRow("Local backend host", self.local_host)
        layout.addRow("Local backend port", self.local_port)
        layout.addRow("Connect remote", self.connect_remote)
        layout.addRow("Auto-start local backend", self.auto_start)
        layout.addRow("Refresh interval (ms)", self.poll_interval)
        layout.addRow(save, reconnect)

        self.tabs.addTab(tab, "Settings")

    def _handle_error(self, title: str, error: Exception) -> None:
        self.connection_label.setText("Disconnected")
        QMessageBox.warning(self, title, str(error))

    def reconnect_backend(self) -> None:
        if not self._apply_settings():
            return
        self.api.set_base_url(self.config.active_backend_url)
        if self.config.connect_remote:
            self.refresh_realtime()
            return
        self.connection_label.setText(f"Connecting: {self.api.base_url}")
        threading.Thread(target=self._start_local_backend_and_refresh, daemon=True).start()

    def _start_local_backend_and_refresh(self) -> None:
        self.backend_manager.start_if_needed()
        QTimer.singleShot(0, self.refresh_realtime)

    def save_settings(self) -> None:
        if not self._apply_settings():
            return
        self.config_manager.save(self.config)
        self.timer.setInterval(max(1000, int(self.config.poll_interval_ms)))
        QMessageBox.information(self, "Saved", "Settings saved.")

    def _apply_settings(self) -> bool:
        try:
            local_port = int(self.local_port.text().strip() or self.config.backend_port)
            poll_interval = int(self.poll_interval.text().strip() or self.config.poll_interval_ms)
        except ValueError:
            QMessageBox.warning(self, "Invalid settings", "Local backend port and refresh interval must be numbers.")
            return False

        self.config.backend_url = self.remote_url.text().strip() or self.config.backend_url
        self.config.backend_host = self.local_host.text().strip() or self.config.backend_host
        self.config.backend_port = local_port
        self.config.connect_remote = self.connect_remote.isChecked()
        self.config.auto_start_backend = self.auto_start.isChecked()
        self.config.poll_interval_ms = poll_interval
        return True

    def send_chat(self) -> None:
        message = self.chat_input.text().strip()
        if not message:
            return
        try:
            result = self.api.chat(message, orchestrated=self.chat_orch.isChecked())
            self.chat_history.appendPlainText(f"You: {message}\nVortex: {result.get('response','')}\n")
            self.chat_input.clear()
        except requests.RequestException as error:
            self._handle_error("Chat failed", error)

    def recall_memory(self) -> None:
        try:
            result = self.api.memory(self.memory_query.text().strip())
            self.memory_results.setPlainText(pretty(result))
        except requests.RequestException as error:
            self._handle_error("Memory recall failed", error)

    def refresh_realtime(self) -> None:
        try:
            health = self.api.health()
            stats = self.api.stats()
            obs = self.api.observability()
            self.connection_label.setText(f"Connected: {self.api.base_url}")
            self.dashboard_health.setText(
                f"Health: {health.get('status')} | Bots: {health.get('bots')} | Generation: {health.get('generation')} | Lessons: {health.get('lessons')}"
            )
            self.dashboard_stats.setPlainText(pretty(stats))
            self.dashboard_obs.setPlainText(pretty(obs))
        except requests.RequestException:
            self.connection_label.setText(f"Disconnected: {self.api.base_url}")

    def refresh_knowledge_graph(self) -> None:
        try:
            payload = self.api.memory_graph(limit=100)
            self.kg_stats.setText(f"Stats: {pretty(payload.get('stats', {}))}")
            nodes = payload.get("nodes", [])
            self.kg_table.setRowCount(len(nodes))
            for row, node in enumerate(nodes):
                self.kg_table.setItem(row, 0, QTableWidgetItem(str(node.get("label", ""))))
                self.kg_table.setItem(row, 1, QTableWidgetItem(str(node.get("count", ""))))
                self.kg_table.setItem(row, 2, QTableWidgetItem(str(node.get("updated_at", ""))))
        except requests.RequestException as error:
            self._handle_error("Knowledge graph refresh failed", error)

    def refresh_council(self) -> None:
        try:
            self.council_out.setPlainText(pretty(self.api.council()))
        except requests.RequestException as error:
            self._handle_error("Council refresh failed", error)

    def run_deliberation(self) -> None:
        goal = self.council_goal.text().strip()
        if not goal:
            return
        try:
            self.council_out.setPlainText(pretty(self.api.deliberate(goal)))
        except requests.RequestException as error:
            self._handle_error("Council deliberation failed", error)

    def refresh_governance(self) -> None:
        try:
            self.gov_policies.setPlainText(pretty(self.api.governance()))
        except requests.RequestException as error:
            self._handle_error("Governance refresh failed", error)

    def evaluate_governance(self) -> None:
        try:
            result = self.api.governance_evaluate(
                task=self.gov_task.text().strip(),
                action=self.gov_action.text().strip() or "execute",
                agent=self.gov_agent.text().strip() or "chief",
            )
            self.gov_out.setPlainText(pretty(result))
        except requests.RequestException as error:
            self._handle_error("Governance evaluation failed", error)

    def refresh_tools(self) -> None:
        try:
            data = self.api.tools()
            tools = data.get("tools", [])
            self.tools_list.clear()
            for item in tools:
                name = item.get("name") if isinstance(item, dict) else str(item)
                self.tools_list.addItem(name)
            self.tool_out.setPlainText(pretty(data))
        except requests.RequestException as error:
            self._handle_error("Tools refresh failed", error)

    def execute_tool(self) -> None:
        selected = self.tools_list.currentItem()
        if not selected:
            QMessageBox.information(self, "Select tool", "Choose a tool first.")
            return
        try:
            args = json.loads(self.tool_args.text().strip() or "{}")
        except json.JSONDecodeError:
            QMessageBox.warning(self, "Invalid JSON", "Tool arguments must be valid JSON.")
            return

        try:
            result = self.api.execute_tool(selected.text(), args, self.tool_agent.text().strip() or "chief")
            self.tool_out.setPlainText(pretty(result))
        except requests.RequestException as error:
            self._handle_error("Tool execution failed", error)

    def refresh_orchestration(self) -> None:
        try:
            self.orch_graph.setPlainText(pretty(self.api.orchestration_list()))
        except requests.RequestException as error:
            self._handle_error("Orchestration refresh failed", error)

    def run_orchestration(self) -> None:
        goal = self.orch_goal.text().strip()
        if not goal:
            return
        try:
            self.orch_graph.setPlainText(pretty(self.api.orchestration_run(goal)))
        except requests.RequestException as error:
            self._handle_error("Orchestration run failed", error)

    def run_benchmark(self) -> None:
        try:
            self.benchmark_out.setPlainText(pretty(self.api.benchmark()))
        except requests.RequestException as error:
            self._handle_error("Benchmark run failed", error)

    def refresh_logs(self) -> None:
        text_filter = self.log_filter.text().strip()
        try:
            governance = self.api.governance()
            audit = governance.get("audit_recent", [])
            if text_filter:
                audit = [entry for entry in audit if text_filter.lower() in json.dumps(entry).lower()]
            self.audit_view.setPlainText(pretty(audit))
        except requests.RequestException as error:
            self._handle_error("Audit refresh failed", error)

        logs = self.backend_manager.get_logs(text_filter)
        self.backend_log_view.setPlainText("\n".join(logs[-500:]))

    def closeEvent(self, event) -> None:  # noqa: N802
        if self._quit_to_tray:
            event.ignore()
            self.hide()
            self.status.showMessage("Vortex Agent Desktop minimized to tray", 3000)
            return
        super().closeEvent(event)

    def set_quit_on_close(self, enabled: bool) -> None:
        self._quit_to_tray = not enabled
