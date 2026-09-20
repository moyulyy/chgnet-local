# CHGNet AIMD CLI

基于 CHGNet 的分子动力学命令行脚本，用于读取结构文件并运行 AIMD 模拟。

当前版本已改为纯 CLI 运行方式：
- 不再包含任何交互式输入
- 计算设备固定为 `cuda`
- 保留所有输出文件，包括原始 MD 轨迹和日志
- 不提供 `--help` / `-h` 参数说明，请直接参考本文档

## 功能简介

程序入口为 `main.py`，主要流程如下：
1. 读取输入结构文件
2. 加载 CHGNet 模型
3. 运行 `MolecularDynamics`
4. 处理轨迹数据
5. 输出 VASP 风格及原始日志/轨迹文件

## 依赖

建议使用 Python 3.10 及以上版本，并安装以下依赖：

```bash
pip install numpy ase pymatgen chgnet
```

另外由于程序固定使用 `cuda`，请确保：
- 本机可用 GPU
- CUDA 环境可正常使用
- 对应的 PyTorch / CHGNet 环境已正确安装

## 运行方式

最简单示例：

```bash
python main.py --input POSCAR
```

完整示例：

```bash
python main.py \
  --input POSCAR \
  --output CONTCAR \
  --temperature 300 \
  --timestep 1.0 \
  --steps 1000 \
  --loginterval 1 \
  --ensemble nvt \
  --thermostat Nose-Hoover
```

## 参数说明

程序当前支持以下命令行参数：

| 参数 | 说明 | 默认值 |
| --- | --- | --- |
| `--input` | 输入结构文件路径 | `POSCAR` |
| `--output` | 最终结构输出文件名 | `CONTCAR` |
| `--temperature` | 模拟温度，单位 K | `300` |
| `--timestep` | 时间步长，单位 fs | `1.0` |
| `--steps` | 总步数 | `1000` |
| `--loginterval` | 日志间隔 | `1` |
| `--ensemble` | 分子动力学系综 | `nvt` |
| `--thermostat` | 恒温器类型 | `Nose-Hoover` |

## 设备说明

程序内部已固定：

```python
use_device = "cuda"
```

这意味着：
- 不再支持通过命令行切换 `cpu`
- 也没有 `--use-device` 参数
- 若本机 CUDA 不可用，程序运行会失败

## 输出文件

程序会在输入结构文件所在目录生成以下文件：

| 文件名 | 说明 |
| --- | --- |
| `OUTCAR` | 运行过程详细日志 |
| `CONTCAR` | 最终结构 |
| `XDATCAR` | 完整轨迹 |
| `OSZICAR` | 能量记录 |
| `log.dat` | 帧数、时间、能量、温度汇总 |
| `md_out.traj` | 原始 MD 轨迹文件 |
| `md_out.log` | 原始 MD 日志文件 |

当前版本不会删除 `md_out.traj` 和 `md_out.log`。

## 使用建议

### 1. 先做短步数测试

建议先运行一个小规模任务检查环境是否正常：

```bash
python main.py --input POSCAR --steps 10
```

### 2. 输出目录规则

程序以输入文件所在目录作为工作目录，因此输出文件会写到输入文件同级目录。

例如：
- 输入文件：`/data/run1/POSCAR`
- 输出目录：`/data/run1/`

### 3. 关于输入文件

虽然默认参数名写的是 `POSCAR`，但程序底层使用的是 `pymatgen.Structure.from_file(...)` 读取结构，因此可兼容 pymatgen 支持的其他结构文件格式。若你只在当前项目场景使用，建议仍优先使用 VASP 的 `POSCAR`。

## 常见问题

### 为什么没有 `--help`？

这是当前版本的设计选择，程序显式关闭了 argparse 的自动帮助参数，因此请直接查看本 README 获取参数说明。

### 为什么不能切换到 CPU？

因为当前版本已按需求将设备固定为 `cuda`，不会再提供 CPU 作为默认设备或回退路径。

### 如果 CUDA 不可用怎么办？

当前脚本不会自动回退到 CPU。你需要先修复本机 CUDA / PyTorch / CHGNet 环境，或者再修改源码后自行增加 CPU 支持。

## 项目文件

当前项目核心文件很简单：

- `main.py`：主程序
- `README.md`：使用说明

## 示例命令

```bash
python main.py --input POSCAR --output CONTCAR --temperature 500 --timestep 2.0 --steps 2000 --loginterval 10 --ensemble nvt --thermostat Nose-Hoover
```

运行完成后，可在输入文件目录中检查生成的输出文件。