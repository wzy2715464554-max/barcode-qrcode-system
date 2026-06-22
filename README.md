# 条形码与二维码实时定位与解码系统

本项目是图像与视频信号处理课程设计程序，支持条形码和二维码的图片识别、摄像头实时识别、结果可视化和网址自动跳转。

## 功能

- 图片文件识别条形码和二维码
- 摄像头实时识别条形码和二维码
- 基于灰度化、滤波、梯度增强、二值化、形态学闭运算的条码候选区定位
- 基于轮廓层级关系检测二维码“回”字形定位角
- 对成功解码区域进行透视变换校正并保存
- 使用 ZXing-C++ 解码二维码、Code 128 等常见条码
- GUI 界面支持摄像头识别、文件识别、批量测试和保存结果
- 当解码内容是网址时自动调用浏览器打开
- 长文本二维码在界面中自动截断，完整内容保存为 txt 文件
- 批量测试文件夹并生成 CSV 测试报告
- 保存灰度图、滤波图、二值形态学图等预处理结果

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
- 批量测试文件夹
- 生成网址二维码
- 保存当前结果
- 保存预处理图
- 复制识别内容

## 命令行运行

生成测试二维码和条形码：

```bash
python 1.py --make-samples
```

把图片地址或网页地址生成二维码：

```bash
python 1.py --make-qr "https://example.com/test.jpg" --qr-output image_url_qrcode.png
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

批量识别文件夹并生成 CSV 报告：

```bash
python 1.py --batch data/complex_qr_samples
```

不保存批量可视化结果图：

```bash
python 1.py --batch data/complex_qr_samples --no-visuals
```

## 目录说明

```text
1.py              核心算法和命令行入口
gui.py            图形界面入口
data/             测试图片
data/complex_qr_samples/ 复杂场景二维码精选样例
outputs/          程序输出结果，默认不上传 GitHub
requirements.txt  Python 依赖
```

## 复杂场景数据

`data/complex_qr_samples` 中的样例来自 BoofCV QR Code benchmark，覆盖模糊、亮度变化、亮斑、破损、反光、透视倾斜、旋转、阴影、弯曲、多二维码等场景。

来源说明见：

```text
data/complex_qr_samples/SOURCE.txt
```
