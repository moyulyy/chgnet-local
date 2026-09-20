#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CHGNet NEB (Nudged Elastic Band) 过渡态计算程序 - 非交互 CLI 版本
功能：读取工作目录下 00、01、02 ... 数字目录中的 POSCAR，进行 NEB 计算寻找过渡态
类似于 VASP 的 NEB 计算方式
"""

import argparse
import sys
import os
import warnings
import numpy as np

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# 设置环境变量以使用中文语言
os.environ['LC_ALL'] = 'zh_CN.UTF-8'
os.environ['LANG'] = 'zh_CN.UTF-8'

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from datetime import datetime
from chgnet.model import CHGNet
from chgnet.model.dynamics import CHGNetCalculator
from pymatgen.core import Structure
from ase.io import read, write
from ase.io.trajectory import Trajectory
# ASE NEB模块导入（兼容不同版本）
try:
    from ase.neb import NEB
except ImportError:
    try:
        from ase.mep import NEB
    except ImportError:
        from ase.mep.neb import NEB

from ase.optimize import BFGS

# ==================== 终端美化工具 ====================
class Colors:
    """ANSI 颜色代码"""
    RESET = '\033[0m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    UNDERLINE = '\033[4m'

    BLACK = '\033[30m'
    RED = '\033[31m'
    GREEN = '\033[32m'
    YELLOW = '\033[33m'
    BLUE = '\033[34m'
    MAGENTA = '\033[35m'
    CYAN = '\033[36m'
    WHITE = '\033[37m'

    BRIGHT_BLACK = '\033[90m'
    BRIGHT_RED = '\033[91m'
    BRIGHT_GREEN = '\033[92m'
    BRIGHT_YELLOW = '\033[93m'
    BRIGHT_BLUE = '\033[94m'
    BRIGHT_MAGENTA = '\033[95m'
    BRIGHT_CYAN = '\033[96m'
    BRIGHT_WHITE = '\033[97m'


class BoxStyle:
    """盒子绘制字符"""
    HORIZONTAL = '='
    VERTICAL = '|'
    TOP_LEFT = '+'
    TOP_RIGHT = '+'
    BOTTOM_LEFT = '+'
    BOTTOM_RIGHT = '+'
    T_LEFT = '+'
    T_RIGHT = '+'
    HORIZONTAL_DOWN = '='
    HORIZONTAL_UP = '='


def print_banner():
    """打印程序横幅"""
    print(f"{Colors.CYAN}{Colors.BOLD}")
    print(r"  _____ _   _  ____   _   _ ____  _____")
    print(r" / ____| |_| |/ ___| | \ | |  _ \| ____|")
    print(r"| |     | '_  | |  _  |  \| | | | |  _|  ")
    print(r"| |___  | | | | |_| | | |\  | |_| | |___ ")
    print(r" \____|_| |_|\____| |_| \_|____/|_____|")
    print()
    print(f"{Colors.BRIGHT_GREEN}       过渡态计算 (Nudged Elastic Band){Colors.RESET}")
    print(f"{Colors.BRIGHT_BLACK}              Powered by CHGNet{Colors.RESET}")
    print(f"{Colors.CYAN}======================================================================{Colors.RESET}")


def print_box(title, content, width=80, color=Colors.CYAN):
    """打印带边框的盒子"""
    print(f"{color}{BoxStyle.TOP_LEFT}{BoxStyle.HORIZONTAL * (width-2)}{BoxStyle.TOP_RIGHT}{Colors.RESET}")
    print(f"{color}{BoxStyle.VERTICAL}{Colors.BOLD}{Colors.BRIGHT_WHITE} {title:<{width-4}} {Colors.RESET}{color}{BoxStyle.VERTICAL}{Colors.RESET}")
    print(f"{color}{BoxStyle.T_LEFT}{BoxStyle.HORIZONTAL * (width-2)}{BoxStyle.T_RIGHT}{Colors.RESET}")
    for line in content.split('\n'):
        print(f"{color}{BoxStyle.VERTICAL}{Colors.RESET} {line:<{width-4}} {color}{BoxStyle.VERTICAL}{Colors.RESET}")
    print(f"{color}{BoxStyle.BOTTOM_LEFT}{BoxStyle.HORIZONTAL * (width-2)}{BoxStyle.BOTTOM_RIGHT}{Colors.RESET}")


def print_section(title):
    """打印章节标题"""
    print(f"\n{Colors.BOLD}{Colors.BRIGHT_CYAN}► {title}{Colors.RESET}")
    print(f"{Colors.DIM}{'─' * 80}{Colors.RESET}")


def print_success(message):
    """打印成功消息"""
    print(f"{Colors.BRIGHT_GREEN}✓ {message}{Colors.RESET}")


def print_error(message):
    """打印错误消息"""
    print(f"{Colors.BRIGHT_RED}✗ {message}{Colors.RESET}")


def print_info(message):
    """打印信息消息"""
    print(f"{Colors.BRIGHT_BLUE}ℹ {message}{Colors.RESET}")


def print_warning(message):
    """打印警告消息"""
    print(f"{Colors.BRIGHT_YELLOW}⚠ {message}{Colors.RESET}")


# ==================== NEB 计算类 ====================
class CHGNetNEB:
    """CHGNet NEB 过渡态计算类"""

    def __init__(self, work_dir='.', fmax=0.05, max_steps=300,
                 spring_constant=0.1, climb=True, dry_run=False):
        work_dir_abs = os.path.abspath(work_dir)
        if not os.path.isdir(work_dir_abs):
            raise NotADirectoryError(f"工作目录不存在: {work_dir_abs}")

        self.original_dir = os.getcwd()
        os.chdir(work_dir_abs)
        self.work_dir = os.getcwd()

        self.fmax = fmax
        self.max_steps = max_steps
        self.spring_constant = spring_constant
        self.climb = climb
        self.dry_run = dry_run
        self.num_images = 0
        self.image_dirs = []
        self.images = []
        self.energies = []
        self.initial_lattice = None
        self.calc = None
        self.ts_index = None
        self.ts_energy = None
        self.is_file = None
        self.fs_file = None
        self.image_histories = []
        self.progress_step = 0

        print_info(f"工作目录: {self.work_dir}")

    def log(self, message):
        """记录日志信息（带时间戳）"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"{Colors.DIM}[{timestamp}]{Colors.RESET} {message}")

    def discover_image_directories(self):
        """扫描并校验数字图像目录"""
        try:
            print_section("扫描图像目录")

            numeric_dirs = []
            missing_poscar_dirs = []
            for entry in os.scandir('.'):
                if not entry.is_dir() or not entry.name.isdigit():
                    continue

                poscar_path = os.path.join(entry.name, 'POSCAR')
                if os.path.exists(poscar_path):
                    numeric_dirs.append((int(entry.name), entry.name))
                else:
                    missing_poscar_dirs.append(entry.name)

            if missing_poscar_dirs:
                missing_dirs = ', '.join(sorted(missing_poscar_dirs, key=int))
                raise FileNotFoundError(f"以下数字目录缺少 POSCAR: {missing_dirs}")

            if len(numeric_dirs) < 2:
                raise FileNotFoundError("至少需要两个数字目录，并在每个目录下提供 POSCAR")

            numeric_dirs.sort(key=lambda item: item[0])
            dir_numbers = [number for number, _ in numeric_dirs]
            expected_numbers = list(range(len(dir_numbers)))
            if dir_numbers != expected_numbers:
                actual_dirs = ', '.join(name for _, name in numeric_dirs)
                raise ValueError(
                    "图像目录必须从 00 开始连续编号，例如 00, 01, 02 ...；"
                    f"当前检测到: {actual_dirs}"
                )

            self.image_dirs = [name for _, name in numeric_dirs]
            self.num_images = len(self.image_dirs) - 2
            self.is_file = os.path.join(self.image_dirs[0], 'POSCAR')
            self.fs_file = os.path.join(self.image_dirs[-1], 'POSCAR')

            path_lines = [
                "",
                f"{Colors.BRIGHT_GREEN}目录驱动路径:{Colors.RESET}",
                f"  工作目录: {self.work_dir}",
                f"  图像目录数: {len(self.image_dirs)}",
                f"  中间图像数: {self.num_images}",
                f"  初态: {self.is_file}",
                f"  末态: {self.fs_file}",
                f"  目录序列: {' -> '.join(self.image_dirs)}",
            ]
            print_box("路径信息", '\n'.join(path_lines), color=Colors.BLUE)
            return self.image_dirs

        except Exception as e:
            print_error(f"扫描图像目录时出错: {str(e)}")
            raise

    def load_structures(self):
        """从数字目录加载初态和末态结构"""
        try:
            self.discover_image_directories()
            print_section("加载结构")

            self.log(f"{Colors.CYAN}正在读取初态结构:{Colors.RESET} {self.is_file}")
            is_structure = Structure.from_file(self.is_file, False)

            self.log(f"{Colors.CYAN}正在读取末态结构:{Colors.RESET} {self.fs_file}")
            fs_structure = Structure.from_file(self.fs_file, False)

            self.initial_lattice = is_structure.lattice.matrix.copy()

            if len(is_structure) != len(fs_structure):
                raise ValueError(f"初态和末态原子数不一致: {len(is_structure)} vs {len(fs_structure)}")

            is_species = [str(site.specie) for site in is_structure]
            fs_species = [str(site.specie) for site in fs_structure]
            if is_species != fs_species:
                raise ValueError("初态和末态的原子种类或顺序不一致")

            info_lines = [
                "",
                f"{Colors.BRIGHT_GREEN}初态 ({self.image_dirs[0]}):{Colors.RESET}",
                f"  化学式: {is_structure.composition.reduced_formula}",
                f"  原子数: {len(is_structure)}",
                "",
                f"{Colors.BRIGHT_GREEN}末态 ({self.image_dirs[-1]}):{Colors.RESET}",
                f"  化学式: {fs_structure.composition.reduced_formula}",
                f"  原子数: {len(fs_structure)}",
                "",
                f"{Colors.BOLD}晶格参数:{Colors.RESET}",
                f"  a     = {is_structure.lattice.a:>12.6f} Å",
                f"  b     = {is_structure.lattice.b:>12.6f} Å",
                f"  c     = {is_structure.lattice.c:>12.6f} Å",
                f"  α     = {is_structure.lattice.alpha:>12.6f}°",
                f"  β     = {is_structure.lattice.beta:>12.6f}°",
                f"  γ     = {is_structure.lattice.gamma:>12.6f}°",
                f"  体积  = {is_structure.lattice.volume:>12.6f} Å³",
            ]

            print_box("结构信息", '\n'.join(info_lines), color=Colors.BLUE)
            return is_structure, fs_structure

        except Exception as e:
            print_error(f"读取结构文件时出错: {str(e)}")
            raise

    def _update_neb_state(self, images):
        """更新当前 NEB 能量状态"""
        self.energies = [float(image.get_potential_energy()) for image in images]
        self.ts_index = int(np.argmax(self.energies))
        self.ts_energy = self.energies[self.ts_index]
        rel_energies = np.array(self.energies) - self.energies[0]
        return {
            'energies': self.energies,
            'rel_energies': rel_energies,
            'ts_index': self.ts_index,
            'ts_energy': self.ts_energy,
            'forward_barrier': float(rel_energies[self.ts_index]),
            'reverse_barrier': float(rel_energies[self.ts_index] - rel_energies[-1]),
            'reaction_energy': float(rel_energies[-1]),
        }

    def _calculate_max_force(self, images):
        """计算当前所有图像中的最大原子受力"""
        max_force = 0.0
        for image in images:
            forces = image.get_forces()
            if len(forces) == 0:
                continue
            image_max_force = float(np.max(np.linalg.norm(forces, axis=1)))
            max_force = max(max_force, image_max_force)
        return max_force

    def _append_neb_oszicar(self, image_dir, step, energy, relative_energy, max_force):
        """追加写入 NEB 过程中的 OSZICAR"""
        oszicar_path = os.path.join(image_dir, 'OSZICAR')
        file_exists = os.path.exists(oszicar_path)
        with open(oszicar_path, 'a', encoding='utf-8') as f:
            if not file_exists or os.path.getsize(oszicar_path) == 0:
                f.write("NEB optimization history\n")
            f_str = self._format_vasp_energy(energy)
            f.write(
                f"{step:4d} F= {f_str} E0= {f_str}  relE= {relative_energy:+.8f}  maxF= {max_force:.6f}\n"
            )

    def _write_results_file(self, result_file, state, final=False, step=None, max_force=None):
        """写入结果文件"""
        with open(result_file, 'w', encoding='utf-8') as f:
            f.write("=" * 70 + "\n")
            if final:
                f.write("                    CHGNet NEB Calculation Results\n")
            else:
                f.write("                     CHGNet NEB Progress Snapshot\n")
            f.write("=" * 70 + "\n\n")

            f.write("Calculation Parameters:\n")
            f.write("-" * 70 + "\n")
            f.write(f"  Work Directory:    {self.work_dir}\n")
            f.write(f"  Initial State:     {self.is_file}\n")
            f.write(f"  Final State:       {self.fs_file}\n")
            f.write(f"  Number of Images:  {self.num_images}\n")
            f.write(f"  Spring Constant:   {self.spring_constant} eV/Å²\n")
            f.write(f"  Climbing Image:    {self.climb}\n")
            f.write(f"  Convergence:       {self.fmax} eV/Å\n")
            f.write(f"  Max Steps:         {self.max_steps}\n")
            if step is not None:
                f.write(f"  Current Step:      {step}\n")
            if max_force is not None:
                f.write(f"  Current Max Force: {max_force:.6f} eV/Å\n")
            f.write("\n")

            f.write("=" * 70 + "\n")
            f.write("Absolute Energy Profile (eV)\n")
            f.write("=" * 70 + "\n")
            f.write(f"{'Image':>10} {'Energy (eV)':>20} {'Rel. Energy (eV)':>20} {'Mark':>10}\n")
            f.write("-" * 70 + "\n")

            for i, (image_dir, energy) in enumerate(zip(self.image_dirs, state['energies'])):
                marker = "TS" if i == state['ts_index'] else ""
                f.write(f"{image_dir:>10} {energy:>20.8f} {state['rel_energies'][i]:>20.4f} {marker:>10}\n")

            f.write("\n")
            f.write("=" * 70 + "\n")
            f.write("Barrier Analysis\n")
            f.write("=" * 70 + "\n")
            f.write(f"  Forward Barrier (IS -> TS):  {state['forward_barrier']:>12.4f} eV\n")
            f.write(f"  Reverse Barrier (FS -> TS):  {state['reverse_barrier']:>12.4f} eV\n")
            f.write(f"  Reaction Energy (FS - IS):   {state['reaction_energy']:>12.4f} eV\n")
            f.write("-" * 70 + "\n")
            if state['reaction_energy'] > 0:
                f.write(f"  Reaction Type: Endothermic (+{state['reaction_energy']:.4f} eV)\n")
            else:
                f.write(f"  Reaction Type: Exothermic ({state['reaction_energy']:.4f} eV)\n")
            f.write("=" * 70 + "\n")

            f.write("\n")
            f.write("=" * 70 + "\n")
            f.write(f"Transition State Information ({self.image_dirs[state['ts_index']]})\n")
            f.write("=" * 70 + "\n")
            f.write(f"  Absolute Energy: {state['ts_energy']:.8f} eV\n")
            f.write(f"  Relative Energy: {state['rel_energies'][state['ts_index']]:.4f} eV\n")
            f.write("=" * 70 + "\n")

            if final:
                f.write("\n")
                f.write("=" * 70 + "\n")
                f.write("Generated Files\n")
                f.write("=" * 70 + "\n")
                f.write("  NEB_RESULTS          - This file\n")
                f.write("  neb_profile.png      - Energy profile plot\n")
                f.write("  neb_initial.traj     - Initial path trajectory\n")
                f.write("  neb_initial.xtd      - Initial path (XTD format)\n")
                f.write("  neb_final.traj       - Converged path trajectory\n")
                f.write("  neb_final.xtd        - Converged path (XTD format)\n")
                f.write("  neb.traj             - ASE optimizer trajectory\n")
                for image_dir in self.image_dirs:
                    f.write(f"  {image_dir}/\n")
                    f.write(f"    ├── POSCAR         - Input structure\n")
                    f.write(f"    ├── CONTCAR        - Latest optimized structure\n")
                    f.write(f"    ├── XDATCAR        - Step-by-step trajectory\n")
                    f.write(f"    ├── OSZICAR        - Step-by-step energy record\n")
                    f.write(f"    └── OUTCAR         - Latest force snapshot\n")
                f.write("=" * 70 + "\n")

    def _record_neb_progress(self, images, step):
        """保存并展示 NEB 当前步结果"""
        state = self._update_neb_state(images)
        max_force = self._calculate_max_force(images)

        for i, (image_dir, image) in enumerate(zip(self.image_dirs, images)):
            write(os.path.join(image_dir, 'CONTCAR'), image, format='vasp')
            self._append_neb_oszicar(image_dir, step, state['energies'][i], state['rel_energies'][i], max_force)
            self._write_outcar(
                image_dir,
                image,
                state['energies'][i],
                image.get_forces(),
                step=step,
                relative_energy=state['rel_energies'][i],
                max_force=max_force,
            )
            self.image_histories[i].append(image.copy())
            self._write_xdatcar(image_dir, self.image_histories[i])

        self._write_results_file('NEB_RESULTS', state, final=False, step=step, max_force=max_force)

        progress_lines = [
            "",
            f"当前最大力: {max_force:.6f} eV/Å",
            f"当前过渡态: {self.image_dirs[state['ts_index']]}",
            f"正向能垒 (IS → TS): {state['forward_barrier']:.4f} eV",
            f"反向能垒 (FS → TS): {state['reverse_barrier']:.4f} eV",
            f"反应热   (FS - IS): {state['reaction_energy']:.4f} eV",
            "",
            f"{Colors.BRIGHT_GREEN}各图像相对能量:{Colors.RESET}",
        ]
        for i, rel_energy in enumerate(state['rel_energies']):
            marker = " ★ TS" if i == state['ts_index'] else ""
            progress_lines.append(f"  {self.image_dirs[i]}: {rel_energy:10.4f} eV{marker}")

        title = "NEB 初始状态" if step == 0 else f"NEB 第 {step:03d} 步"
        print_box(title, '\n'.join(progress_lines), color=Colors.YELLOW)
        return state

    def setup_calculator(self):
        """设置CHGNet模型（只加载一次，后续为每个image创建独立calculator）"""
        try:
            print_info("初始化 CHGNet 模型 (CPU模式)...")
            print_info("(模型只加载一次，避免内存爆炸)")

            # 加载CHGNet模型，使用CPU - 只加载一次！
            self.chgnet_model = CHGNet.load()

            print_success("CHGNet 模型加载完成")

        except Exception as e:
            print_error(f"初始化模型时出错: {str(e)}")
            raise

    def create_calculator(self):
        """为单个image创建calculator（共享同一个CHGNet模型）"""
        return CHGNetCalculator(
            potential=self.chgnet_model,  # 共享模型
            compute_stress=False,
            compute_hessian=False,
        )

    def run_single_point(self, image_dir):
        """对单个image运行单点能计算（使用共享模型创建独立calculator）"""
        try:
            poscar_path = os.path.join(image_dir, 'POSCAR')
            if not os.path.exists(poscar_path):
                raise FileNotFoundError(f"{poscar_path} 不存在")

            # 读取结构，创建独立calculator（共享CHGNet模型）
            atoms = read(poscar_path, format='vasp')
            atoms.calc = self.create_calculator()  # 每个image有自己的calculator

            # 计算能量和力
            energy = atoms.get_potential_energy()
            forces = atoms.get_forces()
            max_force = np.max(np.linalg.norm(forces, axis=1))

            # 保存CONTCAR（单点计算，结构不变）
            write(os.path.join(image_dir, 'CONTCAR'), atoms, format='vasp')

            # 生成OSZICAR
            self._write_oszicar(image_dir, energy, 1)

            # 生成简单的OUTCAR
            self._write_outcar(image_dir, atoms, energy, forces)

            return energy, max_force

        except Exception as e:
            print_error(f"单点计算出错 ({image_dir}): {str(e)}")
            raise

    def _write_oszicar(self, image_dir, energy, step):
        """写入OSZICAR文件（用于单点计算）"""
        oszicar_path = os.path.join(image_dir, 'OSZICAR')
        with open(oszicar_path, 'w') as f:
            f_str = self._format_vasp_energy(energy)
            line = f"{step:4d} F= {f_str} E0= {f_str}  d E = .00000000E+00\n"
            f.write(line)

    def _write_oszicar_simple(self, image_dir, energy):
        """写入简化的OSZICAR文件（用于NEB计算后）"""
        oszicar_path = os.path.join(image_dir, 'OSZICAR')
        with open(oszicar_path, 'w') as f:
            f_str = self._format_vasp_energy(energy)
            f.write("NEB optimization completed\n")
            f.write(f"  1 F= {f_str} E0= {f_str}  d E = .00000000E+00\n")

    def _format_vasp_energy(self, energy):
        """格式化能量为 VASP 格式"""
        import math

        if energy == 0:
            return ".00000000E+00"

        sign = '-' if energy < 0 else ''
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

    def _write_outcar(self, image_dir, atoms, energy, forces, step=None, relative_energy=None, max_force=None):
        """写入简化版OUTCAR文件"""
        outcar_path = os.path.join(image_dir, 'OUTCAR')
        with open(outcar_path, 'w', encoding='utf-8') as f:
            if step is None:
                f.write("CHGNet NEB Single Point Calculation\n")
            else:
                f.write("CHGNet NEB Progress Snapshot\n")
                f.write(f"Step: {step}\n")
                if relative_energy is not None:
                    f.write(f"Relative Energy: {relative_energy:.8f} eV\n")
                if max_force is not None:
                    f.write(f"Current Max Force: {max_force:.8f} eV/Angst\n")
            f.write("====================================\n\n")
            f.write(f"Total Energy: {energy:.8f} eV\n\n")
            f.write("POSITION                                       TOTAL-FORCE (eV/Angst)\n")
            f.write("-----------------------------------------------------------------------------------\n")
            positions = atoms.get_positions()
            for pos, force in zip(positions, forces):
                f.write(f" {pos[0]:10.6f} {pos[1]:10.6f} {pos[2]:10.6f}   {force[0]:11.6f} {force[1]:11.6f} {force[2]:11.6f}\n")

    def _write_xdatcar(self, image_dir, images_list):
        """写入XDATCAR文件"""
        try:
            xdatcar_path = os.path.join(image_dir, 'XDATCAR')
            atoms = images_list[0] if isinstance(images_list, list) else images_list

            symbols = atoms.get_chemical_symbols()
            unique_elements = []
            element_counts = []
            current_element = symbols[0]
            count = 1
            for e in symbols[1:]:
                if e == current_element:
                    count += 1
                else:
                    unique_elements.append(current_element)
                    element_counts.append(count)
                    current_element = e
                    count = 1
            unique_elements.append(current_element)
            element_counts.append(count)

            with open(xdatcar_path, 'w') as f:
                f.write("Generated by CHGNet NEB\n")
                f.write("1.0\n")

                cell = atoms.get_cell()
                for j in range(3):
                    f.write(f"  {cell[j][0]:.10f}  {cell[j][1]:.10f}  {cell[j][2]:.10f}\n")

                f.write("  " + "  ".join(unique_elements) + "\n")
                f.write("  " + "  ".join(map(str, element_counts)) + "\n")

                if isinstance(images_list, list):
                    for i, img in enumerate(images_list):
                        f.write("Direct configuration=  %6d\n" % (i + 1))
                        positions = img.get_scaled_positions()
                        for pos in positions:
                            f.write(f"  {pos[0]:.10f}  {pos[1]:.10f}  {pos[2]:.10f}\n")
                else:
                    f.write("Direct configuration=      1\n")
                    positions = atoms.get_scaled_positions()
                    for pos in positions:
                        f.write(f"  {pos[0]:.10f}  {pos[1]:.10f}  {pos[2]:.10f}\n")

        except Exception as e:
            print_warning(f"写入XDATCAR时出错: {e}")

    def relax_endpoints(self):
        """对始末态进行单点能计算"""
        try:
            print_section("始末态单点计算")

            initial_dir = self.image_dirs[0]
            final_dir = self.image_dirs[-1]

            print_info(f"计算初态 ({initial_dir})...")
            is_energy, is_force = self.run_single_point(initial_dir)
            print_success(f"初态能量: {is_energy:.6f} eV, 最大力: {is_force:.6f} eV/Å")

            print_info(f"计算末态 ({final_dir})...")
            fs_energy, fs_force = self.run_single_point(final_dir)
            print_success(f"末态能量: {fs_energy:.6f} eV, 最大力: {fs_force:.6f} eV/Å")

            reaction_energy = fs_energy - is_energy
            if reaction_energy > 0:
                print_info(f"反应吸热: {reaction_energy:.4f} eV")
            else:
                print_info(f"反应放热: {abs(reaction_energy):.4f} eV")

            return is_energy, fs_energy

        except Exception as e:
            print_error(f"始末态计算出错: {str(e)}")
            raise

    def run_neb_calculation(self):
        """运行NEB计算"""
        try:
            print_section("NEB 计算")

            images = []
            print_info(f"加载 {len(self.image_dirs)} 个图像结构...")
            for image_dir in self.image_dirs:
                poscar_path = os.path.join(image_dir, 'POSCAR')
                atoms = read(poscar_path, format='vasp')
                atoms.calc = self.create_calculator()
                images.append(atoms)
            self.images = images
            self.image_histories = [[] for _ in self.image_dirs]
            print_success(f"已加载 {len(images)} 个图像，每个图像有独立的calculator（共享CHGNet模型）")

            neb = NEB(images, k=self.spring_constant, climb=self.climb, method='aseneb')

            print_info("NEB 参数:")
            print_info(f"  图像数: {self.num_images}")
            print_info(f"  图像目录: {' -> '.join(self.image_dirs)}")
            print_info(f"  弹簧常数: {self.spring_constant}")
            print_info(f"  Climbing: {self.climb}")
            print_info(f"  收敛标准: {self.fmax} eV/Å")
            print_info(f"  最大步数: {self.max_steps}")

            optimizer = BFGS(neb, trajectory='neb.traj', logfile=None)

            print_info("开始NEB优化...")
            print_info("每一步都会刷新终端能垒、写入各目录下的 CONTCAR / XDATCAR / OSZICAR / OUTCAR")

            self.progress_step = 0
            self._record_neb_progress(images, self.progress_step)

            def progress_callback():
                current_step = getattr(optimizer, 'nsteps', self.progress_step)
                if current_step <= self.progress_step:
                    return
                self.progress_step = current_step
                self._record_neb_progress(images, self.progress_step)

            optimizer.attach(progress_callback, interval=1)
            optimizer.run(fmax=self.fmax, steps=self.max_steps)

            print_success("NEB 优化完成!")
            final_state = self._update_neb_state(images)
            self._write_results_file('NEB_RESULTS', final_state, final=True, step=self.progress_step)
            return self.energies

        except Exception as e:
            print_error(f"NEB计算出错: {str(e)}")
            raise

    def plot_neb_profile(self):
        """绘制NEB能量剖面图"""
        try:
            print_section("绘制能量剖面")

            if not self.energies:
                print_error("没有能量数据可供绘图")
                return

            # 相对能量（以初态为参考）
            rel_energies = np.array(self.energies) - self.energies[0]

            # 创建图形
            fig, ax = plt.subplots(figsize=(10, 6))

            # 绘制能量剖面
            x = np.arange(len(rel_energies))
            ax.plot(x, rel_energies, 'o-', linewidth=2, markersize=8, color='blue')

            # 标记过渡态
            if self.ts_index is not None:
                ax.plot(self.ts_index, rel_energies[self.ts_index],
                       'r*', markersize=20, label=f'TS ({self.image_dirs[self.ts_index]})')

            ax.set_xlabel('Image Index', fontsize=12)
            ax.set_ylabel('Relative Energy (eV)', fontsize=12)
            ax.set_title('NEB Energy Profile', fontsize=14, fontweight='bold')
            ax.grid(True, alpha=0.3)
            ax.legend()

            # 保存图片
            plt.tight_layout()
            plt.savefig('neb_profile.png', dpi=150)
            print_success("能量剖面图已保存到 neb_profile.png")
            print_info("请查看 neb_profile.png 文件")

            # 显示结果 (使用eV单位)
            barrier_lines = [
                f"",
                f"{Colors.BRIGHT_GREEN}能垒信息:{Colors.RESET}",
                f"  正向能垒 (IS → TS): {rel_energies[self.ts_index]:.4f} eV",
                f"  反向能垒 (FS → TS): {(rel_energies[self.ts_index] - rel_energies[-1]):.4f} eV",
                f"  反应热 (FS - IS):   {rel_energies[-1]:.4f} eV",
                f"",
                f"{Colors.BRIGHT_GREEN}各图像能量:{Colors.RESET}",
            ]

            for i, e in enumerate(rel_energies):
                marker = " ★ TS" if i == self.ts_index else ""
                barrier_lines.append(f"  {self.image_dirs[i]}: {e:10.4f} eV{marker}")

            print_box("NEB 结果", '\n'.join(barrier_lines), color=Colors.GREEN)

        except Exception as e:
            print_error(f"绘图时出错: {str(e)}")

    def save_trajectories(self):
        """保存初始和收敛后的轨迹"""
        try:
            print_section("保存轨迹")

            initial_traj = []
            for image_dir in self.image_dirs:
                poscar_path = os.path.join(image_dir, 'POSCAR')
                if os.path.exists(poscar_path):
                    atoms = read(poscar_path, format='vasp')
                    initial_traj.append(atoms)

            if initial_traj:
                write('neb_initial.traj', initial_traj, format='traj')
                write('neb_initial.xtd', initial_traj, format='xtd')
                print_success(f"初始轨迹已保存: neb_initial.traj, neb_initial.xtd ({len(initial_traj)} frames)")

            final_traj = []
            for image_dir in self.image_dirs:
                contcar_path = os.path.join(image_dir, 'CONTCAR')
                poscar_path = os.path.join(image_dir, 'POSCAR')
                if os.path.exists(contcar_path):
                    atoms = read(contcar_path, format='vasp')
                    final_traj.append(atoms)
                elif os.path.exists(poscar_path):
                    atoms = read(poscar_path, format='vasp')
                    final_traj.append(atoms)

            if final_traj:
                write('neb_final.traj', final_traj, format='traj')
                write('neb_final.xtd', final_traj, format='xtd')
                print_success(f"收敛轨迹已保存: neb_final.traj, neb_final.xtd ({len(final_traj)} frames)")

            if os.path.exists('neb.traj'):
                try:
                    neb_traj = Trajectory('neb.traj')
                    write('neb_optimization.xtd', [atoms for atoms in neb_traj], format='xtd')
                    print_success("优化轨迹已保存: neb_optimization.xtd")
                except Exception as e:
                    print_warning(f"无法保存优化轨迹: {e}")

        except Exception as e:
            print_error(f"保存轨迹时出错: {str(e)}")

    def save_results(self):
        """保存最终计算结果到文件"""
        try:
            state = self._update_neb_state(self.images)
            self._write_results_file('NEB_RESULTS', state, final=True, step=self.progress_step)
            print_success("详细结果已保存到 NEB_RESULTS")

        except Exception as e:
            print_error(f"保存结果时出错: {str(e)}")

    def run(self):
        """执行完整NEB流程"""
        try:
            is_structure, fs_structure = self.load_structures()

            if self.dry_run:
                print_section("Dry Run 完成")
                print_info("已完成数字目录扫描与结构校验")
                print_info("未加载 CHGNet，未执行单点计算或 NEB 优化")
                os.chdir(self.original_dir)
                return True

            self.setup_calculator()
            self.relax_endpoints()
            self.run_neb_calculation()
            self.plot_neb_profile()
            self.save_trajectories()
            self.save_results()

            print()

            rel_energies = np.array(self.energies) - self.energies[0]
            completion_content = (
                f"\n{Colors.BRIGHT_GREEN}{Colors.BOLD}NEB计算成功完成!{Colors.RESET}\n\n"
                f"{Colors.CYAN}能垒信息:{Colors.RESET}\n"
                f"  正向能垒 (IS → TS): {rel_energies[self.ts_index]:>10.4f} eV\n"
                f"  反向能垒 (FS → TS): {(rel_energies[self.ts_index] - rel_energies[-1]):>10.4f} eV\n"
                f"  反应热 (FS - IS):   {rel_energies[-1]:>10.4f} eV\n"
                f"\n{Colors.CYAN}过渡态位置:{Colors.RESET} {self.image_dirs[self.ts_index]}\n"
                f"\n{Colors.CYAN}输出文件:{Colors.RESET}\n"
                f"  • NEB_RESULTS        - 实时/最终结果汇总\n"
                f"  • neb_profile.png    - 能量剖面图\n"
                f"  • neb_initial.traj   - 初始轨迹\n"
                f"  • neb_initial.xtd    - 初始轨迹(XTD格式)\n"
                f"  • neb_final.traj     - 收敛轨迹\n"
                f"  • neb_final.xtd      - 收敛轨迹(XTD格式)\n"
                f"  • neb.traj           - ASE 优化轨迹\n"
                f"\n{Colors.CYAN}文件夹结构:{Colors.RESET}\n"
                f"  • {self.image_dirs[0]}/                - 初态 (IS)\n"
            )

            for i, image_dir in enumerate(self.image_dirs[1:-1], start=1):
                marker = " ★ TS" if i == self.ts_index else ""
                completion_content += f"  • {image_dir}/                - 插点 {i}{marker}\n"

            completion_content += (
                f"  • {self.image_dirs[-1]}/                - 末态 (FS)\n\n"
                f"{Colors.DIM}每个文件夹都会持续更新: POSCAR, CONTCAR, XDATCAR, OSZICAR, OUTCAR{Colors.RESET}\n"
                f"\n{Colors.BRIGHT_YELLOW}所有文件已保存到: {self.work_dir}{Colors.RESET}\n"
            )

            print_box("任务完成", completion_content, color=Colors.GREEN)
            os.chdir(self.original_dir)
            return True

        except Exception as e:
            print_error(f"程序执行出错: {str(e)}")
            import traceback
            traceback.print_exc()
            os.chdir(self.original_dir)
            return False


def suppress_all_warnings():
    """抑制警告"""
    warnings.filterwarnings('ignore', category=RuntimeWarning)
    warnings.filterwarnings('ignore', category=UserWarning, module='pymatgen')
    warnings.filterwarnings('ignore', category=UserWarning, module='chgnet')
    warnings.filterwarnings('ignore', category=RuntimeWarning, module='ase')
    warnings.filterwarnings('ignore', category=FutureWarning, module='ase')


def parse_bool(value):
    """解析布尔参数"""
    if isinstance(value, bool):
        return value

    normalized = value.strip().lower()
    if normalized in {"true", "1", "yes", "y"}:
        return True
    if normalized in {"false", "0", "no", "n"}:
        return False
    raise argparse.ArgumentTypeError("布尔参数必须为 True/False")


def positive_int(value):
    """校验正整数参数"""
    int_value = int(value)
    if int_value <= 0:
        raise argparse.ArgumentTypeError("参数必须为正整数")
    return int_value


def positive_float(value):
    """校验正浮点数参数"""
    float_value = float(value)
    if float_value <= 0:
        raise argparse.ArgumentTypeError("参数必须为正数")
    return float_value


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description="读取数字目录中的 POSCAR 并使用 CHGNet 进行 NEB 迁移能垒计算"
    )
    parser.add_argument(
        "--work-dir",
        "--work_dir",
        dest="work_dir",
        default=".",
        help="包含 00/01/02... 图像目录的工作目录 (默认: 当前目录)",
    )
    parser.add_argument(
        "--fmax",
        type=positive_float,
        default=0.05,
        help="力收敛阈值，单位 eV/A (默认: 0.05)",
    )
    parser.add_argument(
        "--max-steps",
        "--max_steps",
        dest="max_steps",
        type=positive_int,
        default=300,
        help="最大优化步数 (默认: 300)",
    )
    parser.add_argument(
        "--spring-constant",
        "--spring_constant",
        dest="spring_constant",
        type=positive_float,
        default=0.1,
        help="NEB 弹簧常数 (默认: 0.1)",
    )
    parser.add_argument(
        "--climb",
        type=parse_bool,
        default=True,
        help="是否启用 climbing image，True/False (默认: True)",
    )
    parser.add_argument(
        "--dry-run",
        "--dry_run",
        dest="dry_run",
        type=parse_bool,
        default=False,
        help="True 时只扫描数字目录并校验结构，不执行后续计算 (默认: False)",
    )
    return parser.parse_args()


def main():
    """主函数"""
    suppress_all_warnings()
    print_banner()

    try:
        args = parse_args()

        neb_calculator = CHGNetNEB(
            work_dir=args.work_dir,
            fmax=args.fmax,
            max_steps=args.max_steps,
            spring_constant=args.spring_constant,
            climb=args.climb,
            dry_run=args.dry_run,
        )
        success = neb_calculator.run()
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
