{
  fetchurl,
  lib,
  makeWrapper,
  stdenvNoCC,
}:

let
  sources = {
    aarch64-darwin = {
      # renovate: datasource=github-release-attachments depName=earendil-works/pi packageName=earendil-works/pi versioning=semver
      tag = "v0.78.0";
      asset = "pi-darwin-arm64.tar.gz";
      sha256 = "68ebbe4f56a136a1c7bace3393eca4ad0aa1fd9f253b797fd370058bd39fe070";
    };
    x86_64-darwin = {
      # renovate: datasource=github-release-attachments depName=earendil-works/pi packageName=earendil-works/pi versioning=semver
      tag = "v0.78.0";
      asset = "pi-darwin-x64.tar.gz";
      sha256 = "66074b271260068199f47738a172397f1e0b5a3334697dd2acea35bbd3470b1c";
    };
    aarch64-linux = {
      # renovate: datasource=github-release-attachments depName=earendil-works/pi packageName=earendil-works/pi versioning=semver
      tag = "v0.78.0";
      asset = "pi-linux-arm64.tar.gz";
      sha256 = "49155173682473720d9decf4deecbed754fae84925ef003c0b66aac31d5f9005";
    };
    x86_64-linux = {
      # renovate: datasource=github-release-attachments depName=earendil-works/pi packageName=earendil-works/pi versioning=semver
      tag = "v0.78.0";
      asset = "pi-linux-x64.tar.gz";
      sha256 = "8ac03343d1e1228106e8172157f32d6b882829e46b34feaf577f171a5f1387cc";
    };
  };

  source =
    sources.${stdenvNoCC.hostPlatform.system}
      or (throw "Unsupported pi-coding-agent platform: ${stdenvNoCC.hostPlatform.system}");
in
stdenvNoCC.mkDerivation {
  pname = "pi-coding-agent";
  version = lib.removePrefix "v" source.tag;

  src = fetchurl {
    url = "https://github.com/earendil-works/pi/releases/download/${source.tag}/${source.asset}";
    inherit (source) sha256;
  };

  sourceRoot = "pi";
  nativeBuildInputs = [ makeWrapper ];

  installPhase = ''
    runHook preInstall

    mkdir -p "$out/bin" "$out/share/pi"
    cp -R . "$out/share/pi/"
    chmod +x "$out/share/pi/pi"
    makeWrapper "$out/share/pi/pi" "$out/bin/pi"

    runHook postInstall
  '';

  meta = {
    description = "Coding agent CLI with read, bash, edit, write tools and session management";
    homepage = "https://github.com/earendil-works/pi";
    license = lib.licenses.mit;
    mainProgram = "pi";
    platforms = builtins.attrNames sources;
    sourceProvenance = with lib.sourceTypes; [ binaryNativeCode ];
  };
}
