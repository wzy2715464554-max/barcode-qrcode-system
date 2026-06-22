# 条形码与二维码实时定位与解码系统

本项目是图像与视频信号处理课程设计程序，支持条形码和二维码的图片识别、摄像头实时识别、结果可视化和网址自动跳转。

## 功能

- 图片文件识别条形码和二维码
- 摄像头实时识别条形码和二维码
- 基于灰度化、滤波、梯度增强、二值化、形态学闭运算的条码候选区定位
- 基于轮廓层级关系检测二维码“回”字形定位角
- 对成功解码区域进行透视变换校正并保存
- 使用 ZXing-C++ 解码二维码、Code 128 等常见条码
- GUI 界面支持摄像头识别、文件识别和保存结果
- 当解码内容是网址时自动调用浏览器打开

## 环境安装

推荐使用 Python 3.10。

```bash
pip install -r requirements.txt
```

本机课程设计环境示例：

```bash
conda create -n barcode_env python=3.10 pip -y
conda activate barcode_env
pip install -r requirements.txt
```

## 运行 GUI

```bash
python gui.py
```

界面按钮：

- 打开摄像头识别
- 停止摄像头
- 选择图片识别
- 保存当前结果

## 命令行运行

生成测试二维码和条形码：

```bash
python 1.py --make-samples
```

识别单张图片：

```bash
python 1.py data/sample_qrcode.png
```

只保存结果、不弹窗：

```bash
python 1.py data/sample_qrcode.png --no-window
```

打开摄像头实时识别：

```bash
python 1.py
```

摄像头窗口快捷键：

- `q`：退出
- `s`：保存当前结果

## 目录说明

```text
1.py              核心算法和命令行入口
gui.py            图形界面入口
data/             测试图片
outputs/          程序输出结果，默认不上传 GitHub
requirements.txt  Python 依赖
```

