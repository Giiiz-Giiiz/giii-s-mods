# giii's mods — GiiiCon アプリライブラリ

GiiiCon 本体が Wi-Fi で読む、公式ライブラリの配布サイトです（GitHub Pages：<https://giiiz-giiiz.github.io/giii-s-mods/>）。
本体の「ストア」に並ぶアプリ・テーマ・プロファイルは、ここにある署名付きの一覧から来ます。

**このリポジトリは生成物です。手で編集しないでください。**
何を載せるかは GiiiCon リポジトリの `library/packages/<id>/package.json` で決め、`giii index build` が署名してここに書き出します。

| パス | 中身 |
|---|---|
| `root/<N>.gix` | 信頼の起点（root）。本体のファームウェアに `root/1.gix` が焼き込まれている |
| `timestamp.gix` | 最新の snapshot を指す。期限は 2 日なので、少なくとも 2 日ごとに署名し直す |
| `snapshot/<V>.gix` | 各 shard の版と hash |
| `targets/<shard>.<v>.gix` | パッケージの一覧（`apps-0` など） |
| `blobs/<sha256>.giii` | パッケージ本体（hash の名前で固定） |

本体はどのファイルも署名と hash で確かめるので、配信元（このサイト）を信頼する必要はありません。
形式は GiiiCon の `docs/adr/ADR-009-official-index.md` と `docs/os/store.md` を参照してください。

## 更新のしくみ

- **毎日の再署名**：`.github/workflows/refresh.yml` が毎日 `tools/refresh.py` を動かし、期限の短い metadata
  （timestamp は 2 日、snapshot は 14 日、targets は 60 日）を署名し直します。パッケージの中身は変えません。
  使う鍵は timestamp・snapshot・targets だけで、リポジトリの secrets に置いています。root の鍵は maintainer の手元にあります。
- **アプリを載せる・更新する**：GiiiCon の `library/packages/<id>/package.json` に版を足し、最新のこのリポジトリを
  手元に取ってから、GiiiCon で次を実行して push します。

  ```sh
  git -C ../giii-s-mods pull
  uv run --project tools giii index build --keys ~/.giiicon/keys/index --site ../giii-s-mods
  uv run --project tools giii index verify --site ../giii-s-mods --root library/root/1.gix
  ```

## 掲載中

| アプリ | 版 |
|---|---|
| [Dodge-Dodge-and-Catch](https://github.com/Giiiz-Giiiz/giii-s-mod_Dodge-Dodge-and-Catch) | 0.1.1, 0.1.2, 0.1.3 |
| Hello（サンプル） | 0.1.0, 0.2.0 |
| Retro（テーマのサンプル）・Night（プロファイルのサンプル） | 1.0.0 |
