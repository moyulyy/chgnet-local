# chg-api

基于 CHGNet 的结构弛豫命令行脚本，支持两种计算模式：

- `bulk`：晶胞优化，允许晶格参数变化
- `relax`：固定晶胞参数，只优化原子位置

脚本会读取 `POSCAR`，执行 CHGNet 弛豫，并生成常见的 VASP 风格输出文件。

## 功能

- 非交互式命令行运行
- 支持 `bulk` / `relax` 两种模式
- 生成以下输出文件：
  - `CONTCAR` 或 `CONTCAR_relax`
  - `OSZICAR`
  - `XDATCAR`
  - `OUTCAR`
- 保留 `selective_dynamics` 信息
- 使用 CUDA 运行 CHGNet 优化器

## 依赖

请先确保环境中已安装以下 Python 包：

```bash
pip install chgnet pymatgen numpy
```

说明：当前脚本内部使用的是：

```python
StructOptimizer(use_device="cuda")
```

因此默认要求你的环境可用 CUDA。

## 输入文件

默认输入文件为当前目录下的 `POSCAR`。

## 用法

### 1. 晶胞优化（bulk）

允许晶格参数变化：

```bash
python main.py --type bulk --input POSCAR --max-steps 300 --fmax 0.05
```

默认输出结构文件：

```text
CONTCAR
```

### 2. 固定晶胞结构弛豫（relax）

固定晶胞参数，只优化原子位置：

```bash
python main.py --type relax --input POSCAR --max-steps 300 --fmax 0.05
```

默认输出结构文件：

```text
CONTCAR_relax
```

## 参数说明

- `--type`
  - `bulk`：晶胞优化
  - `relax`：固定晶胞结构弛豫
- `--input`
  - 输入结构文件，默认 `POSCAR`
- `--output`
  - 输出结构文件名
  - 默认情况下：
    - `bulk` -> `CONTCAR`
    - `relax` -> `CONTCAR_relax`
- `--max-steps`
  - 最大优化步数，默认 `300`
- `--fmax`
  - 力收敛阈值，单位 `eV/A`，默认 `0.05`

## 输出文件

运行完成后，脚本会在输入文件所在目录生成：

- `CONTCAR` / `CONTCAR_relax`：优化后的结构
- `OSZICAR`：每一步能量变化
- `XDATCAR`：优化轨迹
- `OUTCAR`：运行日志
- `relax.pkl`：CHGNet 中间结果，用于生成 `XDATCAR`

## 示例

### bulk

```bash
python main.py --type bulk --input POSCAR
```

### relax

```bash
python main.py --type relax --input POSCAR
```

### 指定输出文件名

```bash
python main.py --type bulk --input POSCAR --output CONTCAR_bulk_test
```

## 注意事项

1. 当前脚本为非交互模式，不会提示输入。
2. `--type relax` 不会改变晶格参数。
3. `--type bulk` 会同时优化晶格和原子位置。
4. 如果 CUDA 不可用，当前实现可能无法正常运行，因为优化器固定使用了 `use_device="cuda"`。
5. 如果输入文件不存在，程序会直接退出并返回非零状态码。
