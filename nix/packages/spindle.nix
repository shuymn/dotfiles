{
  lib,
  rustPlatform,
  symlinkJoin,
  spindleSrc,
  extensionsSrc,
}:

let
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
    cargoLock = {
      lockFile = "${extensionsSrc}/Cargo.lock";
      outputHashes = {
        "spindle-extension-sdk-0.1.0" = "sha256-kaoWe2fVeexus+RHSp1r4RceyR+kFAFLOkQ2DaCN8Jo=";
      };
    };

    cargoBuildFlags = [ "--workspace" ];
    doCheck = false;

    postInstall = ''
      install -d "$out/share/spindle"

      for extension_id in aerospace clock sketchybar workspace-indicator; do
        install -d "$out/share/spindle/extensions/$extension_id/bin"
        install -m0644 "extensions/$extension_id/extension.json" \
          "$out/share/spindle/extensions/$extension_id/extension.json"
        install -m0755 "$out/bin/spindle-$extension_id" \
          "$out/share/spindle/extensions/$extension_id/bin/$extension_id"
      done
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
