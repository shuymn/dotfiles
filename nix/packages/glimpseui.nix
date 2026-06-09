{
  lib,
  fetchFromGitHub,
  makeWrapper,
  nodejs,
  swift,
  swiftPackages,
  apple-sdk_14,
}:

swiftPackages.stdenv.mkDerivation rec {
  pname = "glimpseui";
  # renovate: datasource=github-releases depName=HazAT/glimpse
  version = "0.8.1";

  src = fetchFromGitHub {
    owner = "HazAT";
    repo = "glimpse";
    rev = "v${version}";
    hash = "sha256-iiOLxg8UnsKPwqNV+zCLFoQZ78pypMr3WkesSf3nkc8=";
  };

  nativeBuildInputs = [
    makeWrapper
    swift
  ];

  buildInputs = [
    apple-sdk_14
  ];

  buildPhase = ''
    runHook preBuild

    swiftc -O src/glimpse.swift -o src/glimpse

    runHook postBuild
  '';

  installPhase = ''
    runHook preInstall

    install -d "$out/lib/${pname}/src" "$out/lib/${pname}/bin" "$out/bin"
    install -m0644 src/*.mjs src/glimpse.swift "$out/lib/${pname}/src/"
    install -m0755 src/glimpse "$out/lib/${pname}/src/glimpse"
    install -m0644 package.json README.md CHANGELOG.md "$out/lib/${pname}/"
    install -m0755 bin/glimpse.mjs "$out/lib/${pname}/bin/glimpse.mjs"

    makeWrapper ${nodejs}/bin/node "$out/bin/${pname}" \
      --add-flags "$out/lib/${pname}/bin/glimpse.mjs"

    runHook postInstall
  '';

  meta = {
    description = "Native micro-UI for scripts and agents";
    homepage = "https://github.com/HazAT/glimpse";
    license = lib.licenses.mit;
    mainProgram = pname;
    platforms = lib.platforms.darwin;
  };
}
