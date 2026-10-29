<p align="center">
  <img src="/images/URTC_VISION_TOOL_BANNER.svg" alt="URTC Visión Tool Logo" width="100%">
</p>

# 👁️ URTC-VISION-TOOL

<p align="center"><a href="README.md">🇺🇸 English</a> | <a href="README_spa.md">🇪🇸 Español</a> | <a href="README_fra.md">🇫🇷 Français</a> | <a href="README_ita.md">🇮🇹 Italiano</a> | <a href="README_deu.md">🇩🇪 Deutsch</a> | <a href="README_zho.md">🇨🇳 简体中文</a> | 🇯🇵 <b>日本語</b> | <a href="README_por.md">🇵🇹 Português</a></p>

### 🔬 熱画像と RGB 知覚を統合したエンドエフェクター

<p align="center">
  <img src="https://img.shields.io/badge/Licencia-GPL%203.0-blue.svg" alt="GPL 3.0">
  <img src="https://img.shields.io/badge/Sensors-Thermal%20%2B%20RGB-orange.svg" alt="Sensors">
  <img src="https://img.shields.io/badge/Platform-URTC%20%2F%20CAN-blue.svg" alt="Platform">
  <img src="https://img.shields.io/badge/Stack-C%20%2F%20Python-3776AB.svg" alt="C/Python">
</p>

---

**正直な現状確認 - 実際に今動くもの:** ファームウェア側のセンサープロトコル（`sensor_frame.c`、`sensor_reading.c`、`rate_limiter.c`、`sensor_freshness.c`、`sensor_diagnostics.c`、`vision_sensor_link.c`）は本物の純粋な C で、165 件の `TEST_ASSERT` チェック（`tests/test_*.c`、ホストの C コンパイラでコンパイル・実行）がすべて通過しており、このリポジトリの CI が実際に実行しています：`.github/workflows/ci.yml` のファームウェアステップが `build_firmware.sh` を呼び出し、そのステップ 2 が STM32 ビルドの前に必ず `tests/` をコンパイル・実行します。ホスト側の `vision_companion` パッケージ（`alignment.py`、`cli.py`）も本物で、183 件の pytest ケースがすべて通過しており、CI はこのスイートも実行します（専用ステップが `src/vision_companion/requirements.txt` をインストールし、そこで `pytest tests/` を実行）。したがって、どちらの側の退行もビルドを失敗させます。README の冒頭にある通り、このボードの PCB／回路図はまだ存在しないため、ここにあるものは本物の MLX9064x センサーや RGB カメラを読んだことも、本物の CAN トランシーバーを駆動したこともありません——`main.c`/`startup_stm32_minimal.c` は、仮のリンカースクリプトで Cortex-M4F のクロスコンパイルとリンクが成功することを示すだけです。何がリリースされたかは `CHANGELOG.md` を参照してください。

---

> **安全性とセキュリティの現状:** このエコシステムは認証された安全システムではなく、実装済みの URTC 基板もまだ存在しません。ブートローダーはファームウェアイメージを CRC32 と共有鍵の HMAC-SHA256 で検査しており、非対称署名ではありません(予定)。公開されているアプリケーションイメージは公開の開発用鍵(`signing_key_kind: dev`)で署名されているため、誰でもブートローダーが受け入れるイメージを作れます。実際の基板には何も送信されていません。ここに書かれた内容を人の安全のために頼る前に、[セキュリティベースライン](https://github.com/JuanenRac/URTC-DOCS/blob/main/docs/SECURITY_BASELINE.md)と[脅威モデル](https://github.com/JuanenRac/URTC-DOCS/blob/main/docs/THREAT_MODEL.md)をお読みください。

## 📋 ひと目で

| | |
|---|---|
| バージョン | `0.1.5` |
| 成熟度 | 機能する |
| テスト | 183 (`pytest`) |
| 技術 | C / STM32 / Python vision companion |
| 対象 | マイコン基板（ファームウェア）。ビルドは PC で行います |
| 実機での確認 | まだです：このバージョンについて実機での動作記録はありません |

**移動先：** [概要](#-概要) · [アーキテクチャ](#-アーキテクチャ) · [機能](#-機能) · [セキュリティ](#-セキュリティと安全) · [インターフェース](#-インターフェース) · [クイックスタート](#-クイックスタート) · [テスト](#-テスト) · [構成](#-リポジトリの構成) · [関連](#-関連プロジェクト)

<!-- urtc-section:status_vision_tool -->
## 🚦 プロジェクトの状況

🟢 完了・検証済み · 🟡 動作するが既知の制限あり · 🟠 途中、または未検証 · 🔴 未実施または動作しない。実機で一度も動いていないものは緑になりません。

| 項目 | 状態 | リポジトリが示せること |
| --- | :---: | --- |
| ソフトウェア | 🟡 | PC とシミュレーターでは動作します。実際のボードでは一度も実行していません。 |
| テスト | 🟢 | テストスイートはプッシュごとに CI で通ります。 |
| 実機 | 🟠 | 実際のボードでの実行はまだありません。ベンチテストは未実施です。 |
| ドキュメント | 🟡 | 8 言語の README と参照ドキュメントがあります。翻訳はネイティブによるレビューを受けていません。 |

<!-- /urtc-section:status_vision_tool -->

## 🎯 概要

**URTC-VISION-TOOL** は、視覚的知覚と熱知覚を単一の URTC 互換エフェクター
に統合した専用のロボット工具ヘッドです。高度な QA、PCB の熱画像検査、
高精度なピック＆プレースアライメント向けに設計されています。

RGB グローバルシャッターカメラと MLX9064x ファミリーの熱センサーを搭載し、
視覚 AI ノードにデュアルモーダルデータを提供します。これにより、部品の
存在だけでなく、その動作温度やはんだの放熱状況も検知できます。

この基板にはまだ PCB/回路図が存在しないため（`hardware/` 参照）、以下の
どの機能も実際の熱画像/RGB センサーを駆動することはできません——しかし
ファームウェアツールチェーンとホスト側の視覚処理パイプライン（合成フレーム
生成、疑似カラーレンダリング、RGB->熱画像 ROI アライメントと温度統計抽出、
すべて pytest でカバー）は今日すでに本物であり、動作します。

### 主な機能：
* 🔬 **デュアルモーダル知覚** — 同期された熱画像と RGB 画像のキャプチャ。*（両フレームが供給する処理パイプライン自体は本物です——下記参照。実際の同期キャプチャには PCB とセンサーが必要です。）*
* 🌡️ **高精度熱画像** — 統合された MLX90640/41/42 センサーサポート。*（疑似カラーレンダリングと領域ごとの統計抽出は本物です——下記参照。実際の MLX9064x を I2C 経由で読み取るには PCB が必要です。）*
* 🎯 **Eye-in-Hand アライメント** — サブミリメートル単位の PnP と AOI（自動光学検査）。*（RGB->熱画像 ROI 座標マッピングと温度統計抽出は本物でテスト済みです——下記の `vision_companion/alignment.py` 参照。サブミリメートル精度には実際に校正されたカメラが必要です。）*
* 📡 **URTC との統合** — 決定済み：このヘッドは URTC の工具ヘッドであり、第二のプロトコルではなく、URTC の熱画像検査ツール（工具プロファイル 22、MLX90640/90641/90642）とその CAN メッセージ `0x250`-`0x255`（トリガー、ステータス、生および校正済みのピクセルブロック。URTC の `docs/CANBUS.TXT` に記載）を再利用します。このやり取りのホスト側は本物で、ハードウェアなしでテスト済みです（`urtc_thermal.py`、模擬ヘッド付き）。ヘッドのファームウェア、CAN トランシーバー、実装済み基板はまだ存在しないため、バス上で動いたことはありません。*（このリポジトリのセンサー側フレームプロトコル（下記）は、ホストでテスト済みの別個の部品であり、熱画像は運びません。）*
* 🔒 **センサープロトコルの範囲チェック** — バージョン管理されたフレーミング、CRC8 チェックサム、測定範囲検証、レート制限、フレームの鮮度チェック（シーケンスとタイムスタンプ）、そして制御判断とは独立した専用のエラー/レイテンシ/バスリセット診断カウンター。フレームのバージョン 2：複数バイトの値（タイムスタンプと温度の読み取り値）はすべてバスと同じビッグエンディアンで、バージョン 1 のフレームは拒否されます。*（純粋な C として実装され、PC 上でのみテスト済みです。ボードや実際のセンサーで動作したことはなく、安全機能でもありません）*
* ✅ **Cortex-M4F ファームウェアツールチェーン** — 兄弟リポジトリ URTC と URTC-SMART-RACK と同じツールチェーンを用いて、`arm-none-eabi-gcc` でクロスコンパイルおよびリンクされる実際のベアメタルイメージ。*（実装済み——下記の「ビルド」を参照）*
* ✅ **`vision_companion` 処理パイプライン** — 実際に動作する Python パッケージ：合成された熱画像+RGB フレーム生成、疑似カラー熱画像レンダリング、RGB->熱画像 ROI アライメント + 温度統計抽出、統計レポート、183 件の実際の pytest ケースでカバー、ハードウェア接続なしでエンドツーエンドに実行可能。*（実装済み——下記の「VISION COMPANION」を参照）*

## 🧩 URTC での役割

URTC-VISION-TOOL は RGB カメラと MLX9064x 熱センサーを一体にしたツールヘッドで、品質検査、基板の熱検査、実装ヘッドの位置合わせに使います。URTC のツールヘッドで、2 つ目のプロトコルを作る代わりに URTC の熱検査ツールとその CAN メッセージ `0x250` から `0x255` を再利用し、ビジョンノード（Hailo-8）と HYDRA-UMC コントローラーに 2 種類のデータを渡すので、部品を有無だけでなく温度でも判断できます。現時点で実在するのは、ファームウェアのセンサープロトコルとホスト側のビジョンコンパニオンで、どちらもコンピューター上で試験されています。ボードはまだ存在しません。補完的なツールで、URTC の子ではありません。

## 🏛️ アーキテクチャ

<p align="center">
  <img src="images/architecture.svg" alt="URTC-VISION-TOOL のアーキテクチャ：誰が使い、何を持ち、何に依存するか" width="100%">
</p>

このリポジトリの各部分の関係：誰が使い、何を持ち、何に依存するか。図は `docs/architecture.json` から描かれ、コードと照合されます。

<details>
<summary>図のテキスト版 (Mermaid)</summary>

```mermaid
flowchart LR
    TOOL["URTC-VISION-TOOL"] --> RGB["RGB Camera (USB 3.0)"]
    TOOL --> THRM["Thermal Sensor (CAN / I2C)"]
    RGB --> VISION["VISION-NODE (Hailo-8)"]
    THRM --> CORE["HYDRA-UMC Core (STM32)"]
    VISION --> SYNC["Multi-Modal Fusion"]
    CORE --> SYNC
    SYNC --> DASH["Studio Dashboard"]
```

</details>

### アーキテクチャと設計上の決定

* **本プロジェクトが 2 つの独立したバージョン管理系統を持つ理由。** `src/firmware_common.h`（STM32 側のファームウェア）と `src/vision_companion/vision_companion/__init__.py`（独立したホスト側 Python パッケージ）は独立してバージョン管理されています——異なるハードウェア（MCU 対ホストの CM5/PC）上で動作し、異なるスケジュールで出荷されるためです。
* **URTC 自体の子プロジェクトではない理由。** URTC-SMART-RACK 自身の README と同じ理由です——URTC のファームウェアの慣例を共有する補完ツールであり、その統合階層の一部ではありません。
* **そもそもホスト側のコンパニオンパッケージが必要な理由。** 熱画像/RGB のデュアルモーダルキャプチャには、STM32 自体で実行する場所のない実際の画像処理（numpy/Pillow）が必要です——このコンパニオンパッケージは、実際にその処理が行われる場所です。独自のバスアクセスはありませんが、URTC の熱画像検査メッセージを話します（`urtc_thermal.py`）：要求を組み立て、16 ピクセルのブロックを画像に組み直し、メッセージをバスを運ぶ側に渡します。
* **`alignment.py` が実際のホモグラフィではなく共有視野を前提とする理由。** 両方のセンサーは同じ剛体の工具ヘッド上にあるため、RGB 空間と熱画像空間のピクセル座標間で軸ごとの線形再スケーリングを行うのは妥当な v0 近似です——実際のピクセル単位のキャリブレーション（チェッカーボード、レンズ歪み）には、まだ存在しない実際のカメラでの校正が必要です。
* **エコシステムの他の部分との関係。** URTC 自身の工具エコシステムの一員であり（URTC の熱画像検査ツールとその CAN メッセージを再利用、上記参照）、URTC-SMART-RACK も担っているのと同じ視覚認識の役割を果たす HYDRA-UMC-DETECTION-HEF と自然に組み合わされます。
* **センサーフレームプロトコルが独自のタイムスタンプフィールドを持つ理由。** 実際のセンサー側ミリ秒単位のタイムスタンプにより、呼び出し元は、MCU がいつそのフレームの解析にたどり着くかとは無関係に、読み取りが実際に*いつ*行われたかを知ることができます——単に「たった今届いた」という前提では失われてしまう、履歴管理/診断における実際の価値です。
* **診断カウンター（`sensor_diagnostics.c`）が自ら受理/拒否の判断を一切行わない理由。** フレームが信頼できるかどうかを決定するのは `sensor_frame.c`（フレーミング）、`sensor_reading.c`（範囲）、`rate_limiter.c`（レート制限）のみであり——診断はそれらが決定した結果を記録するだけです。この境界を厳格に保つことで、診断側のバグが誤って不正なデータを通過させてしまうことは決してなくなります。これは診断ノート自身が言う「separar diagnostico de salida de control」そのものです。

## ✨ 機能

**領域ごとの熱検査、系列の書き出し、センサーのドリフト、ラック確認(ホストでのテストのみ):** `inspect` は、計画にある各部品を種類ごとの温度ルールで判定し、各領域の最小・最大・平均を HYDRA-UMC データレイク向けのサンプル、JSON 行、OPC-UA ノード値として書き出せます。`drift-check` は基準シーンのフレームを基準データと比べ(不良画素、オフセットのドリフト)、校正ファイルを書き出せます。`rack-check` は熱フレームからツールラックの先端を判定します。`rack-watch` はラックの加熱中に先端を追い、各スロットがいつ目標に達したか、工具を交換してよいかを示します。`rack-simulate` は模擬ラック(正常または異常あり)のフレームを書き出し、カメラなしで試せます。ラックのコマンドは 8 言語で表示します(`--lang`)。[CLI リファレンス](docs/CLI_REFERENCE.md)を参照してください。合成フレームでのみ実行しており、カメラも基板も使っていません。

**シリアル CAN アダプター経由の熱画像取得（新規、模擬アダプターと模擬ヘッドでのみ確認）:** `capture --port PORT` は、熱検査ツールを載せた URTC ヘッドから、SLCAN アダプター（シリアルポートまたは pyserial の URL）を通して `0x250` から `0x255` のやり取りで校正済みの画像を 1 枚読み取り、`.npy` と擬似カラー PNG として保存します。これは `inspect`、`drift-check`、`rack-check` にそのまま渡せます。ヘッドがエラーを報告する、準備完了にならない、またはブロックに応答しない場合は、分かりやすいメッセージでコマンドを終了します（終了コード 1）。開けないポートの場合は終了コード 2 で終了します。実際のアダプター、バス、ヘッドでは実行していません。

## 🔒 セキュリティと安全

| 脅威 | 防御 |
|---|---|
| センサーからの壊れた、または古いフレーム | バージョン付きフレームと CRC-8（`sensor_frame.c`）。バージョン 2 ではタイムスタンプと熱の読み取り値を含む複数バイトの値はバスと同じビッグエンディアンで、バージョン 1 のフレームは拒否されます |
| センサーが出せないはずの読み取り値 | `sensor_reading.c` が熱の読み取り値をデコードし、範囲外のものを拒否します |
| フレームの洪水 | `rate_limiter.c` が最小間隔でフレームを保留します |
| 再生されたフレームや固まったセンサー | `sensor_freshness.c` がシーケンスとセンサー自身のタイムスタンプを検査します |
| カウンターの不具合で不正なデータが通ること | `sensor_diagnostics.c` は他のモジュールの判断（エラー、遅延、バスのリセット）を記録するだけで、フレームを受理も拒否もしません |

これはすべてコンピューター上で試験された純粋な C で、ボード上でも実際のセンサーでも動いたことはなく、安全機能でもありません。

## 🔌 インターフェース

* **URTC の熱検査メッセージ**（`0x250` から `0x255`：トリガー、状態、生および校正済みのピクセルチャンク。URTC の `docs/CANBUS.TXT` に記載）：このやり取りのホスト側は `urtc_thermal.py` で、ハードウェアなしに模擬ヘッドで試験されています。`capture --port PORT` は SLCAN アダプター（シリアルポートまたは pyserial URL）経由でこれを実行し、画像を `.npy` と擬似カラー PNG で保存します。ヘッドがエラーを報告する、準備完了にならない、チャンクに応答しない場合は終了コード 1 で、ポートを開けない場合は終了コード 2 で終わります。
* **ファームウェアのセンサーフレーム：** バージョン 2、ビッグエンディアン、CRC-8（`sensor_frame.c`）。独立したホスト試験済みの部品で、熱画像は運びません。
* **コマンドライン `vision-companion`：** `version`、`selftest`、`analyze-roi`、`capture`、`inspect`、`drift-check`、`rack-check`、`rack-watch`、`rack-simulate`。各オプションと終了コードは [docs/CLI_REFERENCE.md](docs/CLI_REFERENCE.md) にあります。
* **エクスポート：** `inspect` の読み取り値は JSON Lines、OPC UA ノード値、HYDRA-UMC データレイク用のサンプルとして書き出せます。

## 🚀 クイックスタート

ARM GNU ツールチェーン（`arm-none-eabi-gcc`、`arm-none-eabi-objcopy`、
`arm-none-eabi-size`）と Python 3 が必要です。

```bash
# Linux/macOS
chmod +x build_firmware.sh   # 初回のみ
./build_firmware.sh

# Windows
build_firmware.bat
```

### ビジョンコンパニオン（ホスト側 Python）

この部分は今日、ハードウェアを一切接続することなく完全に動作します：

```bash
cd src/vision_companion
python3 -m venv .venv
# Linux/macOS：
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m vision_companion selftest

# Windows：
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python -m vision_companion selftest
```

`selftest` は、MLX9064x 形式に合わせた合成熱画像フレーム（32x24、はんだ
ごて先のようなホットスポット付き）と、合成 RGB カラーバーテストパターン
を生成し、両方を実際のファイルとしてレンダリング/保存し、その統計情報を
表示します——これは、実際のハードウェアが存在するようになった時点で実装
されるセンサーキャプチャのステップとは独立して、numpy/Pillow の処理
パイプラインが本当に機能することの証明です。

`analyze-roi X0 Y0 X1 Y1` は、RGB 空間のバウンディングボックスを熱画像
空間にマッピングし、その領域の実際の温度統計を報告します——README の
「Eye-in-Hand Alignment」機能の背後にあるアライメントロジックで、今日
実際に動作します：

```bash
.venv/bin/python -m vision_companion analyze-roi 280 210 360 270
```

実際の出力例：

```text
RGB ROI (280,210)-(360,270) in a 640x480 frame
  -> thermal stats: min=75.67C max=78.97C mean=77.69C p95=78.70C (16 thermal px)
```

183 件の実際の pytest ケースが `cli.py`、`alignment.py`、およびパッケージのその他のモジュールをカバー
します：

```bash
pip install -e ".[dev]"
pytest
```

完全なコンパニオンドキュメントについては `src/vision_companion/README.md`
を、実際に取得した出力付きの全コマンド・フラグ・終了コード一覧については
[`docs/CLI_REFERENCE.md`](docs/CLI_REFERENCE.md) を参照してください。

<!-- urtc-section:compatibility -->
### 要件と互換性

どのバージョンの URTC プログラムが連携して動作し、それぞれがどのプロトコルバージョンを話すかは、URTC-COMMON が生成する互換性表に載っています：[docs/COMPATIBILITY.md](https://github.com/JuanenRac/URTC/blob/main/docs/COMPATIBILITY.md)。
<!-- /urtc-section:compatibility -->

## 🧪 テスト

テストは 2 系統あります。ファームウェア側は `tests/` の C（165 件の `TEST_ASSERT` 検査）で、センサーフレーム、読み取り値、レート制限、診断、鮮度、リンク全体のシナリオ、不正な入力への堅牢性、URTC-COMMON の共有ベクトルを扱い、コンピューター自身の C コンパイラーでコンパイル・実行し、CI では AddressSanitizer、UBSan、カバレッジ下限も使います。ホスト側は `vision_companion` パッケージで、183 件の pytest ケース（`cd src/vision_companion && pytest`）がハードウェアなしでパイプライン全体を動かします：合成画像、疑似カラー、位置合わせ、校正、模擬ヘッドに対する熱画像の取得、検査、ドリフト、ラックの検査です。4 つの Python テストファイルがビルドスクリプト、リリースの成果物、バージョンファイルを検査します。`bash build_firmware.sh` はクロスコンパイルの前に C のテストを実行し、アサーションが 1 つでも失敗すると失敗します。

## 🏗️ ビルドとリリース

ビルドはまず `tests/` を*コンピューター自身の* C コンパイラー（`arm-none-eabi-gcc` ではありません。純粋なロジックのテストで、MCU のレジスタには触れません）でコンパイル・実行し、アサーションが 1 つでも失敗するとビルド全体が失敗します。その後はじめて `main.c` と `startup_stm32_minimal.c` を Cortex-M4F 用にコンパイルし、仮の `STM32_MINIMAL.ld` メモリマップとリンクして、バージョン付きの `.elf`/`.bin`/`.hex` を `firmware/` に出力します。ビルドがバージョンを変えることはありません。

`src/` 以下のすべてのモジュールも Cortex-M4F 用にコンパイルされ、検査としてまとめてリンクされます（ターゲットには C ライブラリがありません）。現時点でイメージに入っているのは `main.c` と起動ファイルだけです。`URTC_CI=1` を設定すると、バージョン管理されたファイルには一切触れません。

実際のハードウェアにフラッシュできるものは
今のところ何もありません——対象の STM32 部品、ピン配置、MLX9064x の配線、
RGB カメラインターフェースを確認できる PCB が存在しないためです。

ファームウェアイメージ（`.bin`、`.hex`、`.elf`）は git で管理されません。リリースビルドは `firmware/URTC_VISION_TOOL_FIRMWARE_v<バージョン>.*` に書き出し（git の無視対象。CI モード、つまり `URTC_CI=1` では `build/firmware`）、各バージョンの GitHub リリースのアセットとしてのみ公開されます。`python tools/publish_release_assets.py` がファイルを検査し、不足している `.sha256` ファイルを書き出して、添付するファイルを含む正確な `gh release create` コマンドを表示します。

バージョンの全履歴は [`CHANGELOG.md`](CHANGELOG.md) を参照してください。各バージョンにそれぞれの項目があります。

## 📂 リポジトリの構成

<p align="center">
  <img src="images/repository-structure.svg" alt="URTC-VISION-TOOL のリポジトリ構成" width="100%">
</p>

<details>
<summary>ツリーのテキスト版</summary>

```text
URTC-VISION-TOOL/
├── src/                                               ファームウェア（純粋な C のセンサープロトコル、URTC-COMMON の検査済みコピー、エントリーポイント、仮のリンカースクリプト）と Python コンパニオン
├── tests/                                             C のホストテスト（165 件の検査）とビルドスクリプトの Python 検査
├── docs/                                              CLI_REFERENCE.md：すべてのコマンドと終了コード
├── hardware/                                          回路図も PCB もまだありません
├── tools/                                             ビルド、カバレッジ、リリースのツール
├── images/                                            バナーとこの README の画像
├── .github/                                           CI ワークフローと Issue・プルリクエストのテンプレート
├── build-test.sh build-test.bat                       リポジトリを変更しないビルド・テストのスクリプト
├── test.sh test.bat                                   テストを実行
├── urtc.project.json                                  マニフェスト：バージョン、役割、成熟度、ビルドコマンド
├── CHANGELOG.md                                       各バージョンの変更内容
├── SECURITY.md SUPPORT.md LICENSE                     セキュリティポリシー、サポート、ライセンス
├── CONTRIBUTING.md CODE_OF_CONDUCT.md                 貢献方法と行動規範
├── .gitattributes .gitignore                          Git の設定
├── build_firmware.sh build_firmware.bat               ホストテスト、クロスコンパイル、公開
├── bump.py bump_version.py bump_manifest_version.py   バージョンを上げるスクリプト
└── LICENSE.md ruff.toml                               ドキュメントのライセンスと lint 設定
```

</details>

各ソースファイルの注釈付き一覧（1 ファイル 1 行）は [docs/SOURCE_MAP.md](docs/SOURCE_MAP.md) にあります。

## 🗺️ ロードマップと既知の制限

**現時点で分かっている制限**

* このボードにはまだ PCB も回路図もありません（`hardware/` 参照）。ここにあるものは、実際の MLX9064x を I2C で読んだことも、RGB カメラや CAN トランシーバーを動かしたこともありません。`main.c` と起動ファイルが示すのは、仮のリンカースクリプトで Cortex-M4F 向けのクロスコンパイルとリンクが通るということだけです。
* ヘッドのファームウェアはまだ存在しません。熱データのやり取りのホスト側は、模擬ヘッドと模擬 SLCAN アダプターに対してだけ試験されています。
* `alignment.py` は視野が共通であると仮定し、各軸を線形に拡縮します。本当のピクセル単位の校正（チェッカーボード、レンズ歪み）には実際のカメラが必要です。
* サブミリ単位の精度、同期した実際の取得、検査ルールの温度の限界は、実際の部品では試していません。

**次のステップ**

* ボードを設計し、STM32 の部品とカメラのインターフェースを決め、センサーとカメラのドライバーを書き、試験台で実際のヘッドに対して熱画像の取得を実行します。

## 🌍 言語

README とテキストは、英語、スペイン語、フランス語、イタリア語、ドイツ語、中国語、日本語、ヨーロッパポルトガル語で提供されています。

## 🔗 関連プロジェクト

本プロジェクトは、同じ作者(JuanenRac / Electro Hobby 3D)による HYDRA-UMC ロボティクスエコシステムの一部です。リクエストが実はこの中のどれかについてのものである可能性があるため、知っておく価値があります。

**直接関連**
- **[URTC](https://github.com/JuanenRac/URTC)** — 物理的な Universal Robot Tool Controller 基板向けファームウェア、CAN バス経由の 25 以上のツールプロファイル ——同じ CAN バス上の、同じツールエコシステム。
- **[HYDRA-UMC-DETECTION-HEF](https://github.com/JuanenRac/HYDRA-UMC-DETECTION-HEF)** — Hailo アーキテクチャ/チェックサムによる安全読み込み検証を備えた、実際のコンパイル済みモデルレジストリ ——視覚認識という役割における兄弟。
- **[URTC-TESTER](https://github.com/JuanenRac/URTC-TESTER)** — URTC 基板向けのデスクトップ CAN バスライブ診断ツール、ツールプロファイルごとに 1 パネル ——その独自のライブ CAN バス診断は、同じツールヘッドに対する本ツールの視覚的品質保証チェックを補完する。

**エコシステムの他のプロジェクト**

*コアハードウェア&プラットフォーム*
- **[HYDRA-UMC](https://github.com/JuanenRac/HYDRA-UMC)** — ロボットアームのマザーボードの設計——CM5 ホスト + デュアルコア STM32H745、CAN-OTA/SPI-OTA 経由で最大 8 本のツールアームを統括することを目指す(ファームウェアは初期段階で、実装済みの基板はまだない)。
- **[HYDRA-UMC-OS](https://github.com/JuanenRac/HYDRA-UMC-OS)** — CM5 向けの再現可能な Raspberry Pi OS プロダクト層——読み取り専用エージェント、検証済み設定/プロファイル、WiFi 初回接続プロビジョニング。
- **[HYDRA-UMC-SDK](https://github.com/JuanenRac/HYDRA-UMC-SDK)** — すべてのブリッジが自身のコマンドを検証する共有 JSON-Schema 契約とソフトウェアのジョブゲート境界(認証済みの安全機能ではない)。
- **[HYDRA-UMC-CONNECTOR-HUB](https://github.com/JuanenRac/HYDRA-UMC-CONNECTOR-HUB)** — 外部マシン用コネクタのための宣言的アダプターマニフェストのレジストリとバリデーター。SDK 自身の契約という発想を外部マシンにまで拡張し、産業用ゲートウェイ系のプロジェクトを置き換えることはありません。

*コアバックエンド&クライアント*
- **[HYDRA-UMC-SERVER](https://github.com/JuanenRac/HYDRA-UMC-SERVER)** — すべての制御クライアントが実際に通信する、本物のヘッドレスバックエンド(REST/WebSocket)。
- **[HYDRA-UMC-STUDIO](https://github.com/JuanenRac/HYDRA-UMC-STUDIO)** — リアルタイムのマルチロボット 3D 可視化を備えたウェブ制御ダッシュボード。
- **[HYDRA-UMC-SUITE](https://github.com/JuanenRac/HYDRA-UMC-SUITE)** — 複数のサーバーを同時に扱えるデスクトップ(PySide6)スウォームコマンドセンター、スタンドアロン実行ファイルとしてパッケージ化。
- **[HYDRA-UMC-ANDROID-CONTROL](https://github.com/JuanenRac/HYDRA-UMC-ANDROID-CONTROL)** — 生体認証ログインとペアリングされた Wear OS コンパニオンを備えたネイティブ Android 制御アプリ。
- **[HYDRA-UMC-IOS-CONTROL](https://github.com/JuanenRac/HYDRA-UMC-IOS-CONTROL)** — リアルタイム WebSocket 同期を備えた iOS/iPadOS 制御アプリ(Flutter)。
- **[HYDRA-UMC-DSI](https://github.com/JuanenRac/HYDRA-UMC-DSI)** — 本体搭載の 7 インチ DSI タッチスクリーン向けネイティブタッチ UI、CM5 自体に組み込み。
- **[HYDRA-UMC-EDITOR-URDF](https://github.com/JuanenRac/HYDRA-UMC-EDITOR-URDF)** — 完成したモデルを STUDIO 自身のカタログへ送信するデスクトップ用グラフィカル URDF 作成/編集ツール。
- **[HYDRA-UMC-EDITOR-STL](https://github.com/JuanenRac/HYDRA-UMC-EDITOR-STL)** — HYDRA-UMC-EDITOR-URDF も編集する同じモデルカタログ内で、実在するパーツを変換/置換/削除/追加するデスクトップ STL モデルエディタ。
- **[HYDRA-UMC-BRIDGE-AMR](https://github.com/JuanenRac/HYDRA-UMC-BRIDGE-AMR)** — VDA 5050 MQTT パブリッシャーによる AGV/AMR フリートの調整境界(エミュレートしたフリートに対してのみテスト済み)。
- **[HYDRA-UMC-BRIDGE-CNC](https://github.com/JuanenRac/HYDRA-UMC-BRIDGE-CNC)** — GRBL ステータス/制御バイトへのアクセスを持つ、CNC セルの高レベルコーディネーター(エミュレーターに対してのみテスト済み)。
- **[HYDRA-UMC-BRIDGE-DROIDS](https://github.com/JuanenRac/HYDRA-UMC-BRIDGE-DROIDS)** — Boston Dynamics Spot コマンド送信機能を持つ、脚型/ヒューマノイドドロイドの調整境界(エミュレーターに対してのみテスト済み)。
- **[HYDRA-UMC-BRIDGE-LASER](https://github.com/JuanenRac/HYDRA-UMC-BRIDGE-LASER)** — キー/筐体/インターロックの GPIO 信号 3 系統を読み取るレーザーセルのコーディネーター(模擬チップに対してのみテスト済み。レーザーの武装や発射はできない)。
- **[HYDRA-UMC-BRIDGE-OPENPNP](https://github.com/JuanenRac/HYDRA-UMC-BRIDGE-OPENPNP)** — OpenPnP ピックアンドプレースの基板フローを安全に統括する高レベルコーディネーター。
- **[HYDRA-UMC-BRIDGE-PRINTER3D](https://github.com/JuanenRac/HYDRA-UMC-BRIDGE-PRINTER3D)** — 実際にゲート制御されたジョブコマンドを持つ、Moonraker/Klipper 3D プリンター向けの安全な調整境界。
- **[HYDRA-UMC-BRIDGE-ROS2](https://github.com/JuanenRac/HYDRA-UMC-BRIDGE-ROS2)** — 遅延インポートの rclpy ROS 2 トランスポートを持つコーディネーター(ROS 2 環境ではまだ実行していない)。
- **[HYDRA-UMC-BRIDGE-UAV](https://github.com/JuanenRac/HYDRA-UMC-BRIDGE-UAV)** — MAVLink コマンド送信機能を持つ、カメラ搭載 UAV の調整境界(エミュレーターに対してのみテスト済み)。

*URTC ツールプラットフォーム*
- **[URTC-FLASHER](https://github.com/JuanenRac/URTC-FLASHER)** — URTC 基板用のデスクトップ GUI 書き込みツール、CAN-OTA およびフルチップ SWD/JTAG。
- **[URTC-COMMON](https://github.com/JuanenRac/URTC-COMMON)** — 一度だけ書かれた CAN プロトコルのデータ（仕様、生成された表、適合ベクトル）と、各プログラムが共有するコード。このリポジトリは使用する部分のコピーを含みます。
- **[URTC-GATEWAY](https://github.com/JuanenRac/URTC-GATEWAY)** — CAN バスの手前に置き、一覧にある識別子だけを通し、レートを制限し、セッション鍵を求めるゲートウェイ。
- **[URTC-WEB-STUDIO](https://github.com/JuanenRac/URTC-WEB-STUDIO)** — Web Serial API を使ったブラウザベースの URTC-TESTER の代替、ローカルインストール不要。

*ビジョン AI ノード(Hailo-8)*
- **[HYDRA-UMC-VISION-NODE](https://github.com/JuanenRac/HYDRA-UMC-VISION-NODE)** — Hailo-8 ビジョンパイプラインの統合ハブ、段階ごとの実際のハードウェア準備状況チェック付き。
- **[HYDRA-UMC-VISION-STREAMER](https://github.com/JuanenRac/HYDRA-UMC-VISION-STREAMER)** — 実際の HailoRT 統合境界を持つ、実際の GStreamer パイプライン + MediaMTX 設定生成器。
- **[HYDRA-UMC-VISUAL-SERVOING-API](https://github.com/JuanenRac/HYDRA-UMC-VISUAL-SERVOING-API)** — ゾーン状態を条件に承認する Position-Based Visual Servoing 補正則。カメラによる姿勢推定はまだない。
- **[HYDRA-UMC-SAFETY-ZONES](https://github.com/JuanenRac/HYDRA-UMC-SAFETY-ZONES)** — ファイルから物体位置を受け取る、ゾーン侵入・キャリブレーション鮮度・E-STOP 要求の v0 ロジック。検出器は接続されておらず、物理 E-STOP もまだ配線されていない。

*コグニティブ AI ノード(Hailo-10)*
- **[HYDRA-UMC-COGNITIVE-NODE](https://github.com/JuanenRac/HYDRA-UMC-COGNITIVE-NODE)** — Hailo-10 コグニティブパイプライン(LLM/VLA/音声オーケストレーション)の統合ハブ。
- **[HYDRA-UMC-VLA-ENGINE](https://github.com/JuanenRac/HYDRA-UMC-VLA-ENGINE)** — Vision-Language-Action モデル向けの、実際のアクショントークンのエンコード/デコードと軌道生成。
- **[HYDRA-UMC-VOICE-UI](https://github.com/JuanenRac/HYDRA-UMC-VOICE-UI)** — 確認ゲート付きの限定的な Watch リレーを備えた、実際の音声フロントエンド(VAD + 意図解析)。
- **[HYDRA-UMC-SEMANTIC-PLANNER](https://github.com/JuanenRac/HYDRA-UMC-SEMANTIC-PLANNER)** — MCU エラーコードに対する、実際のルールベースのタスク分解と意味的エラー復旧。
- **[HYDRA-UMC-DOCS-QA](https://github.com/JuanenRac/HYDRA-UMC-DOCS-QA)** — このエコシステム自身の Markdown ドキュメントに対する、標準ライブラリのみの実際の TF-IDF 文書検索。
- **[HYDRA-UMC-LOCAL-TECHNICIAN](https://github.com/JuanenRac/HYDRA-UMC-LOCAL-TECHNICIAN)** — エコシステム自身のための、ローカルでポリシーゲート付きのAIメンテナンス技術者 — 観察、診断し、修正を提案する;最上位の2つのリスクレベルは意図的にまだ実装されていない。

*オーケストレーション&スウォーム*
- **[HYDRA-UMC-ORCHESTRATOR](https://github.com/JuanenRac/HYDRA-UMC-ORCHESTRATOR)** — 実際の gRPC/Protobuf ヘルスレポート契約とミッションステートマシンを持つ統合ハブ。
- **[HYDRA-UMC-JOB-DISPATCHER](https://github.com/JuanenRac/HYDRA-UMC-JOB-DISPATCHER)** — 実際の HTTP API 上に構築された、優先度ベースの実際のジョブキュー(重複排除付き)。
- **[HYDRA-UMC-NODE-HEALING](https://github.com/JuanenRac/HYDRA-UMC-NODE-HEALING)** — リトライ/バックオフとアイデンティティ不一致検出を備えた、実際の gRPC ベースのフリートヘルスウォッチドッグ。
- **[HYDRA-UMC-PATH-PLANNER-3D](https://github.com/JuanenRac/HYDRA-UMC-PATH-PLANNER-3D)** — 実際の障害物/ワークスペース衝突検証を備えた、実際の RRT ベースの 3D 経路プランナー。
- **[HYDRA-UMC-SWARM-SYNC](https://github.com/JuanenRac/HYDRA-UMC-SWARM-SYNC)** — 複数セルの収束についてプロパティテストされた、実際の CRDT LWW-Element-Map 状態同期。

*デジタルツイン&シミュレーション*
- **[HYDRA-UMC-TWIN](https://github.com/JuanenRac/HYDRA-UMC-TWIN)** — 実際のバージョン互換性同期契約を持つ、デジタルツインエンジンの統合ハブ。
- **[HYDRA-UMC-HIL-BRIDGE](https://github.com/JuanenRac/HYDRA-UMC-HIL-BRIDGE)** — シミュレーションと実機の間にソフトウェアの衝突インターロックを備えたハードウェア・イン・ザ・ループのルーター(実機なしでテスト済み)。
- **[HYDRA-UMC-PHYSICS-REPLICA](https://github.com/JuanenRac/HYDRA-UMC-PHYSICS-REPLICA)** — 実際の URDF サブセットに対する、実際の順運動学と関節限界検証。
- **[HYDRA-UMC-SYNTHETIC-DATA-GEN](https://github.com/JuanenRac/HYDRA-UMC-SYNTHETIC-DATA-GEN)** — YOLO/COCO アノテーションのエクスポート機能を持つ、実際のプロシージャル 2D シーンジェネレーター。

*データ&分析*
- **[HYDRA-UMC-DATALAKE](https://github.com/JuanenRac/HYDRA-UMC-DATALAKE)** — 実際の取り込み/クエリ HTTP API を備えた、実際の sqlite3 ベースの時系列ストア。
- **[HYDRA-UMC-ANOMALY-DETECTOR](https://github.com/JuanenRac/HYDRA-UMC-ANOMALY-DETECTOR)** — ドリフト監視を備えた、実際の FFT + 統計ベースラインによる異常検知器。
- **[HYDRA-UMC-PRODUCTION-REPORTS](https://github.com/JuanenRac/HYDRA-UMC-PRODUCTION-REPORTS)** — DATALAKE の履歴に対する実際の OEE/稼働率計算、再現可能な CSV エクスポート付き。
- **[HYDRA-UMC-TELEMETRY-COLLECTOR](https://github.com/JuanenRac/HYDRA-UMC-TELEMETRY-COLLECTOR)** — シーケンス重複排除機能を備えた、DATALAKE への実際の CAN/WebSocket 取り込みパイプライン。

*産業用ゲートウェイ*
- **[HYDRA-UMC-GATEWAY-INDUSTRIAL](https://github.com/JuanenRac/HYDRA-UMC-GATEWAY-INDUSTRIAL)** — 実際のコマンド許可リスト/バックプレッシャー層を持つ、産業用プロトコルへ中継する統合ハブ。
- **[HYDRA-UMC-OPCUA-SERVER](https://github.com/JuanenRac/HYDRA-UMC-OPCUA-SERVER)** — 実際のバイナリプロトコルクライアントセッションで検証された、実際の OPC-UA アドレス空間。
- **[HYDRA-UMC-MQTT-BROKER](https://github.com/JuanenRac/HYDRA-UMC-MQTT-BROKER)** — クライアント単位のオプション認証とトピック ACL を備えた、実際の MQTT ブローカー。
- **[HYDRA-UMC-MTCONNECT-ADAPTER](https://github.com/JuanenRac/HYDRA-UMC-MTCONNECT-ADAPTER)** — 縮退モード出力を備えた、実際の MTConnect `/probe` および `/current` XML エンドポイント。

*補完ツール&エコシステム運用*
- **[HYDRA-UMC-DASHBOARD-AI](https://github.com/JuanenRac/HYDRA-UMC-DASHBOARD-AI)** — 誠実な統計フォールバックを備えた、DATALAKE/ANOMALY-DETECTOR 上のスマートサマリーと異常ハイライトパネル。
- **[HYDRA-UMC-TOOL-CLI](https://github.com/JuanenRac/HYDRA-UMC-TOOL-CLI)** — 実際の安定した終了コード契約を持つフリート CLI、HYDRA-UMC-SERVER 自身の API の本物のライブクライアント。
- **[HYDRA-UMC-WATCH](https://github.com/JuanenRac/HYDRA-UMC-WATCH)** — 触覚アラートのパターンとペアリング済みスマートフォンへの音声リレーを備えた WearOS コンパニオンアプリ(物理的なウォッチではまだ実行していない)。
- **[URTC-SMART-RACK](https://github.com/JuanenRac/URTC-SMART-RACK)** — 実際の工具 ID デコードと Smart Idle 予熱ロジックを備えた、基板搭載ラック用ファームウェア。
- **[URTC-UPDATER](https://github.com/JuanenRac/URTC-UPDATER)** — URTC ファミリーのリポジトリを検出・インストール・更新するデスクトップツール。操作は一つずつ明示的に行います。
- **[HYDRA-UMC-UPDATER](https://github.com/JuanenRac/HYDRA-UMC-UPDATER)** — このエコシステム内のすべてのリポジトリを検出・クローン・更新する、管理用デスクトップツール。
- **[HYDRA-UMC-OS-REBUILDER](https://github.com/JuanenRac/HYDRA-UMC-OS-REBUILDER)** — エコシステムの最新バージョンをプリロードした、書き込み可能なCM5イメージを構築するWindows/Linuxデスクトップツール。Raspberry Pi Imager方式の初回起動Wi-Fi/ユーザー/SSH設定を備える。
- **[HYDRA-UMC-OPS-AGENT](https://github.com/JuanenRac/HYDRA-UMC-OPS-AGENT)** — 保守インシデントコーディネーター: 低権限のエッジ役割がサニタイズされたインベントリ/ヘルスのスナップショットを収集し、コントロールプレーン役割がそれを読み取り専用でレンダリングして AI プロバイダーに診断の提案を依頼します - パッチを適用することも、何かをデプロイすることも決してありません。
- **[HYDRA-UMC-DEV-SERVER](https://github.com/JuanenRac/HYDRA-UMC-DEV-SERVER)** — 再現可能な開発ホスト（Raspberry Pi 5 / CM5）。エコシステムのソースコードを保管し、永続キューのもとで境界の明確なビルド/テストタスクを実行する。運用中の CM5 とは明確に異なる、開発専用の役割。

## 📚 ドキュメント

- **[CONTRIBUTING.md](CONTRIBUTING.md)** —— プルリクエストのための技術スタックとコーディング指針。
- **[CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)** —— このコミュニティで期待される行動規範。
- **[SECURITY.md](SECURITY.md)** —— 脆弱性の報告方法と、このプロジェクトの実際のセキュリティ重点領域。
- **[SUPPORT.md](SUPPORT.md)** —— 質問の投稿先とバグの報告先。
- **[LICENSE.md](LICENSE.md)** —— このプロジェクト自身のライセンス。

## 🤝 コントリビュートとコミュニティ

* プルリクエストの前に `URTC_CI=1 python tools/ci_validate.py` を実行してください。通過する必要があります。[CONTRIBUTING.md](CONTRIBUTING.md) と[行動規範](CODE_OF_CONDUCT.md)を参照してください。
* README は 8 言語で提供されています。文章の変更は 8 つのファイルすべてで行い、他のリポジトリと共有するセクションは URTC-COMMON の `tools/readme_sections.py` が書き込みます。
* CAN プロトコルの変更は URTC-COMMON（`spec/can_protocol.json`）から始まり、検査済みのコピーを通じてこのリポジトリに届きます。
* ビルドしただけのものを、ボード上で動いているかのように書かないでください。
* 脆弱性は非公開で報告してください：[SECURITY.md](SECURITY.md)。質問、アイデア、報告：electrohobby3d@gmail.com（[SUPPORT.md](SUPPORT.md)）。

## 👤 作者

**JuanenRac** (Electro Hobby 3D)
📧 electrohobby3d@gmail.com
📺 [youtube.com/@electrohobby3d](https://youtube.com/@electrohobby3d)

## 📜 ライセンス

GPL-3.0-or-later —— 詳細は LICENSE を参照してください。
