#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CHGNet 单点计算程序 (Single-Point Energy)
=====================================================================
读取 POSCAR/CONTCAR 结构, 用 CHGNet 机器学习势在**固定结构**下
计算一次总能量 / 原子受力 / 应力, 不移动任何原子 (真正的单点)。

说明: chgnet-opt/main.py 的 relax 流程要求 max_steps>=1 (会推动原子),
因此单点计算单独放在本脚本, 供模型处理菜单 E. chgnet单点计算 与
singlepoint.bat 调用。

输出 (写入输入结构所在目录):
  CONTCAR  结构原样回写 (与输入一致, 便于后续作为 VASP 输入)
  OSZICAR  单点能量 (VASP 风格一行)
  OUTCAR   完整日志 (能量/受力/应力汇总, 由 OutputLogger 同步写终端)

用法示例:
  python singlepoint_runner.py --input POSCAR
  python singlepoint_runner.py --input CONTCAR --output CONTCAR_sp \
         --device cuda
"""
import argparse
import math
import os
import sys
import warnings
from datetime import datetime

# -------------------- 设备选择 --------------------
def pick_device(requested):
    """返回可用的 torch 设备: 显式 cuda/cpu 优先, 'auto' 自动探测。"""
    import torch
    if requested == "cuda" and not torch.cuda.is_available():
        print("  [警告] 本机不可用 CUDA (torch.cuda.is_available()=False), "
              "自动回退 CPU (较慢)。", file=sys.stderr)
        return "cpu"
    if requested == "auto":
        return "cuda" if torch.cuda.is_available() else "cpu"
    return requested


# -------------------- 日志 (同步写 OUTCAR) --------------------
class OutputLogger:
    """把标准输出同时写入终端与 OUTCAR 文件。"""

    def __init__(self, filename):
        self.filename = filename
        self.terminal = sys.stdout
        self.log_file = None

    def __enter__(self):
        self.log_file = open(self.filename, "w", encoding="utf-8")
        sys.stdout = self
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        sys.stdout = self.terminal
        if self.log_file:
            self.log_file.close()

    def write(self, message):
        self.terminal.write(message)
        if self.log_file and message:
            self.log_file.write(message)
            self.log_file.flush()

    def flush(self):
        self.terminal.flush()
        if self.log_file:
            self.log_file.flush()


def log(message):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}")


# -------------------- VASP 风格能量格式化 --------------------
def format_vasp_energy(energy):
    """把能量格式化成 VASP OSZICAR 风格, 如 -.12345678E+03。"""
    if energy == 0:
        return ".00000000E+00"
    sign = "-" if energy < 0 else ""
    abs_energy = abs(energy)
    exponent = int(math.floor(math.log10(abs_energy)))
    mantissa = abs_energy / (10 ** exponent)
    if mantissa >= 1.0:
        exponent += 1
        mantissa = abs_energy / (10 ** exponent)
    mantissa_str = f"{mantissa:.8f}"
    mantissa_str = mantissa_str[1:]  # 去掉整数位 0, 与 VASP 一致
    return f"{sign}{mantissa_str}E{exponent:+03d}"


# -------------------- 主流程 --------------------
def main():
    parser = argparse.ArgumentParser(
        description="CHGNet single-point energy calculation (no atom movement)")
    parser.add_argument("--input", dest="input_file", default="POSCAR",
                        help="输入结构文件 (默认: POSCAR)")
    parser.add_argument("--output", dest="output_file", default="CONTCAR",
                        help="结构原样回写文件名 (默认: CONTCAR)")
    parser.add_argument("--device", dest="device", default="auto",
                        choices=["auto", "cuda", "cpu"],
                        help="计算设备 (默认: auto, cuda 不可用时自动回退 cpu)")
    args = parser.parse_args()

    if not os.path.exists(args.input_file):
        print(f"Error: input file not found: {args.input_file}", file=sys.stderr)
        return 1

    input_abs = os.path.abspath(args.input_file)
    work_dir = os.path.dirname(input_abs) or os.getcwd()
    output_path = args.output_file
    if not os.path.isabs(output_path):
        output_path = os.path.join(work_dir, output_path)
    outcar_path = os.path.join(work_dir, "OUTCAR")
    oszicar_path = os.path.join(work_dir, "OSZICAR")

    with OutputLogger(outcar_path):
        try:
            # ---------- 1. 读取结构 ----------
            from pymatgen.io.vasp import Poscar
            log(f"读取输入结构: {input_abs}")
            poscar_in = Poscar.from_file(input_abs)
            structure = poscar_in.structure
            print(f"Formula : {structure.composition.reduced_formula}")
            print(f"Atoms   : {len(structure)}")
            print(f"Volume  : {structure.lattice.volume:.6f} A^3")
            print(f"Device  : {pick_device(args.device)}")

            # ---------- 2. 加载 CHGNet 并单点预测 ----------
            from chgnet.model.model import CHGNet
            log("加载 CHGNet 模型 ...")
            device = pick_device(args.device)
            model = CHGNet.load(use_device=device)
            model.eval()

            log("开始单点计算 (结构固定, 不弛豫) ...")
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore")
                pred = model.predict_structure(structure)

            energy = float(pred["e"].flatten()[0]) if "e" in pred else None
            forces = pred.get("f")
            stress = pred.get("s")

            import numpy as np

            def _to_numpy(x):
                """兼容 tensor / numpy 两种返回类型。"""
                if x is None:
                    return None
                if hasattr(x, "detach"):
                    x = x.detach()
                if hasattr(x, "cpu"):
                    x = x.cpu()
                return np.asarray(x)

            f_mat = _to_numpy(forces)
            if f_mat is not None:
                f_mat = f_mat.reshape(-1, 3)
            s_vec = _to_numpy(stress)
            if s_vec is not None:
                s_vec = s_vec.reshape(-1)

            print(f"\n  Total energy = {energy:.8f} eV")
            if f_mat is not None:
                fmax = float(np.abs(f_mat).max())
                frms = float(np.sqrt((f_mat ** 2).mean()))
                print(f"  Max |force| = {fmax:.6f} eV/A")
                print(f"  RMS force   = {frms:.6f} eV/A")
            if s_vec is not None:
                print(f"  Stress      = {s_vec.tolist()}")

            # ---------- 3. 输出文件 ----------
            log(f"写入 CONTCAR(结构原样): {output_path}")
            Poscar(structure, comment=None, true_names=True).write_file(output_path)

            log(f"写入 OSZICAR: {oszicar_path}")
            with open(oszicar_path, "w", encoding="utf-8") as f:
                f.write(f"{1:4d} F= {format_vasp_energy(energy)} "
                        f"E0= {format_vasp_energy(energy)}  d E ="
                        f"{format_vasp_energy(0.0)}\n")

            print("\nGenerated files:")
            print(f"  {output_path}")
            print(f"  {oszicar_path}")
            print(f"  {outcar_path}")
            return 0

        except Exception as exc:
            print(f"\nError: {exc}")
            import traceback
            traceback.print_exc(file=sys.stdout)
            return 1


if __name__ == "__main__":
    sys.exit(main())
