# Kab-board for Firefox: sources for review

`kab-board-extension/` is the extension's source; `firefox/construire.sh` assembles the
Firefox build in `firefox/extension/` from `chrome/extension/`. Everything else in the
package is plain, unminified JavaScript written for the extension.

## Generated or third-party files

- `moteur/kab_lm.mjs`, `kab_lm.wasm`, `kab_crf.mjs`, `kab_crf.wasm`, `kab_xz.mjs`,
  `kab_xz.wasm`: built with Emscripten by `chrome/autonome/construire-wasm.sh` from
  `kenlm_wasm.cc`, `crf_wasm.cc`, `xz_wasm.cc` (in `chrome/autonome/`), KenLM, CRFsuite and
  liblbfgs (`kab-board/natif/amont/`, from https://github.com/ADJ-MSS/kab-board) and
  xz-embedded (`chrome/autonome/xz-embedded/`, 0BSD).

      KAB_BOARD=../kab-board kab-board-extension/chrome/autonome/construire-wasm.sh

- `ort/`: onnxruntime-web 1.18.0, unmodified, from npm
  (`npm pack onnxruntime-web@1.18.0`, files `dist/ort.wasm.min.mjs`,
  `dist/ort-wasm-simd.wasm`; checksums in `firefox/ort.sha256`).

## Data files

`ressources/` holds data, not code: the Kabyle lexicon, language model, tagger and speech
model of the kab-board Android app (https://github.com/ADJ-MSS/kab-board/releases, v0.3).
`chrome/autonome/ressources.sh` extracts them from the APK and checks each file against
`ressources.sha256`; `firefox/compresser.py` compresses the two largest with xz.

## Build

    chrome/autonome/ressources.sh kab-board-0.3.apk
    firefox/construire.sh        # -> firefox/extension/

Needs Node.js, npm, Python 3, xz; Emscripten 3.1+ only to rebuild the WebAssembly files.
The extension makes no network request: everything runs locally.
