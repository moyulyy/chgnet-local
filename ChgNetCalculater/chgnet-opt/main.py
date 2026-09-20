#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CHGNet 变胞弛豫优化程序
功能：读取 POSCAR 文件，使用 CHGNet 进行变胞结构优化，并生成 CONTCAR、OSZICAR、XDATCAR、OUTCAR。
"""

import argparse
import os
import pickle
import sys
import warnings
from datetime import datetime

import numpy as np
from chgnet.model import StructOptimizer
from pymatgen.io.vasp import Poscar


class OutputLogger:
    """将标准输出同时写入终端和 OUTCAR 文件。"""

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


class CHGNetRelaxer:
    """CHGNet 结构弛豫执行器。"""

    def __init__(self, input_file="POSCAR", output_structure="CONTCAR", max_steps=300, fmax=0.05, calc_type="bulk"):
        self.input_file = input_file
        self.work_dir = os.path.dirname(os.path.abspath(input_file)) or "."
        if os.path.isabs(output_structure):
            self.output_structure = output_structure
        else:
            self.output_structure = os.path.join(self.work_dir, output_structure)
        self.max_steps = max_steps
        self.fmax = fmax
        self.calc_type = calc_type
        self.selective_dynamics = None

    def log(self, message):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] {message}")

    def load_structure(self):
        """从 POSCAR 文件加载结构。"""
        if not os.path.exists(self.input_file):
            raise FileNotFoundError(f"输入文件不存在: {self.input_file}")

        self.log(f"读取输入结构: {self.input_file}")
        poscar_in = Poscar.from_file(self.input_file)
        structure = poscar_in.structure
        self.selective_dynamics = poscar_in.selective_dynamics

        print(f"Formula: {structure.composition.reduced_formula}")
        print(f"Atoms: {len(structure)}")
        print(f"Initial volume: {structure.lattice.volume:.6f} A^3")

        if self.selective_dynamics is not None:
            fixed_count = sum(1 for sd in self.selective_dynamics if not any(sd))
            relaxed_count = len(self.selective_dynamics) - fixed_count
            print(f"Selective dynamics: relaxed={relaxed_count}, fixed={fixed_count}")

        return structure

    def optimize_structure(self, structure):
        """使用 CHGNet 进行结构优化。"""
        relax_cell = self.calc_type == "bulk"
        mode_label = "bulk" if relax_cell else "relax"

        self.log(f"开始 CHGNet {mode_label} 优化")
        print(f"type: {self.calc_type}")
        print(f"relax_cell: {relax_cell}")
        print(f"max_steps: {self.max_steps}")
        print(f"fmax: {self.fmax} eV/A")

        relax_pkl_path = os.path.join(self.work_dir, "relax.pkl")
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=UserWarning)
            warnings.filterwarnings("ignore", category=RuntimeWarning)
            relaxer = StructOptimizer(use_device="cuda")
            result = relaxer.relax(
                atoms=structure,
                fmax=self.fmax,
                steps=self.max_steps,
                relax_cell=relax_cell,
                save_path=relax_pkl_path,
            )

        energies = result["trajectory"].energies
        final_structure = result["final_structure"]

        print(f"Initial energy: {energies[0]:.6f} eV")
        print(f"Final energy: {energies[-1]:.6f} eV")
        print(f"Energy change: {energies[-1] - energies[0]:+.6f} eV")
        print(f"Steps: {len(energies)}")
        print(f"Final volume: {final_structure.lattice.volume:.6f} A^3")

        return result

    def save_structure(self, structure):
        """保存优化后的结构。"""
        self.log(f"写入 CONTCAR: {self.output_structure}")
        poscar_out = Poscar(
            structure,
            selective_dynamics=self.selective_dynamics,
            comment=None,
            true_names=True,
            velocities=None,
        )
        poscar_out.write_file(self.output_structure)

    def save_oszicar(self, result):
        """生成 OSZICAR 文件。"""
        energies = result["trajectory"].energies
        oszicar_path = os.path.join(self.work_dir, "OSZICAR")

        with open(oszicar_path, "w", encoding="utf-8") as f:
            for i, energy in enumerate(energies, start=1):
                if i == 1:
                    d_energy = 0.0
                else:
                    d_energy = energy - energies[i - 2]

                f_str = self._format_vasp_energy(energy)
                e0_str = self._format_vasp_energy(energy)
                de_str = self._format_vasp_energy(d_energy)
                f.write(f"{i:4d} F= {f_str} E0= {e0_str}  d E ={de_str}\n")

        self.log(f"写入 OSZICAR: {oszicar_path}")

    def _format_vasp_energy(self, energy):
        """格式化能量为 VASP 风格。"""
        import math

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
        mantissa_str = mantissa_str[1:]
        exp_str = f"E{exponent:+03d}"

        return f"{sign}{mantissa_str}{exp_str}"

    def save_xdatcar(self):
        """根据 relax.pkl 生成 XDATCAR 文件。"""
        relax_pkl_path = os.path.join(self.work_dir, "relax.pkl")
        xdatcar_path = os.path.join(self.work_dir, "XDATCAR")

        if not os.path.exists(relax_pkl_path):
            raise FileNotFoundError(f"未找到 relax.pkl: {relax_pkl_path}")

        with open(relax_pkl_path, "rb") as f:
            data = pickle.load(f)

        atomic_numbers = data["atomic_number"]
        positions = data["atom_positions"]
        cells = data["cell"]
        energies = data["energy"]

        from pymatgen.core import Element

        elements = [Element.from_Z(z).symbol for z in atomic_numbers]

        unique_elements = []
        element_counts = []
        current_element = elements[0]
        count = 1
        for element in elements[1:]:
            if element == current_element:
                count += 1
            else:
                unique_elements.append(current_element)
                element_counts.append(count)
                current_element = element
                count = 1
        unique_elements.append(current_element)
        element_counts.append(count)

        with open(xdatcar_path, "w", encoding="utf-8") as f:
            f.write("Generated by CHGNet Relax Bulk\n")
            f.write("1.0\n")

            for i in range(len(energies)):
                cell = cells[i]
                for j in range(3):
                    f.write(f"  {cell[j][0]:.10f}  {cell[j][1]:.10f}  {cell[j][2]:.10f}\n")

                f.write("  " + "  ".join(unique_elements) + "\n")
                f.write("  " + "  ".join(map(str, element_counts)) + "\n")
                f.write("Direct configuration=  %6d\n" % (i + 1))

                for pos in positions[i]:
                    frac_pos = np.linalg.solve(cell.T, pos)
                    f.write(f"  {frac_pos[0]:.10f}  {frac_pos[1]:.10f}  {frac_pos[2]:.10f}\n")

        self.log(f"写入 XDATCAR: {xdatcar_path}")

    def run(self):
        """执行完整优化流程。"""
        try:
            structure = self.load_structure()
            result = self.optimize_structure(structure)
            self.save_structure(result["final_structure"])
            self.save_oszicar(result)
            self.save_xdatcar()

            print("Generated files:")
            print(f"  {self.output_structure}")
            print(f"  {os.path.join(self.work_dir, 'OSZICAR')}")
            print(f"  {os.path.join(self.work_dir, 'XDATCAR')}")
            print(f"  {os.path.join(self.work_dir, 'OUTCAR')}")
            return True
        except Exception as exc:
            print(f"Error: {exc}")
            import traceback

            traceback.print_exc(file=sys.stdout)
            return False


def suppress_all_warnings():
    """抑制第三方库的常见警告。"""
    warnings.filterwarnings("ignore", category=RuntimeWarning)
    warnings.filterwarnings("ignore", category=UserWarning, module="pymatgen")
    warnings.filterwarnings("ignore", category=UserWarning, module="chgnet")
    warnings.filterwarnings("ignore", category=RuntimeWarning, module="ase")


def parse_args():
    """解析命令行参数。"""
    parser = argparse.ArgumentParser(description="Run CHGNet bulk/cell relaxation and generate VASP-style outputs.")
    parser.add_argument("--type", dest="calc_type", choices=["bulk", "relax"], default="bulk", help="bulk = relax cell and structure; relax = relax structure with fixed cell")
    parser.add_argument("--input", dest="input_file", default="POSCAR", help="input POSCAR file")
    parser.add_argument("--output", dest="output_file", default="CONTCAR", help="optimized structure output file")
    parser.add_argument("--max-steps", type=int, default=300, help="maximum relaxation steps")
    parser.add_argument("--fmax", type=float, default=0.05, help="force convergence threshold in eV/A")
    return parser.parse_args()


def main():
    """非交互 CLI 入口。"""
    suppress_all_warnings()
    args = parse_args()

    if args.max_steps <= 0:
        print("Error: --max-steps must be greater than 0", file=sys.stderr)
        return 1
    if args.fmax <= 0:
        print("Error: --fmax must be greater than 0", file=sys.stderr)
        return 1
    if not args.output_file:
        print("Error: --output must not be empty", file=sys.stderr)
        return 1
    if not os.path.exists(args.input_file):
        print(f"Error: input file not found: {args.input_file}", file=sys.stderr)
        return 1

    work_dir = os.path.dirname(os.path.abspath(args.input_file)) or "."
    outcar_path = os.path.join(work_dir, "OUTCAR")

    with OutputLogger(outcar_path):
        optimizer = CHGNetRelaxer(
            input_file=args.input_file,
            output_structure=args.output_file,
            max_steps=args.max_steps,
            fmax=args.fmax,
            calc_type=args.calc_type,
        )
        success = optimizer.run()

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
