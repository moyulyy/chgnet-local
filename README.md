# ChgNet Studio

> 面向 Windows 的本地桌面 GUI，把 [`ChgNetCalculater/`](ChgNetCalculater) 里的 CHGNet
> 机器学习势命令行脚本包装成一个可视化计算工作台。

![Platform](https://img.shields.io/badge/platform-Windows-0078D6?logo=windows&logoColor=white)
![Python](https://img.shields.io/badge/python-3.9%2B-3776AB?logo=python&logoColor=white)
![GUI](https://img.shields.io/badge/GUI-PySide6-41CD52?logo=qt&logoColor=white)
![Viewer](https://img.shields.io/badge/viewer-3Dmol.js-1E90FF)
![License](https://img.shields.io/badge/license-MIT-green)

无边框圆角窗口、红黄绿控制按钮、三栏卡片布局、3Dmol.js 三维结构可视化。
所有计算都在**独立配置的 Python 环境**中以后台子进程方式运行，
**不写死任何机器相关的路径**——换一台电脑克隆下来也能直接跑起来。

---

## 目录

- [界面预览](#界面预览)
- [快速开始（TL;DR）](#快速开始tldr)
- [安装与配置](#安装与配置)
  - [0. 需要两个 Python 环境](#0-需要两个-python-环境)
  - [1. 获取代码](#1-获取代码)
  - [2. 准备计算环境](#2-准备计算环境)
  - [3. 让 ChgNet Studio 找到你的计算环境](#3-让-chgnet-studio-找到你的计算环境)
  - [4. 安装 GUI 依赖](#4-安装-gui-依赖)
  - [5. 启动](#5-启动)
- [计算项目](#计算项目)
- [使用流程](#使用流程)
- [功能要点](#功能要点)
- [目录结构](#目录结构)
- [常见问题](#常见问题)
- [许可](#许可)

---

## 界面预览

```
┌───────────────────────────────────────────────────────────────────────┐
│ ● ● ●                                                    （可拖拽标题栏）│
├────────────┬──────────────────────────────────────┬───────────────────┤
│  计算项目   │  结构可视化  [旋转|点选|框选]         │  参数设置          │
│            │                                      │  ┌ 输入结构 ────┐  │
│  · 单点能   │                                      │  └─────────────┘  │
│  · 结构弛豫 │                                      │  ┌ 任务参数 ────┐  │
│  · AIMD    │            （3Dmol 画布）             │  └─────────────┘  │
│  · 振动频率 │                                      │  ┌ 结果/日志 ───┐  │
│  · NEB     │                                      │  │ （可滚动）   │  │
│            │                                      │  └─────────────┘  │
│            │                                      │      [开始计算]    │
├────────────┴──────────────────────────────────────┴───────────────────┤
│ 就绪 · ……                                                    （状态栏）│
└───────────────────────────────────────────────────────────────────────┘
```

---

## 快速开始（TL;DR）

```bat
:: 1. 已有一个装了 chgnet + CUDA 版 torch 的 conda 环境（默认名 chem_env）
::    如果环境名不同，设置 CHGNET_ENV；路径特殊则直接设 CHGNET_PYTHON
set CHGNET_ENV=chem_env
:: set CHGNET_PYTHON=D:\some\env\python.exe

:: 2. 安装 GUI 依赖（装进同一个环境即可）
pip install -r requirements.txt

:: 3. 双击 run.bat，或在命令行运行
run.bat
```

`run.bat` 会**自动探测**本机的 conda / Python 环境，找不到时才提示你手动指定，
不会再因为写死 `D:\miniconda3\envs\chem_env\python.exe` 而报错。

---

## 安装与配置

### 0. 需要两个 Python 环境

| 角色 | 需要安装 | 说明 |
| --- | --- | --- |
| **GUI 进程** | `PySide6`、`numpy`、`ase` | 负责界面与 3D 显示，**不导入** torch / chgnet，启动很快 |
| **计算进程** | `chgnet`、`torch`(CUDA)、`pymatgen`、`matplotlib` | 真正跑计算的解释器，由 GUI 以子进程方式调用 |

> 两者**可以是同一个环境**（推荐的 `chem_env`），也可以分开。GUI 只通过
> `python.exe` 的子进程调用计算脚本，因此计算环境里的依赖不会影响 GUI 启动速度。

### 1. 获取代码

```bat
git clone https://github.com/moyulyy/chgnet-local.git
cd chgnet-local
```

### 2. 准备计算环境

推荐直接用 conda 新建一个名为 `chem_env` 的环境（名字可在第 3 步改）：

```bat
conda create -n chem_env python=3.10 -y
conda activate chem_env

:: torch 必须是 CUDA 版，不能是 CPU 版！按显卡驱动选择轮子（示例 CUDA 12.1）
pip install torch --index-url https://download.pytorch.org/whl/cu121

:: 其余计算依赖
pip install chgnet pymatgen matplotlib ase

:: 自检：必须输出 True
python -c "import torch; print(torch.cuda.is_available())"
```

> **为什么要强调 CUDA 版 torch？**
> 所有计算任务都固定使用 CUDA。Windows 上直接 `pip install torch`
> 常常装成 **CPU 版**，会导致任务报错，或悄悄退回 CPU 而极慢。
>
> 其他 CUDA 版本把 `cu121` 换成对应值（如 `cu118`、`cu124`），
> 最新命令见 <https://pytorch.org/get-started/locally/>。
> 若自检输出 `False`，先 `pip uninstall -y torch` 再用 CUDA 索引重装。

### 3. 让 ChgNet Studio 找到你的计算环境

**不需要修改任何源码。** 解释器按以下顺序解析，第一个存在的即被采用：

| 优先级 | 来源 | 说明 |
| --- | --- | --- |
| 1 | 环境变量 `CHGNET_PYTHON` | 直接指定 `python.exe` 完整路径，最明确 |
| 2 | `~/.chgnet_studio.json` 中的 `python_exe` | GUI 自己的配置项（默认留空＝自动探测） |
| 3 | 环境变量 `CONDA_PREFIX` | 当前已被 `conda activate` 的环境 |
| 4 | `CHGNET_ENV`（默认 `chem_env`） | 在常见 conda 安装目录下搜索 `envs\<名字>\python.exe` |
| 5 | 本机 `D:\miniconda3\envs\chem_env\python.exe` | 开发机遗留路径，仅作兜底 |
| 6 | 当前运行 GUI 的解释器 | 最终兜底 |

对应两种常见改法：

**A. 环境名不是 `chem_env`** —— 设置 `CHGNET_ENV`：

```bat
set CHGNET_ENV=my_chgnet_env
run.bat
```

**B. 环境在非常规位置** —— 直接指定解释器：

```bat
set CHGNET_PYTHON=C:\Users\you\anaconda3\envs\chem_env\python.exe
run.bat
```

> `run.bat` 与 `app/config.py` 使用**同一套**解析顺序，因此从命令行启动、
> 双击启动、或在 GUI 内计算，都会指向同一个环境。
>
> 想让设置永久生效：把 `CHGNET_PYTHON` 加到系统环境变量，或编辑
> `%USERPROFILE%\.chgnet_studio.json`：
>
> ```json
> {
>   "python_exe": "C:\\Users\\you\\miniconda3\\envs\\chem_env\\python.exe"
> }
> ```

`ChgNetCalculater/` 下附带的独立 `*.bat` 小脚本同样会优先读取
`CHGNET_PYTHON`，然后才回退到旧路径。

### 4. 安装 GUI 依赖

GUI 只依赖 `PySide6 / numpy / ase`。装进计算环境即可（也可以另建环境）：

```bat
pip install -r requirements.txt
```

### 5. 启动

双击项目根目录的 **`run.bat`**，或：

```bat
run.bat
```

也可以直接手动指定解释器启动：

```bat
D:\path\to\env\python.exe main.py
```

启动后 GUI 会打印实际使用的解释器与脚本目录，便于排查：

```
ChgNet Studio 已启动
Python  : D:\...\envs\chem_env\python.exe
脚本目录: ...\chgnet-local\ChgNetCalculater
```

---

## 计算项目

界面左侧列出 5 个计算任务，全部复用 `ChgNetCalculater/` 下的原始 `.py` 脚本：

| 项目 | 调用脚本 | 关键参数 |
| --- | --- | --- |
| 单点能计算 | `chgnet-opt/singlepoint_runner.py` | `--device cuda` |
| 结构弛豫优化 | `chgnet-opt/main.py` | `--type bulk/relax`、`--max-steps`、`--fmax` |
| 从头分子动力学 | `chgnet-aimd/main.py` | 温度、步长、步数、日志间隔、系综、恒温器 |
| 振动频率计算 | `chgnet-freq/main.py` | `--delta`、`--nfree`(2/4)、`--temperature` |
| NEB 过渡态搜索 | `chgnet-neb/main.py` | IS/插点/FS 路径、`--fmax`、`--max-steps`、`--spring-constant`、climb |

> 所有任务统一使用 **CUDA**（界面不再提供设备选项）；请确保计算环境中的 torch 是
> **CUDA 版本**而非 CPU 版本（`python -c "import torch; print(torch.cuda.is_available())"`
> 必须为 `True`）。

### NEB 说明

NEB **不需要单独选择初态 / 末态**，只需给出包含 **连续编号子目录** 的路径：

```
你选择的路径/
├── 00/POSCAR     ← IS
├── 01/POSCAR     ← 插点
├── 02/POSCAR     ← 插点
└── 03/POSCAR     ← FS
```

程序 **只读取数字命名子目录（`00`、`01`、`02` …）中的 `POSCAR`**，
其他扩展名的结构文件、非数字目录、散落文件全部忽略；目录按数字升序排列
（`02` 在 `10` 之前）。

加载后所有图像作为一条轨迹显示在中间视图中，拖动视图下方 **进度条即可逐帧预览**
（第 1 张＝IS，最后一张＝FS）。开始计算时程序把每个图像重写为
`00/POSCAR … NN/POSCAR` 到本次任务目录再调用 CHGNet-NEB（不修改原目录）；
若原目录编号不从 `00` 开始也无需处理，重写时会自动从 `00` 开始连续编号。

计算过程中，3D 视图下方的状态栏会**实时刷新每一步**的受力、TS 对应帧与能垒 Ea：

```
NEB 第 12 步   ·   受力 maxF = 0.0345 eV/Å   ·   TS 帧 = 04   ·   能垒 Ea = 0.5123 eV
```

---

## 使用流程

1. **打开结构**：右侧「输入结构」→ **打开结构**，选择
   `cif / POSCAR / CONTCAR / xsdf / XDATCAR`。
   `XDATCAR` 会作为轨迹载入，可用底部滑块逐帧播放。
2. **（可选）固定原子**：把中间视图切到 **点选** 或 **框选**，固定原子以黑色网格球显示。
   参数面板中「已固定原子」旁有 **取消全部固定** 按钮，可一键清除所有约束。
   - 固定信息会以 **Selective dynamics** 写入 `POSCAR`；
   - 「振动频率计算」会 **只对未固定原子** 计算频率；
   - 结构弛豫 / AIMD 脚本本身不施加固定约束（仅保留标记）。
3. **选择任务并填参**：左侧点选项目，右侧填写参数。
4. **开始计算**：点击「开始计算」，状态栏显示进度，可随时「取消」终止子进程。
5. **查看结果**：
   - **计算结果** 页：能量 / 频率 / 能垒等关键数值与产物清单、任务目录；
   - **运行日志** 页：实时打印脚本原始终端输出；
   - 若产物包含轨迹，中间视图会自动载入并可播放。

### 结果输出

每次任务在 **所打开结构文件所在目录** 下创建 `<时间戳>_<任务名>/`：

```
/path/to/POSCAR
/path/to/20260919_181630_relax/
    POSCAR              ← GUI 写入的输入结构（含 Selective dynamics）
    CONTCAR             ← 优化后结构
    OSZICAR / XDATCAR / OUTCAR / relax.pkl
```

各任务的产物：

- **单点能** → `CONTCAR / OSZICAR / OUTCAR`
- **结构弛豫** → 上述加 `XDATCAR / relax.pkl`
- **AIMD** → 上述加 `log.dat / md_out.traj / md_out.log`
- **频率** → `FREQ_RESULTS / zpe-ts.dat / vib_summary.txt`
- **NEB** → `NEB_RESULTS / neb_profile.png / neb_final.traj` 及每个图像目录的 `CONTCAR`

---

## 功能要点

- **窗口**：无边框 + 圆角 + 红黄绿控制按钮；拖拽标题栏移动、双击标题栏缩放；
  启动时按屏幕自适应并居中；橙色/青色应用图标已接入窗口与任务栏。
- **三栏布局**：左「计算项目」、中「3D 可视化」、右「参数 + 结果 / 日志」。
- **3D 交互（3Dmol.js）**：**正交投影（orthographic）**，拖拽旋转、滚轮缩放、
  右键平移、双击复位；点选 / 框选固定原子；轨迹逐帧播放。
- **帧预览滑块**：结构弛豫 / AIMD / NEB 完成后，3D 视图下方出现进度条，
  可任意拖动预览每一帧（当前帧会作为下一次计算的输入结构，方便接力计算）。
- **后台执行**：`QThread` + `subprocess`，界面不卡死、支持取消；
  子进程输出实时清理 ANSI 颜色码后写入「运行日志」。
- **格式支持**：统一经 ASE 读取 `cif / POSCAR / CONTCAR / xsd / XDATCAR`，
  发送计算前一律写成 VASP `POSCAR`。文件名与目录名可包含 `@` 等特殊字符
  （已关闭 ASE 按 `@` 切分“文件名@索引”的行为）。
- **免配置路径**：解释器 / 脚本目录自动探测，支持 `CHGNET_PYTHON` /
  `CHGNET_ENV` 环境变量覆盖，不在源码里写死任何机器路径。

---

## 目录结构

```
chgnet-local/
├── run.bat                     # Windows 启动器（自动探测 Python 环境）
├── main.py                     # 程序入口
├── requirements.txt            # GUI 与计算依赖说明
├── README.md
├── LICENSE
├── 3Dmol-min.js                # 3D 渲染库（本地，无需联网）
├── assets/
│   ├── app.ico / app.png       # 应用图标
│   └── make_icon.py            # 图标生成脚本
├── viewer/
│   └── viewer.html             # 3Dmol 页面：点选 / 框选 / 播放 + QWebChannel
├── ChgNetCalculater/           # CHGNet 计算脚本（.py 原样保留）
│   ├── chgnet-opt/             # 单点 / 弛豫
│   ├── chgnet-aimd/            # 分子动力学
│   ├── chgnet-freq/            # 振动频率
│   └── chgnet-neb/             # NEB
└── app/
    ├── styles.py               # 调色板与全局 QSS
    ├── widgets.py              # 卡片、分段控件、文件行、任务图标
    ├── window.py               # 无边框圆角窗口 + 红黄绿按钮
    ├── structure_io.py         # 基于 ASE 的结构 / 轨迹读写（含容错 XDATCAR）
    ├── viewer.py               # QWebEngineView 封装与 JS 桥接
    ├── chgnet_runner.py        # 命令构造 + 子进程执行 + 环境探测
    ├── results.py              # 解析各脚本输出（能量 / 频率 / 能垒 / 轨迹）
    ├── panels.py               # 项目列表、参数表单、结果 / 日志视图
    ├── workers.py              # QThread：建任务目录、跑子进程、汇总结果
    ├── main_window.py          # 主窗口与任务调度
    └── config.py               # 配置持久化 + 解释器自动探测
```

---

## 常见问题

**Q: 启动时报「环境未就绪」或找不到 Python？**

程序会按[第 3 步](#3-让-chgnet-studio-找到你的计算环境)的顺序自动探测计算环境。
若失败，请任选其一：

```bat
:: 指定解释器完整路径
set CHGNET_PYTHON=C:\Users\you\miniconda3\envs\chem_env\python.exe

:: 或告诉程序环境叫什么名字
set CHGNET_ENV=my_chgnet_env
```

并确认项目目录下存在 `ChgNetCalculater/` 脚本文件夹。

**Q: 计算报 CUDA 相关错误？**

所有任务都固定使用 CUDA，请确认计算环境里装的是 **CUDA 版 torch**（不是 CPU 版）：

```bat
python -c "import torch; print(torch.cuda.is_available())"
```

若输出 `False`，卸载 CPU 版后从 CUDA 索引重装（示例 CUDA 12.1）：

```bat
pip uninstall -y torch
pip install torch --index-url https://download.pytorch.org/whl/cu121
```

**Q: 提示 `No module named 'PySide6'` / `numpy` / `ase`？**

GUI 依赖没有装进启动解释器。在对应环境里执行：

```bat
pip install -r requirements.txt
```

**Q: 振动频率任务报 `assert nfree in [2, 4]`？**

ASE 要求 `nfree` 只能取 2 或 4，界面已限定为这两个取值。

**Q: 3D 区域空白？**

确认项目根目录存在 `3Dmol-min.js`；无 GPU 时 Chromium 会回退软件渲染。

**Q: 如何中断长时间任务？**

点击「取消」，程序会终止对应的子进程；已完成的部分产物仍保留在任务目录中。

---

## 许可

本项目基于 [MIT License](LICENSE) 发布。

计算脚本所属的 CHGNet 及相关库遵循各自的开源许可。
