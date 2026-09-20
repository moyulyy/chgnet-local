# CHGNet Frequency CLI

在 Ubuntu 环境下使用 CHGNet 进行振动频率计算，输出 ZPE、TS 和 `ZPE-TS` 自由能修正项。

当前程序已经是**纯命令行模式**，运行时不会再弹出任何交互提示。

## 功能

- 读取 `POSCAR` 结构文件
- 使用 CHGNet + ASE 有限位移法计算振动频率
- 自动识别 `Selective dynamics`
- 输出热力学修正量：
  - `ZPE`
  - `TS`
  - `ZPE-TS`
- 生成以下文件：
  - `FREQ_RESULTS`
  - `vib_summary.txt`
  - `zpe-ts.dat`
  - `vib.*`

## Ubuntu 环境准备

建议使用 Python 3.10 及以上版本。

先安装基础环境：

```bash
sudo apt update
sudo apt install -y python3 python3-pip python3-venv
```

## 创建虚拟环境

在项目目录中执行：

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
```

## 安装依赖

如果你没有单独的 `requirements.txt`，可以直接安装程序所需的核心依赖：

```bash
pip install numpy ase pymatgen chgnet
```

如果 `chgnet` 安装过程中涉及 PyTorch，请按你当前机器环境安装对应版本的 PyTorch 后再重试。

## 输入文件

程序默认读取 `POSCAR`。

请确保你的输入结构文件存在，例如：

```bash
POSCAR
```

如果文件不在当前目录，可以通过 `--input` 指定完整路径或相对路径。

## 运行方式

### 最简单运行命令

```bash
python main.py --input POSCAR
```

在 Ubuntu 中，如果 `python` 没有指向 Python 3，也可以使用：

```bash
python3 main.py --input POSCAR
```

### 可选参数

```bash
python main.py --input POSCAR --delta 0.015 --nfree 2 --temperature 298.15
```

参数说明：

- `--input`：输入结构文件，默认 `POSCAR`
- `--delta`：有限位移大小，默认 `0.015`
- `--nfree`：位移次数，默认 `2`
- `--temperature`：热力学温度，默认 `298.15 K`

## 输出文件说明

程序会在输入文件所在目录输出结果。

### 1. `FREQ_RESULTS`

主要热力学结果汇总文件，包含：

- 势能 `E_pot`
- 零点能 `ZPE`
- 熵项 `TS`
- 自由能修正 `F_corr = ZPE - TS`

### 2. `vib_summary.txt`

ASE 生成的振动频率摘要。

### 3. `zpe-ts.dat`

你需要的简化结果文件，格式如下：

```text
ZPE = xxx eV
TS = xxx eV
ZPE-TS = xxx eV
```

### 4. `vib.*`

振动计算过程中生成的数据文件。

## 使用示例

### 当前目录有 POSCAR

```bash
python main.py --input POSCAR
```

### 指定其他输入文件

```bash
python main.py --input ./structures/POSCAR
```

### 指定温度

```bash
python main.py --input POSCAR --temperature 300
```

## 常见问题

### 1. 报错：找不到 POSCAR

请确认：

- 文件名是否正确
- 文件路径是否正确
- 当前终端所在目录是否正确

可以先检查：

```bash
ls
```

或指定完整路径：

```bash
python main.py --input /path/to/POSCAR
```

### 2. 运行很慢

振动频率计算本身需要多次位移和能量评估，耗时取决于：

- 体系原子数
- 可振动原子数
- 机器 CPU / GPU 性能

### 3. 终端里出现中文乱码

Ubuntu 一般不会有这个问题。如果遇到编码问题，可以先执行：

```bash
export LANG=en_US.UTF-8
export LC_ALL=en_US.UTF-8
```

## 项目文件

- `main.py`：主程序入口
- `README.md`：Ubuntu 运行说明

## 推荐运行流程

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install numpy ase pymatgen chgnet
python main.py --input POSCAR
```
