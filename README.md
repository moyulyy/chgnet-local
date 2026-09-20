# ChgNet Studio

一个 **本地桌面 GUI**，把 `ChgNetCalculater/` 里已有的 CHGNet 机器学习势命令行
脚本包装成 iOS / macOS 风格的可视化计算工作台：无边框圆角窗口、红黄绿控制按钮、
三栏卡片布局、3Dmol.js 三维结构可视化，并通过 **`D:\miniconda3\envs\chem_env`**
解释器在后台以子进程方式调用 CHGNet 计算器。

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

## 快速开始

双击项目根目录下的 **`run.bat`**，或在命令行运行：

```bat
D:\miniconda3\envs\chem_env\python.exe main.py
```

GUI 本身只依赖 `PySide6 / numpy / ase`（chem_env 已具备）；真正的计算在子进程中
由 chem_env 的 `chgnet / torch / pymatgen` 完成。**GUI 进程不会导入 torch / chgnet**，
因此启动很快。

> 解释器与脚本目录会自动探测（默认 `D:\miniconda3\envs\chem_env\python.exe`
> 与本项目下的 `ChgNetCalculater/`），最近使用的目录保存在 `~/.chgnet_studio.json`。

### 安装依赖

GUI 本身只需要 PySide6 / numpy / ase：

```bat
pip install -r requirements.txt
```

计算引擎（chgnet / torch / pymatgen）必须安装在**运行计算脚本的解释器**中。其中
**torch 必须是 CUDA 版本，不能是 CPU 版本**——所有计算任务都固定使用 CUDA，
CPU 版 torch 会导致任务报错或退回 CPU 而极慢。Windows 上直接 `pip install torch`
默认常常装成 **CPU 版**，因此请从 PyTorch 的 CUDA 索引安装：

```bat
rem 1) 按显卡驱动选择对应的 CUDA 轮子（示例为 CUDA 12.1）
pip install torch --index-url https://download.pytorch.org/whl/cu121
rem 2) 安装其余引擎依赖
pip install chgnet pymatgen matplotlib
rem 3) 自检：必须输出 True
python -c "import torch; print(torch.cuda.is_available())"
```

> 其他 CUDA 版本把 `cu121` 换成对应值（如 `cu118`、`cu124`），
> 最新命令见 <https://pytorch.org/get-started/locally/>。
> 若自检输出 `False`，说明装的是 CPU 版，请先 `pip uninstall -y torch`
> 再用上面的 CUDA 索引重装。

---

## 计算项目

界面左侧列出 5 个计算任务，全部复用 `ChgNetCalculater/` 下的原始脚本：

| 项目 | 调用脚本 | 关键参数 |
| --- | --- | --- |
| 单点能计算 | `chgnet-opt/singlepoint_runner.py` | `--device cuda` |
| 结构弛豫优化 | `chgnet-opt/main.py` | `--type bulk/relax`、`--max-steps`、`--fmax` |
| 从头分子动力学 | `chgnet-aimd/main.py` | 温度、步长、步数、日志间隔、系综、恒温器 |
| 振动频率计算 | `chgnet-freq/main.py` | `--delta`、`--nfree`(2/4)、`--temperature` |
| NEB 过渡态搜索 | `chgnet-neb/main.py` | IS/插点/FS 路径、`--fmax`、`--max-steps`、`--spring-constant`、climb |

> 所有任务统一使用 **CUDA**（界面不再提供设备选项）；请确保 chem_env 中的 torch 是
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
（第 1 张=IS，最后一张=FS）。开始计算时程序把每个图像重写为
`00/POSCAR … NN/POSCAR` 到本次任务目录再调用 CHGNet-NEB（不修改原目录）；
若原目录编号不从 `00` 开始也无需处理，重写时会自动从 `00` 开始连续编号。

计算过程中，3D 视图下方的状态栏会**实时刷新每一步**的受力、TS 对应帧与能垒 Ea，
例如：

```
NEB 第 12 步   ·   受力 maxF = 0.0345 eV/Å   ·   TS 帧 = 04   ·   能垒 Ea = 0.5123 eV
```

---

## 使用流程

1. **打开结构**：右侧「输入结构」→ **打开结构**，选择 `cif / POSCAR / CONTCAR / xsdf / XDATCAR`。
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

各任务的产物：单点能 → `CONTCAR/OSZICAR/OUTCAR`；弛豫 → 上述加 `XDATCAR/relax.pkl`；
AIMD → 上述加 `log.dat/md_out.traj/md_out.log`；频率 → `FREQ_RESULTS/zpe-ts.dat/vib_summary.txt`；
NEB → `NEB_RESULTS/neb_profile.png/neb_final.traj` 及每个图像目录的 `CONTCAR` 等。

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

---

## 目录结构

```
chgnet-local/
├── run.bat                     # Windows 启动脚本（优先使用 chem_env）
├── main.py                     # 程序入口
├── requirements.txt
├── README.md
├── 3Dmol-min.js                # 3D 渲染库（本地）
├── assets/
│   ├── app.ico / app.png       # 应用图标
│   └── make_icon.py            # 图标生成脚本
├── viewer/
│   └── viewer.html             # 3Dmol 页面：点选 / 框选 / 播放 + QWebChannel
├── ChgNetCalculater/           # 原有 CHGNet 计算脚本（不修改）
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
    └── config.py               # 配置持久化（解释器 / 脚本目录 / 默认参数）
```

---

## 常见问题

**Q: 提示「环境未就绪」？**
程序会自动探测计算环境：请确认 `D:\miniconda3\envs\chem_env\python.exe` 存在，
且本项目目录下包含 `ChgNetCalculater/` 脚本文件夹。

**Q: 计算报 CUDA 相关错误？**
所有任务都固定使用 CUDA，请确认 chem_env 里装的是 **CUDA 版 torch**（不是 CPU 版）：

```bat
python -c "import torch; print(torch.cuda.is_available())"
```

若输出 `False`，请卸载 CPU 版后从 CUDA 索引重装，例如 CUDA 12.1：

```bat
pip uninstall -y torch
pip install torch --index-url https://download.pytorch.org/whl/cu121
```

**Q: 振动频率任务报 `assert nfree in [2, 4]`？**
ASE 要求 `nfree` 只能取 2 或 4，界面已限定为这两个取值。

**Q: 3D 区域空白？**
确认项目根目录存在 `3Dmol-min.js`；无 GPU 时 Chromium 会回退软件渲染。

**Q: 如何中断长时间任务？**
点击「取消」，程序会终止对应的子进程；已完成的部分产物仍保留在任务目录中。
