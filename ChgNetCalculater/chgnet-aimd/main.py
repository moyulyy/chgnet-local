#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CHGNet AIMD 分子动力学模拟程序 - CLI 版本
功能：读取 POSCAR 文件，使用 CHGNet 进行分子动力学模拟
"""

import argparse
import os
import sys
import warnings
from datetime import datetime

import numpy as np
from ase.io.trajectory import Trajectory
from chgnet.model.dynamics import MolecularDynamics
from chgnet.model.model import CHGNet
from pymatgen.core import Structure
from pymatgen.io.vasp import Poscar


# ==================== 终端美化工具 ====================
class Colors:
    """ANSI 颜色代码"""
    RESET = '\033[0m'
    BOLD = '\033[1m'
    DIM = '\033[2m'

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


def print_banner():
    """打印程序横幅"""
    print(f"{Colors.BRIGHT_BLUE}{Colors.BOLD}")
    print("   ____ _   _  ____   _____     _   _ _______   ____  _____ _   _")
    print("  / ____| |_| |/ ___| | ____|   | | | |__   __| / ___|| ____| \\ | |")
    print(" | |     | '_  | |  _  |  _|     | | | |  | |    | |  _|  _| |  \\| |")
    print(" | |___  | | | | |_| | | |___    | | | |  | |    | |_| | |___| |\\  |")
    print("  \\____|_| |_|\\____| |_____|    |_| |_|  |_|     \\____|_____|_| \\_|")
    print()
    print(f"{Colors.BRIGHT_CYAN}              分子动力学模拟  (Ab Initio Molecular Dynamics){Colors.RESET}")
    print(f"{Colors.BRIGHT_BLACK}                        Powered by CHGNet{Colors.RESET}")
    print(f"{Colors.BLUE}======================================================================{Colors.RESET}")


def print_box(title, content, width=80, color=Colors.BLUE):
    """打印带边框的盒子"""
    print(f"{color}{BoxStyle.TOP_LEFT}{BoxStyle.HORIZONTAL * (width-2)}{BoxStyle.TOP_RIGHT}{Colors.RESET}")
    print(f"{color}{BoxStyle.VERTICAL}{Colors.BOLD}{Colors.BRIGHT_WHITE} {title:<{width-4}} {Colors.RESET}{color}{BoxStyle.VERTICAL}{Colors.RESET}")
    print(f"{color}{BoxStyle.T_LEFT}{BoxStyle.HORIZONTAL * (width-2)}{BoxStyle.T_RIGHT}{Colors.RESET}")
    for line in content.split('\n'):
        print(f"{color}{BoxStyle.VERTICAL}{Colors.RESET} {line:<{width-4}} {color}{BoxStyle.VERTICAL}{Colors.RESET}")
    print(f"{color}{BoxStyle.BOTTOM_LEFT}{BoxStyle.HORIZONTAL * (width-2)}{BoxStyle.BOTTOM_RIGHT}{Colors.RESET}")


def print_section(title):
    """打印章节标题"""
    print(f"\n{Colors.BOLD}{Colors.BRIGHT_BLUE}► {title}{Colors.RESET}")
    print(f"{Colors.DIM}{'─' * 80}{Colors.RESET}")


def print_success(message):
    print(f"{Colors.BRIGHT_GREEN}✓ {message}{Colors.RESET}")


def print_error(message):
    print(f"{Colors.BRIGHT_RED}✗ {message}{Colors.RESET}")


def print_info(message):
    print(f"{Colors.BRIGHT_CYAN}ℹ {message}{Colors.RESET}")


def print_warning(message):
    print(f"{Colors.BRIGHT_YELLOW}⚠ {message}{Colors.RESET}")


# ==================== 输出记录器 ====================
class OutputLogger:
    """输出记录器：将标准输出同时写入控制台和文件"""

    def __init__(self, filename):
        self.filename = filename
        self.terminal = sys.stdout
        self.log_file = None
        self.indent = " " * 23

    def __enter__(self):
        self.log_file = open(self.filename, 'w', encoding='utf-8')
        sys.stdout = self
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        sys.stdout = self.terminal
        if self.log_file:
            self.log_file.close()

    def write(self, message):
        self.terminal.write(message)
        if self.log_file and message:
            lines = message.split('\n')
            formatted_lines = []
            for line in lines:
                is_force_line = (
                    'POSITION' in line or
                    'TOTAL-FORCE' in line or
                    'total drift' in line or
                    line.strip().startswith('-') or
                    (len(line.strip().split()) >= 6 and all(part.replace('.', '').replace('-', '').isdigit() for part in line.strip().split()[:6]))
                )
                if line and not line.startswith('[') and not is_force_line:
                    formatted_lines.append(self.indent + line)
                else:
                    formatted_lines.append(line)
            formatted_message = '\n'.join(formatted_lines)
            self.log_file.write(formatted_message)
            self.log_file.flush()

    def flush(self):
        self.terminal.flush()
        if self.log_file:
            self.log_file.flush()


# ==================== 参数处理 ====================
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
        description="CHGNet AIMD 分子动力学模拟程序",
        add_help=False,
    )
    parser.add_argument(
        "--input",
        dest="input_file",
        default="POSCAR",
        help="输入结构文件路径 (默认: POSCAR)",
    )
    parser.add_argument(
        "--output",
        dest="output_file",
        default="CONTCAR",
        help="最终结构输出文件名 (默认: CONTCAR)",
    )
    parser.add_argument(
        "--temperature",
        type=positive_float,
        default=300.0,
        help="温度，单位 K (默认: 300.0)",
    )
    parser.add_argument(
        "--timestep",
        type=positive_float,
        default=1.0,
        help="时间步长，单位 fs (默认: 1.0)",
    )
    parser.add_argument(
        "--steps",
        type=positive_int,
        default=1000,
        help="总步数 (默认: 1000)",
    )
    parser.add_argument(
        "--loginterval",
        type=positive_int,
        default=1,
        help="日志间隔 (默认: 1)",
    )
    parser.add_argument(
        "--ensemble",
        default="nvt",
        help="分子动力学系综 (默认: nvt)",
    )
    parser.add_argument(
        "--thermostat",
        default="Nose-Hoover",
        help="恒温器类型 (默认: Nose-Hoover)",
    )
    return parser.parse_args()


# ==================== 主程序 ====================
class CHGNetAIMD:
    """CHGNet AIMD 模拟器类"""

    def __init__(self, input_file="POSCAR", output_structure="CONTCAR",
                 temperature=300, timestep=1.0, steps=1000, loginterval=1,
                 ensemble="nvt", thermostat="Nose-Hoover"):
        self.input_file = input_file
        self.work_dir = os.path.dirname(os.path.abspath(input_file)) or '.'
        self.output_structure = os.path.join(self.work_dir, output_structure)
        self.temperature = temperature
        self.timestep = timestep
        self.steps = steps
        self.loginterval = loginterval
        self.ensemble = ensemble
        self.thermostat = thermostat
        self.use_device = "cuda"
        self.md_data = []  # 存储MD数据：帧数、时间、能量、温度

    def log(self, message):
        """记录日志信息（带时间戳）"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"{Colors.DIM}[{timestamp}]{Colors.RESET} {message}")

    def load_structure(self):
        """从 POSCAR 文件加载结构"""
        try:
            if not os.path.exists(self.input_file):
                raise FileNotFoundError(f"输入文件 {self.input_file} 不存在")

            self.log(f"{Colors.BLUE}正在读取输入文件:{Colors.RESET} {self.input_file}")

            structure = Structure.from_file(self.input_file)

            info_lines = [
                f"",
                f"{Colors.BRIGHT_GREEN}化学式:{Colors.RESET} {structure.composition.reduced_formula}",
                f"{Colors.BRIGHT_GREEN}原子数:{Colors.RESET} {len(structure)}",
                f"",
                f"{Colors.BOLD}晶格参数:{Colors.RESET}",
                f"  a     = {structure.lattice.a:>12.6f} Å",
                f"  b     = {structure.lattice.b:>12.6f} Å",
                f"  c     = {structure.lattice.c:>12.6f} Å",
                f"  α     = {structure.lattice.alpha:>12.6f}°",
                f"  β     = {structure.lattice.beta:>12.6f}°",
                f"  γ     = {structure.lattice.gamma:>12.6f}°",
                f"  体积  = {structure.lattice.volume:>12.6f} Å³",
            ]

            print_box("结构信息", '\n'.join(info_lines), color=Colors.CYAN)

            return structure
        except Exception as e:
            print_error(f"读取结构文件时出错: {str(e)}")
            raise

    def run_md(self, structure):
        """运行分子动力学模拟"""
        try:
            print_section("开始分子动力学模拟")

            print_info("初始化 CHGNet 模型...")
            chgnet = CHGNet.load()

            traj_path = os.path.join(self.work_dir, "md_out.traj")
            log_path = os.path.join(self.work_dir, "md_out.log")

            params = [
                f"{Colors.BRIGHT_BLUE}系综:{Colors.RESET}         {self.ensemble}",
                f"{Colors.BRIGHT_BLUE}恒温器:{Colors.RESET}       {self.thermostat}",
                f"{Colors.BRIGHT_BLUE}温度:{Colors.RESET}         {self.temperature} K",
                f"{Colors.BRIGHT_BLUE}步长:{Colors.RESET}         {self.timestep} fs",
                f"{Colors.BRIGHT_BLUE}总步数:{Colors.RESET}       {self.steps}",
                f"{Colors.BRIGHT_BLUE}总时间:{Colors.RESET}       {self.steps * self.timestep / 1000:.2f} ps",
                f"{Colors.BRIGHT_BLUE}日志间隔:{Colors.RESET}     每 {self.loginterval} 步",
                f"{Colors.BRIGHT_BLUE}计算设备:{Colors.RESET}     {self.use_device.upper()}",
                f"",
                f"{Colors.DIM}正在运行分子动力学模拟，请稍候...{Colors.RESET}",
            ]
            print_box("模拟参数", '\n'.join(params), color=Colors.MAGENTA)
            print()

            print_info(f"初始化分子动力学 ({self.thermostat} {self.ensemble})...")
            md = MolecularDynamics(
                atoms=structure,
                model=chgnet,
                ensemble=self.ensemble,
                thermostat=self.thermostat,
                temperature=self.temperature,
                timestep=self.timestep,
                trajectory=traj_path,
                logfile=log_path,
                loginterval=self.loginterval,
                use_device=self.use_device,
            )

            print_info(f"开始运行 {self.steps} 步模拟...")
            print()

            import threading
            import time

            stop_monitoring = threading.Event()
            last_log_line = [""]

            def monitor_log():
                """监控日志文件，读取最后一行"""
                while not stop_monitoring.is_set():
                    try:
                        if os.path.exists(log_path):
                            with open(log_path, 'r', encoding='utf-8') as f:
                                lines = f.readlines()
                                if len(lines) > 1:
                                    last_line = lines[-1].strip()
                                    if last_line and last_line != last_log_line[0]:
                                        last_log_line[0] = last_line
                                        parts = last_line.split()
                                        if len(parts) >= 5:
                                            try:
                                                time_ps = float(parts[0])
                                                step = int(time_ps * 1000 / self.timestep)
                                                progress = min(100, int(100 * step / self.steps))
                                                bar_width = 40
                                                filled = int(bar_width * progress / 100)
                                                bar = f"{Colors.BRIGHT_GREEN}{('=' * filled)}{Colors.DIM}{('-' * (bar_width - filled))}{Colors.RESET}"
                                                percent = f"{Colors.BOLD}{progress}%{Colors.RESET}"
                                                info = f"Time:{time_ps:.3f}ps Etot:{parts[1]}eV T:{parts[4]}K"
                                                print(f"\r{Colors.CYAN}[{bar}{Colors.CYAN}] {percent} {Colors.DIM}{info}{Colors.RESET}   ", end='', flush=True)
                                            except Exception:
                                                pass
                    except Exception:
                        pass
                    time.sleep(0.5)

            monitor_thread = threading.Thread(target=monitor_log)
            monitor_thread.daemon = True
            monitor_thread.start()

            try:
                md.run(self.steps)
            finally:
                stop_monitoring.set()
                monitor_thread.join(timeout=1)

            print()
            print_success("分子动力学模拟完成！")

            return traj_path

        except Exception as e:
            print_error(f"分子动力学模拟出错: {str(e)}")
            raise

    def process_trajectory(self, traj_path):
        """处理轨迹文件，生成各种输出文件"""
        try:
            print_section("处理轨迹数据")

            print_info("读取轨迹文件...")
            traj = Trajectory(traj_path)

            print_info(f"轨迹包含 {len(traj)} 帧")

            self.md_data = []
            for i, atoms in enumerate(traj):
                frame = i * self.loginterval
                time = frame * self.timestep
                energy = atoms.get_potential_energy()
                temp = atoms.get_temperature()
                self.md_data.append([frame, time, energy, temp])

            return traj

        except Exception as e:
            print_error(f"处理轨迹时出错: {str(e)}")
            raise

    def save_contcar(self, traj):
        """保存最终结构到 CONTCAR"""
        try:
            print_info("正在保存最终结构到 CONTCAR...")

            final_atoms = traj[-1]
            final_structure = Structure(
                lattice=final_atoms.get_cell(),
                species=final_atoms.get_chemical_symbols(),
                coords=final_atoms.get_positions(),
                coords_are_cartesian=True,
            )

            poscar_out = Poscar(final_structure)
            poscar_out.write_file(self.output_structure)

            print_success("CONTCAR 已保存")
        except Exception as e:
            print_error(f"保存 CONTCAR 时出错: {str(e)}")
            raise

    def save_xdatcar1(self, traj):
        """生成 XDATCAR 文件"""
        try:
            print_info("正在生成 XDATCAR 文件...")

            xdatcar_path = os.path.join(self.work_dir, "XDATCAR")

            atoms = traj[0]
            symbols = atoms.get_chemical_symbols()

            unique_elements = []
            element_counts = []
            current_elem = symbols[0]
            count = 1
            for symbol in symbols[1:]:
                if symbol == current_elem:
                    count += 1
                else:
                    unique_elements.append(current_elem)
                    element_counts.append(count)
                    current_elem = symbol
                    count = 1
            unique_elements.append(current_elem)
            element_counts.append(count)

            with open(xdatcar_path, "w", encoding='utf-8') as f:
                f.write("Generated by CHGNet AIMD\n")
                f.write("1.0\n")

                for i, atoms in enumerate(traj):
                    cell = atoms.get_cell()
                    for j in range(3):
                        f.write(f"  {cell[j][0]:.10f}  {cell[j][1]:.10f}  {cell[j][2]:.10f}\n")

                    f.write("  " + "  ".join(unique_elements) + "\n")
                    f.write("  " + "  ".join(map(str, element_counts)) + "\n")
                    f.write("Direct configuration=  %6d\n" % (i + 1))

                    positions = atoms.get_positions()
                    for pos in positions:
                        frac_pos = np.linalg.solve(cell.T, pos)
                        f.write(f"  {frac_pos[0]:.10f}  {frac_pos[1]:.10f}  {frac_pos[2]:.10f}\n")

            print_success(f"XDATCAR 已生成 ({len(traj)} 帧)")

        except Exception as e:
            print_error(f"生成 XDATCAR 时出错: {str(e)}")
            raise


    def save_xdatcar2(self, traj):
        """生成 XDATCAR 文件"""
        try:
            print_info("正在生成 XDATCAR 文件...")

            xdatcar_path = os.path.join(self.work_dir, "XDATCAR")

            if traj is None or len(traj) == 0:
                raise ValueError("轨迹为空，无法生成 XDATCAR")

            atoms = traj[0]
            cell = atoms.get_cell()
            symbols = atoms.get_chemical_symbols()

            unique_elements = []
            element_counts = []
            current_elem = symbols[0]
            count = 1
            for symbol in symbols[1:]:
                if symbol == current_elem:
                    count += 1
                else:
                    unique_elements.append(current_elem)
                    element_counts.append(count)
                    current_elem = symbol
                    count = 1
            unique_elements.append(current_elem)
            element_counts.append(count)

            # 记录第一帧中各元素对应的原子索引，后续各帧按同样顺序输出
            element_indices = {}
            start = 0
            for elem, count in zip(unique_elements, element_counts):
                element_indices[elem] = list(range(start, start + count))
                start += count

            with open(xdatcar_path, "w", encoding='utf-8') as f:
                f.write("Generated by CHGNet AIMD\n")
                f.write("1.0\n")

                # XDATCAR 的晶格矩阵只写一次，固定使用第一帧
                for j in range(3):
                    f.write(f"  {cell[j][0]:.10f}  {cell[j][1]:.10f}  {cell[j][2]:.10f}\n")

                f.write("  " + "  ".join(unique_elements) + "\n")
                f.write("  " + "  ".join(map(str, element_counts)) + "\n")

                for i, atoms in enumerate(traj):
                    # 检查原子顺序是否与第一帧一致
                    if atoms.get_chemical_symbols() != symbols:
                        raise ValueError(
                            f"第 {i + 1} 帧的原子种类或顺序与第一帧不一致，无法写入 XDATCAR"
                        )

                    f.write("Direct configuration=  %6d\n" % (i + 1))

                    # 直接使用分数坐标
                    positions = atoms.get_scaled_positions(wrap=True)

                    for elem in unique_elements:
                        for idx in element_indices[elem]:
                            pos = positions[idx]
                            f.write(f"  {pos[0]:.10f}  {pos[1]:.10f}  {pos[2]:.10f}\n")

            print_success(f"XDATCAR 已生成 ({len(traj)} 帧)")

        except Exception as e:
            print_error(f"生成 XDATCAR 时出错: {str(e)}")
            raise


    def save_xdatcar(self, traj):
        """生成 XDATCAR 文件"""
        try:
            print_info("正在生成 XDATCAR 文件...")

            xdatcar_path = os.path.join(self.work_dir, "XDATCAR")

            if traj is None or len(traj) == 0:
                raise ValueError("轨迹为空，无法生成 XDATCAR")

            # 使用第一帧作为整个 XDATCAR 的基准
            atoms = traj[0]
            cell = atoms.get_cell()
            symbols = atoms.get_chemical_symbols()

            # 不合并相同元素，完全保留第一帧的原子标签顺序
            unique_elements = symbols[:]
            element_counts = [1] * len(symbols)

            with open(xdatcar_path, "w", encoding="utf-8") as f:
                # XDATCAR 头部只写一次，晶格固定使用第一帧
                f.write("Generated by CHGNet AIMD\n")
                f.write("1.0\n")
                for j in range(3):
                    f.write(f"  {cell[j][0]:.10f}  {cell[j][1]:.10f}  {cell[j][2]:.10f}\n")

                # 保留逐原子的元素标签，不合并
                f.write("  " + "  ".join(unique_elements) + "\n")
                f.write("  " + "  ".join(map(str, element_counts)) + "\n")

                # 逐帧写入分数坐标
                for i, atoms in enumerate(traj):
                    current_symbols = atoms.get_chemical_symbols()

                    if len(current_symbols) != len(symbols):
                        raise ValueError(
                            f"第 {i + 1} 帧原子数与第一帧不一致，无法写入 XDATCAR"
                        )

                    # 为了保证逐原子标签和坐标对应关系稳定，要求顺序一致
                    if current_symbols != symbols:
                        raise ValueError(
                            f"第 {i + 1} 帧的原子种类或顺序与第一帧不一致，无法稳定写入 XDATCAR"
                        )

                    f.write("Direct configuration=  %6d\n" % (i + 1))

                    # 直接按原子顺序写分数坐标
                    positions = atoms.get_scaled_positions(wrap=True)
                    for pos in positions:
                        f.write(f"  {pos[0]:.10f}  {pos[1]:.10f}  {pos[2]:.10f}\n")

            print_success(f"XDATCAR 已生成 ({len(traj)} 帧)")

        except Exception as e:
            print_error(f"生成 XDATCAR 时出错: {str(e)}")
            raise


    def save_oszicar(self):
        """生成 OSZICAR 文件"""
        try:
            print_info("正在生成 OSZICAR 文件...")

            oszicar_path = os.path.join(self.work_dir, "OSZICAR")

            with open(oszicar_path, 'w', encoding='utf-8') as f:
                prev_energy = None
                for i, (_, _, energy, temp) in enumerate(self.md_data, start=1):
                    if i == 1:
                        d_energy = 0.0
                    else:
                        d_energy = energy - prev_energy
                    prev_energy = energy

                    f_str = self._format_vasp_energy(energy)
                    e0_str = self._format_vasp_energy(energy)
                    de_str = self._format_vasp_energy(d_energy)

                    line = f"{i:4d} F= {f_str} E0= {e0_str}  d E ={de_str}  T={temp:8.2f}\n"
                    f.write(line)

            print_success(f"OSZICAR 已生成 ({len(self.md_data)} 步)")

        except Exception as e:
            print_error(f"生成 OSZICAR 时出错: {str(e)}")
            raise

    def save_log_dat(self):
        """生成 log.dat 文件（帧数、时间、能量、温度）"""
        try:
            print_info("正在生成 log.dat 文件...")

            log_dat_path = os.path.join(self.work_dir, "log.dat")

            with open(log_dat_path, 'w', encoding='utf-8') as f:
                f.write("# CHGNet AIMD Log\n")
                f.write("# Frame    Time(fs)      Energy(eV)    Temperature(K)\n")

                for frame, time_fs, energy, temp in self.md_data:
                    f.write(f"{frame:8d}  {time_fs:12.2f}  {energy:14.6f}  {temp:12.2f}\n")

            print_success(f"log.dat 已生成 ({len(self.md_data)} 条记录)")

            energies = [data[2] for data in self.md_data]
            temps = [data[3] for data in self.md_data]

            stats_lines = [
                f"",
                f"{Colors.BOLD}能量统计:{Colors.RESET}",
                f"  平均能量: {np.mean(energies):>12.6f} eV",
                f"  能量波动: {np.std(energies):>12.6f} eV",
                f"",
                f"{Colors.BOLD}温度统计:{Colors.RESET}",
                f"  平均温度: {np.mean(temps):>12.2f} K",
                f"  温度波动: {np.std(temps):>12.2f} K",
            ]
            print_box("模拟统计", '\n'.join(stats_lines), color=Colors.GREEN)

        except Exception as e:
            print_error(f"生成 log.dat 时出错: {str(e)}")
            raise

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

    def run(self):
        """执行完整的 AIMD 流程"""
        try:
            structure = self.load_structure()
            traj_path = self.run_md(structure)
            traj = self.process_trajectory(traj_path)

            print_section("保存结果")
            self.save_contcar(traj)
            self.save_xdatcar(traj)
            self.save_oszicar()
            self.save_log_dat()

            print()
            print_box(
                "任务完成",
                f"\n{Colors.BRIGHT_GREEN}{Colors.BOLD}所有文件已成功生成!{Colors.RESET}\n\n"
                f"{Colors.CYAN}输出文件:{Colors.RESET}\n"
                f"  • CONTCAR    - 最终结构\n"
                f"  • XDATCAR    - 完整轨迹\n"
                f"  • OUTCAR     - 详细日志\n"
                f"  • OSZICAR    - 能量记录\n"
                f"  • log.dat    - 帧数/时间/能量/温度\n"
                f"  • md_out.traj - 原始 MD 轨迹\n"
                f"  • md_out.log  - 原始 MD 日志\n",
                color=Colors.GREEN,
            )

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


def main():
    """主函数"""
    suppress_all_warnings()

    try:
        args = parse_args()
        work_dir = os.path.dirname(os.path.abspath(args.input_file)) or '.'
        outcar_path = os.path.join(work_dir, 'OUTCAR')

        with OutputLogger(outcar_path):
            print_banner()
            md_runner = CHGNetAIMD(
                input_file=args.input_file,
                output_structure=args.output_file,
                temperature=args.temperature,
                timestep=args.timestep,
                steps=args.steps,
                loginterval=args.loginterval,
                ensemble=args.ensemble,
                thermostat=args.thermostat,
            )
            success = md_runner.run()

        if success:
            sys.exit(0)
        sys.exit(1)

    except KeyboardInterrupt:
        print(f"\n\n{Colors.BRIGHT_YELLOW}用户中断操作{Colors.RESET}")
        sys.exit(1)
    except Exception as e:
        print_error(f"程序错误: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


    from ase.io import read

    traj = read('md_out.traj', index=':')
    if len(traj) == 0:
        raise ValueError("No frames in trajectory")

    # 使用第一帧的信息构建头部
    atoms0 = traj[0]
    cell = atoms0.get_cell()
    symbols = atoms0.get_chemical_symbols()
    # 按元素排序（与 POSCAR 一致）
    unique_symbols = sorted(set(symbols), key=lambda s: symbols.index(s))
    counts = [symbols.count(s) for s in unique_symbols]

    with open('XDATCAR_clean', 'w') as f:
        f.write("Generated by CHGNet AIMD\n")
        f.write("1.0\n")
        for vec in cell:
            f.write(f"  {vec[0]:.12f}  {vec[1]:.12f}  {vec[2]:.12f}\n")
        f.write("  " + "  ".join(unique_symbols) + "\n")
        f.write("  " + "  ".join(str(c) for c in counts) + "\n")
        
        for i, atoms in enumerate(traj):
            f.write(f"Direct configuration=       {i+1}\n")
            # 假定为分数坐标（直接打印 scaled positions）
            spos = atoms.get_scaled_positions()
            # 保持原子顺序与 symbols 排序一致？
            # 如果轨迹中原子顺序没有变，可以直接按索引写出
            # 为了安全，按照 symbols 排序的顺序写 (如 C, N, Fe)
            for sym in unique_symbols:
                indices = [j for j, s in enumerate(symbols) if s == sym]
                for idx in indices:
                    s = spos[idx]
                    f.write(f"  {s[0]:.12f}  {s[1]:.12f}  {s[2]:.12f}\n")




if __name__ == "__main__":
    main()
    