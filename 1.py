import argparse
import csv
import datetime as dt
from pathlib import Path
from urllib.parse import urlparse
import webbrowser

import cv2
import numpy as np

try:
    import zxingcpp
except ImportError as exc:
    raise SystemExit(
        "缺少 zxing-cpp，请先运行：R:\\anaconda\\envs\\barcode_env\\python.exe -m pip install zxing-cpp"
    ) from exc


ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
OUTPUT_DIR = ROOT / "outputs"
OPENED_URLS = set()
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
TEXT_PREVIEW_LIMIT = 220


class DecodedItem:
    def __init__(self, fmt, text, points):
        self.format = fmt
        self.text = text
        self.points = np.array(points, dtype=np.int32)


def normalize_url(text):
    value = (text or "").strip()
    if value.startswith(("http://", "https://")):
        parsed = urlparse(value)
        if parsed.netloc:
            return value
    if value.lower().startswith("www."):
        return "https://" + value
    return None


def open_urls(decoded):
    for item in decoded:
        url = normalize_url(item.text)
        if url and url not in OPENED_URLS:
            OPENED_URLS.add(url)
            print(f"检测到网址，正在打开：{url}")
            webbrowser.open(url)


def preview_text(text, limit=TEXT_PREVIEW_LIMIT):
    value = (text or "").strip()
    if len(value) <= limit:
        return value
    return value[:limit] + "..."


def preprocess(frame):
    """Return an enhanced binary image used by the classical localization demo."""
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    grad_x = cv2.Sobel(blur, cv2.CV_32F, 1, 0, ksize=-1)
    grad_y = cv2.Sobel(blur, cv2.CV_32F, 0, 1, ksize=-1)
    gradient = cv2.convertScaleAbs(cv2.subtract(grad_x, grad_y))
    _, binary = cv2.threshold(gradient, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (21, 7))
    closed = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
    closed = cv2.erode(closed, None, iterations=2)
    closed = cv2.dilate(closed, None, iterations=2)
    return closed


def locate_barcode_candidates(frame):
    """Locate likely 1D barcode regions with gradients and contour filtering."""
    mask = preprocess(frame)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    boxes = []

    for contour in contours:
        area = cv2.contourArea(contour)
        if area < 1200:
            continue
        rect = cv2.minAreaRect(contour)
        width, height = rect[1]
        if width <= 0 or height <= 0:
            continue
        long_side = max(width, height)
        short_side = min(width, height)
        ratio = long_side / short_side
        if ratio < 1.6:
            continue
        box = cv2.boxPoints(rect).astype(int)
        boxes.append(box)

    return boxes


def locate_qr_finder_patterns(frame):
    """Find QR finder-pattern candidates by contour nesting like 回-shaped marks."""
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    binary = cv2.adaptiveThreshold(
        blur, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 5
    )
    contours, hierarchy = cv2.findContours(binary, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    if hierarchy is None:
        return []

    hierarchy = hierarchy[0]
    boxes = []
    used_centers = []

    for index, contour in enumerate(contours):
        area = cv2.contourArea(contour)
        if area < 80:
            continue

        child = hierarchy[index][2]
        if child == -1:
            continue
        grandchild = hierarchy[child][2]
        if grandchild == -1:
            continue

        x, y, w, h = cv2.boundingRect(contour)
        ratio = w / float(h)
        if not 0.65 <= ratio <= 1.35:
            continue

        center = (x + w // 2, y + h // 2)
        if any(abs(center[0] - px) < 10 and abs(center[1] - py) < 10 for px, py in used_centers):
            continue

        used_centers.append(center)
        boxes.append(np.array([[x, y], [x + w, y], [x + w, y + h], [x, y + h]], dtype=np.int32))

    return boxes


def decode_image(image):
    # zxing-cpp accepts OpenCV's native BGR arrays or grayscale arrays directly.
    return zxingcpp.read_barcodes(image, try_rotate=True, try_downscale=True, try_invert=True)


def enhance_for_decode(image):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
    equalized = cv2.equalizeHist(gray)
    binary = cv2.adaptiveThreshold(
        equalized, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 7
    )
    inverted = cv2.bitwise_not(binary)
    return [image, equalized, binary, inverted]


def add_decoded_item(items, seen, raw_item, fallback_points=None):
    text = (raw_item.text or "").strip()
    fmt = str(raw_item.format)
    key = (fmt, text)
    if not text or key in seen:
        return

    seen.add(key)
    if fallback_points is None:
        items.append(raw_item)
    else:
        items.append(DecodedItem(fmt, text, fallback_points))


def decode_barcodes(frame, candidates=None):
    """Decode QR codes and common barcodes, then retry on corrected candidate regions."""
    decoded = []
    seen = set()

    for image in enhance_for_decode(frame):
        for item in decode_image(image):
            add_decoded_item(decoded, seen, item)

    for box in candidates or []:
        corrected = perspective_correct(frame, box)
        if corrected.size == 0:
            continue
        corrected = cv2.copyMakeBorder(corrected, 18, 18, 18, 18, cv2.BORDER_CONSTANT, value=(255, 255, 255))
        if min(corrected.shape[:2]) < 120:
            corrected = cv2.resize(corrected, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)

        for image in enhance_for_decode(corrected):
            for item in decode_image(image):
                add_decoded_item(decoded, seen, item, fallback_points=box)

    return decoded


def barcode_points(barcode):
    if hasattr(barcode, "points"):
        return barcode.points
    pos = barcode.position
    points = [
        (int(pos.top_left.x), int(pos.top_left.y)),
        (int(pos.top_right.x), int(pos.top_right.y)),
        (int(pos.bottom_right.x), int(pos.bottom_right.y)),
        (int(pos.bottom_left.x), int(pos.bottom_left.y)),
    ]
    return np.array(points, dtype=np.int32)


def draw_results(frame, decoded, candidates=None, qr_patterns=None):
    result = frame.copy()

    for box in candidates or []:
        cv2.polylines(result, [box], True, (255, 180, 0), 2)

    for box in qr_patterns or []:
        cv2.polylines(result, [box], True, (255, 80, 80), 2)

    for item in decoded:
        points = barcode_points(item)
        cv2.polylines(result, [points], True, (0, 255, 0), 3)
        text = item.text if item.text else "<empty>"
        label = f"{item.format}: {text}"
        x, y = points[0]
        y = max(25, y - 10)
        cv2.putText(result, label[:80], (x, y), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

    return result


def order_points(points):
    rect = np.zeros((4, 2), dtype="float32")
    pts = points.astype("float32")
    s = pts.sum(axis=1)
    diff = np.diff(pts, axis=1)
    rect[0] = pts[np.argmin(s)]
    rect[2] = pts[np.argmax(s)]
    rect[1] = pts[np.argmin(diff)]
    rect[3] = pts[np.argmax(diff)]
    return rect


def perspective_correct(frame, points):
    rect = order_points(points)
    tl, tr, br, bl = rect
    width_a = np.linalg.norm(br - bl)
    width_b = np.linalg.norm(tr - tl)
    height_a = np.linalg.norm(tr - br)
    height_b = np.linalg.norm(tl - bl)
    max_width = max(1, int(max(width_a, width_b)))
    max_height = max(1, int(max(height_a, height_b)))

    dst = np.array(
        [[0, 0], [max_width - 1, 0], [max_width - 1, max_height - 1], [0, max_height - 1]],
        dtype="float32",
    )
    matrix = cv2.getPerspectiveTransform(rect, dst)
    return cv2.warpPerspective(frame, matrix, (max_width, max_height))


def save_rectified_regions(frame, decoded, prefix):
    OUTPUT_DIR.mkdir(exist_ok=True)
    saved = []
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    for index, item in enumerate(decoded, 1):
        points = barcode_points(item)
        corrected = perspective_correct(frame, points)
        path = OUTPUT_DIR / f"{prefix}_rectified_{index}_{stamp}.jpg"
        cv2.imwrite(str(path), corrected)
        saved.append(path)
    return saved


def save_result(image, prefix):
    OUTPUT_DIR.mkdir(exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    path = OUTPUT_DIR / f"{prefix}_{stamp}.jpg"
    cv2.imwrite(str(path), image)
    print(f"结果已保存：{path}")
    return path


def save_decoded_text(decoded, prefix):
    OUTPUT_DIR.mkdir(exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    path = OUTPUT_DIR / f"{prefix}_decoded_{stamp}.txt"
    with path.open("w", encoding="utf-8") as file:
        if not decoded:
            file.write("未检测到可解码的条形码或二维码。\n")
        for index, item in enumerate(decoded, 1):
            file.write(f"{index}. 类型：{item.format}\n")
            file.write(f"   内容：{item.text}\n\n")
    return path


def save_preprocess_images(frame, prefix):
    OUTPUT_DIR.mkdir(exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    mask = preprocess(frame)
    paths = []
    outputs = {
        "gray": gray,
        "blur": blur,
        "binary_morph": mask,
    }
    for name, image in outputs.items():
        path = OUTPUT_DIR / f"{prefix}_{name}_{stamp}.jpg"
        cv2.imwrite(str(path), image)
        paths.append(path)
    return paths


def analyze_frame(frame):
    candidates = locate_barcode_candidates(frame)
    decoded = decode_barcodes(frame, candidates)
    qr_patterns = locate_qr_finder_patterns(frame)
    result = draw_results(frame, decoded, candidates, qr_patterns)
    return {
        "decoded": decoded,
        "candidates": candidates,
        "qr_patterns": qr_patterns,
        "result": result,
    }


def image_files(folder):
    root = Path(folder)
    return sorted(
        path for path in root.rglob("*")
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
    )


def category_from_path(path):
    name = Path(path).stem
    parts = name.split("_")
    if len(parts) >= 3 and parts[0] == "qr":
        return parts[1]
    return Path(path).parent.name


def batch_test_folder(folder, save_visuals=True):
    files = image_files(folder)
    OUTPUT_DIR.mkdir(exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = OUTPUT_DIR / f"batch_report_{stamp}.csv"
    visual_dir = OUTPUT_DIR / f"batch_visuals_{stamp}"
    if save_visuals:
        visual_dir.mkdir(exist_ok=True)

    rows = []
    success_count = 0
    for path in files:
        frame = cv2.imread(str(path))
        if frame is None:
            rows.append({
                "file": str(path),
                "category": category_from_path(path),
                "success": "否",
                "count": 0,
                "formats": "",
                "contents": "无法读取图片",
            })
            continue

        analysis = analyze_frame(frame)
        decoded = analysis["decoded"]
        success = bool(decoded)
        success_count += int(success)

        if save_visuals:
            result_path = visual_dir / f"{path.stem}_result.jpg"
            cv2.imwrite(str(result_path), analysis["result"])

        rows.append({
            "file": str(path),
            "category": category_from_path(path),
            "success": "是" if success else "否",
            "count": len(decoded),
            "formats": " | ".join(str(item.format) for item in decoded),
            "contents": " | ".join(preview_text(item.text, 120) for item in decoded),
        })

    with csv_path.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=["file", "category", "success", "count", "formats", "contents"],
        )
        writer.writeheader()
        writer.writerows(rows)

    total = len(files)
    rate = (success_count / total * 100) if total else 0.0
    return {
        "csv_path": csv_path,
        "visual_dir": visual_dir if save_visuals else None,
        "rows": rows,
        "total": total,
        "success": success_count,
        "rate": rate,
    }


def run_image(path, show_window=True):
    frame = cv2.imread(str(path))
    if frame is None:
        raise SystemExit(f"无法读取图片：{path}")

    analysis = analyze_frame(frame)
    decoded = analysis["decoded"]
    open_urls(decoded)
    result = analysis["result"]

    print(f"检测到 {len(decoded)} 个可解码条码/二维码")
    for i, item in enumerate(decoded, 1):
        print(f"{i}. 类型：{item.format}，内容：{preview_text(item.text)}")

    save_result(result, "image_result")
    text_path = save_decoded_text(decoded, "image_result")
    print(f"完整识别文本已保存：{text_path}")
    rectified = save_rectified_regions(frame, decoded, "image_result")
    for path in rectified:
        print(f"校正区域已保存：{path}")
    if show_window:
        cv2.imshow("barcode/qrcode result", result)
        cv2.waitKey(0)
        cv2.destroyAllWindows()


def run_camera(camera_id):
    cap = cv2.VideoCapture(camera_id)
    if not cap.isOpened():
        raise SystemExit(f"无法打开摄像头：{camera_id}")

    print("摄像头已启动：按 q 退出，按 s 保存当前识别结果。")
    last_result = None

    while True:
        ok, frame = cap.read()
        if not ok:
            print("读取摄像头画面失败。")
            break

        analysis = analyze_frame(frame)
        decoded = analysis["decoded"]
        open_urls(decoded)
        result = analysis["result"]
        last_result = result

        cv2.putText(result, "q: quit  s: save", (15, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (40, 220, 255), 2)
        cv2.imshow("real-time barcode/qrcode detection", result)

        key = cv2.waitKey(1) & 0xFF
        if key == ord("q"):
            break
        if key == ord("s") and last_result is not None:
            save_result(last_result, "camera_result")

    cap.release()
    cv2.destroyAllWindows()


def make_samples():
    DATA_DIR.mkdir(exist_ok=True)

    import qrcode
    from barcode import Code128
    from barcode.writer import ImageWriter

    qr = qrcode.make("https://www.njit.edu.cn/")
    qr_path = DATA_DIR / "sample_qrcode.png"
    qr.save(qr_path)

    barcode_path = DATA_DIR / "sample_code128"
    Code128("NJIT2026BARCODE", writer=ImageWriter()).save(str(barcode_path))

    print(f"已生成二维码：{qr_path}")
    print(f"已生成条形码：{barcode_path}.png")


def make_qr_code(content, output_name=None):
    DATA_DIR.mkdir(exist_ok=True)

    import qrcode

    if not output_name:
        stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        output_name = f"custom_qrcode_{stamp}.png"
    if not output_name.lower().endswith(".png"):
        output_name += ".png"

    path = DATA_DIR / output_name
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=4,
    )
    qr.add_data(content)
    qr.make(fit=True)
    image = qr.make_image(fill_color="black", back_color="white")
    image.save(path)
    print(f"已生成二维码：{path}")
    print(f"二维码内容：{content}")
    return path


def parse_args():
    parser = argparse.ArgumentParser(description="条形码与二维码实时定位与解码系统")
    parser.add_argument("image", nargs="?", help="待检测图片路径；不填则打开摄像头")
    parser.add_argument("--camera", type=int, default=0, help="摄像头编号，默认 0")
    parser.add_argument("--make-samples", action="store_true", help="生成二维码和条形码测试图片")
    parser.add_argument("--make-qr", help="根据输入文字或网址生成二维码")
    parser.add_argument("--qr-output", help="二维码输出文件名，默认保存到 data/ 文件夹")
    parser.add_argument("--batch", help="批量识别指定文件夹，并生成 CSV 测试报告")
    parser.add_argument("--no-visuals", action="store_true", help="批量测试时不保存可视化结果图")
    parser.add_argument("--no-window", action="store_true", help="只保存结果，不弹出显示窗口")
    return parser.parse_args()


def main():
    args = parse_args()
    if args.make_samples:
        make_samples()
        return
    if args.make_qr:
        make_qr_code(args.make_qr, args.qr_output)
        return
    if args.batch:
        report = batch_test_folder(args.batch, save_visuals=not args.no_visuals)
        print(f"批量测试完成：{report['success']}/{report['total']}，成功率 {report['rate']:.2f}%")
        print(f"CSV 报告：{report['csv_path']}")
        if report["visual_dir"]:
            print(f"可视化结果：{report['visual_dir']}")
        return
    if args.image:
        run_image(Path(args.image), show_window=not args.no_window)
        return
    run_camera(args.camera)


if __name__ == "__main__":
    main()
