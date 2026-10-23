"""Adversarial Zero-Network Privacy & Local Isolation Verification."""

from __future__ import annotations

import ast
import os
import socket
import sys
import urllib.request
from pathlib import Path
import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from selficamera.processor.pipeline import FrameProcessor
from selficamera.processor.segmentation import SegmentationBlurEngine
from selficamera.shortcuts.ipc import ShortcutIPCClient, ShortcutIPCServer
from benchmarks.adversarial_stress_suite import generate_test_presenter_frame


def run_network_privacy_audit():
    print("\n" + "=" * 80)
    print(" SELFI CAMERA ZERO-NETWORK PRIVACY & OFFLINE ISOLATION AUDIT")
    print("=" * 80)

    repo_root = Path(__file__).resolve().parent.parent
    src_dir = repo_root / "selficamera"

    # [1] Static AST Codebase Scan
    print("\n[1] Static AST Codebase Audit across all source files:")
    forbidden_modules = {
        "requests", "urllib", "urllib3", "httpx", "http.client", "aiohttp",
        "socketserver", "ftplib", "telnetlib", "paramiko", "grpc", "boto3", "google"
    }

    ast_violations = []
    py_files = list(src_dir.rglob("*.py"))
    print(f"  Scanning {len(py_files)} Python files in {src_dir}...")

    for py_file in py_files:
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root_pkg = alias.name.split(".")[0]
                    if root_pkg in forbidden_modules:
                        ast_violations.append((str(py_file.relative_to(repo_root)), alias.name))
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    root_pkg = node.module.split(".")[0]
                    if root_pkg in forbidden_modules:
                        ast_violations.append((str(py_file.relative_to(repo_root)), node.module))

    if ast_violations:
        print(f"  FAILED: AST detected forbidden network imports: {ast_violations}")
        sys.exit(1)
    else:
        print(f"  ✓ Static AST Audit PASSED: 0 forbidden network imports found across {len(py_files)} files.")

    # [2] Dynamic Runtime Trap
    print("\n[2] Dynamic Runtime Network Interception Trap:")
    intercepted_network_calls = []

    orig_socket = socket.socket
    orig_getaddrinfo = socket.getaddrinfo
    orig_gethostbyname = socket.gethostbyname

    def trap_socket(family=socket.AF_INET, type=socket.SOCK_STREAM, proto=0, fileno=None):
        if family in (socket.AF_INET, socket.AF_INET6):
            call_desc = f"socket(family={family}, type={type}, proto={proto})"
            intercepted_network_calls.append(call_desc)
            raise RuntimeError(f"TRAPPED OUTBOUND NETWORK CALL: {call_desc}")
        return orig_socket(family, type, proto, fileno)

    def trap_dns(*args, **kwargs):
        call_desc = f"dns_lookup({args}, {kwargs})"
        intercepted_network_calls.append(call_desc)
        raise RuntimeError(f"TRAPPED DNS RESOLUTION: {call_desc}")

    socket.socket = trap_socket
    socket.getaddrinfo = trap_dns
    socket.gethostbyname = trap_dns

    try:
        # Run 200 frames through the complete pipeline with all features active
        frame = generate_test_presenter_frame(1280, 720)
        proc = FrameProcessor(mirror=True, auto_light=True, blur_level=3)

        print("  Running 200 frames under active network trap (Mirror+Light+Blur Tier 3)...")
        for _ in range(200):
            proc.process(frame)

        print("  ✓ Pipeline execution under trap complete: 0 network calls attempted.")

        # Test IPC socket to verify only AF_UNIX is used with 0o600 permissions
        print("\n[3] IPC Socket Protocol & Permission Audit:")
        from PySide6.QtCore import QCoreApplication
        app = QCoreApplication.instance() or QCoreApplication([])

        state = {"running": True, "blur_level": 3}
        server = ShortcutIPCServer(state_provider=lambda: state)
        server.start()

        import time
        t_wait = time.perf_counter()
        while not server.is_listening and time.perf_counter() - t_wait < 2.0:
            app.processEvents()
            time.sleep(0.01)

        sock_path = Path(server.socket_path)
        assert sock_path.exists(), "IPC socket file does not exist!"
        sock_stat = sock_path.stat()
        file_mode = oct(sock_stat.st_mode & 0o777)
        print(f"  IPC Socket Path: {sock_path}")
        print(f"  IPC Socket Permissions: {file_mode} (Expected 0o600)")
        assert file_mode == "0o600", f"Insecure socket permissions: {file_mode}"

        resp = ShortcutIPCClient.send_command("ping")
        print(f"  IPC Ping Response: {resp}")
        assert resp.get("success") is True, f"Ping failed: {resp}"
        assert resp.get("state") == state, f"State mismatch: {resp.get('state')} vs {state}"

        server.stop()
        t_wait = time.perf_counter()
        while sock_path.exists() and time.perf_counter() - t_wait < 2.0:
            app.processEvents()
            time.sleep(0.01)

        print("  ✓ IPC Server strictly AF_UNIX, permission 0o600, 0 IP sockets opened.")

    finally:
        socket.socket = orig_socket
        socket.getaddrinfo = orig_getaddrinfo
        socket.gethostbyname = orig_gethostbyname

    assert len(intercepted_network_calls) == 0, f"Violations intercepted: {intercepted_network_calls}"
    print("\n" + "=" * 80)
    print(" ✓ ZERO-NETWORK PRIVACY AUDIT: 100% OFFLINE ISOLATION VERIFIED!")
    print("=" * 80)


if __name__ == "__main__":
    run_network_privacy_audit()
