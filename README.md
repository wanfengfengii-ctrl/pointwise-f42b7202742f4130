# 青榆小剧场字幕领播服务

文字编辑员把舞台监督提供的分段剧本定稿。场务将定稿绑定到登记屏开演，领播员按节目口令预取、点亮并处理勘误。场务收台后按实际点亮顺序复盘。

## 运行

使用 Python 3.11 标准库。从项目根目录运行以下命令。

```sh
python3 -B -m control.runtime serve --data-dir ./data --port 8765
python3 -B -m control.runtime demo
python3 -B check_project.py
python3 -B -m unittest discover -s tests -t .
```

`serve` 默认绑定本机 `127.0.0.1`，登记屏 P1 为六列。可用 `--screens` 指定 JSON 配置，例如 `{"screens":[{"screen":"P1","width":6}]}`。初始化只补缺失屏号。领播库 `control.sqlite3` 和屏端库 `display.sqlite3` 位于数据目录并分别提交。demo 在自己的临时目录用实际 HTTP 运行，样例输入在 `examples/`。`check_project.py` 由运行平台提供。

## HTTP

POST 接收 JSON 对象，GET 通过查询字符串传参。段号从 1 起。

| 方法 | 路径 | 输入 | 结果 |
| --- | --- | --- | --- |
| POST | `/publish` | `width`、`cues`，每条含 `cue`、`order`、`segments` | 201，稿号 `revision`、行宽及含正文和显示行的有序条段 |
| POST | `/open` | `show`、`screen`、`revision` | 200，场次的屏、初始稿和 `live` 阶段 |
| GET | `/preview` | `show`、`screen`、`cue`，可选 `segment` | 200，候选稿及一段或整条的排版行 |
| POST | `/advance` | `show`、`screen`、`cue`、`segment` | 200，已有实显的精确身份、稿号、序号和行，或 202 `pending` |
| POST | `/correct` | `show`、`screen`、`revision`、`request` | 200 `confirmed`，或 202 `pending` |
| GET | `/correction_status` | `show`、`request` | 同一勘误的结果，未查实返回 202 |
| POST | `/close` | `show` | 200，场次进入 `closed` |
| GET | `/history` | `show`、`screen` | 200，`events` 按实际点亮序返回条、段、稿号和序号 |

请求错误返回含 `error` 和 `message` 的 JSON。400 表示非法输入或不兼容稿，404 表示未知资源或不匹配的场屏，409 表示场次阶段、请求身份或播放顺序冲突。已结束场次仍可查询历史和原勘误结果。查询勘误只核实已提交的结果。需要重送尚未落实的勘误时，使用原请求号和原参数再次提交。

字幕条号唯一，`order` 为严格递增的正整数，每条有一至两段。定稿使用编辑员选定的正整数列宽。东亚宽度 W/F 占两列，其他基字符占一列，附着的组合标记占零列。按空白分词，词间加一个空格，超宽词按字符单元硬断。段内换行随定稿保存，预取与点亮都使用这些行。勘误可改正文和显示行，保持条号、条序与分段数。

预取只返回候选。不确定期间，尚未开条的首段等待核实，已开条的尾段按开条稿继续。屏端实际点亮时才取得实显序号。迟到的旧指令不能开条，迟到或重复的实显回报不会改写历史。样例先用 R1 点亮 C17 首段，再换 R2，C17 尾段用 R1，C18 首段用 R2。
