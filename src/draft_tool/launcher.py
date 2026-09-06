"""Native Windows launcher for collection, validation, preview and draft save."""
from __future__ import annotations

import json
import os
import queue
import shutil
import subprocess
import sys
import threading
import tkinter as tk
import uuid
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Callable

from draft_tool import __version__
from draft_tool.config import AppConfig
from draft_tool.runtime import bundled_path, initialize_runtime
from draft_tool.security import atomic_write


EXIT_MESSAGES = {
    0: "操作完成",
    1: "输入或采集失败",
    2: "需要登录或采集结果被阻断",
    3: "页面控件缺失",
    4: "质量门禁或安全校验阻断",
    5: "卖家浏览器正在被其他任务使用",
}


def _child_command(mode: str, arguments: list[str]) -> list[str]:
    if getattr(sys, "frozen", False):
        return [sys.executable, mode, *arguments]
    return [sys.executable, "-m", "draft_tool.launcher", mode, *arguments]


def _chrome_path() -> str:
    candidates = [
        shutil.which("chrome"),
        os.path.join(os.environ.get("PROGRAMFILES", ""), "Google", "Chrome", "Application", "chrome.exe"),
        os.path.join(os.environ.get("PROGRAMFILES(X86)", ""), "Google", "Chrome", "Application", "chrome.exe"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Google", "Chrome", "Application", "chrome.exe"),
    ]
    return next((str(path) for path in candidates if path and Path(path).is_file()), "")


class ConfigDialog(tk.Toplevel):
    FIELDS = (
        ("category_id", "叶子类目 ID"),
        ("category_name", "类目名称"),
        ("store_identity_text", "店铺识别文本"),
        ("shipping_address", "发货地址匹配文本"),
        ("freight_template_text", "运费模板名称"),
        ("delivery_promise", "发货承诺"),
        ("package_weight_grams", "包裹重量（克）"),
    )

    def __init__(self, parent: tk.Misc, config_path: Path, on_saved: Callable[[], None]):
        super().__init__(parent)
        self.title("店铺与类目配置")
        self.geometry("620x520")
        self.minsize(560, 480)
        self.transient(parent)
        self.grab_set()
        self.config_path = config_path
        self.on_saved = on_saved
        self.payload = json.loads(config_path.read_text(encoding="utf-8"))
        self.values: dict[str, tk.StringVar] = {}
        body = ttk.Frame(self, padding=16)
        body.pack(fill="both", expand=True)
        target = self.payload.get("target") or {}
        for row, (key, label) in enumerate(self.FIELDS):
            ttk.Label(body, text=label).grid(row=row, column=0, sticky="w", padx=(0, 12), pady=6)
            value = target.get(key)
            var = tk.StringVar(value="" if value is None else str(value))
            self.values[key] = var
            ttk.Entry(body, textvariable=var).grid(row=row, column=1, sticky="ew", pady=6)
        row = len(self.FIELDS)
        ttk.Label(body, text="卖家 Profile 目录").grid(row=row, column=0, sticky="w", padx=(0, 12), pady=6)
        self.profile_var = tk.StringVar(value=str(self.payload.get("profile_dir") or ""))
        ttk.Entry(body, textvariable=self.profile_var).grid(row=row, column=1, sticky="ew", pady=6)
        row += 1
        ttk.Label(body, text="草稿输出目录").grid(row=row, column=0, sticky="w", padx=(0, 12), pady=6)
        self.output_var = tk.StringVar(value=str(self.payload.get("output_root") or ""))
        ttk.Entry(body, textvariable=self.output_var).grid(row=row, column=1, sticky="ew", pady=6)
        body.columnconfigure(1, weight=1)
        actions = ttk.Frame(body)
        actions.grid(row=row + 1, column=0, columnspan=2, sticky="e", pady=(20, 0))
        ttk.Button(actions, text="取消", command=self.destroy).pack(side="left", padx=4)
        ttk.Button(actions, text="保存", command=self.save).pack(side="left", padx=4)

    def save(self) -> None:
        try:
            target = self.payload.setdefault("target", {})
            for key, _ in self.FIELDS:
                value = self.values[key].get().strip()
                target[key] = int(value) if key == "package_weight_grams" and value else (value or None)
            self.payload["profile_dir"] = self.profile_var.get().strip()
            self.payload["output_root"] = self.output_var.get().strip()
            validation_path = self.config_path.with_name("settings.validation.json")
            atomic_write(validation_path, json.dumps(self.payload, ensure_ascii=False, indent=2))
            try:
                AppConfig.from_file(validation_path)
                os.replace(validation_path, self.config_path)
            finally:
                validation_path.unlink(missing_ok=True)
        except Exception as exc:
            messagebox.showerror("配置未保存", str(exc), parent=self)
            return
        self.on_saved()
        self.destroy()


class Launcher(tk.Tk):
    def __init__(self):
        super().__init__()
        self.paths = initialize_runtime()
        self.title(f"1688 自动草稿工具 {__version__}")
        self.geometry("900x680")
        self.minsize(760, 580)
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.process: subprocess.Popen[str] | None = None
        self.events: queue.Queue[tuple[str, object]] = queue.Queue()
        self.product_var = tk.StringVar()
        self.url_var = tk.StringVar()
        self.config_var = tk.StringVar(value=str(self.paths["config"]))
        self.status_var = tk.StringVar(value="就绪")
        self._build()
        self.after(100, self._drain_events)

    def _build(self) -> None:
        root = ttk.Frame(self, padding=16)
        root.pack(fill="both", expand=True)
        root.columnconfigure(1, weight=1)
        ttk.Label(root, text="商品文件").grid(row=0, column=0, sticky="w", padx=(0, 10), pady=6)
        ttk.Entry(root, textvariable=self.product_var).grid(row=0, column=1, sticky="ew", pady=6)
        ttk.Button(root, text="选择…", command=self.choose_product).grid(row=0, column=2, padx=(8, 0), pady=6)

        ttk.Label(root, text="采集链接").grid(row=1, column=0, sticky="w", padx=(0, 10), pady=6)
        ttk.Entry(root, textvariable=self.url_var).grid(row=1, column=1, sticky="ew", pady=6)
        self.collect_button = ttk.Button(root, text="采集商品", command=self.collect)
        self.collect_button.grid(row=1, column=2, padx=(8, 0), pady=6)

        ttk.Label(root, text="运行配置").grid(row=2, column=0, sticky="w", padx=(0, 10), pady=6)
        ttk.Entry(root, textvariable=self.config_var, state="readonly").grid(row=2, column=1, sticky="ew", pady=6)
        ttk.Button(root, text="编辑…", command=self.edit_config).grid(row=2, column=2, padx=(8, 0), pady=6)

        actions = ttk.Frame(root)
        actions.grid(row=3, column=0, columnspan=3, sticky="ew", pady=(12, 10))
        self.validate_button = ttk.Button(actions, text="数据校验", command=lambda: self.run_product("validate"))
        self.preview_button = ttk.Button(actions, text="预览填充", command=lambda: self.run_product("preview"))
        self.save_button = ttk.Button(actions, text="保存草稿", command=lambda: self.run_product("save"))
        for button in (self.validate_button, self.preview_button, self.save_button):
            button.pack(side="left", padx=(0, 8))
        ttk.Button(actions, text="打开数据目录", command=lambda: os.startfile(self.paths["root"])).pack(side="right")
        ttk.Button(actions, text="操作说明", command=self.open_manual).pack(side="right", padx=8)

        chrome = _chrome_path()
        environment_text = f"Chrome：{'已检测' if chrome else '未检测'}    数据目录：{self.paths['root']}"
        ttk.Label(root, text=environment_text).grid(row=4, column=0, columnspan=3, sticky="w", pady=(0, 8))
        self.log = tk.Text(root, wrap="word", height=20, state="disabled", font=("Consolas", 10))
        self.log.grid(row=5, column=0, columnspan=3, sticky="nsew")
        scrollbar = ttk.Scrollbar(root, orient="vertical", command=self.log.yview)
        scrollbar.grid(row=5, column=3, sticky="ns")
        self.log.configure(yscrollcommand=scrollbar.set)
        root.rowconfigure(5, weight=1)
        ttk.Label(root, textvariable=self.status_var).grid(row=6, column=0, columnspan=3, sticky="w", pady=(8, 0))

    def choose_product(self) -> None:
        selected = filedialog.askopenfilename(title="选择 product.json", filetypes=[("商品数据", "product.json"), ("JSON", "*.json")])
        if selected:
            self.product_var.set(selected)

    def edit_config(self) -> None:
        ConfigDialog(self, Path(self.config_var.get()), lambda: self.status_var.set("配置已保存"))

    def open_manual(self) -> None:
        manual = bundled_path("docs/操作说明.md")
        if not manual.exists():
            manual = bundled_path("README.md")
        if manual.exists():
            os.startfile(manual)
        else:
            messagebox.showinfo("操作说明", "操作说明文件未找到。", parent=self)

    def collect(self) -> None:
        url = self.url_var.get().strip()
        if not url:
            messagebox.showwarning("缺少链接", "请输入 1688 商品详情链接。", parent=self)
            return
        arguments = [
            "--url", url,
            "--output-dir", str(self.paths["products"]),
            "--profile-dir", str(self.paths["buyer_profile"]),
            "--wait-for-challenge", "120",
        ]
        self._start("--collect", arguments, "正在采集商品", self._after_collect)

    def run_product(self, action: str) -> None:
        product = Path(self.product_var.get().strip())
        if not product.is_file():
            messagebox.showwarning("缺少商品文件", "请选择有效的 product.json。", parent=self)
            return
        config = Path(self.config_var.get().strip())
        arguments = ["--product", str(product), "--config", str(config)]
        if action == "validate":
            arguments.append("--validate-only")
            label = "正在校验"
        elif action == "preview":
            arguments.append("--preview-only")
            label = "正在预览填充"
        else:
            if not messagebox.askyesno("保存草稿", "确认打开卖家后台并保存草稿？程序不会正式发布。", parent=self):
                return
            label = "正在保存草稿"
        self._start("--cli", arguments, label)

    def _start(self, mode: str, arguments: list[str], label: str, callback: Callable[[str], None] | None = None) -> None:
        if self.process is not None:
            messagebox.showwarning("任务运行中", "请等待当前任务结束。", parent=self)
            return
        command = _child_command(mode, arguments)
        env = os.environ.copy()
        env["PYTHONUTF8"] = "1"
        capture_path = self.paths["logs"] / f"worker-{uuid.uuid4().hex}.log"
        env["DRAFT_TOOL_CAPTURE_FILE"] = str(capture_path)
        flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        try:
            self.process = subprocess.Popen(
                command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                encoding="utf-8", errors="replace", env=env, creationflags=flags,
            )
        except OSError as exc:
            messagebox.showerror("无法启动", str(exc), parent=self)
            self.process = None
            return
        self._set_busy(True)
        self.status_var.set(label)
        self._append_log(f"\n> {label}\n")

        def reader() -> None:
            assert self.process and self.process.stdout
            chunks = []
            for line in self.process.stdout:
                chunks.append(line)
                self.events.put(("line", line))
            code = self.process.wait()
            if capture_path.is_file():
                captured = capture_path.read_text(encoding="utf-8", errors="replace")
                if captured:
                    chunks.append(captured)
                    self.events.put(("line", captured))
            self.events.put(("done", (code, "".join(chunks), callback)))

        threading.Thread(target=reader, daemon=True).start()

    def _after_collect(self, output: str) -> None:
        try:
            payload = json.loads(output.strip())
            saved = Path(payload["saved_to"]) / "product.json"
            if saved.is_file():
                self.product_var.set(str(saved))
        except (ValueError, KeyError, TypeError):
            pass

    def _drain_events(self) -> None:
        try:
            while True:
                kind, value = self.events.get_nowait()
                if kind == "line":
                    self._append_log(str(value))
                else:
                    code, output, callback = value
                    self.process = None
                    self._set_busy(False)
                    self.status_var.set(f"{EXIT_MESSAGES.get(code, '操作失败')}（退出码 {code}）")
                    if code == 0 and callback:
                        callback(output)
        except queue.Empty:
            pass
        self.after(100, self._drain_events)

    def _append_log(self, text: str) -> None:
        self.log.configure(state="normal")
        self.log.insert("end", text)
        self.log.see("end")
        self.log.configure(state="disabled")

    def _set_busy(self, busy: bool) -> None:
        state = "disabled" if busy else "normal"
        for button in (self.collect_button, self.validate_button, self.preview_button, self.save_button):
            button.configure(state=state)

    def close(self) -> None:
        if self.process and not messagebox.askyesno("退出", "任务仍在运行，确认退出启动器？后台任务将继续。", parent=self):
            return
        self.destroy()


def _dispatch(arguments: list[str]) -> int:
    if arguments and arguments[0] == "--cli":
        from draft_tool.cli import main as cli_main
        return cli_main(arguments[1:])
    if arguments and arguments[0] == "--collect":
        from draft_tool.collector import main as collector_main
        return collector_main(arguments[1:])
    if arguments == ["--smoke-test"]:
        paths = initialize_runtime()
        print(json.dumps({"version": __version__, "runtime": str(paths["root"])}, ensure_ascii=False))
        return 0
    app = Launcher()
    app.mainloop()
    return 0


def main(argv: list[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    capture_file = os.environ.get("DRAFT_TOOL_CAPTURE_FILE", "").strip()
    if capture_file:
        capture_path = Path(capture_file)
        capture_path.parent.mkdir(parents=True, exist_ok=True)
        with capture_path.open("w", encoding="utf-8") as stream:
            with redirect_stdout(stream), redirect_stderr(stream):
                return _dispatch(arguments)
    return _dispatch(arguments)


if __name__ == "__main__":
    raise SystemExit(main())
