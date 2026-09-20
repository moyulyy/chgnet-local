# CHGNet NEB CLI

基于 CHGNet 的 NEB（Nudged Elastic Band）命令行脚本，用于直接读取工作目录下的 `00/01/02/...` 数字图像目录并计算迁移能垒。

当前版本为纯 CLI 运行方式：
- 不再使用 IDPP 自动创建插点
- 直接读取已有的 `00/01/02/.../POSCAR`
- 计算过程中持续刷新能垒与各图像能量
- 计算过程中持续写出各目录下的 `CONTCAR / XDATCAR / OSZICAR / OUTCAR`
- 默认以当前目录作为工作目录，也可通过 `--work-dir` 指定

## 功能简介

程序入口为 `main.py`，主要流程如下：
1. 扫描工作目录下的数字图像目录
2. 读取 `00/POSCAR` 作为初态、最后一个数字目录中的 `POSCAR` 作为末态
3. 检查路径连续性与结构兼容性
4. 执行始末态单点与 NEB 优化
5. 在优化过程中持续输出当前能垒、TS 位置与各图像相对能量
6. 持续更新每个图像目录中的结果文件，并在结束后输出汇总结果

## 依赖

建议使用 Python 3.10 及以上版本，并安装以下依赖：

```bash
pip install numpy ase pymatgen chgnet matplotlib
```

其中：
- `matplotlib` 用于保存 `neb_profile.png`

## 输入目录结构

你需要先准备好连续编号的数字目录，并在每个目录下放置 `POSCAR`：

```text
work-dir/
├── 00/
│   └── POSCAR
├── 01/
│   └── POSCAR
├── 02/
│   └── POSCAR
└── 03/
    └── POSCAR
```

要求如下：
- 目录必须从 `00` 开始连续编号，例如 `00/01/02/03`
- 每个数字目录下都必须存在 `POSCAR`
- `00/POSCAR` 与最后一个目录中的 `POSCAR` 必须原子数一致
- `00/POSCAR` 与最后一个目录中的 `POSCAR` 必须原子种类及顺序一致

中间目录（如 `01/02/...`）将直接作为 NEB 初始路径使用。

## 运行方式

### Ubuntu / Linux

```bash
python main.py --work-dir ./your-neb-path
```

如果环境使用 `python3`：

```bash
python3 main.py --work-dir ./your-neb-path
```

### Windows

```bash
python main.py --work-dir .\your-neb-path
```

## 参数说明

| 参数 | 说明 | 默认值 |
| --- | --- | --- |
| `--work-dir` | 包含 `00/01/02...` 图像目录的工作目录 | `.` |
| `--fmax` | 力收敛阈值，单位 eV/Å | `0.05` |
| `--max-steps` | 最大优化步数 | `300` |
| `--spring-constant` | NEB 弹簧常数 | `0.1` |
| `--climb` | 是否启用 climbing image，传 `True/False` | `True` |
| `--dry-run` | 是否只扫描目录并校验结构，传 `True/False` | `False` |

## dry-run 说明

当设置：

```bash
--dry-run True
```

程序只会执行：
- 扫描数字目录
- 检查编号是否连续
- 读取初态 / 末态结构
- 检查结构兼容性

不会执行：
- CHGNet 模型加载
- 始末态单点计算
- NEB 优化
- `NEB_RESULTS`
- `neb_profile.png`
- `neb_final.traj` / `neb_final.xtd`

这适合先检查目录布局与结构是否正确。

## 示例

### 1. 只检查目录与结构

```bash
python main.py --work-dir ./your-neb-path --dry-run True
```

### 2. 完整 NEB 计算

```bash
python main.py \
  --work-dir ./your-neb-path \
  --fmax 0.05 \
  --max-steps 300 \
  --spring-constant 0.1 \
  --climb True
```

### 3. 关闭 climbing image

```bash
python main.py --work-dir ./your-neb-path --climb False
```

## 过程输出

NEB 优化过程中，程序会：
- 在终端输出当前步数
- 显示当前最大力
- 显示当前过渡态目录
- 显示当前正向能垒、反向能垒、反应热
- 显示每个图像的相对能量
- 持续更新 `NEB_RESULTS`

## 输出文件

完整计算模式下会生成：
- `NEB_RESULTS`：实时/最终能垒结果汇总
- `neb_profile.png`：能量剖面图
- `neb.traj`：ASE 优化轨迹
- `neb_initial.traj`
- `neb_initial.xtd`
- `neb_final.traj`
- `neb_final.xtd`
- `neb_optimization.xtd`（若轨迹转换成功）

每个 image 目录下会持续更新：
- `POSCAR`
- `CONTCAR`
- `XDATCAR`
- `OSZICAR`
- `OUTCAR`

## 输出目录规则

程序在 `--work-dir` 指定的目录中运行，并将所有输出写回该目录。

例如：
- 工作目录：`/data/neb_case/`
- 输入目录：`/data/neb_case/00`, `/data/neb_case/01`, ...
- 输出文件：也写回 `/data/neb_case/`

## 注意事项

### 1. 数字目录必须连续

例如允许：

```text
00 01 02 03
```

不允许：

```text
00 02 03
```

### 2. 中间图像不会自动生成

当前版本不会根据初态和末态自动插点，也不会使用 IDPP。
你需要自行准备好中间图像目录中的 `POSCAR`。

### 3. 建议先 dry-run

推荐先执行：

```bash
python main.py --work-dir ./your-neb-path --dry-run True
```

确认目录和结构正确后，再执行完整计算。
