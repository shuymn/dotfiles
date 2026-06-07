{
  lib,
  rustPlatform,
  symlinkJoin,
  python3,
  spindleSrc,
  extensionsSrc,
}:

let
  cleanedExtensionsLock = lib.concatStringsSep "\n" (
    builtins.filter
      (line: !(lib.hasPrefix ''source = "git+https://github.com/shuymn/spindle'' line))
      (lib.splitString "\n" (builtins.readFile "${extensionsSrc}/Cargo.lock"))
  );

  spindleCore = rustPlatform.buildRustPackage {
    pname = "spindle";
    version = "0.1.0-local";

    src = spindleSrc;
    cargoLock.lockFile = "${spindleSrc}/Cargo.lock";

    cargoBuildFlags = [
      "-p"
      "spindle"
    ];
    doCheck = false;
  };

  spindleExtensions = rustPlatform.buildRustPackage {
    pname = "spindle-extensions";
    version = "0.1.0-local";

    src = extensionsSrc;
    cargoLock.lockFileContents = cleanedExtensionsLock;

    nativeBuildInputs = [ python3 ];

    postPatch = ''
      mkdir -p crates
      cp -R ${spindleSrc}/crates/spindle-extension-sdk crates/spindle-extension-sdk
      chmod -R u+w crates/spindle-extension-sdk
      substituteInPlace Cargo.toml \
        --replace-fail 'spindle-extension-sdk = { git = "https://github.com/shuymn/spindle", branch = "main", package = "spindle-extension-sdk" }' \
        'spindle-extension-sdk = { path = "crates/spindle-extension-sdk" }'
      sed -i '/^source = "git+https:\/\/github\.com\/shuymn\/spindle/d' Cargo.lock
      python3 - <<'PY'
      from pathlib import Path

      sdk_manifest = Path('crates/spindle-extension-sdk/Cargo.toml')
      sdk_manifest.write_text(
          sdk_manifest.read_text().replace('\n[lints]\nworkspace = true\n', '\n')
      )

      PY
    '';

    cargoBuildFlags = [ "--workspace" ];
    doCheck = false;

    postInstall = ''
      install -d "$out/share/spindle"
      cat >"$out/share/spindle/capabilities.json" <<'JSON'
      {
        "emits": {
          "aerospace": [
            "aerospace.workspace.changed",
            "aerospace.focus.changed",
            "aerospace.monitor.changed",
            "aerospace.mode.changed",
            "aerospace.layout.changed"
          ],
          "sketchybar": ["sketchybar.workspace.clicked"]
        },
        "direct": {},
        "routes": {
          "workspace-indicator": [
            {
              "source": "aerospace",
              "event": "aerospace.workspace.changed",
              "capabilities": ["aerospace.state.read"]
            },
            {
              "source": "aerospace",
              "event": "aerospace.monitor.changed",
              "capabilities": ["aerospace.state.read"]
            },
            {
              "source": "aerospace",
              "event": "aerospace.mode.changed",
              "capabilities": ["aerospace.state.read"]
            },
            {
              "source": "aerospace",
              "event": "aerospace.focus.changed",
              "capabilities": ["aerospace.state.read"]
            },
            {
              "source": "aerospace",
              "event": "aerospace.layout.changed",
              "capabilities": ["aerospace.state.read"]
            },
            {
              "source": "sketchybar",
              "event": "sketchybar.workspace.clicked",
              "capabilities": ["aerospace.window.control"]
            },
            {
              "source": "workspace-indicator",
              "event": "workspace-indicator.sketchybar.message.requested",
              "capabilities": ["sketchybar.ui.write"]
            }
          ]
        }
      }
      JSON

      for extension in aerospace sketchybar workspace-indicator; do
        install -d "$out/share/spindle/extensions/$extension"
      done

      cat >"$out/share/spindle/extensions/aerospace/extension.json" <<JSON
      {
        "id": "aerospace",
        "version": "0.1.0",
        "entrypoint": "$out/bin/spindle-aerospace",
        "runtime": "stdio-jsonl"
      }
      JSON

      cat >"$out/share/spindle/extensions/sketchybar/extension.json" <<JSON
      {
        "id": "sketchybar",
        "version": "0.1.0",
        "entrypoint": "$out/bin/spindle-sketchybar",
        "runtime": "stdio-jsonl"
      }
      JSON

      cat >"$out/share/spindle/extensions/workspace-indicator/extension.json" <<JSON
      {
        "id": "workspace-indicator",
        "version": "0.1.0",
        "entrypoint": "$out/bin/spindle-workspace-indicator",
        "runtime": "stdio-jsonl"
      }
      JSON
    '';
  };
in
symlinkJoin {
  name = "spindle-0.1.0-local";
  paths = [
    spindleCore
    spindleExtensions
  ];

  meta = {
    description = "Self-extensible local automation harness for macOS workflows";
    license = lib.licenses.mit;
    mainProgram = "spindle";
    platforms = lib.platforms.darwin;
  };
}
