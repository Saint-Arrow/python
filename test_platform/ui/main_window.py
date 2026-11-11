# -*- coding: utf-8 -*-
"""测试平台主窗口（PySide6）。

布局：
+--------------------------------------------------------------+
| 运行 | 停止 | 循环轮数 | 失败策略 | 保存方案 | 加载方案        |
+--------------------+-----------------------------------------+
| 可用测试项(勾选)    | 测试队列(拖拽排序) [上移/下移/移除]       |
|                    | 选中项参数表单                           |
+--------------------+-----------------------------------------+
| 实时日志                                                     |
+--------------------------------------------------------------+
"""

from __future__ import annotations  # 兼容 Python 3.8：注解不求值（int | None / list[...] 语法安全）

import itertools
import json
import os
import sys
from datetime import datetime

from typing import List, Optional

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QApplication, QComboBox, QFileDialog, QFormLayout, QGroupBox, QHBoxLayout,
    QHeaderView, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMainWindow,
    QPlainTextEdit, QPushButton, QSplitter, QSpinBox, QTreeWidget,
    QTreeWidgetItem, QVBoxLayout, QWidget,
)

# 兼容直接运行：把平台根目录加入 sys.path
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from core.base import TestStatus  # noqa: E402
from core.registry import all_cases, discover, discover_from_config  # noqa: E402
from core.runner import (  # noqa: E402
    FAIL_ABORT, FAIL_CONTINUE, QueueItem, QueueRunner,
)

_STATUS_COLOR = {
    TestStatus.PENDING.value: "#888888",
    TestStatus.RUNNING.value: "#1565c0",
    TestStatus.PASSED.value: "#2e7d32",
    TestStatus.FAILED.value: "#c62828",
    TestStatus.ERROR.value: "#8e0000",
    TestStatus.SKIPPED.value: "#e65100",
}
_STATUS_ICON = {
    TestStatus.PENDING.value: "○",
    TestStatus.RUNNING.value: "▶",
    TestStatus.PASSED.value: "✔",
    TestStatus.FAILED.value: "✘",
    TestStatus.ERROR.value: "!!",
    TestStatus.SKIPPED.value: "⏭",
}


class RunnerBridge(QObject):
    """后台线程 -> UI 线程的信号桥。"""
    log_sig = Signal(str)
    status_sig = Signal(int, int, str, str, float)  # idx, loop, status, msg, dur
    done_sig = Signal(dict)


class MainWindow(QMainWindow):
    _uid_seq = itertools.count(1)

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Python 测试平台")
        self.resize(1100, 720)

        discover("tests")  # 自动发现平台内置测试项插件
        discover_from_config()  # 加载 platform.json 登记的外部"脚本即插件"
        self.cases = all_cases()
        self.queue_items: list[QueueItem] = []
        self._uid_of: dict[int, QueueItem] = {}   # uid -> QueueItem（含运行时状态）
        self.runner: QueueRunner | None = None
        self.bridge = RunnerBridge()
        self.bridge.log_sig.connect(self._append_log)
        self.bridge.status_sig.connect(self._on_item_status)
        self.bridge.done_sig.connect(self._on_all_done)

        self._build_ui()
        self._log_file = self._open_log_file()
        self._append_log(f"日志文件: {os.path.abspath(self._log_file.name)}")
        self._append_log(f"已加载 {len(self.cases)} 个测试项: "
                         + ", ".join(sorted(self.cases)))

    # ------------------------------------------------------------------ UI
    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)

        # ---- 工具栏 ----
        bar = QHBoxLayout()
        self.btn_run = QPushButton("▶ 运行")
        self.btn_run.clicked.connect(self._start_run)
        self.btn_stop = QPushButton("■ 停止")
        self.btn_stop.clicked.connect(self._stop_run)
        self.btn_stop.setEnabled(False)
        bar.addWidget(self.btn_run)
        bar.addWidget(self.btn_stop)
        bar.addWidget(QLabel("循环轮数:"))
        self.spin_loops = QSpinBox()
        self.spin_loops.setRange(1, 100000)
        self.spin_loops.setValue(1)
        self.spin_loops.setToolTip("整条队列重复执行的轮数（老化测试用）")
        bar.addWidget(self.spin_loops)
        bar.addWidget(QLabel("失败策略:"))
        self.combo_fail = QComboBox()
        self.combo_fail.addItem("失败后继续", FAIL_CONTINUE)
        self.combo_fail.addItem("失败后中止", FAIL_ABORT)
        bar.addWidget(self.combo_fail)
        bar.addStretch(1)
        btn_save = QPushButton("保存方案")
        btn_save.clicked.connect(self._save_plan)
        btn_load = QPushButton("加载方案")
        btn_load.clicked.connect(self._load_plan)
        bar.addWidget(btn_save)
        bar.addWidget(btn_load)
        root.addLayout(bar)

        # ---- 中部：左可用项 / 右队列+参数 ----
        split = QSplitter(Qt.Horizontal)

        gb_left = QGroupBox("可用测试项（勾选后点添加，或双击分类下条目）")
        lv = QVBoxLayout(gb_left)
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["名称", "id"])
        self.tree.itemDoubleClicked.connect(self._on_tree_double)
        lv.addWidget(self.tree)
        btn_add = QPushButton("添加所选 →")
        btn_add.clicked.connect(self._add_checked)
        lv.addWidget(btn_add)
        self._fill_tree()
        split.addWidget(gb_left)

        gb_right = QGroupBox("测试队列（拖拽排序）")
        rv = QVBoxLayout(gb_right)
        self.list_queue = QListWidget()
        self.list_queue.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        self.list_queue.model().rowsMoved.connect(self._resync_from_view)
        self.list_queue.currentRowChanged.connect(
            lambda *_: self._show_params())
        rv.addWidget(self.list_queue, 2)

        row_btns = QHBoxLayout()
        for text, slot in (("↑ 上移", self._move_up), ("↓ 下移", self._move_down),
                           ("✖ 移除", self._remove_item), ("清空", self._clear_queue)):
            b = QPushButton(text)
            b.clicked.connect(slot)
            row_btns.addWidget(b)
        row_btns.addStretch(1)
        rv.addLayout(row_btns)

        gb_params = QGroupBox("选中项参数")
        self.form_params = QFormLayout(gb_params)
        rv.addWidget(gb_params, 1)
        split.addWidget(gb_right)
        split.setSizes([330, 640])
        root.addWidget(split, 3)

        self.txt_log = QPlainTextEdit()
        self.txt_log.setReadOnly(True)
        self.txt_log.setMaximumBlockCount(5000)
        root.addWidget(self.txt_log, 2)

    def _fill_tree(self) -> None:
        by_cat: dict[str, list] = {}
        for cls in self.cases.values():
            by_cat.setdefault(cls.category, []).append(cls)
        for cat in sorted(by_cat):
            cat_item = QTreeWidgetItem([cat, ""])
            cat_item.setFlags(Qt.ItemIsEnabled)
            f = cat_item.font(0)
            f.setBold(True)
            cat_item.setFont(0, f)
            for cls in sorted(by_cat[cat], key=lambda c: c.name):
                child = QTreeWidgetItem([cls.name, cls.id])
                child.setFlags(Qt.ItemIsEnabled | Qt.ItemIsUserCheckable)
                child.setCheckState(0, Qt.Unchecked)
                child.setToolTip(0, cls.description)
                cat_item.addChild(child)
            self.tree.addTopLevelItem(cat_item)
        self.tree.expandAll()
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeToContents)

    def _on_tree_double(self, item: QTreeWidgetItem, col: int) -> None:
        if item.childCount() == 0:
            self._append_to_queue(item.text(1))

    # ------------------------------------------------------------ 队列操作
    def _add_checked(self) -> None:
        added = 0

        def walk(parent: QTreeWidgetItem) -> None:
            nonlocal added
            for i in range(parent.childCount()):
                ch = parent.child(i)
                if ch.childCount():
                    walk(ch)
                elif ch.checkState(0) == Qt.Checked:
                    self._append_to_queue(ch.text(1))
                    ch.setCheckState(0, Qt.Unchecked)
                    added += 1

        for i in range(self.tree.topLevelItemCount()):
            walk(self.tree.topLevelItem(i))
        if added:
            self._append_log(f"已添加 {added} 个测试项到队列")

    def _append_to_queue(self, case_id: str) -> None:
        cls = self.cases.get(case_id)
        if cls is None:
            return
        uid = next(self._uid_seq)
        qi = QueueItem(case_id=case_id, name=cls.name,
                       params={p.key: str(p.default) for p in cls.params})
        self._uid_of[uid] = qi
        lw = QListWidgetItem(f"○  {cls.name}")
        lw.setData(Qt.UserRole, uid)
        lw.setToolTip(cls.description)
        self.list_queue.addItem(lw)
        # 同步数据队列（运行/保存方案读的是 self.queue_items，不能只更新视图）
        self.queue_items = [self._uid_of[u] for u in self._uid_rows()]

    def _uid_at(self, row: int) -> int | None:
        lw = self.list_queue.item(row)
        return lw.data(Qt.UserRole) if lw else None

    def _uid_rows(self) -> list[int]:
        return [u for u in (self._uid_at(i) for i in range(self.list_queue.count()))
                if u is not None]

    def _resync_from_view(self, *args) -> None:
        """拖拽后按界面顺序重建 queue_items（uid 关联，不怕重名）。"""
        order = self._uid_rows()
        self.queue_items = [self._uid_of[u] for u in order]
        for i in range(self.list_queue.count()):
            self._refresh_queue_row(i)

    def _swap_rows(self, a: int, b: int) -> None:
        lw = self.list_queue.takeItem(a)
        self.list_queue.insertItem(b, lw)
        self.list_queue.setCurrentRow(b)
        self._resync_from_view()

    def _move_up(self) -> None:
        idx = self.list_queue.currentRow()
        if idx > 0:
            self._swap_rows(idx, idx - 1)

    def _move_down(self) -> None:
        idx = self.list_queue.currentRow()
        if 0 <= idx < self.list_queue.count() - 1:
            self._swap_rows(idx, idx + 1)

    def _remove_item(self) -> None:
        idx = self.list_queue.currentRow()
        if idx < 0:
            return
        uid = self._uid_at(idx)
        if uid is not None:
            self._uid_of.pop(uid, None)
        self.list_queue.takeItem(idx)
        self.queue_items = [self._uid_of[u] for u in self._uid_rows()]
        self._show_params()

    def _clear_queue(self) -> None:
        self.queue_items.clear()
        self._uid_of.clear()
        self.list_queue.clear()
        self._show_params()

    def _refresh_queue_row(self, idx: int) -> None:
        uid = self._uid_at(idx)
        if uid is None:
            return
        qi = self._uid_of.get(uid)
        if qi is None:
            return
        lw = self.list_queue.item(idx)
        dur = f"  {qi.duration}s" if qi.duration else ""
        msg = f"  | {qi.message[:70]}" if qi.message else ""
        lw.setText(f"{_STATUS_ICON[qi.status.value]}  {qi.name}{dur}{msg}")
        lw.setForeground(QColor(_STATUS_COLOR[qi.status.value]))

    # ------------------------------------------------------------- 参数表单
    def _show_params(self) -> None:
        while self.form_params.count():
            item = self.form_params.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        idx = self.list_queue.currentRow()
        uid = self._uid_at(idx)
        if uid is None or uid not in self._uid_of:
            self.form_params.addRow(QLabel("（未选中测试项）"), QLabel(""))
            return
        qi = self._uid_of[uid]
        cls = self.cases.get(qi.case_id)
        if cls is None:
            return
        header = QLabel(f"{qi.name} — {cls.description}")
        header.setWordWrap(True)
        self.form_params.addRow(header, QLabel(""))
        for p in cls.params:
            edit = QLineEdit(str(qi.params.get(p.key, p.default)))
            edit.setToolTip(p.hint or p.label)
            edit.editingFinished.connect(
                lambda e=edit, k=p.key, u=uid: self._save_param(u, k, e.text()))
            hint = f"（{p.hint}）" if p.hint else ""
            self.form_params.addRow(QLabel(f"{p.label} {hint}"), edit)

    def _save_param(self, uid: int, key: str, value: str) -> None:
        qi = self._uid_of.get(uid)
        if qi is not None:
            qi.params[key] = value

    # ------------------------------------------------------------- 运行控制
    def _start_run(self) -> None:
        if not self.queue_items:
            self._append_log("队列为空，请先从左侧勾选添加测试项")
            return
        if self.runner and self.runner.is_alive():
            return
        for i in range(self.list_queue.count()):
            uid = self._uid_at(i)
            qi = self._uid_of.get(uid)
            if qi:
                qi.status, qi.message, qi.duration = TestStatus.PENDING, "", 0.0
            self._refresh_queue_row(i)
        self.btn_run.setEnabled(False)
        self.btn_stop.setEnabled(True)

        self.runner = QueueRunner(
            queue=list(self.queue_items),
            loops=self.spin_loops.value(),
            fail_policy=self.combo_fail.currentData(),
            on_log=lambda line: self.bridge.log_sig.emit(line),
            on_item_status=lambda i, lp, st, msg, d:
                self.bridge.status_sig.emit(i, lp, st.value, msg, d),
            on_done=lambda s: self.bridge.done_sig.emit(s),
        )
        self.runner.start()

    def _stop_run(self) -> None:
        if self.runner:
            self._append_log("已请求停止，长等待步骤会在数秒内响应退出...")
            self.runner.request_stop()

    def _on_item_status(self, idx: int, loop: int, status: str,
                        msg: str, dur: float) -> None:
        uid = self._uid_at(idx)
        qi = self._uid_of.get(uid) if uid is not None else None
        if qi is not None:
            try:
                qi.status = TestStatus(status)
            except ValueError:
                pass
            loop_txt = f"[轮{loop}] " if self.spin_loops.value() > 1 else ""
            qi.message = loop_txt + msg
            qi.duration = dur
            self._refresh_queue_row(idx)

    def _on_all_done(self, summary: dict) -> None:
        self.btn_run.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self._append_log(
            f"汇总: 通过 {summary['passed_items']} / 失败 {summary['failed_items']}"
            f" / 中止 {'是' if summary['aborted'] else '否'}"
            f" / 耗时 {summary['total_seconds']}s")

    # ------------------------------------------------------------- 日志/方案
    def _open_log_file(self):
        """在平台根目录 logs/ 下创建 log_<启动时间>.log；失败则降级为丢弃模式。"""
        try:
            log_dir = os.path.join(_ROOT, "logs")
            os.makedirs(log_dir, exist_ok=True)
            path = os.path.join(log_dir, f"log_{datetime.now():%Y%m%d_%H%M%S}.log")
            return open(path, "a", encoding="utf-8")
        except OSError:
            return open(os.devnull, "w", encoding="utf-8")

    def _append_log(self, line: str) -> None:
        self.txt_log.appendPlainText(line)
        try:
            self._log_file.write(line + "\n")
            self._log_file.flush()
        except OSError:
            pass

    def _save_plan(self) -> None:
        if not self.queue_items:
            self._append_log("队列为空，无可保存方案")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "保存测试方案", "plan.json", "JSON (*.json)")
        if not path:
            return
        plan = {
            "loops": self.spin_loops.value(),
            "fail_policy": self.combo_fail.currentData(),
            "items": [qi.to_dict() for qi in self.queue_items],
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(plan, f, ensure_ascii=False, indent=2)
        self._append_log(f"方案已保存: {path}")

    def _load_plan(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "加载测试方案", "", "JSON (*.json)")
        if not path:
            return
        try:
            with open(path, encoding="utf-8") as f:
                plan = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            self._append_log(f"加载失败: {e}")
            return
        self._clear_queue()
        for d in plan.get("items", []):
            cls = self.cases.get(d.get("case_id"))
            if cls is None:
                self._append_log(f"跳过未知测试项: {d.get('case_id')}")
                continue
            self._append_to_queue(d["case_id"])
            uid = self._uid_at(self.list_queue.count() - 1)
            qi = self._uid_of.get(uid)
            if qi:
                qi.params = {p.key: str(d.get("params", {}).get(p.key, p.default))
                             for p in cls.params}
        self.spin_loops.setValue(plan.get("loops", 1))
        idx = self.combo_fail.findData(plan.get("fail_policy", FAIL_CONTINUE))
        if idx >= 0:
            self.combo_fail.setCurrentIndex(idx)
        for i in range(self.list_queue.count()):
            self._refresh_queue_row(i)
        self._append_log(f"方案已加载: {path}（{self.list_queue.count()} 项）")

    def closeEvent(self, event) -> None:  # noqa: N802
        if self.runner and self.runner.is_alive():
            self.runner.request_stop()
            self.runner.join(timeout=3)
        try:
            self._log_file.close()
        except OSError:
            pass
        super().closeEvent(event)


def main() -> int:
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
