{ pkgs, ... }:

{
  home.packages = with pkgs; [
    acli
    circleci-cli
    google-cloud-sdk
    grpcurl
    phpactor
    watch
  ];
}
