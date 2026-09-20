#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CHGNet 振动频率计算程序 - CLI 版本
功能：使用有限位移法计算吸附物种振动频率，得到 ZPE 和 TS 用于自由能修正
类似 VASP: IBRION=5, NFREE=2, NSW=1
"""

import argparse
import sys
import os
import warnings
import numpy as np
from datetime import datetime
from chgnet.model import CHGNet
from chgnet.model.dynamics import CHGNetCalculator
from pymatgen.core import Structure
from pymatgen.io.vasp import Poscar
from pymatgen.io.ase import AseAtomsAdaptor
from ase.vibrations import Vibrations
from ase.thermochemistry import HarmonicThermo


def configure_output():
    """配置标准输出，避免 Windows 终端因字符编码报错"""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(errors="replace")


# ==================== CLI 输出工具 ====================
class Colors:
    """兼容旧格式化字符串，CLI 模式下不再输出颜色控制符"""
    RESET = ''
    BOLD = ''
    DIM = ''
    BLACK = ''
    RED = ''
    GREEN = ''
    YELLOW = ''
    BLUE = ''
    MAGENTA = ''
    CYAN = ''
    WHITE = ''
    BRIGHT_BLACK = ''
    BRIGHT_RED = ''
    BRIGHT_GREEN = ''
    BRIGHT_YELLOW = ''
    BRIGHT_BLUE = ''
    BRIGHT_MAGENTA = ''
    BRIGHT_CYAN = ''
    BRIGHT_WHITE = ''


def print_box(title, content, width=80, color=Colors.GREEN):
    """CLI 模式下输出普通文本块"""
    del width, color
    print(f"\n[{title}]")
    print(content)


def print_section(title):
    """输出普通章节标题"""
    print(f"\n== {title} ==")


def print_success(message):
    print(f"[OK] {message}")


def print_error(message):
    print(f"[ERROR] {message}", file=sys.stderr)


def print_info(message):
    print(f"[INFO] {message}")


def print_warning(message):
    print(f"[WARN] {message}")


# ==================== 主程序 ====================
class CHGNetFreq:
    """CHGNet 振动频率计算器类（类似 VASP IBRION=5）"""

    def __init__(self, input_file="POSCAR", delta=0.015, nfree=2, temperature=298.15):
        self.input_file = input_file
        self.work_dir = os.path.dirname(os.path.abspath(input_file)) or '.'
        self.delta = delta
        self.nfree = nfree
        self.temperature = temperature
        self.selective_dynamics = None
        self.indices = None  # 需要计算频率的原子索引
        self.vib_energies = None  # 振动能量 (eV)
        self.potentialenergy = None

    def log(self, message):
        """记录日志信息（带时间戳）"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"{Colors.DIM}[{timestamp}]{Colors.RESET} {message}")

    def load_structure(self):
        """从 POSCAR 文件加载结构，识别固定的原子"""
        try:
            if not os.path.exists(self.input_file):
                raise FileNotFoundError(f"输入文件 {self.input_file} 不存在")

            self.log(f"{Colors.YELLOW}正在读取输入文件:{Colors.RESET} {self.input_file}")

            # 使用 Poscar 读取以保留 selective_dynamics
            poscar_in = Poscar.from_file(self.input_file)
            structure = poscar_in.structure
            self.selective_dynamics = poscar_in.selective_dynamics

            # 确定哪些原子需要计算频率
            if self.selective_dynamics:
                # 找到未被固定的原子（至少有一个方向可以移动）
                self.indices = []
                fixed_indices = []
                for i, sd in enumerate(self.selective_dynamics):
                    if any(sd):  # 至少一个方向可以移动
                        self.indices.append(i)
                    else:
                        fixed_indices.append(i)

                print_info(f"检测到原子约束信息")
                print_info(f"总原子数: {len(structure)}")
                print_info(f"弛豫原子数: {len(self.indices)}")
                print_info(f"固定原子数: {len(fixed_indices)}")

                if len(self.indices) == 0:
                    print_warning("所有原子都被固定！将对所有原子计算频率")
                    self.indices = None
            else:
                print_info("未检测到原子约束，将对所有原子计算频率")
                self.indices = None

            # 显示结构信息
            info_lines = [
                f"",
                f"{Colors.BRIGHT_GREEN}化学式:{Colors.RESET} {structure.composition.reduced_formula}",
                f"{Colors.BRIGHT_GREEN}原子数:{Colors.RESET} {len(structure)}",
                f"",
                f"{Colors.BOLD}晶格参数:{Colors.RESET}",
                f"  a     = {structure.lattice.a:>12.6f} Å",
                f"  b     = {structure.lattice.b:>12.6f} Å",
                f"  c     = {structure.lattice.c:>12.6f} Å",
                f"  体积  = {structure.lattice.volume:>12.6f} Å³",
            ]

            if self.indices is not None:
                info_lines.extend([
                    f"",
                    f"{Colors.BRIGHT_YELLOW}振动计算原子:{Colors.RESET} {len(self.indices)} 个",
                ])

            print_box("结构信息", '\n'.join(info_lines), color=Colors.CYAN)

            return structure

        except Exception as e:
            print_error(f"读取结构文件时出错: {str(e)}")
            raise

    def calculate_vibrations(self, structure):
        """计算振动频率"""
        try:
            print_section("振动频率计算")

            print_info("初始化 CHGNet 模型...")
            chgnet = CHGNet.load()

            # 修复 CHGNet 的 JSON 序列化问题
            chgnet.todict = lambda: {"model_name": "CHGNet", "model_args": chgnet.model_args}

            print_info("创建 ASE 计算器...")
            calc = CHGNetCalculator(
                potential=chgnet,
                compute_stress=False,
                compute_hessian=False,
            )

            # 转换为 ASE Atoms
            print_info("转换为 ASE Atoms...")
            atoms = AseAtomsAdaptor.get_atoms(structure)
            atoms.calc = calc

            # 计算能量
            print_info("计算体系能量...")
            self.potentialenergy = atoms.get_potential_energy()
            print_success(f"体系能量: {self.potentialenergy:.6f} eV")

            # 创建振动对象
            print_info(f"创建振动对象 (位移: {self.delta} Å, nfree: {self.nfree})...")
            print_info("注意：仅对未被固定的原子计算振动频率")

            vib = Vibrations(
                atoms,
                indices=self.indices,  # 只计算这些原子的频率
                delta=self.delta,
                nfree=self.nfree,
                name=os.path.join(self.work_dir, 'vib')
            )

            print_info("运行有限位移计算（这可能需要一些时间）...")
            print(f"{Colors.DIM}计算 {3*len(self.indices) if self.indices else 3*len(atoms)} 个振动模式...{Colors.RESET}\n")

            vib.run()

            print_success("振动计算完成！")

            # 获取振动能量 (转换为 eV)
            self.vib_energies = vib.get_energies()

            # 过滤虚频 (负频率)
            real_vib_energies = []
            imag_modes = []
            for i, energy in enumerate(self.vib_energies):
                if energy.real > 0:
                    real_vib_energies.append(energy.real)
                else:
                    imag_modes.append((i, energy))

            # 显示振动模式信息
            freq_lines = [
                f"",
                f"{Colors.BRIGHT_GREEN}振动模式总数:{Colors.RESET} {len(self.vib_energies)}",
                f"{Colors.BRIGHT_GREEN}实频数量:{Colors.RESET} {len(real_vib_energies)}",
            ]

            if imag_modes:
                freq_lines.append(f"{Colors.BRIGHT_YELLOW}虚频数量:{Colors.RESET} {len(imag_modes)}")
                for idx, energy in imag_modes[:3]:  # 最多显示3个
                    freq_lines.append(f"  模式 {idx}: {energy:.4f} eV")

            # 显示前几个频率
            freq_lines.extend([
                f"",
                f"{Colors.BOLD}前 5 个振动频率:{Colors.RESET}",
            ])
            for i, energy in enumerate(real_vib_energies[:5]):
                wavenumber = energy * 8065.54  # cm^-1
                freq_lines.append(f"  模式 {i+1}: {energy*1000:.4f} meV ({wavenumber:.2f} cm⁻¹)")

            print_box("振动频率结果", '\n'.join(freq_lines), color=Colors.MAGENTA)

            # 保存振动数据
            vib_summary_path = os.path.join(self.work_dir, 'vib_summary.txt')
            vib.summary(log=vib_summary_path)
            print_success(f"振动摘要已保存到 {vib_summary_path}")

            return real_vib_energies

        except Exception as e:
            print_error(f"振动计算出错: {str(e)}")
            raise

    def calculate_thermochemistry(self, vib_energies):
        """计算热化学性质（ZPE 和 TS）"""
        try:
            print_section("热力学性质计算")

            print_info(f"计算 T = {self.temperature} K 时的热力学量...")

            # 创建 HarmonicThermo 对象
            thermo = HarmonicThermo(
                vib_energies=vib_energies,
                potentialenergy=self.potentialenergy,
            )

            # 获取各热力学量 (ASE HarmonicThermo API)
            # get_ZPE() 只在旧版本中存在，新版本使用 _vibrational_energy_contribution
            # 直接计算 ZPE: sum of hbar*omega/2 for all modes
            hbar = 6.582119569e-16  # eV*s
            ZPE = 0.5 * np.sum(vib_energies)  # ZPE = sum(0.5 * hbar * omega)

            U = thermo.get_internal_energy(temperature=self.temperature)  # 内能
            S = thermo.get_entropy(temperature=self.temperature)  # 熵
            TS = self.temperature * S  # TS
            F = thermo.get_helmholtz_energy(temperature=self.temperature)  # Helmholtz自由能

            # 显示结果
            result_lines = [
                f"",
                f"{Colors.BOLD}零点能 (ZPE):{Colors.RESET}",
                f"  E_ZPE = {ZPE:.6f} eV",
                f"",
                f"{Colors.BOLD}热力学量 (T = {self.temperature} K):{Colors.RESET}",
                f"  U          = {U:.6f} eV",
                f"  S          = {S:.6e} eV/K",
                f"  T×S        = {TS:.6f} eV",
                f"",
                f"{Colors.BOLD}{Colors.BRIGHT_GREEN}自由能修正项:{Colors.RESET}",
                f"  ZPE        = {ZPE:.6f} eV",
                f"  -T×S       = {-TS:.6f} eV",
                f"  ─────────────────────────",
                f"  F - E_pot  = {F - self.potentialenergy:.6f} eV",
                f"",
                f"{Colors.BOLD}{Colors.BRIGHT_GREEN}Helmholtz 自由能:{Colors.RESET}",
                f"  F = E_pot + ZPE - T×S",
                f"  F = {F:.6f} eV",
            ]
            print_box("热力学计算结果", '\n'.join(result_lines), color=Colors.GREEN)

            # 保存结果到文件
            self.save_results(ZPE, U, S, TS, F)

            return ZPE, TS

        except Exception as e:
            print_error(f"热力学计算出错: {str(e)}")
            raise

    def save_results(self, ZPE, U, S, TS, F):
        """保存计算结果到文件"""
        try:
            result_file = os.path.join(self.work_dir, "FREQ_RESULTS")
            zpe_ts_file = os.path.join(self.work_dir, "zpe-ts.dat")

            with open(result_file, 'w', encoding='utf-8') as f:
                f.write("=" * 70 + "\n")
                f.write("CHGNet Vibrational Frequency Calculation Results\n")
                f.write("=" * 70 + "\n\n")

                f.write(f"Input file: {self.input_file}\n")
                f.write(f"Temperature: {self.temperature} K\n")
                f.write(f"Displacement: {self.delta} Å\n")
                f.write(f"Nfree: {self.nfree}\n")
                if self.indices:
                    f.write(f"Vibrating atoms: {len(self.indices)} / {len(self.indices) + (len(self.selective_dynamics) - len(self.indices) if self.selective_dynamics else 0)}\n")
                f.write("\n")

                f.write("=" * 70 + "\n")
                f.write("Zero-Point Energy (ZPE)\n")
                f.write("=" * 70 + "\n")
                f.write(f"E_ZPE = {ZPE:.6f} eV\n")
                f.write(f"E_ZPE = {ZPE * 23.0605:.6f} kcal/mol\n\n")

                f.write("=" * 70 + "\n")
                f.write("Entropy and Free Energy Corrections\n")
                f.write("=" * 70 + "\n")
                f.write(f"S       = {S:.6e} eV/K\n")
                f.write(f"T×S     = {TS:.6f} eV\n")
                f.write(f"-T×S    = {-TS:.6f} eV\n\n")

                f.write("=" * 70 + "\n")
                f.write("Summary for Free Energy Correction\n")
                f.write("=" * 70 + "\n")
                f.write(f"E_pot   = {self.potentialenergy:.6f} eV\n")
                f.write(f"ZPE     = {ZPE:.6f} eV\n")
                f.write(f"-T×S    = {-TS:.6f} eV\n")
                f.write("-" * 70 + "\n")
                f.write(f"F       = {F:.6f} eV\n")
                f.write(f"F_corr  = {ZPE - TS:.6f} eV\n")
                f.write("=" * 70 + "\n")

            with open(zpe_ts_file, 'w', encoding='utf-8') as f:
                f.write(f"ZPE = {ZPE:.6f} eV\n")
                f.write(f"TS = {TS:.6f} eV\n")
                f.write(f"ZPE-TS = {ZPE - TS:.6f} eV\n")

            print_success(f"结果已保存到 {result_file}")
            print_success(f"ZPE/TS 数据已保存到 {zpe_ts_file}")

        except Exception as e:
            print_error(f"保存结果时出错: {str(e)}")

    def run(self):
        """执行完整的振动频率计算流程"""
        try:
            # 1. 加载结构
            structure = self.load_structure()

            # 2. 计算振动频率
            vib_energies = self.calculate_vibrations(structure)

            # 3. 热力学计算
            ZPE, TS = self.calculate_thermochemistry(vib_energies)

            # 完成
            print()
            print_box("任务完成",
                f"\n{Colors.BRIGHT_GREEN}{Colors.BOLD}振动频率计算完成！{Colors.RESET}\n\n"
                f"{Colors.CYAN}输出文件:{Colors.RESET}\n"
                f"  • FREQ_RESULTS   - 热力学计算结果\n"
                f"  • vib_summary.txt - 振动频率摘要\n"
                f"  • zpe-ts.dat     - ZPE/TS 修正值\n"
                f"  • vib.*.pckl     - 振动数据文件\n\n"
                f"{Colors.BRIGHT_YELLOW}用于自由能修正:{Colors.RESET}\n"
                f"  ZPE    = {ZPE:.6f} eV\n"
                f"  TS     = {TS:.6f} eV\n"
                f"  ZPE-TS = {ZPE - TS:.6f} eV\n",
                color=Colors.GREEN)

            return True

        except Exception as e:
            print_error(f"程序执行出错: {str(e)}")
            import traceback
            traceback.print_exc()
            return False


def suppress_all_warnings():
    """抑制警告"""
    warnings.filterwarnings('ignore', category=RuntimeWarning)
    warnings.filterwarnings('ignore', category=UserWarning, module='pymatgen')
    warnings.filterwarnings('ignore', category=UserWarning, module='chgnet')
    warnings.filterwarnings('ignore', category=RuntimeWarning, module='ase')
    warnings.filterwarnings('ignore', category=FutureWarning, module='ase')
    warnings.filterwarnings('ignore', category=FutureWarning, module='chgnet')


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description="使用 CHGNet 进行振动频率计算并输出 ZPE/TS 修正"
    )
    parser.add_argument(
        "--input",
        default="POSCAR",
        help="输入结构文件路径，默认值为 POSCAR",
    )
    parser.add_argument(
        "--delta",
        type=float,
        default=0.015,
        help="有限位移大小（Å），默认值为 0.015",
    )
    parser.add_argument(
        "--nfree",
        type=int,
        default=2,
        help="有限位移次数，默认值为 2",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=298.15,
        help="热力学温度（K），默认值为 298.15",
    )

    args = parser.parse_args()

    if args.delta <= 0:
        parser.error("--delta 必须为正数")
    if args.nfree <= 0:
        parser.error("--nfree 必须为正整数")
    if args.temperature <= 0:
        parser.error("--temperature 必须为正数")

    return args


def main():
    """主函数"""
    configure_output()
    suppress_all_warnings()

    try:
        args = parse_args()

        freq_calculator = CHGNetFreq(
            input_file=args.input,
            delta=args.delta,
            nfree=args.nfree,
            temperature=args.temperature,
        )
        success = freq_calculator.run()
        sys.exit(0 if success else 1)

    except KeyboardInterrupt:
        print(f"\n\n{Colors.BRIGHT_YELLOW}用户中断操作{Colors.RESET}")
        sys.exit(1)
    except Exception as e:
        print_error(f"程序错误: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
