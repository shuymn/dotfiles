{
  fetchurl,
  lib,
  stdenvNoCC,
}:

let
  sources = {
    aarch64-darwin = {
      # renovate: datasource=github-release-attachments depName=aquaproj/aqua packageName=aquaproj/aqua versioning=semver
      tag = "v2.59.1";
      asset = "aqua_darwin_arm64.tar.gz";
      sha256 = "8c658418ba81cf2629813d374358f3dfe13c6715d27ccb476baf85c873acc501";
    };
    x86_64-darwin = {
      # renovate: datasource=github-release-attachments depName=aquaproj/aqua packageName=aquaproj/aqua versioning=semver
      tag = "v2.59.1";
      asset = "aqua_darwin_amd64.tar.gz";
      sha256 = "c2ffc0f9f406f703e07a2c6f16b2e4dd7756b9bddc1c13e7f9f485f54b33e78d";
    };
    aarch64-linux = {
      # renovate: datasource=github-release-attachments depName=aquaproj/aqua packageName=aquaproj/aqua versioning=semver
      tag = "v2.59.1";
      asset = "aqua_linux_arm64.tar.gz";
      sha256 = "92298717b849c4baa36947dc4fcdedf7a542a2686dbc939a0dcda83d891b9a25";
    };
    x86_64-linux = {
      # renovate: datasource=github-release-attachments depName=aquaproj/aqua packageName=aquaproj/aqua versioning=semver
      tag = "v2.59.1";
      asset = "aqua_linux_amd64.tar.gz";
      sha256 = "f2ec38dece860fee4fc48d1213da176fa7bd900e95036cac8d952800d91644e7";
    };
  };

  source =
    sources.${stdenvNoCC.hostPlatform.system}
      or (throw "Unsupported aqua platform: ${stdenvNoCC.hostPlatform.system}");
in
stdenvNoCC.mkDerivation {
  pname = "aqua";
  version = lib.removePrefix "v" source.tag;

  src = fetchurl {
    url = "https://github.com/aquaproj/aqua/releases/download/${source.tag}/${source.asset}";
    inherit (source) sha256;
  };

  sourceRoot = ".";

  installPhase = ''
    runHook preInstall

    mkdir -p "$out/bin" "$out/share/doc/aqua"
    cp aqua "$out/bin/aqua"
    chmod +x "$out/bin/aqua"
    cp LICENSE README.md "$out/share/doc/aqua/"
    cp -R third_party_licenses "$out/share/doc/aqua/"

    runHook postInstall
  '';

  meta = {
    description = "Declarative CLI version manager";
    homepage = "https://aquaproj.github.io/";
    license = lib.licenses.mit;
    mainProgram = "aqua";
    platforms = builtins.attrNames sources;
    sourceProvenance = with lib.sourceTypes; [ binaryNativeCode ];
  };
}
