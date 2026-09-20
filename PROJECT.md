# ChgNet Studio · 项目描述

**ChgNet Studio** 是一个面向 Windows 的本地桌面 GUI，把 `ChgNetCalculater/` 里
已有的 CHGNet 机器学习势命令行脚本，包装成 iOS / macOS 风格的可视化计算工作台。

## 它能做什么

在一套界面里完成 5 类 CHGNet 计算，并即时预览结构：

| 任务 | 说明 |
| --- | --- |
| 单点能计算 | 固定结构，计算能量与受力 |
| 结构弛豫优化 | bulk / relax 几何优化 |
| 从头分子动力学 (AIMD) | 温度、系综、恒温器可调 |
| 振动频率计算 | 有限差分频率与热力学量 |
| NEB 过渡态搜索 | IS → 插点 → FS 路径，支持 climbing image |

支持读取 CIF、POSCAR / CONTCAR、VASP XDATCAR、Materials Studio XSD 等格式；
打开 POSCAR / CONTCAR 时会保留其中的 Selective dynamics 固定原子信息。

## 技术要点

- **界面**：PySide6（Qt 6）+ QtWebEngine，无边框圆角窗口、三栏卡片布局。
- **三维可视化**：3Dmol.js 渲染，支持旋转 / 点选 / 框选固定原子。
- **结构 I/O**：ASE 负责解析与写出，统一转换为 POSCAR 供计算使用。
- **计算解耦**：GUI 进程不导入 torch / chgnet，计算在 `chem_env` 解释器下以
  子进程方式运行，界面保持快速启动。
- **硬件**：所有任务固定使用 **CUDA**，要求 `chem_env` 安装 **CUDA 版 torch**。

## 快速开始

```bat
run.bat
```

GUI 依赖见 `requirements.txt`；计算引擎需在 `chem_env` 中安装
`chgnet / torch(CUDA) / pymatgen`。详见 `README.md`。
